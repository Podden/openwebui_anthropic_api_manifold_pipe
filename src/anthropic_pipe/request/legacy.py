"""Compiled Pipe method group: assistant turns stored as <details> HTML (pipe < 0.11). Compiled into class Pipe.

Before output items, a turn went into OpenWebUI as one string: thinking, server
tools and tool calls as <details> blocks with base64 carriers. This group reads
such turns back into API blocks, and converts them into output items once
(LEGACY_CHAT_MIGRATION). It goes away once every chat is migrated and no API
client sends that HTML back.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class PipeLegacyMethods:
    def _legacy_assistant_blocks(self, content: str) -> List[dict]:
        """Blocks of an assistant turn stored as one string with <details> HTML (pipe < 0.11)."""
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
            # Pre-scan the standalone *_tool_result carriers, keyed by
            # tool_use_id. The API requires a server_tool_use to be
            # followed directly by its result; the stored HTML does not
            # guarantee that order once several server tools run in
            # quick succession (their carriers interleave with text and
            # with each other), and replaying document order then 400s
            # the next request with "tool use found without a
            # corresponding tool_result block".
            standalone_results: dict[str, dict] = {}
            for _, kind, match in all_matches:
                if kind != "server_tool_result":
                    continue
                attrs = dict(PATTERN_DATA_ATTR.findall(match.group(1)))
                payload_b64 = attrs.get("payload-b64", "")
                decoded = (
                    self._decode_block_payload(payload_b64) if payload_b64 else None
                )
                if (
                    isinstance(decoded, dict)
                    and decoded.get("type", "").endswith("_tool_result")
                    and decoded.get("tool_use_id")
                ):
                    standalone_results[decoded["tool_use_id"]] = decoded
            consumed_results: set[str] = set()
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
                        result_decoded = (
                            self._decode_block_payload(result_b64) if result_b64 else None
                        )
                        if (
                            isinstance(result_decoded, dict)
                            and result_decoded.get("type", "").endswith("_tool_result")
                        ):
                            blocks.append(result_decoded)
                            if result_decoded.get("tool_use_id"):
                                consumed_results.add(result_decoded["tool_use_id"])
                        else:
                            # No embedded result — pull the standalone
                            # carrier forward so the pair stays adjacent.
                            tool_use_id = decoded.get("id", "")
                            if tool_use_id in standalone_results:
                                blocks.append(standalone_results[tool_use_id])
                                consumed_results.add(tool_use_id)
                            else:
                                logger.warning(
                                    "server_tool_use id=%r has no result carrier; "
                                    "replaying it unpaired will 400 the request",
                                    tool_use_id,
                                )
                    # else: legacy/missing payload → drop
                elif kind == "server_tool_result":
                    attrs_str = match.group(1)
                    attrs = dict(PATTERN_DATA_ATTR.findall(attrs_str))
                    payload_b64 = attrs.get("payload-b64", "")
                    decoded = self._decode_block_payload(payload_b64) if payload_b64 else None
                    if isinstance(decoded, dict) and decoded.get("type", "").endswith("_tool_result"):
                        # Skip what was already pulled forward next to
                        # its server_tool_use above.
                        if decoded.get("tool_use_id") not in consumed_results:
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

        if content.strip():
            return [{"type": "text", "text": content}]
        return []

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
        all matching ``tool_result`` blocks. Any content between tool-call runs
        (text, thinking, server tools) terminates the current turn and starts
        a new assistant message.
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
                # Anything after a finished client tool round -- prose, thinking,
                # a server tool -- was produced by the NEXT response, which the
                # API only starts once the round's tool_results are in. Closing
                # the round on prose alone folded A / [web search, thinking] / B
                # into one assistant message, and the API rejected A for having
                # blocks after it instead of its tool_result (#58). The one
                # exception: a server tool called in the SAME response as the
                # client tool_use (marked after-client, see below).
                if pending_results:
                    # A server tool the model called right after the client
                    # tool_use belongs to that same assistant message; only its
                    # result opens the next one (see server_tool.py, after_client).
                    after_client_ids = {
                        html.unescape(a.get("tool-use-id", ""))
                        for a in (
                            dict(PATTERN_DATA_ATTR.findall(m.group(1)))
                            for m in PATTERN_SERVER_TOOL_USE_BLOCK.finditer(data)
                        )
                        if a.get("after-client") == "true"
                    }
                    while (
                        blocks
                        and blocks[0].get("type") == "server_tool_use"
                        and blocks[0].get("id") in after_client_ids
                    ):
                        current_assistant.append(blocks.pop(0))
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
                tc_result_raw = self._canonical_tool_result_text(html.unescape(attrs.get("result", "") or ""))
                tc_done = (attrs.get("done", "true") or "true") == "true"
                tc_error = (attrs.get("error", "false") or "false") == "true"
                try:
                    tc_input = json.loads(tc_args_raw) if tc_args_raw else {}
                    if not isinstance(tc_input, dict):
                        tc_input = {}
                except (json.JSONDecodeError, ValueError):
                    logger.warning(
                        f"Failed to parse tool_use arguments for "
                        f"{tc_name!r} ({len(tc_args_raw)}c)"
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

    # -- one-time migration to output items -----------------------------------
    def _legacy_items(self, text: str) -> Optional[list]:
        """Output items for one stored assistant turn; None when it holds no <details> to convert."""
        if not isinstance(text, str) or "<details" not in text:
            return None
        messages = []
        if '<details type="tool_calls"' in text:
            messages = self._parse_assistant_tool_calls_string(text)
        if not messages:
            messages = [{"role": "assistant", "content": self._legacy_assistant_blocks(text)}]
        items = ItemStream()
        for message in messages:
            if message["role"] == "assistant":
                items.begin_response()
                for block in message["content"]:
                    items.add_block(block)
                items.end_response()
            else:
                for block in message["content"]:
                    if block.get("type") == "tool_result":
                        items.tool_result(block.get("tool_use_id", ""), block, _tool_text(block.get("content")))
        items.finish()
        return items.items if any(i.get("type") != "message" for i in items.items) else None

    @staticmethod
    def _legacy_comparable(messages: list) -> list:
        """Messages without what output items cannot carry: the cache-diagnostics
        block (legacy replay sent it to the model) and the seam between adjacent
        text blocks (items join them). A difference there costs one cache miss."""
        out = []
        for message in messages:
            blocks: list = []
            for block in message["content"]:
                block = {k: v for k, v in block.items() if k != "cache_control"}
                if block.get("type") == "text":
                    block["text"] = PATTERN_CACHE_DIAGNOSTICS_BLOCK.sub("", block["text"])
                    if blocks and blocks[-1].get("type") == "text":
                        blocks[-1]["text"] += block["text"]
                        continue
                blocks.append(block)
            out.append([b for b in blocks if b.get("type") != "text" or b["text"].strip()])
        return out

    def _migrate_legacy_message(self, message: dict, convert: Callable) -> tuple[str, Optional[list]]:
        """(outcome, items) for one stored message.

        ``convert`` is OpenWebUI's convert_output_to_messages: the check runs the
        same path the next turn will. "converted" replays byte-identical, so the
        chat keeps its prompt cache; "reflowed" differs only in what output items
        cannot carry (one cache miss when the chat continues); "mismatch" stays legacy.
        """
        if message.get("role") != "assistant":
            return "skip", None
        output = message.get("output") if isinstance(message.get("output"), list) else []
        if any(isinstance(i, dict) and i.get("type") != "message" for i in output):
            return "skip", None  # already output items
        replayed = (convert(output) if output else None) or [{"role": "assistant", "content": message.get("content") or ""}]
        if len(replayed) != 1 or not isinstance(replayed[0].get("content"), str):
            return "skip", None
        items = self._legacy_items(replayed[0]["content"])
        if items is None:
            return "skip", None

        def frame(middle: list) -> list:
            return [{"role": "user", "content": "."}, *middle, {"role": "user", "content": "."}]

        before = self._convert_messages_to_claude_format(frame(replayed))
        after = self._convert_messages_to_claude_format(frame(convert(items)))
        if before[1:] == after[1:]:
            return "converted", items
        if before[2] == after[2] and self._legacy_comparable(before[1]) == self._legacy_comparable(after[1]):
            return "reflowed", items
        return "mismatch", None

    async def _migrate_legacy_chats(self, prefix: str, apply: bool) -> dict:
        """Give every legacy assistant turn of this pipe's models output items (one write per chat)."""
        from open_webui.models.chat_messages import ChatMessages
        from open_webui.models.chats import Chats
        from open_webui.utils.misc import convert_output_to_messages

        def convert(output: list) -> list:
            return convert_output_to_messages(output, raw=True, reasoning_format=None, flatten_tool_images=True)

        stats: dict = {"chats": 0, "skip": 0, "converted": 0, "reflowed": 0, "mismatch": 0, "written": 0, "failed": 0, "mismatches": []}
        chat_ids: set = set()
        # Messages sent through a workspace model carry its id, not the pipe model's.
        # Without them the migration still covers the pipe's own model ids, as before.
        workspace: set = set()
        try:
            from open_webui.models.models import Models

            workspace = {m.id for m in await Models.get_all_models() if str(m.base_model_id or "").startswith(prefix + ".")}
        except Exception as e:
            logger.warning(f"Legacy migration: workspace models not listed, pipe models only: {e}")

        def ours(model_id) -> bool:
            return str(model_id).startswith(prefix + ".") or str(model_id) in workspace

        # OpenWebUI 0.12.4 renamed get_unique_counts_by_model; both return {model_id: count}.
        count_by_model = getattr(ChatMessages, "get_unique_counts_by_model", None) or ChatMessages.get_message_count_by_model
        for model_id in await count_by_model():
            if not ours(model_id):
                continue
            skip = 0
            while page := await ChatMessages.get_chat_ids_by_model_id(model_id, skip=skip, limit=200):
                chat_ids.update(page)
                skip += len(page)
        for chat_id in sorted(chat_ids):
            stats["chats"] += 1
            try:
                messages = await Chats.get_messages_map_by_chat_id(chat_id) or {}
                chat = await Chats.get_chat_by_id(chat_id)
                stored = (((chat.chat if chat else None) or {}).get("history") or {}).get("messages") or {}
                changed = {}
                for mid, message in messages.items():
                    if not ours(message.get("model", "")):
                        continue
                    outcome, items = self._migrate_legacy_message(message, convert)
                    stats[outcome] += 1
                    if outcome == "mismatch" and len(stats["mismatches"]) < 50:
                        stats["mismatches"].append(f"{chat_id}/{mid}")
                    if items and isinstance(stored.get(mid), dict):
                        changed[mid] = {**stored[mid], "output": items}
                if changed and apply:
                    if await Chats.update_chat_by_id(chat_id, {"history": {"messages": changed}}, touch=False):
                        stats["written"] += 1
                    else:
                        stats["failed"] += 1
            except Exception:
                stats["failed"] += 1
                logger.exception(f"Legacy migration: chat {chat_id} failed")
            await asyncio.sleep(0)
        return stats

    def _start_legacy_migration(self, model: str) -> None:
        """LEGACY_CHAT_MIGRATION: run once per process and mode, in the background."""
        mode = getattr(self.valves, "LEGACY_CHAT_MIGRATION", "off")
        if mode == "off" or "." not in (model or "") or getattr(self, "_legacy_migration_mode", None) == mode:
            return
        self._legacy_migration_mode = mode
        self._legacy_migration_task = asyncio.create_task(
            self._run_legacy_migration(model.split(".", 1)[0], apply=mode == "on")
        )

    async def _run_legacy_migration(self, prefix: str, apply: bool) -> None:
        # ponytail: no cross-worker lock. With several uvicorn workers each runs
        # it once; a turn converted twice is just written twice, both valid.
        try:
            from open_webui.env import DATA_DIR
        except ImportError:
            return  # not inside OpenWebUI (tests, API-only use)

        # One file per mode, written after every finished run: each mode runs once
        # per installation, not on every restart. Delete the file to run it again.
        done_file = os.path.join(str(DATA_DIR), f"anthropic_pipe_legacy_migration_{prefix}.json")
        report = done_file if apply else done_file.replace(".json", ".dryrun.json")
        if os.path.exists(done_file) or os.path.exists(report):
            return
        started = time.time()
        try:
            stats = await self._migrate_legacy_chats(prefix, apply)
        except Exception:
            logger.exception("Legacy chat migration failed")
            return
        stats["seconds"] = round(time.time() - started, 1)
        stats["applied"] = apply
        logger.info(f"Legacy chat migration ({'applied' if apply else 'dry run'}): "
                    f"{ {k: v for k, v in stats.items() if k != 'mismatches'} }")
        if stats["failed"]:
            logger.warning(f"Legacy chat migration: {stats['failed']} chat(s) failed; delete {report} to retry")
        with open(report, "w", encoding="utf-8") as fh:
            json.dump({**stats, "at": int(time.time())}, fh, indent=1)