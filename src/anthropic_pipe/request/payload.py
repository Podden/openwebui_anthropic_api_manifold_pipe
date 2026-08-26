"""Request payload creation for the Anthropic OpenWebUI pipe.
This module is compiled into ``anthropic_pipe.py`` for OpenWebUI upload.
Keep request-shaping logic here so cache/debug work does not require
reading the full streaming pipe.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional
from urllib.parse import unquote

logger = logging.getLogger(__name__)

async def create_request_payload(
    pipe,
    body: Dict,
    __metadata__: dict[str, Any],
    __user__: Dict[str, Any],
    __tools__: Optional[Dict[str, Dict[str, Any]]],
    __event_emitter__: Callable[[Dict[str, Any]], Awaitable[None]],
    __files__: Optional[List[Dict[str, Any]]] = None,
) -> tuple[dict, dict, List[str], List[str]]:
    """Build the Anthropic API request payload, headers, and marker/tool metadata for one turn."""

    status_cls = globals().get("StatusEmitter")
    if status_cls:
        status = status_cls(__event_emitter__)
    else:
        class _PayloadStatus:
            def __init__(self, emit_event):
                """Store the OpenWebUI event emitter callback."""
                self._emit_event = emit_event

            async def activity(self, description: str) -> None:
                """Emit an in-progress status event."""
                await self._emit_event(
                    {"type": "status", "data": {"description": description, "done": False}}
                )

            async def complete(self, description: str) -> None:
                """Emit a completed status event."""
                await self._emit_event(
                    {"type": "status", "data": {"description": description, "done": True}}
                )

            async def notification(self, content: str, *, type: str = "warning") -> None:
                """Emit a notification event."""
                await self._emit_event(
                    {"type": "notification", "data": {"type": type, "content": content}}
                )

        status = _PayloadStatus(__event_emitter__)

    ## General payload creation
    actual_model_name = body["model"].split("/")[-1]
    model_info = pipe.get_model_info(actual_model_name)
    max_tokens_limit = model_info["max_tokens"]
    requested_max_tokens = body.get("max_tokens", max_tokens_limit)
    max_tokens = min(requested_max_tokens, max_tokens_limit)
    payload: dict[str, Any] = {
        "model": actual_model_name,
        "max_tokens": max_tokens,
        "stream": body.get("stream", True),
        "metadata": body.get("metadata", {}),
    }
    # Opus 4.7 / 4.8 and the 4.6+ adaptive-thinking family reject sampling params
    # (temperature / top_p / top_k) — API returns 400. Strip them there.
    # Heuristic: models that support adaptive thinking (Opus 4.6, Sonnet 4.6,
    # Opus 4.7, Opus 4.8) do not accept these fields when adaptive is enabled.
    # On Opus 4.7 / 4.8 they are rejected unconditionally. Safe to skip for the set.
    _strip_sampling = bool(model_info.get("supports_adaptive_thinking"))
    if not _strip_sampling and body.get("temperature") is not None:
        payload["temperature"] = float(body.get("temperature", 0))
    if not _strip_sampling and body.get("top_k") is not None:
        payload["top_k"] = float(body.get("top_k", 0))
    if not _strip_sampling and body.get("top_p") is not None:
        payload["top_p"] = float(body.get("top_p", 0))

    # Add data residency if set to US (1.1x token cost)
    if pipe.valves.DATA_RESIDENCY == "us":
        payload["inference_geo"] = "us"

    # Add Fast Mode if enabled and model supports it (Opus 4.8 / Opus 5)
    if pipe.valves.ENABLE_FAST_MODE and model_info.get("supports_fast_mode", False):
        payload["speed"] = "fast"
        logger.debug("Fast Mode enabled for this request")
        
    # Handle "Effort" parameter (maps from OpenWebUI's reasoning_effort or user valves)
    # Effort works differently based on model capabilities
    effort_config = None
    effective_effort = None

    if model_info["supports_effort"]:
        # Clamp an effort value to what the current model supports.
        #   xhigh -> high if the model doesn't advertise xhigh (Opus 4.7 only)
        #   max   -> high if the model doesn't advertise max   (Opus 4.7/4.6, Sonnet 4.6)
        def _clamp_effort(value: str) -> str:
            """Downgrade an effort value the current model does not support to 'high'."""
            if value == "xhigh" and not model_info.get("supports_effort_xhigh"):
                return "high"
            if value == "max" and not model_info.get("supports_effort_max"):
                return "high"
            return value

        body_effort = body.get("reasoning_effort")
        if body_effort in ("low", "medium", "high", "xhigh", "max"):
            effective_effort = _clamp_effort(body_effort)
        else:
            effective_effort = _clamp_effort(__user__["valves"].EFFORT)

        effort_config = {"effort": effective_effort}
        logger.debug(f"Effort level set to: {effective_effort}")

    # Handle Thinking
    enable_thinking = __user__["valves"].ENABLE_THINKING or __metadata__.get(
        "anthropic_thinking", False
    )
    if enable_thinking and model_info["supports_thinking"]:
        # Opus 4.6 (supports adaptive thinking) uses effort as the control
        if model_info["supports_adaptive_thinking"]:
            thinking_config = {"type": "adaptive"}
        else:
            user_budget = __user__["valves"].THINKING_BUDGET_TOKENS
            max_tokens = min(
                body.get("max_tokens", model_info["max_tokens"]),
                model_info["max_tokens"],
            )
            context_limit = model_info.get("context_length", 200000)

            # For Claude 4 models with interleaved thinking+tools, allow up to context window
            if model_info.get("supports_thinking") and model_info.get(
                "supports_programmatic_calling"
            ):
                thinking_budget = min(user_budget, context_limit)
            else:
                # budget_tokens must be < max_tokens
                thinking_budget = (
                    min(user_budget, max_tokens - 1) if max_tokens > 1 else 1
                )
            thinking_config = {
                "type": "enabled",
                "budget_tokens": thinking_budget,
            }
            logger.debug(
                f"Using manual thinking with budget_tokens: {thinking_budget}, effort: {effective_effort}"
            )

        thinking_display = __user__["valves"].THINKING_DISPLAY
        if thinking_display in ("omitted", "summarized"):
            thinking_config["display"] = thinking_display

        payload["thinking"] = thinking_config
    elif model_info.get("thinking_on_by_default"):
        # Opus 5 / Sonnet 5 think unless told otherwise, so simply omitting the
        # `thinking` field no longer honours the toggle — send the explicit
        # disable. Opus 5 rejects `thinking:{"type":"disabled"}` at effort
        # xhigh/max with a 400, so the toggle also caps effort at high.
        payload["thinking"] = {"type": "disabled"}
        if effective_effort in ("xhigh", "max"):
            logger.info(
                f"Thinking disabled on {actual_model_name}: effort "
                f"'{effective_effort}' is incompatible with thinking:disabled, "
                "clamping to 'high'"
            )
            effective_effort = "high"
            effort_config = {"effort": "high"}

    raw_messages = body.get("messages", []) or []

    system_messages, processed_messages, previous_marker_metadata = (
        pipe._convert_messages_to_claude_format(raw_messages)
    )
    new_marker_metadata: List[str] = []

    # Extract container_id from previous metadata markers for multi-turn container reuse
    previous_container_id = None
    for metadata_entry in previous_marker_metadata:
        # Format: "N:container_id:ENCODED_VALUE"
        parts = metadata_entry.split(":", 2)
        if len(parts) >= 3 and parts[1] == "container_id":
            previous_container_id = unquote(parts[2])
            logger.debug(f"📦 Restored container_id from marker: {previous_container_id}")

    # Track if Files API uploaded any files (for auto-enabling code execution)
    has_files_api_uploads = False
    user_valves_for_features = __user__["valves"]
    requested_skills = list(getattr(user_valves_for_features, "SKILLS", []) or [])
    use_files_api = bool(getattr(user_valves_for_features, "USE_FILES_API", False)) or bool(
        __metadata__.get("enforce_files_api")
    )
    has_full_files_attached = any(
        file.get("type") == "file" and file.get("context", "full") == "full"
        for file in (__files__ or [])
    )

    if requested_skills and has_full_files_attached and not use_files_api:
        await status.activity("Skills require Files API for attached files")
        await status.notification(
            "Anthropic API Skills cannot access attached files through OpenWebUI RAG or native PDF upload. "
            "Enable USE_FILES_API, use the Files API Toggle, or attach the Companion Filter so files are routed to Anthropic Files API."
        )

    if __files__ and use_files_api and not FILES_AVAILABLE:
        await status.complete("Files API unavailable")
        await status.notification(
            "Anthropic Files API mode was requested, but OpenWebUI Files/Storage support is unavailable in this runtime. "
            "Enable OpenWebUI Files support or disable Files API mode for this request."
        )

    # Native-PDF anchors persisted on earlier turns. OpenWebUI drops full-context
    # files from __files__ on follow-up turns (it only sends a file in __files__
    # the turn it was attached). Without restoring the document block from these
    # markers, the native PDF vanishes from the cache prefix on every later turn,
    # which both hides the PDF from the model and forces a full cache rebuild.
    has_prior_pdf_markers = any(
        len(e.split(":", 2)) >= 3 and e.split(":", 2)[1] == "pdf"
        for e in (previous_marker_metadata or [])
    )

    if __files__ and use_files_api and FILES_AVAILABLE:
        # Files API overrules native PDF upload — all files go as container_upload
        blocks_by_user_msg, uploaded_filenames = await pipe._process_files_api_data(
            __files__, __event_emitter__, processed_messages
        )
        if blocks_by_user_msg:
            has_files_api_uploads = True
            # Insert container_upload blocks at the correct user messages
            user_msg_num = 0
            for i, msg in enumerate(processed_messages):
                if msg["role"] == "user" and user_msg_num in blocks_by_user_msg:
                    # Ensure content is a list
                    if isinstance(msg["content"], str):
                        msg["content"] = [{"type": "text", "text": msg["content"]}]
                    msg["content"] = blocks_by_user_msg[user_msg_num] + msg["content"]
                if msg["role"] == "user":
                    user_msg_num += 1

            # Remove RAG sources for uploaded files
            if uploaded_filenames:
                logger.debug(f"📋 RAG: Removing {len(uploaded_filenames)} file source(s) from RAG")
                pipe._remove_specific_sources_from_rag_message(processed_messages, uploaded_filenames)

    elif __user__["valves"].USE_PDF_NATIVE_UPLOAD and (__files__ or has_prior_pdf_markers):
        # Native PDF upload (base64 document blocks) — only PDFs.
        # Each PDF is anchored to the user-message it was first attached
        # to (tracked via metadata markers); never to msg[0]. This keeps
        # the byte-prefix of the conversation cache-stable across turns.
        # This branch also runs on follow-up turns with an empty __files__
        # as long as a prior PDF marker exists, so the document block is
        # restored at its original anchor instead of disappearing.
        native_pdf_filenames = list(dict.fromkeys(
            file.get("name")
            for file in (__files__ or [])
            if (
                file.get("type") == "file"
                and file.get("context") == "full"
                and file.get("name", "").lower().endswith(".pdf")
            )
            and file.get("name")
        ))
        pdf_blocks_by_user_msg, new_marker_metadata = (
            await pipe._get_full_context_pdfs(
                __files__, previous_marker_metadata, processed_messages, raw_messages
            )
        )
        if pdf_blocks_by_user_msg:
            user_msg_num = 0
            for msg in processed_messages:
                if msg["role"] == "user":
                    if user_msg_num in pdf_blocks_by_user_msg:
                        if isinstance(msg["content"], str):
                            msg["content"] = [
                                {"type": "text", "text": msg["content"]}
                            ]
                        msg["content"] = (
                            pdf_blocks_by_user_msg[user_msg_num]
                            + msg["content"]
                        )
                    user_msg_num += 1

        # Remove RAG sources for native-PDF files on every turn, even
        # when the PDF block itself was restored from prior metadata.
        # Otherwise OpenWebUI can re-inject the same PDF as <context>
        # on the latest user message after the PDF is already attached
        # natively.
        if native_pdf_filenames:
            logger.debug(
                f"📋 RAG: Removing {len(native_pdf_filenames)} native PDF source(s) from RAG"
            )
            pipe._remove_specific_sources_from_rag_message(
                processed_messages, native_pdf_filenames
            )

    # Full-context uploads that neither the Files API nor native PDF upload
    # claimed (EPUB, DOCX, TXT, MD — and PDFs too when native upload is off).
    # OpenWebUI merges them into its <context> RAG template on the last user
    # message, where the cache-control pass must treat them as volatile and the
    # breakpoint lands in front of them: the whole file is re-sent uncached on
    # every turn. Anchor them like PDFs instead and cut them out of the
    # template, so the existing breakpoint covers them.
    if not has_files_api_uploads:
        (
            full_ctx_blocks_by_user_msg,
            full_ctx_markers,
            full_ctx_filenames,
        ) = await pipe._get_full_context_texts(
            __files__,
            previous_marker_metadata,
            processed_messages,
            raw_messages,
            exclude_pdfs=bool(__user__["valves"].USE_PDF_NATIVE_UPLOAD),
        )
        if full_ctx_blocks_by_user_msg:
            user_msg_num = 0
            for msg in processed_messages:
                if msg["role"] == "user":
                    if user_msg_num in full_ctx_blocks_by_user_msg:
                        if isinstance(msg["content"], str):
                            msg["content"] = [
                                {"type": "text", "text": msg["content"]}
                            ]
                        msg["content"] = (
                            full_ctx_blocks_by_user_msg[user_msg_num]
                            + msg["content"]
                        )
                    user_msg_num += 1
            new_marker_metadata.extend(full_ctx_markers)
        if full_ctx_filenames:
            logger.debug(
                f"📋 RAG: Removing {len(full_ctx_filenames)} full-context source(s) from RAG"
            )
            pipe._remove_specific_sources_from_rag_message(
                processed_messages, full_ctx_filenames
            )

    ## Tools Handling
    # Correct Order for Caching: Tools, System, Messages
    tools_list, api_tool_names = pipe._convert_tools_to_claude_format(
        __tools__, body, actual_model_name, __user__, __metadata__
    )

    activate_code_execution = __metadata__.get(
        "activate_code_execution_tool", False
    )

    # Auto-enable code execution when Files API uploaded files (container_upload needs it)
    if has_files_api_uploads:
        activate_code_execution = True

    # Auto-enable code execution when programmatic tool calling is active
    # (programmatic calling requires code execution to orchestrate tool calls)
    if (
        pipe.valves.ENABLE_PROGRAMMATIC_TOOL_CALLING
        and model_info.get("supports_programmatic_calling", False)
        and tools_list  # Only when there are tools to call programmatically
    ):
        activate_code_execution = True

    # Check if any dynamic filtering web tools (20260209) are in tools_list.
    # These tools cause the API to AUTO-INJECT code_execution internally.
    # We must NOT add code_execution_20250825 manually when these are present —
    # doing so triggers: "Auto-injecting tools would conflict with existing tool names"
    # However, code_execution_20260120 (programmatic) CAN coexist because we provide
    # it explicitly and the API won't auto-inject a second code_execution.
    has_dynamic_filtering_tools = any(
        t.get("type", "").endswith("_20260209") for t in tools_list
    )
    has_code_execution = any(
        t.get("name") == "code_execution" for t in tools_list
    )

    # Open Terminal bridge is mutually exclusive with the code_execution sandbox:
    # when Claude's native bash / text_editor tools are wired to the real
    # terminal session, don't also hand it Anthropic's ephemeral server sandbox
    # for the same operations. No terminal → these tools are absent and
    # code_execution is injected as usual.
    has_native_terminal_tools = any(
        t.get("name") in ("bash", "str_replace_based_edit_tool") for t in tools_list
    )

    # Determine which code_execution version to add
    use_programmatic_code_exec = (
        pipe.valves.ENABLE_PROGRAMMATIC_TOOL_CALLING
        and model_info.get("supports_programmatic_calling", False)
    )

    if activate_code_execution and not has_code_execution and not has_native_terminal_tools:
        if use_programmatic_code_exec:
            # Always add code_execution_20260120 for programmatic calling,
            # even alongside dynamic filtering tools (it supersedes the auto-injected one)
            code_exec_type = "code_execution_20260120"
            tools_list.insert(0, {"type": code_exec_type, "name": "code_execution"})
            has_code_execution = True
        elif not has_dynamic_filtering_tools:
            # Only add code_execution_20250825 if no dynamic filtering
            # (dynamic filtering auto-injects its own code_execution)
            code_exec_type = "code_execution_20250825"
            tools_list.insert(0, {"type": code_exec_type, "name": "code_execution"})
            has_code_execution = True
        # else: dynamic filtering tools present, no programmatic → let API auto-inject

    if requested_skills and not has_code_execution:
        await status.activity("Skills require Anthropic code_execution")
        await status.notification(
            "Anthropic API Skills require Anthropic code_execution. Enable the Code Execution Toggle, "
            "or attach the Companion Filter so OpenWebUI code_interpreter requests set activate_code_execution_tool."
        )

    # Create Headers - check UserValves API key first
    user_valves = __user__.get("valves") if __user__ else None
    user_api_key = getattr(user_valves, "ANTHROPIC_API_KEY", "") if user_valves else ""
    api_key = user_api_key.strip() if user_api_key and user_api_key.strip() else pipe.valves.ANTHROPIC_API_KEY

    headers = {
        "x-api-key": api_key,
        "anthropic-version": pipe.API_VERSION,
        "content-type": "application/json",
    }

    beta_headers: list[str] = []

    # Enable prompt caching if not disabled
    if pipe.valves.CACHE_CONTROL != "cache disabled":
        beta_headers.append("prompt-caching-2024-07-31")

    # Add code-execution beta header ONLY when we explicitly added code_execution to tools.
    # Do NOT add when using dynamic filtering v20260209 web tools — those auto-inject
    # code_execution internally and the beta header would cause a second injection → duplicate error.
    if has_code_execution:
        # code_execution_20260120 doesn't need the old beta header
        code_exec_is_new = any(
            t.get("type") == "code_execution_20260120" for t in tools_list
        )
        if not code_exec_is_new:
            beta_headers.append("code-execution-2025-08-25")
        if activate_code_execution:
            beta_headers.append("files-api-2025-04-14")
    if (
        pipe.valves.ENABLE_INTERLEAVED_THINKING
        and model_info["supports_thinking"]
        and not model_info["supports_adaptive_thinking"]
    ):
        beta_headers.append("interleaved-thinking-2025-05-14")

    # Add web_fetch beta header when using the older version (20250910)
    # The newer 20260209 version doesn't need a beta header
    uses_old_web_fetch = any(
        t.get("type") == "web_fetch_20250910" for t in tools_list
    )
    if pipe.valves.WEB_FETCH and uses_old_web_fetch:
        beta_headers.append("web-fetch-2025-09-10")

    # Add Files API beta header when files were uploaded but code_execution
    # wasn't otherwise activated (standalone file upload scenario)
    if has_files_api_uploads and "files-api-2025-04-14" not in beta_headers:
        beta_headers.append("files-api-2025-04-14")

    # Skills Integration. Anthropic expects an object container:
    # {"skills": [...]}, optionally with {"id": previous_container_id} for reuse.
    if requested_skills and has_code_execution:
        if "skills-2025-10-02" not in beta_headers:
            beta_headers.append("skills-2025-10-02")
        if "files-api-2025-04-14" not in beta_headers:
            beta_headers.append("files-api-2025-04-14")

        # Validate skills (cached to avoid API calls on every turn)
        validated_skills = await pipe._validate_and_get_skills(
            requested_skills,
            api_key,
            __event_emitter__,
        )
        if validated_skills:
            container: dict[str, Any] = {"skills": validated_skills}
            if previous_container_id:
                container["id"] = previous_container_id
            payload["container"] = container
            logger.debug(f"🔧 Added {len(validated_skills)} skills")
        else:
            await status.notification(
                f"No valid Anthropic API Skills found from requested list: {', '.join(requested_skills)}. Skills ignored."
            )
    elif previous_container_id:
        # Reuse container from previous turn for code execution state continuity
        payload["container"] = previous_container_id
        logger.info(f"📦 Reusing container from previous turn: {previous_container_id}")

    # Add advanced tool use beta (for programmatic calling and tool search)
    if __user__["valves"].ENABLE_TOOL_SEARCH or pipe.valves.ENABLE_PROGRAMMATIC_TOOL_CALLING:
        beta_headers.append("advanced-tool-use-2025-11-20")

    # Add advisor tool beta
    if __user__["valves"].ENABLE_ADVISOR_TOOL:
        beta_headers.append("advisor-tool-2026-03-01")

    # Add context editing strategies if enabled
    context_editing_strategy = __user__["valves"].CONTEXT_EDITING_STRATEGY
    if context_editing_strategy != "none":
        if "context-management-2025-06-27" not in beta_headers:
            beta_headers.append("context-management-2025-06-27")

        # Build context_management array for payload
        # IMPORTANT: clear_thinking must be FIRST if present (API requirement)
        context_management = []

        # Add clear_thinking FIRST if needed
        if (
            context_editing_strategy in ["clear_thinking", "clear_both"]
            and enable_thinking
            and model_info["supports_thinking"]
        ):
            _keep_val = __user__["valves"].CONTEXT_EDITING_THINKING_KEEP
            clear_thinking = {
                "type": "clear_thinking_20251015",
                # keep=0 → "all" (preserve all thinking → stable prompt cache).
                # keep>0 → sliding window (breaks cache every turn past threshold).
                "keep": "all" if _keep_val <= 0 else {
                    "type": "thinking_turns",
                    "value": _keep_val,
                },
            }
            context_management.append(clear_thinking)

        # Add clear_tool_uses SECOND
        if (
            context_editing_strategy in ["clear_tool_results", "clear_both"]
            and len(tools_list) > 2
        ):
            clear_tool_uses = {
                "type": "clear_tool_uses_20250919",
                "trigger": {
                    "type": "input_tokens",
                    "value": __user__["valves"].CONTEXT_EDITING_TOOL_TRIGGER,
                },
                "keep": {
                    "type": "tool_uses",
                    "value": __user__["valves"].CONTEXT_EDITING_TOOL_KEEP,
                },
            }
            if __user__["valves"].CONTEXT_EDITING_TOOL_CLEAR_AT_LEAST > 0:
                clear_tool_uses["clear_at_least"] = {
                    "type": "input_tokens",
                    "value": __user__["valves"].CONTEXT_EDITING_TOOL_CLEAR_AT_LEAST,
                }
            if __user__["valves"].CONTEXT_EDITING_TOOL_CLEAR_TOOL_INPUT:
                clear_tool_uses["clear_tool_inputs"] = True
            context_management.append(clear_tool_uses)

        if context_management:
            payload["context_management"] = {"edits": context_management}

    # Add compaction if enabled and model supports it. New beta support may need
    # MODEL_CAPABILITY_OVERRIDES because API capability metadata can lag.
    if __user__["valves"].ENABLE_COMPACTION and model_info.get("supports_compaction", False):
        if "context-management-2025-06-27" not in beta_headers:
            beta_headers.append("context-management-2025-06-27")
        beta_headers.append("compact-2026-01-12")

        compact_edit: dict[str, Any] = {
            "type": "compact_20260112",
            "trigger": {
                "type": "input_tokens",
                "value": __user__["valves"].COMPACTION_TRIGGER_TOKENS,
            },
        }
        if __user__["valves"].COMPACTION_INSTRUCTIONS.strip():
            compact_edit["instructions"] = __user__["valves"].COMPACTION_INSTRUCTIONS.strip()

        if "context_management" not in payload:
            payload["context_management"] = {"edits": []}
        payload["context_management"]["edits"].append(compact_edit)

    # Add effort beta header and output_config if effort is configured
    if model_info["supports_effort"] and effort_config:
        beta_headers.append("effort-2025-11-24")
        payload["output_config"] = effort_config

    # Add Fast Mode beta header if enabled and model supports it
    if pipe.valves.ENABLE_FAST_MODE and model_info.get("supports_fast_mode", False):
        beta_headers.append("fast-mode-2026-02-01")

    # Server-side fallback on safety refusals. Claude API only — not supported on
    # Bedrock / Vertex / Foundry or the Batches API, so it stays off whenever the
    # base URL is not Anthropic's.
    fallback_mode = getattr(pipe.valves, "REFUSAL_FALLBACK", "off")
    if fallback_mode != "off" and pipe.valves.ANTHROPIC_BASE_URL.rstrip("/") == pipe._DEFAULT_API_BASE:
        beta_headers.append("server-side-fallback-2026-07-01")
        # `fallbacks` is not a named SDK parameter yet, so pass it through
        # extra_body (same route as `diagnostics`) instead of as a kwarg the
        # installed SDK version may reject.
        _fallbacks = (
            "default" if fallback_mode == "default" else [{"model": fallback_mode}]
        )
        payload.setdefault("extra_body", {})["fallbacks"] = _fallbacks
        logger.debug(f"Server-side refusal fallback: {_fallbacks}")

    # Cache diagnostics beta — only meaningful with prompt caching active. Always
    # send `diagnostics.previous_message_id` (null on first turn) so the API can
    # report `cache_miss_reason` whenever the cache prefix diverged from last turn.
    if (
        getattr(pipe.valves, "ENABLE_CACHE_DIAGNOSTICS", False)
        and pipe.valves.CACHE_CONTROL != "cache disabled"
    ):
        beta_headers.append("cache-diagnosis-2026-04-07")
        chat_id_for_diag = __metadata__.get("chat_id") if __metadata__ else None
        # Prefer the response id persisted as a `cachediag` marker on the prior
        # assistant message (survives pipe restarts / multiple workers). Fall
        # back to the in-memory state dict only if no marker is present.
        previous_message_id = None
        for _entry in previous_marker_metadata:
            _parts = _entry.split(":", 2)
            if len(_parts) >= 3 and _parts[1] == "cachediag":
                previous_message_id = unquote(_parts[2])
        if previous_message_id is None and chat_id_for_diag:
            previous_message_id = pipe._cache_diagnostics_state.get(chat_id_for_diag)
        # `diagnostics` is not a native SDK parameter — pass it via extra_body
        # so the SDK forwards it as-is in the JSON request body.
        payload.setdefault("extra_body", {})["diagnostics"] = {
            "previous_message_id": previous_message_id
        }
        logger.debug(
            f"[CACHE-DIAG] previous_message_id={previous_message_id} chat_id={chat_id_for_diag}"
        )

    # A compaction block replayed from history requires the compaction beta even
    # when API-side compaction isn't enabled for this turn — otherwise Anthropic
    # 400s with "Input tag 'compaction' does not match any of the expected tags".
    # This keeps previously-compacted chats replayable regardless of valve state.
    def _messages_have_compaction_block(msgs) -> bool:
        """Return True if any message content contains a 'compaction' type block."""
        for _m in msgs or []:
            _content = _m.get("content") if isinstance(_m, dict) else None
            if isinstance(_content, list):
                for _block in _content:
                    if isinstance(_block, dict) and _block.get("type") == "compaction":
                        return True
        return False

    if _messages_have_compaction_block(processed_messages):
        if "context-management-2025-06-27" not in beta_headers:
            beta_headers.append("context-management-2025-06-27")
        if "compact-2026-01-12" not in beta_headers:
            beta_headers.append("compact-2026-01-12")

    if beta_headers and len(beta_headers) > 0:
        headers["anthropic-beta"] = ",".join(beta_headers)
        # Add betas list to payload for beta.messages.stream
        payload["betas"] = beta_headers

        ## Tool Choice Handling
        if __metadata__.get("web_search_enforced"):
            # Check if web_search is actually in the tools list
            has_web_search = any(t.get("name") == "web_search" for t in tools_list)
            if has_web_search:
                if "thinking" not in payload:
                    # No thinking active - enforce web_search
                    payload["tool_choice"] = {"type": "tool", "name": "web_search"}
                    logger.debug("Enforcing web_search via tool_choice")
                else:
                    # Thinking is active - cannot enforce web_search, but it's still available
                    payload["tool_choice"] = {"type": "auto"}
                    logger.debug(
                        "Thinking active - web_search added but not enforced (tool_choice=auto)"
                    )
            else:
                # No enforcement - use auto tool choice
                payload["tool_choice"] = {"type": "auto"}

    # API tool_choice passthrough (outside beta_headers block)
    # If no tool_choice was set by web_search enforcement, pass through from body
    if "tool_choice" not in payload and body.get("tool_choice"):
        api_tc = body["tool_choice"]
        if isinstance(api_tc, dict) and "function" in api_tc:
            # OpenAI format: {"type": "function", "function": {"name": "X"}}
            payload["tool_choice"] = {
                "type": "tool",
                "name": api_tc["function"]["name"],
            }
        elif isinstance(api_tc, str):
            # OpenAI string format: "auto", "none", "required"
            mapping = {"auto": "auto", "none": "none", "required": "any"}
            payload["tool_choice"] = {"type": mapping.get(api_tc, api_tc)}
        else:
            # Already in Anthropic format or other dict format
            payload["tool_choice"] = api_tc
        logger.debug(f"API tool_choice passthrough: {payload['tool_choice']}")

    # Filter stale tool_search references for tools toggled OFF.
    # History `tool_search_tool_result` blocks list `tool_references` for tools
    # the search surfaced on an earlier turn.  If such a user tool is no longer
    # enabled it is absent from `tools`, and replaying the reference makes the
    # API reject the request with 400 "Tool reference 'X' not found in available
    # tools".  Drop the missing references entirely rather than re-advertising a
    # disabled tool: a stub definition would let the model call a non-functional
    # tool again.  The cache is already invalidated by the tool-set change
    # (`tools_changed`), so editing history here costs nothing extra.
    _reserved_server_tool_names = {
        "web_search",
        "web_fetch",
        "code_execution",
        "bash",
        "str_replace_based_edit_tool",
        "str_replace_editor",
        "computer",
        "tool_search_tool_regex",
        "tool_search_tool_bm25",
        "advisor",
    }
    _present_tool_names = {
        t.get("name")
        for t in tools_list
        if isinstance(t, dict) and t.get("name")
    }
    for _msg in processed_messages:
        _content = _msg.get("content") if isinstance(_msg, dict) else None
        if not isinstance(_content, list):
            continue
        for _block in _content:
            if not isinstance(_block, dict) or _block.get("type") != "tool_search_tool_result":
                continue
            _inner = _block.get("content")
            if not isinstance(_inner, dict):
                continue
            _refs = _inner.get("tool_references")
            if not isinstance(_refs, list):
                continue
            _kept = [
                _ref
                for _ref in _refs
                if isinstance(_ref, dict)
                and (
                    _ref.get("tool_name") in _present_tool_names
                    or _ref.get("tool_name") in _reserved_server_tool_names
                )
            ]
            if len(_kept) != len(_refs):
                _dropped = [
                    _ref.get("tool_name")
                    for _ref in _refs
                    if _ref not in _kept
                ]
                _inner["tool_references"] = _kept
                logger.info(
                    f"[TOOL-FILTER] Dropped stale tool_search references "
                    f"(tool no longer enabled): {_dropped}"
                )

    payload["tools"] = tools_list

    # Tool search nudge: deferred tools are stripped from the prompt prefix, so the
    # model can't see them and tends to claim it lacks the capability. Tell it to
    # search first. Static text → does not churn the cache across turns.
    if any(isinstance(_t, dict) and _t.get("defer_loading") for _t in tools_list):
        _tool_search_nudge = {
            "type": "text",
            "text": (
                "Some available tools are not listed directly in this request; they are "
                "loaded on demand via the tool search tool (tool_search_tool_*). Before "
                "telling the user you cannot do something or that you lack access to a tool, "
                "call the tool search tool to find a relevant tool, then use whatever it returns."
            ),
        }
        if isinstance(system_messages, list):
            system_messages = system_messages + [_tool_search_nudge]
        elif system_messages:
            system_messages = [{"type": "text", "text": str(system_messages)}, _tool_search_nudge]
        else:
            system_messages = [_tool_search_nudge]

    # Processing Messages and Caching
    if system_messages and len(system_messages) > 0:
        payload["system"] = system_messages

    payload["messages"] = processed_messages

    # Last step before the payload leaves: give every content block one
    # deterministic key order. Live blocks come from SDK objects and replayed
    # blocks from literal dicts, so the same content otherwise serializes to
    # different bytes -- and the prefix cache compares bytes. Done here rather
    # than at each construction site so it cannot be forgotten, and after
    # cache_control placement so those markers are ordered too.
    payload["messages"] = pipe._canonicalize_block(payload["messages"])
    if payload.get("system") is not None:
        payload["system"] = pipe._canonicalize_block(payload["system"])

    return payload, headers, new_marker_metadata, api_tool_names
