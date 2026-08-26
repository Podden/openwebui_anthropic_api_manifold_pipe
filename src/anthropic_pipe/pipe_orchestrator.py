"""Compiled main Pipe.pipe orchestrator extracted from pipe_template.py."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class PipeOrchestratorMethods:
    async def pipe(
        self,
        body: dict[str, Any],
        __user__: Dict[str, Any],
        __event_emitter__: Callable[[Dict[str, Any]], Awaitable[None]],
        __metadata__: dict[str, Any] = {},
        __tools__: Optional[Dict[str, Dict[str, Any]]] = None,
        __files__: Optional[Dict[str, Any]] = None,
        __task__: Optional[dict[str, Any]] = None,
        __task_body__: Optional[dict[str, Any]] = None,
        __request__: Optional[Any] = None,
        __event_call__: Optional[Callable[[Dict[str, Any]], Awaitable[Any]]] = None,
    ):
        """
        OpenWebUI Claude streaming pipe with integrated streaming logic.
        """
        # =========================================================================
        # PHASE 1: RESPONSE ACCUMULATION STATE
        # =========================================================================
        request_ctx = PipeRequestContext(pipe=self, event_emitter=__event_emitter__)
        final_message = request_ctx.final_message
        emit_event_local = request_ctx.emit_event
        emit_message_delta = request_ctx.emit_delta
        emit_message_replace = request_ctx.emit_replace
        update_content_block = request_ctx.update_content_block
        final_text = request_ctx.text
        status = StatusEmitter(emit_event_local)
        request_ctx.status = status
        request_ctx.metadata = __metadata__ or {}
        request_ctx.user = __user__ or {}
        request_ctx.tools = __tools__
        # Content-block dispatch. Handlers own one block family each and read
        # everything off request_ctx; families not migrated yet return False and
        # fall through to the inline chain below.
        handler_registry = HandlerRegistry(default_handlers())
        # Bound here, not only inside the try below: the finalisation phase reads
        # it from outside the try block.
        is_internal = False

        # Run marker. Every later lifecycle line carries the same `run=`, so a log
        # window can be split into invocations without guessing from timestamps —
        # the thing that made the doubled cache-diagnostics block hard to pin down.
        run_id = request_ctx.run_id
        logger.info(
            "[RUN %s] pipe() start chat_id=%s message_id=%s session_id=%s",
            run_id,
            (__metadata__ or {}).get("chat_id"),
            (__metadata__ or {}).get("message_id"),
            (__metadata__ or {}).get("session_id"),
        )


        try:
            # =========================================================================
            # PHASE 2: VALIDATION & SETUP
            # =========================================================================

            # Debug: Log all Valves and UserValves settings
            if logger.isEnabledFor(logging.DEBUG):
                # Environment first: most bug reports come down to an OpenWebUI
                # version whose behaviour differs from the one under test.
                logger.debug(f"OpenWebUI version: {OPENWEBUI_VERSION}")
                logger.debug(f"Valves: {self.valves.model_dump()}")
                user_valves = __user__.get("valves")
                if user_valves and hasattr(user_valves, "model_dump"):
                    logger.debug(f"UserValves: {user_valves.model_dump()}")
                elif user_valves:
                    logger.debug(f"UserValves: {user_valves}")

            # Get API key - check UserValves first, then fall back to admin valve
            user_valves = __user__.get("valves")
            user_api_key = getattr(user_valves, "ANTHROPIC_API_KEY", "") if user_valves else ""
            api_key = user_api_key.strip() if user_api_key and user_api_key.strip() else self.valves.ANTHROPIC_API_KEY
            # Compare against the plaintext: an encrypted valve never equals the
            # placeholder, so an unconfigured pipe would otherwise sail past this
            # check and fail later with a 401.
            resolved_api_key = decrypt_valve_secret(api_key).strip()
            if not resolved_api_key or resolved_api_key == "Your API Key Here":
                error_msg = "Error: No API key configured. Set it in admin Valves or your personal UserValves."
                logger.error(f"{error_msg}")
                await status.complete("No API Key Set!")
                return error_msg

            # Publish this user's block visibility preference for the formatters,
            # which are too deep in the call chain to be handed a request context.
            HIDDEN_BLOCKS.set(
                self._parse_hidden_blocks(getattr(user_valves, "HIDE_BLOCKS", None))
            )

            # Human-in-the-loop tool approval (OpenWebUI 0.11.1+). The mode is a
            # per-conversation chat param; automations, channel replies and
            # temporary chats never carry "ask". Without an __event_call__ there
            # is no channel to ask on, so the gate stays open — matching
            # OpenWebUI, which also only prompts in a saved conversation.
            TOOL_APPROVAL.set(
                (
                    (__metadata__ or {}).get("params", {}).get("tool_approval_mode", "full"),
                    __event_call__,
                )
            )

            # OpenWebUI marks sub-agent runs with request.state.internal; it is
            # the same flag OpenWebUI itself uses to skip chat persistence and to
            # refuse nested delegation. Such a run has no human reader -- its
            # text is handed straight to the parent agent -- so strip the whole
            # presentation layer and emit plain prose.
            is_internal = bool(
                __request__ is not None
                and getattr(getattr(__request__, "state", None), "internal", False) is True
            )
            SLIM_OUTPUT.set(is_internal)
            if is_internal:
                logger.debug("Internal (sub-agent) run: emitting slim prose output")

            # STEP 1: Detect if task model (generate title, tags, follow-ups etc.), handle it separately
            if __task__:
                return await self._run_task_model_request(body, task=__task__)

            # STEP 2: Await tools if needed
            if inspect.isawaitable(__tools__):
                __tools__ = await __tools__

            # STEP 2.5: Get builtin tools from OpenWebUI (for tools from body.tools)
            builtin_tools = {}
            if BUILTIN_TOOLS_AVAILABLE and __request__:
                try:
                    # Determine if memory feature is enabled
                    memory_enabled = (
                        __user__.get("settings", {}).get("ui", {}).get("memory", False)
                        if __user__
                        else False
                    )
                    # Resolve skill IDs for view_skill builtin tool
                    skill_ids = []
                    try:
                        openwebui_model_id = __metadata__.get("model_id") or body.get("model", "")
                        if openwebui_model_id and MODELS_AVAILABLE:
                            owui_model = await Models.get_model_by_id(openwebui_model_id)
                            if owui_model:
                                # ModelModel has .meta (ModelMeta pydantic model), not .info
                                meta = owui_model.meta
                                if meta:
                                    meta_dict = meta.model_dump() if hasattr(meta, "model_dump") else (meta if isinstance(meta, dict) else {})
                                    model_skill_ids = set(meta_dict.get("skillIds", []))
                                else:
                                    model_skill_ids = set()
                                logger.debug(f"Model {openwebui_model_id} skill IDs: {model_skill_ids}")
                                if model_skill_ids:
                                    from open_webui.models.skills import Skills as SkillsModel

                                    user_id = __user__.get("id", "") if __user__ else ""
                                    accessible_skills = await SkillsModel.get_skills_by_user_id(user_id, "read")
                                    accessible = {s.id for s in accessible_skills}
                                    logger.debug(f"Accessible skills for user: {accessible}")
                                    skill_ids = []
                                    for sid in model_skill_ids:
                                        if sid not in accessible:
                                            continue
                                        s = await SkillsModel.get_skill_by_id(sid)
                                        if s and s.is_active:
                                            skill_ids.append(sid)
                                    logger.debug(f"Resolved skill_ids: {skill_ids}")
                    except Exception as e:
                        logger.debug(f"Could not resolve skill IDs: {e}")

                    builtin_tools = get_builtin_tools(
                        __request__,
                        {
                            "__user__": __user__,
                            "__event_emitter__": __event_emitter__,
                            "__chat_id__": (
                                __metadata__.get("chat_id") if __metadata__ else None
                            ),
                            "__message_id__": (
                                __metadata__.get("message_id") if __metadata__ else None
                            ),
                            "__skill_ids__": skill_ids,
                        },
                        features={"memory": memory_enabled},
                        model={},
                    )
                    if inspect.isawaitable(builtin_tools):
                        builtin_tools = await builtin_tools
                    logger.debug(
                        f"Loaded {len(builtin_tools)} builtin tools: {list(builtin_tools.keys())}"
                    )
                except Exception as e:
                    logger.warning(f"Could not load builtin tools: {e}")
                    builtin_tools = {}

            # Merge external tools from metadata (Open Terminal, external tool servers)
            # These have callables for execution but are not in __tools__ or builtin_tools
            metadata_tools = __metadata__.get("tools", {}) if __metadata__ else {}
            if metadata_tools:
                for t_name, t_data in metadata_tools.items():
                    if t_name not in builtin_tools and (not __tools__ or t_name not in __tools__):
                        if isinstance(t_data, dict) and t_data.get("callable"):
                            builtin_tools[t_name] = t_data
                if builtin_tools:
                    logger.debug(
                        f"After metadata merge, builtin_tools: {list(builtin_tools.keys())}"
                    )

            # STEP 3: Auto-enable native function calling if tools are present
            # This prevents OpenWebUI's function_calling task system from being triggered
            if __tools__ and MODELS_AVAILABLE:
                try:
                    # Get the OpenWebUI model ID from metadata
                    openwebui_model_id = (
                        __metadata__.get("model_id") if __metadata__ else None
                    )
                    if not openwebui_model_id and body and "model" in body:
                        openwebui_model_id = body["model"]

                    if openwebui_model_id:
                        model = await Models.get_model_by_id(openwebui_model_id)
                        if model:
                            params = dict(model.params or {})
                            if params.get("function_calling") != "native":
                                logger.debug(
                                    f"Auto-enabling native function calling for model: {openwebui_model_id}"
                                )

                                # Notify user
                                await emit_event_local(
                                    {
                                        "type": "notification",
                                        "data": {
                                            "type": "info",
                                            "content": f"Enabling native function calling for model: {openwebui_model_id}. Please re-run your query.",
                                        },
                                    }
                                )

                                params["function_calling"] = "native"
                                form_data = model.model_dump()
                                form_data["params"] = params
                                await Models.update_model_by_id(
                                    openwebui_model_id, ModelForm(**form_data)
                                )
                except Exception as e:
                    logger.warning(
                        f"Could not auto-enable native function calling: {e}"
                    )

            # Tell middleware to skip reasoning tag detection — the pipe renders
            # its own <details type="reasoning"> blocks which must not be re-parsed.
            if __metadata__ is not None:
                __metadata__.setdefault("params", {})["reasoning_tags"] = False

            payload, headers, new_marker_metadata, api_tool_names = await self._create_payload(
                body, __metadata__, __user__, __tools__, __event_emitter__, __files__
            )

            # =========================================================================
            # PHASE 3: STREAMING STATE INITIALIZATION
            # =========================================================================
            api_key = headers.get("x-api-key", self.valves.ANTHROPIC_API_KEY)
            # Use UserValves API key if available (override header-level key too)
            if user_api_key and user_api_key.strip():
                api_key = user_api_key.strip()
                logger.debug("Using user-provided API key from UserValves")
            request_timeout = self.valves.REQUEST_TIMEOUT
            # Tool resolution and auth are settled — hand them to the handlers.
            request_ctx.api_key = api_key
            request_ctx.builtin_tools = builtin_tools
            request_ctx.api_tool_names = api_tool_names
            client = self._build_anthropic_client(api_key, default_headers=headers, timeout=request_timeout)
            payload_for_stream = {k: v for k, v in payload.items() if k != "stream"}
            include_usage = (
                __user__["valves"].SHOW_TOKEN_COUNT != "Off"
                or body.get("stream_options", {}).get("include_usage", False)
            )
            total_usage: Optional[dict[str, int]] = None
            if include_usage:
                total_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "_ctx_input": 0, "_ctx_output": 0}
                if self.valves.CACHE_CONTROL != "cache disabled":
                    total_usage["cache_creation_input_tokens"] = 0
                    total_usage["cache_read_input_tokens"] = 0
            # Per-turn capture of Anthropic cache diagnostics (beta cache-diagnosis-2026-04-07).
            # First entry that has a non-null cache_miss_reason wins for display.
            cache_diagnostics_records: list[dict[str, Any]] = []
            cache_diagnostics_chat_id: Optional[str] = (
                __metadata__.get("chat_id") if __metadata__ else None
            )

            # Stream configuration from valves
            token_buffer_size = getattr(self.valves, "TOKEN_BUFFER_SIZE", 1)
            max_function_calls = self.valves.MAX_TOOL_CALLS

            # Thinking state lives on request_ctx.state.thinking, owned by
            # ThinkingBlockHandler. Compaction likewise on .state.compaction.

            # SDK-accumulated message: captured after each stream completes
            # Replaces manual api_assistant_blocks/thinking_blocks accumulation
            sdk_final_message = None

            # Tool execution state is owned by ClientToolUseBlockHandler and lives on
            # request_ctx.state.tool_use. The alias keeps the still-inline tool-result
            # processing below on the same object the handler mutates.
            # Note: tool_use_blocks and current_tool_caller removed - SDK preserves these in accumulated message
            tool_use_state = request_ctx.state.tool_use
            has_pending_tool_calls = False
            tool_calls = []

            # Server-tool state (web_search, code_execution, text_editor) is owned by
            # ServerToolUseBlockHandler and the code-execution result handlers, and
            # lives on request_ctx.state.server_tool. The alias keeps the still-inline
            # sites below (programmatic tool-call capture, final flush) on the same
            # object those handlers mutate.
            server_tool_state = request_ctx.state.server_tool

            # Dynamic filtering detection:
            # If code_execution was NOT explicitly added to tools (no code_execution_20250825 or
            # code_execution_20260120 in payload), then any code_execution in the stream is from
            # dynamic filtering auto-injection → suppress UI.
            # If code_execution WAS explicitly added, code_exec blocks could be real code → show UI.
            payload_tools = payload.get("tools", [])
            has_explicit_code_execution = any(
                t.get("name") == "code_execution" for t in payload_tools
            )
            server_tool_state.has_explicit_code_execution = has_explicit_code_execution

            # Text/citation state is owned by TextBlockHandler and lives on
            # request_ctx.state.text. The alias keeps the still-inline call sites below
            # (metadata markers, tool-result flush, stop-reason messages) on the very
            # same object the handler mutates.
            text_state = request_ctx.state.text

            # Loop control state
            conversation_ended = False
            retry_attempts = 0
            current_function_calls = 0

            await status.waiting()

            # =========================================================================
            # PHASE 4: MAIN STREAMING LOOP
            # Continues until conversation ends or max tool calls reached
            # =========================================================================
            tool_loop_iteration = 0
            while (
                current_function_calls < max_function_calls
                and not conversation_ended
                and retry_attempts <= self.valves.MAX_RETRIES
            ):
                tool_loop_iteration += 1
                # Reset per-iteration state
                stream_output_tokens = 0

                try:
                    stream_event_counts = {}  # Track event types for diagnostics#
                    # Apply cache breakpoints right before sending to API
                    self._apply_cache_control(
                        payload_for_stream,
                        is_tool_loop=(tool_loop_iteration > 1),
                        iteration=tool_loop_iteration,
                    )
                    # Log message-hash diff vs previous request on same chat_id
                    # to pinpoint byte-drift that breaks the prompt cache prefix.
                    _diff_chat_id = __metadata__.get("chat_id") if __metadata__ else None
                    self._log_message_hash_diff(_diff_chat_id, payload_for_stream)
                    # Dump the full (stripped) outgoing payload so we can audit
                    # cache_control placement, tool list, message order and byte
                    # drift across turns without logging megabytes of base64.
                    try:
                        logger.debug(
                            "[PAYLOAD run=%s] iter=%d retry=%d %s",
                            run_id,
                            tool_loop_iteration,
                            retry_attempts,
                            json.dumps(
                                self._strip_payload(payload_for_stream),
                                ensure_ascii=False,
                                separators=(",", ":"),
                                default=str,
                            ),
                        )
                    except Exception as _pl_err:
                        logger.debug(f"[PAYLOAD] strip/log failed: {_pl_err}")
                    async with client.beta.messages.stream(
                        **payload_for_stream
                    ) as stream:
                        async for event in stream:
                            event_type = getattr(event, "type", None)
                            stream_event_counts[event_type] = stream_event_counts.get(event_type, 0) + 1
                            logger.debug(f"Received stream event: {event_type} | counts: {stream_event_counts} | payload: {event}")
                            if event_type == "message_start":
                                # Note: Container ID is not in message_start for streaming;
                                # it arrives in message_delta.
                                stream_output_tokens = self._handle_message_start_usage(
                                    event,
                                    include_usage=include_usage,
                                    total_usage=total_usage if include_usage else None,
                                    stream_output_tokens=stream_output_tokens,
                                )
                                if getattr(self.valves, "ENABLE_CACHE_DIAGNOSTICS", False):
                                    msg = getattr(event, "message", None)
                                    msg_id = getattr(msg, "id", None) if msg else None
                                    # Capture HTTP request-id from response headers for
                                    # matching against the Anthropic Console / dashboard.
                                    http_request_id = None
                                    try:
                                        http_request_id = stream.response.headers.get("request-id")
                                    except Exception:
                                        pass
                                    # `diagnostics` is attached to the response Message when
                                    # the cache-diagnosis beta is active. SDK exposes it as
                                    # an attribute; fall back to dict-style for resilience.
                                    diag_obj = getattr(msg, "diagnostics", None) if msg else None
                                    if diag_obj is None and isinstance(msg, dict):
                                        diag_obj = msg.get("diagnostics")
                                    diag_dump = self._dump_sdk_obj(diag_obj) if diag_obj else None
                                    # Capture per-call usage (input/output/cache tokens).
                                    usage_obj = getattr(msg, "usage", None) if msg else None
                                    usage_dump = self._dump_sdk_obj(usage_obj) if usage_obj else None
                                    if msg_id or diag_dump or http_request_id or usage_dump:
                                        cache_diagnostics_records.append(
                                            {"message_id": msg_id, "request_id": http_request_id, "usage": usage_dump, "diagnostics": diag_dump}
                                        )
                                        logger.info(
                                            f"[CACHE-DIAG run={run_id}] record #{len(cache_diagnostics_records)} "
                                            f"iter={tool_loop_iteration} retry={retry_attempts} "
                                            f"chat_id={cache_diagnostics_chat_id} "
                                            f"message_id={msg_id} request_id={http_request_id} "
                                            f"usage={usage_dump} diagnostics={diag_dump}"
                                        )

                            # ---------------------------------------------------------
                            # EVENT: content_block_start
                            # Routed to the handler owning this block type; see
                            # stream/handlers.py for the block-type -> handler map.
                            # ---------------------------------------------------------
                            elif event_type == "content_block_start":
                                content_block = getattr(event, "content_block", None)
                                content_type = getattr(content_block, "type", None)
                                if not content_block:
                                    continue
                                # No status is emitted here: each handler announces
                                # its own phase on start. Emitting a generic one for
                                # every block put a meaningless "Responding..." into
                                # the (persistent, user-visible) status history after
                                # every single tool result.
                                await handler_registry.handle_start(event, request_ctx)

                            # ---------------------------------------------------------
                            # EVENT: content_block_delta
                            # Routed by the block type recorded at content_block_start.
                            # ---------------------------------------------------------
                            elif event_type == "content_block_delta":
                                await handler_registry.handle_delta(event, request_ctx)

                            # ---------------------------------------------------------
                            # EVENT: content_block_stop
                            # Routed by the block's own type, falling back to the type
                            # recorded at start for raw SDK events that omit it.
                            # ---------------------------------------------------------
                            elif event_type == "content_block_stop":
                                await handler_registry.handle_stop(event, request_ctx)

                            # ---------------------------------------------------------
                            # EVENT: message_delta
                            # Updates output token counts, handles stop_reason
                            # Flushes buffered chunks
                            # ---------------------------------------------------------
                            elif event_type == "message_delta":
                                if include_usage:
                                    usage = getattr(event, "usage", None)
                                    if usage:
                                        current_output_tokens = getattr(
                                            usage, "output_tokens", 0
                                        )
                                        diff = (
                                            current_output_tokens - stream_output_tokens
                                        )
                                        total_usage["output_tokens"] += diff
                                        stream_output_tokens = current_output_tokens
                                        # Cost total, and this call's own output for
                                        # the context gauge — see
                                        # _handle_message_start_usage for why the two
                                        # must not be mixed.
                                        total_usage["_ctx_output"] = current_output_tokens
                                        # OpenWebUI contract: input + output only,
                                        # cache traffic stays in its own fields.
                                        total_usage["total_tokens"] = (
                                            total_usage.get("input_tokens", 0)
                                            + total_usage.get("output_tokens", 0)
                                        )
                                delta = getattr(event, "delta", None)
                                code_execution_container_id = getattr(delta, "container", None)
                                if code_execution_container_id:
                                    delta_container_id = getattr(code_execution_container_id, "id", None) if hasattr(code_execution_container_id, "id") else (code_execution_container_id.get("id") if isinstance(code_execution_container_id, dict) else str(code_execution_container_id))
                                    if delta_container_id:
                                        current_container_id = payload_for_stream.get("container")
                                        if current_container_id != delta_container_id:
                                            text_state.chunk += self._create_metadata_marker(
                                                "container_id",
                                                delta_container_id,
                                                messagenum=len(
                                                    payload_for_stream.get("messages", [])
                                                ),
                                            )
                                            logger.debug(
                                                f"📦 Container ID from message_delta: {delta_container_id}"
                                            )
                                        payload_for_stream["container"] = delta_container_id

                                stop_reason = getattr(delta, "stop_reason", None)
                                if stop_reason:
                                    logger.debug(f"📍 stop_reason received: {stop_reason}")
                                if stop_reason == "tool_use":
                                    # Emit any remaining text chunk before tool results
                                    if text_state.chunk:
                                        if not text_state.chunk.endswith("\n"):
                                            text_state.chunk += "\n"
                                        await emit_message_delta(text_state.chunk)
                                        text_state.chunk = ""
                                        text_state.chunk_count = 0

                                    # API tool passthrough — skip tool loop, return directly
                                    if tool_use_state.api_passthrough and not tool_use_state.running_tasks:
                                        logger.info(
                                            "🔄 API tool passthrough complete — skipping tool loop"
                                        )
                                        conversation_ended = True
                                        break

                                    # Wait for all running tool tasks to complete
                                    if tool_use_state.running_tasks:
                                        logger.debug(
                                            f"⏳ Waiting for %d tool tasks to complete...",
                                            len(tool_use_state.running_tasks),
                                        )

                                        try:
                                            completed_results = 0

                                            # Build tool_result messages and emit to UI as each task completes.
                                            for completed_task in asyncio.as_completed(
                                                tool_use_state.running_tasks
                                            ):
                                                (
                                                    tool_call_data,
                                                    tool_result,
                                                    task_error,
                                                ) = await completed_task
                                                completed_results += 1
                                                tool_use_id = tool_call_data.get(
                                                    "id", ""
                                                )
                                                tool_name = tool_call_data.get(
                                                    "name", ""
                                                )
                                                tool_input = tool_call_data.get(
                                                    "input", {}
                                                )

                                                if task_error is not None:
                                                    tool_result = f"Error executing tool '{tool_name}': {task_error}"

                                                # Process tool result through OpenWebUI's handler
                                                # for Rich UI (HTMLResponse, embeds, files)
                                                tool_result_embeds = []
                                                tool_result_files = []
                                                if PROCESS_TOOL_RESULT_AVAILABLE and __request__:
                                                    try:
                                                        tool_result, tool_result_files, tool_result_embeds = (
                                                            await process_tool_result(
                                                                __request__,
                                                                tool_name,
                                                                tool_result,
                                                                "pipe",
                                                                metadata=__metadata__,
                                                                user=__user__,
                                                            )
                                                        )
                                                    except Exception as e:
                                                        logger.warning(f"process_tool_result failed for '{tool_name}': {e}")

                                                # Emit files event if tool produced files
                                                if tool_result_files and __event_emitter__:
                                                    await __event_emitter__(
                                                        {
                                                            "type": "files",
                                                            "data": {"files": tool_result_files},
                                                        }
                                                    )

                                                # OpenWebUI renders Tool Rich UI inline only when
                                                # embeds are attached to the matching tool_calls
                                                # details block. Message-level `embeds` events render
                                                # above the response text, so we deliberately avoid
                                                # emitting them here and persist the embed with the
                                                # completed tool block below.

                                                # Determine if error
                                                is_error = isinstance(
                                                    tool_result, str
                                                ) and (
                                                    tool_result.startswith("Error:")
                                                    or tool_result.startswith("Error executing tool")
                                                )

                                                # Build result block for API
                                                # Ensure result is valid JSON string (not Python repr with single quotes)
                                                if isinstance(tool_result, str):
                                                    result_str = tool_result
                                                else:
                                                    try:
                                                        result_str = json.dumps(tool_result, ensure_ascii=False)
                                                    except (TypeError, ValueError):
                                                        result_str = str(tool_result)
                                                # Convert any embedded data:image;base64 URI (e.g. a
                                                # read_file tool returning a PNG) into a real Anthropic
                                                # image block instead of raw base64 TEXT, and apply the
                                                # TOOL_RESULT_MAX_TOKENS backstop to non-image output.
                                                result_block = {
                                                    "type": "tool_result",
                                                    "tool_use_id": tool_use_id,
                                                    "content": self._convert_tool_result_content(result_str, __user__),
                                                }
                                                if is_error:
                                                    result_block["is_error"] = True
                                                tool_calls.append(result_block)

                                                if server_tool_state.in_code_execution:
                                                    # Accumulate for unified code execution display
                                                    server_tool_state.tool_calls_info.append({
                                                        "name": tool_name,
                                                        "input": tool_input,
                                                        "result": result_str,
                                                        "is_error": is_error,
                                                    })
                                                else:
                                                    # Replace the in-progress block with completed version.
                                                    # Tool Rich UI HTML belongs to the tool_calls block:
                                                    # OpenWebUI renders message.embeds above the text, but
                                                    # tool-call embeds inline at the tool call indicator.
                                                    completed = self._format_tool_result_block(
                                                        tool_use_id, tool_name, tool_input,
                                                        str(tool_result), is_error=is_error, done=True,
                                                        files=tool_result_files,
                                                        embeds=tool_result_embeds,
                                                    )
                                                    old_block = tool_use_state.progress_blocks.pop(tool_use_id, None)
                                                    if old_block:
                                                        text = final_text()
                                                        text = text.replace(old_block, completed, 1)
                                                        final_message.clear()
                                                        final_message.append(text)
                                                        await request_ctx.emit_event({"type": "replace", "data": {"content": text}})
                                                    else:
                                                        # Fallback: append if placeholder not found
                                                        text = self._append_block_to_text(final_text(), completed)
                                                        final_message.clear()
                                                        final_message.append(text)
                                                        await emit_message_replace(text)

                                            logger.debug(
                                                f"✅ All %d tool tasks completed",
                                                completed_results,
                                            )
                                        except Exception as ex:
                                            logger.error(
                                                f"❌ Tool execution failed: %s", ex
                                            )
                                            for task in tool_use_state.running_tasks:
                                                if not task.done():
                                                    task.cancel()

                                            # Create error results and update in-progress blocks
                                            for tool_use_id, old_block in list(tool_use_state.progress_blocks.items()):
                                                error_result = f"Error executing tool: {str(ex)}"
                                                tool_calls.append(
                                                    {
                                                        "type": "tool_result",
                                                        "tool_use_id": tool_use_id,
                                                        "content": error_result,
                                                        "is_error": True,
                                                    }
                                                )
                                                completed = self._format_tool_result_block(
                                                    tool_use_id,
                                                    "unknown",
                                                    {},
                                                    error_result,
                                                    is_error=True,
                                                    done=True,
                                                )
                                                if old_block:
                                                    text = final_text()
                                                    text = text.replace(old_block, completed, 1)
                                                    final_message.clear()
                                                    final_message.append(text)
                                                    await request_ctx.emit_event({"type": "replace", "data": {"content": text}})

                                            tool_use_state.progress_blocks = {}

                                    logger.debug(
                                        f" Tool use detected, collected {len(tool_calls)} tool results:\nTool_Call JSON: {tool_calls}"
                                    )

                                    # Reset for next iteration
                                    tool_use_state.reset_for_iteration()
                                    has_pending_tool_calls = True
                                elif stop_reason == "max_tokens":
                                    text_state.chunk += "Claude has Reached the maximum token limit!"
                                elif stop_reason == "end_turn":
                                    conversation_ended = True
                                elif stop_reason == "pause_turn":
                                    # API paused a long-running turn — auto-continue
                                    has_pending_tool_calls = True  # reuses tool loop mechanism
                                    # tool_calls stays empty → PHASE 5 detects pause_turn
                                    await status.activity("⏳ Long-running turn paused, continuing...")
                                elif stop_reason == "refusal":
                                    # Extract stop_details from the live SDK snapshot.
                                    # Available after the message_delta event updates it.
                                    _snap = getattr(stream, "current_message_snapshot", None)
                                    _stop_details = getattr(_snap, "stop_details", None) if _snap else None
                                    _category = getattr(_stop_details, "category", None) if _stop_details else None
                                    _explanation = getattr(_stop_details, "explanation", None) if _stop_details else None
                                    _REFUSAL_LABELS = {
                                        "cyber": "cybersecurity policy",
                                        "bio": "biological safety policy",
                                        "reasoning_extraction": "reasoning extraction policy",
                                    }
                                    _cat_label = _REFUSAL_LABELS.get(_category, "content policy") if _category else "content policy"
                                    _ref_msg = f"\u26a0\ufe0f Request declined by Claude ({_cat_label})."
                                    if _explanation:
                                        _ref_msg += f"\n\n_{_explanation}_"
                                    logger.info(f"\U0001f6ab Refusal: category={_category!r} explanation={(_explanation or '')[:120]!r}")
                                    text_state.chunk += _ref_msg
                                    conversation_ended = True
                                elif stop_reason == "stop_sequence":
                                    text_state.chunk += "Claude stopped generating based on stop sequence."
                                    conversation_ended = True
                                elif stop_reason == "model_context_window_exceeded":
                                    text_state.chunk += "Claude has reached the maximum context window for this model."
                                    conversation_ended = True
                                elif stop_reason == "compaction":
                                    # Compaction triggered — response contains only the compaction block.
                                    # We need to continue the conversation with the compacted context.
                                    # Reuse tool loop mechanism to auto-continue.
                                    has_pending_tool_calls = True
                                    logger.info("Compaction stop_reason — will auto-continue")

                            # ---------------------------------------------------------
                            # EVENT: message_stop
                            # Stream complete for this turn
                            # ---------------------------------------------------------
                            elif event_type == "message_stop":
                                pass  # No deferred blocks to flush

                            # ---------------------------------------------------------
                            # EVENT: message_error
                            # Handle stream-level errors
                            # ---------------------------------------------------------
                            elif event_type == "message_error":
                                error = getattr(event, "error", None)
                                if error:
                                    # Handle stream errors through handle_errors method
                                    error_details = f"Stream Error: {getattr(error, 'message', str(error))}"
                                    if hasattr(error, "type"):
                                        error_details = f"Stream Error ({error.type}): {getattr(error, 'message', str(error))}"

                                    # Create a mock exception for consistent error handling
                                    stream_error = Exception(error_details)
                                    await self.handle_errors(
                                        stream_error, __event_emitter__
                                    )
                                    return (
                                        final_text()
                                        + f"\n\nAn error occurred: {error_details}"
                                    )

                            if text_state.chunk_count > token_buffer_size:
                                if text_state.chunk:
                                    await emit_message_delta(text_state.chunk)
                                    text_state.chunk = ""
                                    text_state.chunk_count = 0

                        # Capture SDK accumulated message after stream is fully consumed
                        # This replaces manual api_assistant_blocks/thinking_blocks accumulation
                        sdk_final_message = stream.current_message_snapshot
                    # Log stream event diagnostics
                    logger.debug(f"📊 Stream events: {stream_event_counts}")

                    # Cache diagnostics: the `cache_miss_reason` inside `diagnostics`
                    # is pending/null on the `message_start` event during streaming and
                    # is only fully populated on the final accumulated message. Refresh
                    # the record captured at message_start so the rendered details block
                    # and logs show the authoritative miss reason and final usage.
                    if (
                        getattr(self.valves, "ENABLE_CACHE_DIAGNOSTICS", False)
                        and cache_diagnostics_records
                    ):
                        try:
                            _fmsg = sdk_final_message
                            _final_diag = getattr(_fmsg, "diagnostics", None) if _fmsg else None
                            if _final_diag is None and isinstance(_fmsg, dict):
                                _final_diag = _fmsg.get("diagnostics")
                            _final_diag_dump = self._dump_sdk_obj(_final_diag) if _final_diag else None
                            _final_usage = getattr(_fmsg, "usage", None) if _fmsg else None
                            _final_usage_dump = self._dump_sdk_obj(_final_usage) if _final_usage else None
                            _rec = cache_diagnostics_records[-1]
                            if _final_diag_dump:
                                _rec["diagnostics"] = _final_diag_dump
                            if _final_usage_dump:
                                _rec["usage"] = _final_usage_dump
                            logger.info(
                                f"[CACHE-DIAG run={run_id}] final-message refresh "
                                f"chat_id={cache_diagnostics_chat_id} "
                                f"message_id={_rec.get('message_id')} "
                                f"diagnostics={_final_diag_dump}"
                            )
                        except Exception as _e:
                            logger.debug(f"[CACHE-DIAG] final-message refresh failed: {_e}")

                    conversation_ended, has_pending_tool_calls, tool_calls = await self._apply_sdk_stop_reason_fallback(
                        sdk_final_message=sdk_final_message,
                        conversation_ended=conversation_ended,
                        has_pending_tool_calls=has_pending_tool_calls,
                        tool_calls=tool_calls,
                        tool_loop_iteration=tool_loop_iteration,
                        payload_for_stream=payload_for_stream,
                        stream_event_counts=stream_event_counts,
                        request_ctx=request_ctx,
                    )

                    if text_state.chunk:
                        await emit_message_delta(text_state.chunk)
                        text_state.chunk = ""
                        text_state.chunk_count = 0

                    # ---------------------------------------------------------
                    # PHASE 5: TOOL EXECUTION LOOP
                    # After stream ends, if tools were called:
                    # 1. Check max tool call limit
                    # 2. Build assistant message with thinking + text + tool_use blocks
                    # 3. Execute tools and collect results
                    # 4. Add tool_result blocks as user message
                    # 5. Loop back to API for continuation
                    # ---------------------------------------------------------
                    if has_pending_tool_calls and tool_calls:
                        # Log tool call details
                        tool_names = [tc.get("name", tc.get("tool_use_id", "?")) for tc in tool_calls]
                        sdk_block_types = [getattr(b, "type", "?") for b in sdk_final_message.content] if sdk_final_message else []
                        logger.info(
                            f"🔧 Tool loop iter {tool_loop_iteration} complete | "
                            f"{len(tool_calls)} tool results: {tool_names} | "
                            f"SDK blocks: {sdk_block_types}"
                        )
                        # Check if we've reached the max tool call limit
                        # Count actual tool results (not loop iterations) for accurate tracking
                        num_tool_results = sum(1 for tc in tool_calls if tc.get("type") == "tool_result")
                        current_function_calls += num_tool_results
                        if current_function_calls >= max_function_calls:
                            await status.complete(
                                f"⚠️ Maximum tool call limit ({max_function_calls}) reached. Stopping tool execution."
                            )
                            await emit_event_local(
                                {
                                    "type": "notification",
                                    "data": {
                                        "type": "warning",
                                        "content": f"Tool call limit ({max_function_calls}) reached. Increase MAX_TOOL_CALLS in valves if needed.",
                                    },
                                }
                            )
                            await emit_message_delta(
                                f"\n\n⚠️ **Tool call limit reached** ({current_function_calls}/{max_function_calls}). Some tool results may not have been processed. You can increase the limit in the model's valve settings."
                            )
                            break

                        # Tools were already executed during stream (in message_delta)
                        # tool_calls now contains tool_result blocks ready for API
                        # UI output was already emitted during message_delta

                        # Build assistant message from SDK accumulated message
                        # SDK correctly handles: signature accumulation, block ordering,
                        # caller field preservation, input JSON assembly
                        if sdk_final_message:
                            assistant_content = self._convert_sdk_message_to_api_blocks(sdk_final_message)
                            logger.debug(
                                f"Built assistant_content from SDK message: "
                                f"{[b.get('type') for b in assistant_content]}"
                            )
                        else:
                            # Fallback: build from final_message text
                            assistant_content = []
                            final_message_snapshot = final_text()
                            if final_message_snapshot.strip():
                                assistant_content.append({"type": "text", "text": final_message_snapshot})
                            logger.warning("No SDK message available, using text fallback")

                        if assistant_content:
                            # Log detailed block analysis for debugging
                            for i, block in enumerate(assistant_content):
                                btype = block.get("type", "?")
                                if btype == "thinking":
                                    logger.debug(
                                        f"  assistant_content[{i}]: thinking "
                                        f"({len(block.get('thinking', ''))}c, "
                                        f"sig={len(block.get('signature', ''))}c)"
                                    )
                                elif btype == "redacted_thinking":
                                    logger.debug(
                                        f"  assistant_content[{i}]: redacted_thinking "
                                        f"(data={len(block.get('data', ''))}c)"
                                    )
                                elif btype == "tool_use":
                                    logger.debug(
                                        f"  assistant_content[{i}]: tool_use "
                                        f"name={block.get('name')}, id={block.get('id')}"
                                    )
                                elif btype == "text":
                                    logger.debug(
                                        f"  assistant_content[{i}]: text ({len(block.get('text', ''))}c)"
                                    )
                                else:
                                    logger.debug(f"  assistant_content[{i}]: {btype}")

                            payload_for_stream["messages"].append(
                                {"role": "assistant", "content": assistant_content}
                            )

                        # Safety: ensure every tool_use in assistant has a tool_result
                        tool_use_ids_in_assistant = {
                            b.get("id") for b in assistant_content
                            if b.get("type") == "tool_use"
                        }
                        tool_result_ids = {
                            b.get("tool_use_id") for b in tool_calls
                            if b.get("type") == "tool_result"
                        }
                        missing_ids = tool_use_ids_in_assistant - tool_result_ids
                        for missing_id in missing_ids:
                            logger.warning(f"⚠️ Missing tool_result for tool_use {missing_id}, adding error result")
                            tool_calls.append({
                                "type": "tool_result",
                                "tool_use_id": missing_id,
                                "content": "Error: tool execution failed - no result was produced",
                                "is_error": True,
                            })

                        # Add user message with tool results (tool_calls already contains tool_result blocks)
                        user_content = tool_calls.copy()
                        if user_content:
                            # Optimization: Move cache_control to the end for multi-step tool loops
                            # This ensures we cache the tool results for the next iteration
                            # IMPORTANT: Skip when programmatic tool calling is active - Anthropic rejects
                            payload_for_stream["messages"].append(
                                {"role": "user", "content": user_content}
                            )
                            # Debug log tool results with content sizes
                            if logger.isEnabledFor(logging.DEBUG):
                                for b in user_content:
                                    if b.get("type") == "tool_result":
                                        _content = b.get("content", "")
                                        _clen = len(_content) if isinstance(_content, str) else len(json.dumps(_content, default=str))
                                        logger.debug(
                                            f"📤 tool_result: id={b.get('tool_use_id', '?')[:25]} | "
                                            f"is_error={b.get('is_error', False)} | "
                                            f"content_size={_clen}c"
                                        )

                        # Ensure we added at least one message, otherwise break the loop
                        if not assistant_content and not user_content:
                            logger.debug(
                                f"🔧 No valid content to add, ending conversation"
                            )
                            break

                        # Check if we're approaching the limit BEFORE next iteration
                        # (current_function_calls already updated above with actual tool result count)
                        remaining = max_function_calls - current_function_calls
                        if remaining <= 0:
                            # Hard limit reached - this shouldn't happen as we check above, but safety first
                            break
                        elif remaining == 1:
                            # Only 1 call left - warn Claude this is the final chance
                            await status.activity(
                                f"⚠️ Final tool call available ({current_function_calls}/{max_function_calls} used)"
                            )
                            await asyncio.sleep(0.05)

                            # Add system message to warn Claude
                            # Skip when programmatic tool calling is active - only tool_result blocks allowed
                            if not self.valves.ENABLE_PROGRAMMATIC_TOOL_CALLING:
                                payload_for_stream["messages"].append(
                                    {
                                        "role": "user",
                                        "content": [
                                            {
                                                "type": "text",
                                                "text": f"⚠️ SYSTEM WARNING: Tool call limit nearly reached ({current_function_calls}/{max_function_calls} used). You have 1 tool call remaining. After the next tool use, the conversation will be automatically terminated. Please provide a comprehensive text response instead of calling more tools, and suggest the user continue manually if needed.",
                                            }
                                        ],
                                    }
                                )
                        elif remaining <= 5:
                            # Approaching limit - inform both user and Claude
                            await status.activity(
                                f"⚠️ {remaining} tool call(s) remaining ({current_function_calls}/{max_function_calls} used)"
                            )
                            await asyncio.sleep(0.05)

                            # Notify Claude about remaining calls so it can plan accordingly
                            if not self.valves.ENABLE_PROGRAMMATIC_TOOL_CALLING:
                                payload_for_stream["messages"].append(
                                    {
                                        "role": "user",
                                        "content": [
                                            {
                                                "type": "text",
                                                "text": f"[SYSTEM: {remaining} tool call(s) remaining out of {max_function_calls}. Plan your remaining tool calls carefully.]",
                                            }
                                        ],
                                    }
                                )

                        has_pending_tool_calls = False
                        tool_calls = []
                        sdk_final_message = None  # Reset for next iteration
                        current_tool_choice = payload_for_stream.get("tool_choice")
                        if (
                            isinstance(current_tool_choice, dict)
                            and current_tool_choice.get("type") in {"tool", "any"}
                        ):
                            payload_for_stream.pop("tool_choice", None)
                            logger.debug("Cleared forced tool_choice after tool loop iteration")
                        text_state.reset_for_iteration()
                        continue

                    # pause_turn continuation: API paused a long-running turn,
                    # send the response back as-is to let Claude continue
                    elif has_pending_tool_calls and not tool_calls:
                        logger.info(
                            f"⏸️ pause_turn continuation (iter {tool_loop_iteration})"
                        )
                        if sdk_final_message:
                            assistant_content = self._convert_sdk_message_to_api_blocks(sdk_final_message)
                            if assistant_content:
                                payload_for_stream["messages"].append(
                                    {"role": "assistant", "content": assistant_content}
                                )
                        has_pending_tool_calls = False
                        sdk_final_message = None
                        text_state.reset_for_iteration()
                        continue

                    # SAFETY / TRUNCATED STREAM RETRY:
                    # If we reach here, the stream completed but no tool loop
                    # continuation was triggered and conversation_ended is False.
                    # This typically means a truncated stream (200 OK but no stop_reason).
                    # Auto-retry with the same payload instead of silently breaking.
                    if not conversation_ended:
                        retry_attempts += 1
                        if retry_attempts <= self.valves.MAX_RETRIES:
                            # Determine what happened for logging
                            sdk_block_types = (
                                [getattr(b, "type", "?") for b in getattr(sdk_final_message, "content", [])]
                                if sdk_final_message else []
                            )
                            # `final_message` is cleared below but the diagnostics
                            # records are not — the retried call adds a second
                            # record for the same turn. Log both counts so a
                            # doubled diagnostics block can be attributed to the
                            # retry rather than guessed at.
                            logger.warning(
                                f"⚠️ [RUN {run_id}] Truncated stream (no stop_reason, no tool handling). "
                                f"SDK blocks: {sdk_block_types}. "
                                f"iter={tool_loop_iteration} "
                                f"diag_records={len(cache_diagnostics_records)} "
                                f"discarding {len(final_text())} char(s) of accumulated text. "
                                f"Auto-retrying ({retry_attempts}/{self.valves.MAX_RETRIES})..."
                            )
                            await status.activity(
                                f"⚠️ Stream abgebrochen, Retry ({retry_attempts}/{self.valves.MAX_RETRIES})..."
                            )
                            # Reset streaming state for retry — clear any partial content
                            # from this truncated iteration so we get a clean response
                            final_message.clear()
                            sdk_final_message = None
                            text_state.reset_for_retry()
                            request_ctx.state.thinking.reset_for_retry()
                            server_tool_state.reset_for_retry()
                            request_ctx.state.reset_current_block()
                            # payload_for_stream stays unchanged → same messages, same tools
                            # Cache from previous messages is preserved server-side
                            continue
                        else:
                            logger.error(
                                f"❌ Truncated stream: max retries ({self.valves.MAX_RETRIES}) exhausted. "
                                f"Returning error to user."
                            )
                            await request_ctx.emit_delta(
                                "\n\n⚠️ Die Anthropic API hat den Stream mehrfach abgebrochen "
                                f"({self.valves.MAX_RETRIES} Versuche). Bitte versuche es erneut."
                            )
                    break

                # ---------------------------------------------------------
                # PHASE 6: ERROR HANDLING
                # Catches and handles Anthropic API errors with retry logic:
                # - RateLimitError (429): Retryable, backoff
                # - AuthenticationError (401): API key issues
                # - InternalServerError (500, 529): Retryable
                # - APIConnectionError: Network issues, retryable
                # ---------------------------------------------------------
                except Exception as e:
                    # Finalize any open live code_exec block before handling error, so it
                    # does not stay stuck mid-render behind the error message.
                    await _finalize_open_code_block(request_ctx)
                    server_tool_state.current_code = ""
                    should_retry, retry_attempts, response_suffix = await self._handle_stream_exception(
                        e,
                        retry_attempts=retry_attempts,
                        request_ctx=request_ctx,
                    )
                    if should_retry:
                        continue
                    if response_suffix:
                        return final_text() + response_suffix
                    return final_text()
        except asyncio.CancelledError:
            # OpenWebUI stop button cancels the pipe task (task.cancel() ->
            # CancelledError raised inside `async for event in stream`).
            # CancelledError is a BaseException, so the `except Exception` paths
            # never finalize the UI.  Mark the status done and emit the completion
            # event so the frontend stops showing the generating indicator and the
            # status does not stay stuck active, then re-raise so OpenWebUI emits
            # chat:tasks:cancel and tears the task down.  The cancellation has
            # already been delivered, so awaiting the emits here is safe.
            try:
                await status.emit("⏹️ Request Cancelled", done=True, hidden=False, force=True)
                consolidated = final_text()
                if consolidated:
                    await emit_event_local(
                        {"type": "replace", "data": {"content": consolidated}}
                    )
                await emit_event_local(
                    {
                        "type": "chat:completion",
                        "data": {
                            "choices": [
                                {"finish_reason": "stop", "delta": {"content": ""}}
                            ],
                            "done": True,
                        },
                    }
                )
            except Exception as _cancel_cleanup_err:
                logger.debug(f"Cancel cleanup emit failed: {_cancel_cleanup_err}")
            raise
        except Exception as e:
            await self.handle_errors(e, __event_emitter__)
            return final_text()

        # ---------------------------------------------------------
        # PHASE 7: FINALIZATION
        # After successful completion:
        # - Build final status with token count display
        # - Emit completion status event
        # - Emit chat:completion event with usage stats
        # - Return final message text
        # ---------------------------------------------------------

        final_status = "✅ Response Complete"
        # ============ Token Count Display ============
        show_token_setting = __user__["valves"].SHOW_TOKEN_COUNT
        if include_usage and show_token_setting != "Off" and total_usage and not is_internal:
            def format_num(n: int) -> str:
                """Format a token count as a short human-readable string (e.g. 1.2K, 3.4M)."""
                if n >= 1_000_000:
                    return f"{n/1_000_000:.1f}M"
                if n >= 1_000:
                    return f"{n/1_000:.1f}K"
                return str(n)

            # Context window gauge: a point-in-time reading of the LAST call
            # (its full input plus its own output). Summing across tool-loop
            # calls would double-count, since each call's input already carries
            # the previous calls' answers.
            context_used = (
                total_usage.get("_ctx_input", 0) + total_usage.get("_ctx_output", 0)
            )
            model_info = self.get_model_info(body["model"].split("/")[-1])
            context_window = model_info.get("context_length", 200_000)
            context_label = f"{context_window // 1000}k" if context_window < 1_000_000 else f"{context_window / 1_000_000:.0f}M"
            percentage = min((context_used / context_window) * 100, 100)
            filled = int(percentage / 10)
            bar = "█" * filled + "░" * (10 - filled)

            final_status += (
                f" [{bar}] {format_num(context_used)}/{context_label} ({percentage:.1f}%)"
            )
            # Only worth showing when it explains why the cost figures below are
            # larger than the context gauge.
            calls = total_usage.get("_calls", 1)
            if calls > 1:
                final_status += f" · {calls} calls"

            # Cache status display (only in "With Cache" mode). These are billed
            # totals for the whole turn, so they can exceed the context gauge.
            if (
                show_token_setting == "With Cache"
                and self.valves.CACHE_CONTROL != "cache disabled"
            ):
                ttl_label = "1hr" if self.valves.CACHE_TTL == "1 hour" else "5min"
                cache_write = total_usage.get("cache_creation_input_tokens", 0)
                cache_read = total_usage.get("cache_read_input_tokens", 0)
                fresh_input = total_usage.get("input_tokens", 0)
                billed_input = cache_write + cache_read + fresh_input
                final_status += (
                    f" | 📝 {format_num(cache_write)} ({ttl_label})"
                    f" | 📖 {format_num(cache_read)}"
                )
                # The one number that answers "is caching actually working for
                # me": the share of billed input served from cache at 0.1x.
                if billed_input:
                    final_status += f" | ⚡ {cache_read / billed_input * 100:.0f}% cached"

        # Consolidate: emit a final replace with the complete message so OpenWebUI
        # has the authoritative content (replaces any partial delta/replace state).
        # Cache diagnostics: persist last response id for next turn and render a
        # collapsible details block if the API reported any miss reasons.
        # `not is_internal`: a sub-agent's text is pasted into the PARENT agent's
        # context, where a diagnostics collapsible is a kilobyte of markup no one
        # will ever expand. Measured on a real run: the injected sub-agent result
        # carried a full cache-diagnostics block into the parent.
        if (
            getattr(self.valves, "ENABLE_CACHE_DIAGNOSTICS", False)
            and cache_diagnostics_records
            and not is_internal
        ):
            try:
                last_id = next(
                    (rec.get("message_id") for rec in reversed(cache_diagnostics_records) if rec.get("message_id")),
                    None,
                )
                if cache_diagnostics_chat_id and last_id:
                    self._cache_diagnostics_state[cache_diagnostics_chat_id] = last_id
                # Persist the response id as a metadata marker on the saved
                # assistant message so the next turn can re-inject it as
                # `diagnostics.previous_message_id`. This survives pipe restarts
                # and multi-worker setups where the in-memory
                # `_cache_diagnostics_state` dict is not shared. The marker is an
                # invisible markdown link, stripped from future prompts by
                # `_extract_metadata_marker_from_message`.
                if last_id:
                    try:
                        if not isinstance(new_marker_metadata, list):
                            new_marker_metadata = list(new_marker_metadata or [])
                        new_marker_metadata.append(
                            self._create_metadata_marker("cachediag", last_id)
                        )
                    except Exception as _e:
                        logger.debug(f"[CACHE-DIAG] could not persist id marker: {_e}")
                # Pick the first non-empty diagnostics record for display.
                # Also show per-call usage even when no diagnostics object is present.
                visible = next(
                    (rec for rec in cache_diagnostics_records if rec.get("diagnostics")),
                    cache_diagnostics_records[0] if cache_diagnostics_records else None,
                )
                if visible:
                    import json as _json
                    # Build display dict: IDs first (for easy copy-paste into Console), then
                    # per-call usage array (one entry per API call in this turn), then diagnostics.
                    all_request_ids = [
                        rec["request_id"] for rec in cache_diagnostics_records if rec.get("request_id")
                    ]
                    all_message_ids = [
                        rec["message_id"] for rec in cache_diagnostics_records if rec.get("message_id")
                    ]
                    all_usages = [
                        rec["usage"] for rec in cache_diagnostics_records if rec.get("usage")
                    ]
                    display_obj = {}
                    if all_request_ids:
                        display_obj["request_ids"] = all_request_ids if len(all_request_ids) > 1 else all_request_ids[0]
                    if all_message_ids:
                        display_obj["message_ids"] = all_message_ids if len(all_message_ids) > 1 else all_message_ids[0]
                    if all_usages:
                        display_obj["usage"] = all_usages if len(all_usages) > 1 else all_usages[0]
                    if visible.get("diagnostics"):
                        display_obj["diagnostics"] = visible["diagnostics"]
                    body_json = _json.dumps(display_obj, indent=2, ensure_ascii=False, default=str)
                    reason = ""
                    try:
                        reason = (
                            (visible.get("diagnostics") or {})
                            .get("cache_miss_reason", {})
                            .get("type", "")
                        )
                    except Exception:
                        reason = ""
                    summary = f"Cache Diagnostics{(' — ' + reason) if reason else ''}"
                    diag_block = (
                        f'\n\n<details type="cache-diagnostics">\n'
                        f'<summary>{summary}</summary>\n\n'
                        f'```json\n{body_json}\n```\n'
                        f'</details>\n'
                    )
                    # One block per message is the invariant. If the accumulated
                    # text already carries one, this run is finalising a second
                    # time (or a previous run's content survived into ours) —
                    # the exact situation that produced two blocks with different
                    # request ids in chat 8e36a4d0. Log it loudly instead of
                    # silently appending a duplicate.
                    _already = final_text().count('<details type="cache-diagnostics">')
                    logger.info(
                        "[CACHE-DIAG run=%s] emit block: records=%d request_ids=%s "
                        "already_present=%d accumulated=%d char(s) fragments=%d",
                        run_id,
                        len(cache_diagnostics_records),
                        all_request_ids,
                        _already,
                        len(final_text()),
                        len(final_message),
                    )
                    if _already:
                        logger.warning(
                            "[CACHE-DIAG run=%s] DUPLICATE: %d block(s) already in the "
                            "accumulated text before emitting request_ids=%s — "
                            "finalisation ran more than once for this message",
                            run_id,
                            _already,
                            all_request_ids,
                        )
                    await request_ctx.emit_delta(diag_block)
            except Exception as e:
                logger.warning(f"[CACHE-DIAG] failed to emit diagnostics block: {e}")

        # Persist request-side metadata (e.g. native PDF attachment anchors) in
        # the saved assistant message. The marker is an empty markdown link and
        # is stripped from future prompts by _extract_metadata_marker_from_message.
        if new_marker_metadata and not is_internal:
            marker_text = "".join(new_marker_metadata) if isinstance(new_marker_metadata, list) else str(new_marker_metadata)
            if marker_text:
                final_message.append(marker_text)
                logger.debug("Persisted %d metadata marker char(s)", len(marker_text))

        consolidated = final_text()
        # The authoritative content this run hands to OpenWebUI. Comparing the
        # block count here against what ends up persisted in the DB separates a
        # pipe-side duplication from anything OpenWebUI does downstream
        # (normalizer, delta/replace ordering, frontend merge).
        logger.info(
            "[RUN %s] final replace: %d char(s), %d diagnostics block(s), %d fragment(s)",
            run_id,
            len(consolidated),
            consolidated.count('<details type="cache-diagnostics">'),
            len(final_message),
        )
        if consolidated:
            await emit_event_local(
                {"type": "replace", "data": {"content": consolidated}}
            )

        await status.complete(final_status)
        
        # Emit chat:completion done event so frontend knows streaming finished
        # (triggers TTS finish, usage display, etc.)
        done_data: dict = {"choices": [{"finish_reason": "stop", "delta": {"content": ""}}], "done": True}
        if include_usage and total_usage:
            done_data["usage"] = self._public_usage(total_usage)
        await emit_event_local({"type": "chat:completion", "data": done_data})

        # Persist usage to chat_message.usage column for the 0.9.0+ analytics page.
        # chat:completion events are NOT persisted by the socket event emitter
        # (only status|message|replace|embeds|files|source are), so without this
        # direct DB write the analytics tab never sees our token counts.
        if include_usage and total_usage and CHATS_AVAILABLE and __metadata__:
            chat_id = __metadata__.get("chat_id")
            message_id = __metadata__.get("message_id")
            if chat_id and message_id and not str(chat_id).startswith("local:"):
                try:
                    await Chats.upsert_message_to_chat_by_id_and_message_id(
                        chat_id, message_id, {"usage": self._public_usage(total_usage)}
                    )
                except Exception as e:
                    logger.warning(f"Failed to persist usage to chat_message: {e}")

        return final_text()
