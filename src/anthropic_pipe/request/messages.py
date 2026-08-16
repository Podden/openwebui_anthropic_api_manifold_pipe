"""Compiled Pipe method group: OpenWebUI -> Claude message/content conversion (text, images, tool_calls/tool_results, tool_result content processing). Compiled into class Pipe."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class PipeRequestMessagesMethods:
    def _convert_messages_to_claude_format(
        self, raw_messages
    ) -> tuple[list[dict], list[dict], list[str]]:
        """Convert a raw OpenWebUI message list into Claude system/processed messages plus extracted marker metadata."""
        processed_messages: list[Dict[str, Any]] = []
        extracted_memories = None
        previous_marker_metadata: list[str] = []
        system_messages = []
        if raw_messages is None or len(raw_messages) == 0:
            return system_messages, processed_messages, previous_marker_metadata

        for i, msg in enumerate(raw_messages):
            role = msg.get("role")
            raw_content = msg.get("content")

            # OpenAI-style tool result messages (role: "tool") are not valid for
            # Anthropic's API.  Convert them to role: "user" + type: "tool_result"
            # blocks.  Batch consecutive tool messages into a single user message
            # so the API always sees alternating user/assistant turns.
            if role == "tool":
                tool_use_id = msg.get("tool_call_id", "")
                content_str = (
                    raw_content
                    if isinstance(raw_content, str)
                    else (raw_content[0].get("text", "") if isinstance(raw_content, list) and raw_content else "")
                )
                tool_result_block: dict = {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": content_str,
                }
                # Merge into the preceding user message if it already holds
                # tool_result blocks (i.e. a previous role: "tool" message was
                # already converted), otherwise open a new user message.
                if (
                    processed_messages
                    and processed_messages[-1].get("role") == "user"
                    and isinstance(processed_messages[-1].get("content"), list)
                    and processed_messages[-1]["content"]
                    and isinstance(processed_messages[-1]["content"][0], dict)
                    and processed_messages[-1]["content"][0].get("type") == "tool_result"
                ):
                    processed_messages[-1]["content"].append(tool_result_block)
                else:
                    processed_messages.append({"role": "user", "content": [tool_result_block]})
                logger.debug(f"Converted role=tool → tool_result block (id={tool_use_id!r})")
                continue

            # Historical assistant turns may carry tool calls serialized as
            # <details type="tool_calls"> HTML (OpenWebUI stores flat strings
            # only). Parse them back into structured tool_use/tool_result
            # blocks so Claude sees its own prior tool usage and doesn't
            # re-execute tools on follow-up turns.
            if (
                role == "assistant"
                and isinstance(raw_content, str)
                and '<details type="tool_calls"' in raw_content
            ):
                parsed_msgs = self._parse_assistant_tool_calls_string(raw_content)
                if parsed_msgs:
                    for pmsg in parsed_msgs:
                        if pmsg["role"] == "assistant":
                            extracted_metadata = self._extract_metadata_marker_from_message(pmsg)
                            if extracted_metadata:
                                previous_marker_metadata.extend(extracted_metadata)
                        processed_messages.append(pmsg)
                    continue

            claude_message = self._convert_content_to_claude_format(raw_content, role=role)
            if not claude_message:
                continue
            if role == "system":
                for block in claude_message:
                    text = block["text"]

                    # Driven by what actually arrived, not by the user's memory
                    # toggle: OpenWebUI injects based on the request's
                    # `features.memory` and an admin ConfigVar, so the toggle can
                    # read "off" while memories are in the prompt. Missing that
                    # case costs a full prefix rewrite every turn. The helper
                    # short-circuits on a substring scan when nothing is there.
                    cleaned_text, extracted_memories = (
                        self._extract_and_remove_memories(text)
                    )

                    if extracted_memories:
                        logger.debug(
                            f"✓ Extracted User Context: {extracted_memories[:100]}..."
                        )
                        logger.debug(
                            f"✓ System prompt after removal (last 200 chars): ...{cleaned_text[-200:]}"
                        )

                    # Update block with cleaned text
                    block["text"] = cleaned_text

                    # Only add non-empty blocks to system (cache_control will be added later to last block only)
                    if block["text"].strip():
                        system_messages.append(block)
            else:
                # Wrap as dict so _extract_metadata_marker_from_message can check role
                # and modify content blocks in-place to strip markers
                wrapped_msg = {"role": role, "content": claude_message}
                extracted_metadata = self._extract_metadata_marker_from_message(
                    wrapped_msg
                )
                if extracted_metadata:
                    previous_marker_metadata.extend(extracted_metadata)

                processed_messages.append(wrapped_msg)

                if i == len(raw_messages) - 1 and role == "user":
                    # Volatile context has to end up in trailing blocks of its
                    # own, so the cache breakpoint can sit right before it. RAG
                    # first, then memories -- RAG arrives merged into the prose
                    # by OpenWebUI, memories are appended by us.
                    self._split_rag_into_trailing_block(processed_messages[-1])

                    if extracted_memories:
                        processed_messages[-1]["content"].append(
                            {
                                "type": "text",
                                "text": f"{MEMORY_CONTEXT_APPENDIX_HEADER}{extracted_memories}",
                            }
                        )

        # Client-side compaction trim: drop messages before the last compaction
        # block. The API would ignore them anyway but this saves bandwidth and
        # avoids sending stale context over the wire.
        last_compaction_idx = -1
        for idx, msg in enumerate(processed_messages):
            if msg.get("role") == "assistant":
                for block in msg.get("content", []):
                    if isinstance(block, dict) and block.get("type") == "compaction":
                        last_compaction_idx = idx
                        break
        if last_compaction_idx > 0:
            dropped = len(processed_messages[:last_compaction_idx])
            processed_messages = processed_messages[last_compaction_idx:]
            logger.info(
                f"Compaction trim: dropped {dropped} messages before compaction boundary"
            )

        return system_messages, processed_messages, previous_marker_metadata

    def _convert_content_to_claude_format(
        self, content: Union[str, List[dict], None], role: str = "user"
    ) -> List[dict]:
        """
        Process content from OpenWebUI format to Claude API format.
        Handles text, images, PDFs, tool_calls, and tool_results according to
        Anthropic API documentation.
        Filters out empty text blocks to prevent API errors.
        """
        if content is None:
            return []

        if isinstance(content, str):
            # NOTE: Do NOT remove thinking blocks from assistant messages!
            # Per Anthropic docs: thinking blocks MUST be preserved unmodified during tool use loops.
            # The entire sequence of consecutive thinking blocks must match the original model output.
            # For multi-turn: prior turn thinking CAN be omitted (API auto-filters), but preserving is preferred.
            # With interleaved thinking (Claude 4), thinking blocks can appear BETWEEN tool calls too.
            # Thinking blocks come back as serialized text (with <details type="reasoning">...) from OpenWebUI,
            # and the API requires them to remain unchanged.

            # Strip OpenWebUI UI-rendering artifacts from conversation history.
            # <details type="tool_calls"> and <details type="code_interpreter"> are display-only
            # HTML that OpenWebUI stores in message content. If sent to Claude 4.6 models,
            # they pattern-match these and generate fake tool call HTML as text output
            # instead of making actual API tool_use calls.
            if role == "assistant":
                content = PATTERN_TOOL_CALLS_DETAILS.sub("", content)
                content = PATTERN_CODE_INTERPRETER_DETAILS.sub("", content)
                content = PATTERN_CACHE_TRACE_DETAILS.sub("", content)

                # Reconstruct ALL replayable <details> blocks (reasoning,
                # server_tool_use, *_tool_result, compaction) into their
                # API-native forms, in original document order. Positional
                # fidelity is critical: the Anthropic API requires the exact
                # sequence of thinking + server_tool_use + tool_result blocks
                # to match the original assistant turn byte-exact, otherwise
                # subsequent requests 400 with "thinking blocks cannot be
                # modified" and the prompt cache prefix is invalidated.
                all_matches: list[tuple[int, str, re.Match]] = []
                for m in PATTERN_REASONING_BLOCK.finditer(content):
                    all_matches.append((m.start(), "reasoning", m))
                for m in PATTERN_SERVER_TOOL_USE_BLOCK.finditer(content):
                    all_matches.append((m.start(), "server_tool_use", m))
                for m in PATTERN_SERVER_TOOL_RESULT_BLOCK.finditer(content):
                    all_matches.append((m.start(), "server_tool_result", m))
                for m in PATTERN_COMPACTION_DETAILS.finditer(content):
                    all_matches.append((m.start(), "compaction", m))
                for m in PATTERN_HIDDEN_BLOCK.finditer(content):
                    all_matches.append((m.start(), "hidden", m))

                if all_matches:
                    all_matches.sort(key=lambda t: t[0])
                    blocks: list[dict] = []
                    last_end = 0
                    for _, kind, match in all_matches:
                        text_before = content[last_end:match.start()]
                        if text_before.strip():
                            blocks.append({"type": "text", "text": text_before})
                        if kind == "reasoning":
                            attrs_str = match.group(1)
                            sig_match = re.search(
                                r'data-signature="([^"]*)"', attrs_str
                            )
                            if sig_match:
                                signature = html.unescape(sig_match.group(1))
                                body = match.group(2)
                                thinking_text = html.unescape(
                                    PATTERN_REASONING_QUOTED_LINE.sub("", body)
                                ).strip()
                                blocks.append({
                                    "type": "thinking",
                                    "thinking": thinking_text,
                                    "signature": signature,
                                })
                            # else: unsignatured reasoning → drop
                        elif kind == "server_tool_use":
                            attrs_str = match.group(1)
                            attrs = dict(PATTERN_DATA_ATTR.findall(attrs_str))
                            payload_b64 = attrs.get("payload-b64", "")
                            decoded = self._decode_block_payload(payload_b64) if payload_b64 else None
                            if isinstance(decoded, dict) and decoded.get("type") == "server_tool_use":
                                blocks.append(decoded)
                                # If this carrier also embeds the matching
                                # *_tool_result payload (merged display mode),
                                # emit it right after so the API sees the
                                # full tool_use + tool_result pair at the
                                # original position.
                                # data-result-kind carries the block type (e.g. "web_search_tool_result")
                                # and data-result-payload-b64 carries the encoded payload. The decoded
                                # payload already has "type": "...", so result_kind is just sanity-check.
                                result_b64 = attrs.get("result-payload-b64", "")
                                if result_b64:
                                    result_decoded = self._decode_block_payload(result_b64)
                                    if (
                                        isinstance(result_decoded, dict)
                                        and result_decoded.get("type", "").endswith("_tool_result")
                                    ):
                                        blocks.append(result_decoded)
                            # else: legacy/missing payload → drop
                        elif kind == "server_tool_result":
                            attrs_str = match.group(1)
                            attrs = dict(PATTERN_DATA_ATTR.findall(attrs_str))
                            payload_b64 = attrs.get("payload-b64", "")
                            decoded = self._decode_block_payload(payload_b64) if payload_b64 else None
                            if isinstance(decoded, dict) and decoded.get("type", "").endswith("_tool_result"):
                                blocks.append(decoded)
                            # else: legacy/missing payload → drop
                        elif kind == "hidden":
                            # One carrier may hold several blocks (a merged
                            # server_tool_use + its *_tool_result), replayed in
                            # the order they were emitted.
                            decoded = self._decode_block_payload(match.group(1))
                            if isinstance(decoded, list):
                                blocks.extend(
                                    b for b in decoded if isinstance(b, dict) and b.get("type")
                                )
                            # else: corrupt payload → drop
                        elif kind == "compaction":
                            blocks.append({
                                "type": "compaction",
                                "content": match.group(1).strip(),
                            })
                        last_end = match.end()
                    after = content[last_end:]
                    if after.strip():
                        blocks.append({"type": "text", "text": after})
                    return blocks

            # Only return non-empty text blocks
            if content.strip():
                return [{"type": "text", "text": content}]
            else:
                return []

        processed_content = []
        for item in content:
            if item.get("type") == "text":
                text_content = item.get("text", "")
                # Only add non-empty text blocks (Anthropic API requirement)
                if text_content.strip():
                    processed_content.append({"type": "text", "text": text_content})

            elif item.get("type") == "image_url":
                image_url = item.get("image_url", {}).get("url", "")

                if image_url.startswith("data:image"):
                    # Handle base64 encoded image data
                    try:
                        header, encoded = image_url.split(",", 1)
                        mime_type = header.split(":")[1].split(";")[0]

                        # Resolve the real format from the bytes and transcode if
                        # needed. OpenWebUI's mime label is not trustworthy --
                        # see _resolve_image_for_anthropic.
                        try:
                            raw_bytes = base64.b64decode(encoded)
                        except Exception as decode_ex:
                            logger.debug(f" Image base64 decode failed: {decode_ex}")
                            processed_content.append(
                                {
                                    "type": "text",
                                    "text": "[Image data could not be decoded - invalid base64 format]",
                                }
                            )
                            continue

                        mime_type, encoded, image_error = self._resolve_image_for_anthropic(
                            mime_type, encoded, raw_bytes
                        )
                        if image_error:
                            processed_content.append({"type": "text", "text": image_error})
                            continue

                        # Check image size - API has 32MB request limit, but be conservative
                        MAX_IMAGE_SIZE = 25 * 1024 * 1024  # 25 MB (conservative)
                        try:
                            decoded_bytes = base64.b64decode(encoded)
                            if len(decoded_bytes) > MAX_IMAGE_SIZE:
                                logger.debug(
                                    f" Image too large: {len(decoded_bytes)} bytes"
                                )
                                processed_content.append(
                                    {
                                        "type": "text",
                                        "text": f"[Image too large for Anthropic API. Max size: 25MB, received: {len(decoded_bytes)//1024//1024}MB]",
                                    }
                                )
                                continue
                        except Exception as decode_ex:
                            logger.debug(f" Image base64 decode failed: {decode_ex}")
                            processed_content.append(
                                {
                                    "type": "text",
                                    "text": "[Image data could not be decoded - invalid base64 format]",
                                }
                            )
                            continue

                        processed_content.append(
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": mime_type,
                                    "data": encoded,
                                },
                            }
                        )

                    except ValueError as e:
                        logger.debug(f"Error parsing image data URL: {e}")
                        processed_content.append(
                            {
                                "type": "text",
                                "text": "[Error processing image - invalid data URL format]",
                            }
                        )
                    except Exception as e:
                        logger.debug(f"Unexpected error processing image: {e}")
                        processed_content.append(
                            {
                                "type": "text",
                                "text": "[Unexpected error processing image]",
                            }
                        )
                else:
                    # For image URLs (not base64), Claude API supports URL references
                    if image_url.startswith(("http://", "https://")):
                        processed_content.append(
                            {
                                "type": "image",
                                "source": {"type": "url", "url": image_url},
                            }
                        )
                    else:
                        processed_content.append(
                            {
                                "type": "text",
                                "text": f"[Invalid image URL format: {image_url}. Only HTTP/HTTPS URLs are supported]",
                            }
                        )

            elif item.get("type") == "tool_calls":
                converted_calls = self._process_tool_calls(item)
                processed_content.extend(converted_calls)

            elif item.get("type") == "tool_results":
                converted_results = self._process_tool_results(item)
                processed_content.extend(converted_results)

            else:
                logger.debug(
                    f" Unknown content type: {item.get('type')}, converting to text"
                )
                processed_content.append(
                    {
                        "type": "text",
                        "text": f"[Unsupported content type: {item.get('type')}]",
                    }
                )

        return processed_content

    def _process_tool_calls(self, tool_calls_item):
        """Convert OpenWebUI tool_calls format to Claude tool_use format."""
        claude_tool_uses = []
        if "tool_calls" in tool_calls_item:
            for tool_call in tool_calls_item["tool_calls"]:
                if tool_call.get("type") == "function" and "function" in tool_call:
                    function_def = tool_call["function"]
                    claude_tool_uses.append({
                        "type": "tool_use",
                        "id": tool_call.get("id", ""),
                        "name": function_def.get("name", ""),
                        "input": function_def.get("arguments", {}),
                    })
        return claude_tool_uses

    def _process_tool_results(self, tool_results_item):
        """Convert OpenWebUI tool_results format to Claude tool_result format."""
        claude_tool_results = []
        if "results" in tool_results_item:
            for result_item in tool_results_item["results"]:
                if "call" in result_item and "result" in result_item:
                    tool_call = result_item["call"]
                    tool_use_id = tool_call.get("id", "")
                    if tool_use_id:
                        claude_tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": self._convert_tool_result_content(str(result_item["result"])),
                        })
        return claude_tool_results

    # What the Anthropic API accepts as an image block.
    ANTHROPIC_IMAGE_TYPES = ("image/jpeg", "image/png", "image/gif", "image/webp")

    # ISO-BMFF brands identifying a HEIF-family still image. iPhone photos use
    # heic/heix; mif1/msf1 appear on images written by other encoders.
    _HEIF_BRANDS = frozenset({
        b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"hevm", b"hevs",
        b"mif1", b"msf1",
    })
    _AVIF_BRANDS = frozenset({b"avif", b"avis"})

    @classmethod
    def _sniff_image_media_type(cls, raw: bytes) -> Optional[str]:
        """Identify an image from its leading bytes, ignoring any declared type.

        Necessary because OpenWebUI's label is wrong in two different ways
        (both in MessageInput.svelte):

          * Its HEIC branch tests `file.type === 'image/heic'` exactly, so
            `image/heif`, the `*-sequence` variants, and the very common case of
            an empty `file.type` skip conversion entirely.
          * When conversion DOES run, the resulting JPEG is re-wrapped with
            `new File([blob], name, { type: file.type })` -- the ORIGINAL type.
            So a successfully converted image still arrives labelled HEIC.

        The bytes are the only reliable source.
        """
        if raw.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if raw.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if raw[:6] in (b"GIF87a", b"GIF89a"):
            return "image/gif"
        if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
            return "image/webp"
        # ISO-BMFF: size, then "ftyp", then the brand.
        if raw[4:8] == b"ftyp":
            brand = raw[8:12]
            if brand in cls._AVIF_BRANDS:
                return "image/avif"
            if brand in cls._HEIF_BRANDS:
                return "image/heic"
        return None

    @staticmethod
    def _transcode_image_to_jpeg(raw: bytes, media_type: str) -> Optional[bytes]:
        """Re-encode an image the API rejects into JPEG, or None if impossible.

        AVIF needs nothing extra (Pillow 11.3+ decodes it). HEIF does: Pillow
        ships no HEIF decoder for licensing reasons, so it needs pillow-heif,
        declared in the pipe's requirements header.
        """
        try:
            import io

            from PIL import Image

            if media_type == "image/heic":
                try:
                    import pillow_heif

                    pillow_heif.register_heif_opener()
                except ImportError:
                    logger.warning(
                        "HEIC image received but pillow-heif is not installed; "
                        "re-import the pipe so OpenWebUI installs its requirements"
                    )
                    return None

            img = Image.open(io.BytesIO(raw))
            # JPEG has no alpha channel, and a palette or 16-bit source has to be
            # reduced before saving.
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=90, optimize=True)
            return buf.getvalue()
        except Exception as e:
            logger.warning(f"Image transcode to JPEG failed ({media_type}): {e}")
            return None

    @classmethod
    def _resolve_image_for_anthropic(
        cls, declared_type: str, encoded: str, raw: bytes
    ) -> tuple[str, str, Optional[str]]:
        """Return (media_type, base64_data, error_text).

        ``error_text`` is None on success; otherwise it is the placeholder to
        show in place of the image.
        """
        sniffed = cls._sniff_image_media_type(raw)

        # Trust the bytes. This alone repairs the mislabelled-JPEG case, which
        # needs no transcoding at all.
        effective = sniffed or declared_type
        if effective in cls.ANTHROPIC_IMAGE_TYPES:
            if sniffed and sniffed != declared_type:
                logger.debug(
                    f"Image declared as {declared_type} is actually {sniffed}; "
                    f"correcting media_type"
                )
            return effective, encoded, None

        if effective in ("image/heic", "image/avif"):
            jpeg = cls._transcode_image_to_jpeg(raw, effective)
            if jpeg is not None:
                logger.debug(
                    f"Transcoded {effective} -> image/jpeg "
                    f"({len(raw)} -> {len(jpeg)} bytes)"
                )
                return "image/jpeg", base64.b64encode(jpeg).decode("ascii"), None
            label = "HEIC/HEIF" if effective == "image/heic" else "AVIF"
            return effective, encoded, (
                f"[{label} image could not be converted on the server. "
                f"Anthropic accepts JPEG, PNG, GIF and WebP.]"
            )

        logger.debug(f" Unsupported image mime type: {effective}")
        return effective, encoded, (
            f"[Image type {effective} not supported. "
            f"Supported formats: JPEG, PNG, GIF, WebP]"
        )

    @staticmethod
    def _split_rag_into_trailing_block(msg: dict) -> bool:
        """Move OpenWebUI's RAG template out of the prose into its own trailing
        text block. Returns True when something was moved.

        OpenWebUI merges the retrieved context straight INTO the existing text
        block and PREPENDS it (`utils/misc.py::update_message_content` with
        append=False), so prose and volatile context share one block. That makes
        the volatile part unexcludable: a cache breakpoint marks the end of a
        prefix, so there is no way to cache the question without also caching
        chunks that will be different -- or gone -- next turn. The pipe could
        only retreat a whole message, giving up the current question and the
        preceding assistant answer as well.

        Splitting it out makes the rule uniform with relocated memories: every
        volatile block trails the stable content, and the breakpoint goes on the
        last stable block.

        The text is moved VERBATIM, so what the model reads is unchanged except
        for its position: the context now follows the question instead of
        preceding it. That is the deliberate trade -- Anthropic's "documents
        early" advice is a soft quality heuristic aimed at stable documents,
        while a re-retrieved chunk set inside the cached prefix costs a full
        prefix rewrite on every single turn. Stable documents (native PDF
        upload) are untouched by this and keep their leading position.
        """
        content = msg.get("content")
        if not isinstance(content, list):
            return False

        extracted: list[str] = []
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "text":
                continue
            text = block.get("text", "")
            match = PATTERN_RAG_MESSAGE.search(text)
            if not match:
                continue
            extracted.append(match.group(0))
            # Strip, so a leftover newline cannot itself become cache drift.
            block["text"] = (text[: match.start()] + text[match.end():]).strip()

        if not extracted:
            return False

        # A message that was nothing but RAG would leave an empty text block,
        # which the API rejects.
        msg["content"] = [
            b for b in content
            if not (isinstance(b, dict) and b.get("type") == "text" and not b.get("text", "").strip())
        ]
        msg["content"].append({"type": "text", "text": "\n\n".join(extracted)})
        logger.debug(
            f"📋 RAG: moved {len(extracted)} block(s) into a trailing content block"
        )
        return True

    def _parse_assistant_tool_calls_string(self, content: str) -> list[dict]:
        """Reconstruct structured Claude messages from an OpenWebUI assistant
        string that contains ``<details type="tool_calls">`` HTML blocks.

        OpenWebUI stores the entire assistant turn (including tool calls and
        results) as a single flat text string. To replay the conversation via
        the Claude API we must parse that HTML back into structured
        ``tool_use`` / ``tool_result`` blocks and emit the correct
        assistant→user→assistant sequence.

        Returns a list of ``{"role": ..., "content": [...]}`` dicts. Each
        consecutive run of ``tool_calls`` becomes one assistant message with
        multiple ``tool_use`` blocks followed by a single user message carrying
        all matching ``tool_result`` blocks. Text between tool-call runs
        terminates the current turn and starts a new assistant message.
        """
        segments: list[tuple[str, str]] = []
        last_end = 0
        for m in PATTERN_TOOL_CALLS_BLOCK.finditer(content):
            segments.append(("text", content[last_end:m.start()]))
            segments.append(("tool_call", m.group(1)))
            last_end = m.end()
        segments.append(("text", content[last_end:]))

        messages: list[dict] = []
        current_assistant: list[dict] = []
        pending_results: list[dict] = []

        def flush() -> None:
            """Emit the accumulated assistant/tool_result messages and reset the buffers."""
            if current_assistant:
                messages.append({"role": "assistant", "content": list(current_assistant)})
                current_assistant.clear()
            if pending_results:
                messages.append({"role": "user", "content": list(pending_results)})
                pending_results.clear()

        for kind, data in segments:
            if kind == "text":
                # Emptiness is checked BEFORE the flush, not after. Consecutive
                # tool-call blocks are separated by an empty segment (the pattern
                # eats the newline on both sides), and flushing on that split a
                # single multi-tool assistant turn into one message per tool --
                # a valid but different structure than the live turn, so the
                # prefix diverged there.
                if not data.strip():
                    continue
                # Reuse the existing converter for text (handles compaction
                # extraction and code_interpreter stripping). It will also no-op
                # on the already-extracted tool_calls HTML.
                blocks = self._convert_content_to_claude_format(data, role="assistant")
                if not blocks:
                    continue
                # Only real prose terminates the prior turn. A segment holding
                # nothing but server-tool carriers (web_search and friends are
                # rendered as <details type="tool_calls"> too, but carry
                # data-payload-b64 and are therefore skipped by
                # PATTERN_TOOL_CALLS_BLOCK) belongs to the SAME assistant
                # message it was emitted in. Flushing there produced
                # assistant[text, tool_use] / user[tool_result] /
                # assistant[server_tool_use] -- three messages where the live
                # turn had two.
                if pending_results and any(
                    isinstance(b, dict) and b.get("type") == "text" for b in blocks
                ):
                    flush()
                current_assistant.extend(blocks)
            else:  # tool_call
                attrs = dict(PATTERN_TOOL_CALLS_ATTRS.findall(data))
                tc_id = html.unescape(attrs.get("id", "") or "")
                tc_name = html.unescape(attrs.get("name", "") or "")
                if not tc_id or not tc_name:
                    logger.warning(
                        "Skipping malformed <details type='tool_calls'> "
                        "block (missing id/name) during history reconstruction"
                    )
                    continue
                tc_args_raw = html.unescape(attrs.get("arguments", "") or "")
                tc_result_raw = html.unescape(attrs.get("result", "") or "")
                tc_done = (attrs.get("done", "true") or "true") == "true"
                tc_error = (attrs.get("error", "false") or "false") == "true"
                try:
                    tc_input = json.loads(tc_args_raw) if tc_args_raw else {}
                    if not isinstance(tc_input, dict):
                        tc_input = {}
                except (json.JSONDecodeError, ValueError):
                    logger.warning(
                        f"Failed to parse tool_use arguments for "
                        f"{tc_name!r}: {tc_args_raw[:120]!r}"
                    )
                    tc_input = {}
                current_assistant.append({
                    "type": "tool_use",
                    "id": tc_id,
                    "name": tc_name,
                    "input": tc_input,
                })
                if tc_done:
                    # Route through the same converter as live tool results:
                    # embedded data:image URIs become real image blocks instead
                    # of raw base64 text (~1.5k vs ~170k tokens per image), and
                    # the TOOL_RESULT_MAX_TOKENS backstop applies on replay too.
                    result_content = (
                        self._convert_tool_result_content(tc_result_raw)
                        if tc_result_raw
                        else "(no result)"
                    )
                    result_block: dict = {
                        "type": "tool_result",
                        "tool_use_id": tc_id,
                        "content": result_content,
                    }
                    if tc_error:
                        result_block["is_error"] = True
                else:
                    # Interrupted / aborted tool call — synthesize an error
                    # result so the assistant/user chain stays valid.
                    result_block = {
                        "type": "tool_result",
                        "tool_use_id": tc_id,
                        "content": "tool execution was interrupted",
                        "is_error": True,
                    }
                pending_results.append(result_block)

        flush()
        return messages

    def _convert_tool_result_content(self, result_str, user=None):
        """
        Convert a raw client-tool result string into Anthropic tool_result content.

        Detects `data:image/<fmt>;base64,...` data URIs (as produced by e.g. a
        file-reading tool returning a PNG/JPEG) and converts them into real
        Anthropic image blocks instead of sending the raw base64 as TEXT - the
        same image costs ~1.5k tokens as an image block vs. ~170k tokens as
        text, and Claude can actually see it. Mixed text+image output is split
        into ordered text/image blocks; non-image output is returned unchanged
        (as a plain string) except for a token-count backstop
        (UserValves.TOOL_RESULT_MAX_TOKENS) that truncates runaway tool text.

        Returns either a plain string (old behavior: no image, no truncation)
        or a list of Anthropic content blocks (text/image).
        """
        if not isinstance(result_str, str) or not result_str:
            return result_str

        matches = list(PATTERN_TOOL_RESULT_DATA_IMAGE.finditer(result_str))
        if not matches:
            return self._truncate_tool_result_text(result_str, user)

        blocks = []
        last_end = 0
        for match in matches:
            prefix = result_str[last_end:match.start()]
            if prefix.strip():
                blocks.append({"type": "text", "text": self._truncate_tool_result_text(prefix, user)})
            blocks.append(
                self._build_tool_result_image_block(match.group("mime"), match.group("data"), user)
            )
            last_end = match.end()

        suffix = result_str[last_end:]
        if suffix.strip():
            blocks.append({"type": "text", "text": self._truncate_tool_result_text(suffix, user)})

        return blocks if blocks else result_str

    def _truncate_tool_result_text(self, text: str, user=None) -> str:
        """
        Backstop against a runaway non-image tool result blowing the context
        window. Truncates to UserValves.TOOL_RESULT_MAX_TOKENS (estimated as
        len//4 chars). 0 disables the guard. Image blocks are exempt - they
        are already cheap after conversion.
        """
        if not text:
            return text
        max_tokens = 50000
        try:
            user_valves = user.get("valves") if isinstance(user, dict) else None
            if user_valves is not None:
                max_tokens = getattr(user_valves, "TOOL_RESULT_MAX_TOKENS", 50000)
        except Exception:
            pass
        if not max_tokens or max_tokens <= 0:
            return text
        max_chars = max_tokens * 4
        if len(text) <= max_chars:
            return text
        logger.debug(f" Tool result text truncated: {len(text)}c > {max_chars}c limit")
        return text[:max_chars] + "\n[tool result truncated: exceeded TOOL_RESULT_MAX_TOKENS]"

    def _get_tool_result_image_max_dims(self, user=None) -> tuple[int, int]:
        """
        Read the user's OpenWebUI image-compression max dimensions from
        __user__["settings"]["ui"] (keys "imageCompression" bool and
        "imageCompressionSize" {"width":.., "height":..}). Falls back to a
        1568px long-edge cap (Anthropic's own recommended max before it
        downscales anyway) when compression is off or dims aren't set.
        """
        default_dim = 1568
        try:
            ui_settings = (user or {}).get("settings", {}).get("ui", {}) or {}
            if ui_settings.get("imageCompression"):
                size = ui_settings.get("imageCompressionSize") or {}
                width = size.get("width")
                height = size.get("height")
                width = int(width) if width not in (None, "") else None
                height = int(height) if height not in (None, "") else None
                if width and height:
                    return width, height
        except Exception as e:
            logger.debug(f" Failed to read imageCompressionSize, using default: {e}")
        return default_dim, default_dim

    def _build_tool_result_image_block(self, mime_type: str, encoded: str, user=None) -> dict:
        """
        Decode a base64 image payload extracted from a tool result into an
        Anthropic image content block, downscaling it per
        _get_tool_result_image_max_dims() to keep token cost low. Falls back
        to the original image (if under the 25MB cap) or a text placeholder
        on any decode/resize failure - mirrors the size-cap approach used for
        image_url content blocks above.
        """
        media_type = f"image/{mime_type}"
        MAX_IMAGE_SIZE = 25 * 1024 * 1024  # 25 MB (conservative, matches the image_url path)

        try:
            decoded_bytes = base64.b64decode(encoded)
        except Exception as decode_ex:
            logger.debug(f" Tool result image base64 decode failed: {decode_ex}")
            return {"type": "text", "text": "[Image data could not be decoded - invalid base64 format]"}

        final_bytes = decoded_bytes
        final_media_type = media_type

        if PIL_AVAILABLE:
            try:
                import io

                max_w, max_h = self._get_tool_result_image_max_dims(user)
                with PILImage.open(io.BytesIO(decoded_bytes)) as img:
                    img.load()
                    width, height = img.size
                    if width > max_w or height > max_h:
                        scale = min(max_w / width, max_h / height)
                        new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
                        if img.mode == "P":
                            img = img.convert("RGBA")
                        resized = img.resize(new_size, PILImage.LANCZOS)
                        buf = io.BytesIO()
                        resized.save(buf, format="PNG")
                        final_bytes = buf.getvalue()
                        final_media_type = "image/png"
            except Exception as resize_ex:
                logger.debug(f" Tool result image resize failed, sending original: {resize_ex}")
                final_bytes = decoded_bytes
                final_media_type = media_type

        if len(final_bytes) > MAX_IMAGE_SIZE:
            logger.debug(f" Tool result image too large: {len(final_bytes)} bytes")
            return {
                "type": "text",
                "text": f"[Image too large for Anthropic API. Max size: 25MB, received: {len(final_bytes)//1024//1024}MB]",
            }

        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": final_media_type,
                "data": base64.b64encode(final_bytes).decode("ascii"),
            },
        }
