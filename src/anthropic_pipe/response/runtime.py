"""Compiled Pipe method group extracted from pipe_template.py."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class PipeStreamRuntimeSupportMethods:
    def _handle_message_start_usage(
        self,
        event: Any,
        *,
        include_usage: bool,
        total_usage: Optional[dict[str, int]],
        stream_output_tokens: int,
    ) -> int:
        """Handle message_start usage accounting and return updated stream output tokens."""

        message = getattr(event, "message", None)
        if not message:
            return stream_output_tokens

        request_id = getattr(message, "id", None)
        logger.debug(f" Message started with ID: {request_id}")

        if not include_usage or total_usage is None:
            return stream_output_tokens

        usage = getattr(message, "usage", {})
        if not usage:
            return stream_output_tokens

        input_tokens = getattr(usage, "input_tokens", 0)
        current_output_tokens = getattr(usage, "output_tokens", 0)

        total_usage["input_tokens"] += input_tokens
        diff = current_output_tokens - stream_output_tokens
        total_usage["output_tokens"] += diff
        stream_output_tokens = current_output_tokens

        if self.valves.CACHE_CONTROL != "cache disabled":
            cache_creation_input_tokens = getattr(usage, "cache_creation_input_tokens", 0) or 0
            cache_read_input_tokens = getattr(usage, "cache_read_input_tokens", 0) or 0
            # Accumulated, because every call is billed for its own cache traffic:
            # a write costs 1.25x (5m) or 2x (1h) and a read 0.1x, each time it
            # happens. Reporting only the last call's numbers hid the writes
            # entirely on any multi-call turn -- exactly the turns that cost the
            # most. Multi-call happens on client tool loops, `pause_turn`
            # continuations (server tools such as web_search) and retries.
            total_usage["cache_creation_input_tokens"] += cache_creation_input_tokens
            total_usage["cache_read_input_tokens"] += cache_read_input_tokens
            logger.debug(
                f" Usage stats: input={input_tokens}, output={current_output_tokens}, "
                f"cache_creation={cache_creation_input_tokens}, cache_read={cache_read_input_tokens}"
            )
        else:
            cache_creation_input_tokens = 0
            cache_read_input_tokens = 0
            logger.debug(f" Usage stats: input={input_tokens}, output={current_output_tokens}")

        total_usage["_calls"] = total_usage.get("_calls", 0) + 1

        # Two different questions, deliberately kept apart:
        #
        # "What did this turn cost?" -> cumulative. Every call is billed
        #   separately, so the usage dict sums input, output and cache traffic.
        # "How full is the context window?" -> point in time. Never a sum: call
        #   N's input already CONTAINS calls 1..N-1's outputs, so adding the
        #   running output total on top counts every intermediate answer twice
        #   and the error grows with each tool iteration.
        #
        # `_ctx_*` are private (stripped before the usage dict is handed to
        # OpenWebUI) and describe the last call only.
        total_usage["_ctx_input"] = (
            input_tokens + cache_creation_input_tokens + cache_read_input_tokens
        )
        total_usage["_ctx_output"] = current_output_tokens
        # OpenWebUI's contract (utils/response.py normalize_usage):
        # total_tokens == input_tokens + output_tokens, with cache traffic kept
        # in its own two fields. Adding the cache counters here double-counted
        # them against every other provider on the analytics page.
        total_usage["total_tokens"] = (
            total_usage.get("input_tokens", 0) + total_usage.get("output_tokens", 0)
        )
        logger.debug(f" Accumulated usage: {total_usage}")

        return stream_output_tokens

    @staticmethod
    def _public_usage(total_usage: dict[str, int]) -> dict[str, int]:
        """Project the internal usage tally onto OpenWebUI's usage schema.

        OpenWebUI reads token counts through two different field pairs, and it
        asks a different question with each. Filling both lets one usage dict
        answer both correctly instead of forcing a compromise:

        `input_tokens`/`output_tokens`/`total_tokens` -- cumulative over the
            whole turn, input counted UNCACHED-ONLY. This is OpenWebUI's own
            convention (`utils/anthropic.py` derives `input_tokens` as
            `prompt_tokens - cache_creation - cache_read`) and matches how the
            Anthropic API reports `input_tokens` natively. Cost and the
            analytics page read these, and cache traffic stays in its own two
            fields so nothing is counted twice.
        `prompt_tokens`/`completion_tokens` -- the LAST call only, with input
            counted in FULL (uncached + cache writes + cache reads). This is
            the real occupancy of the context window, which is what the
            auto-compaction reader needs. Cumulative sums would understate it
            badly under caching (most input arrives as cache reads), so
            compaction would fire far too late or never.

        `cache_n` is deliberately NOT set: the compaction reader adds it on top
        of `prompt_tokens`, which already includes the cached tokens here.
        """

        public = {k: v for k, v in total_usage.items() if not k.startswith("_")}
        public["prompt_tokens"] = total_usage.get("_ctx_input", 0)
        public["completion_tokens"] = total_usage.get("_ctx_output", 0)
        return public

    async def _handle_stream_exception(
        self,
        exc: Exception,
        *,
        retry_attempts: int,
        request_ctx: PipeRequestContext,
    ) -> tuple[bool, int, str]:
        """Central stream exception policy.

        Returns: (should_retry, updated_retry_attempts, response_suffix)
        """

        max_retries = self.valves.MAX_RETRIES
        status = StatusEmitter(request_ctx.emit_event)

        non_retry_map: dict[type[Exception], str] = {
            RateLimitError: f"\n\n⚠️ Rate limit exceeded - maximum retries ({max_retries}) reached. Please try again later.",
            AuthenticationError: f"\n\nError: API key issues. Reason: {getattr(exc, 'message', str(exc))}",
            PermissionDeniedError: f"\n\nError: Permission denied. Reason: {getattr(exc, 'message', str(exc))}",
            NotFoundError: f"\n\nError: Resource not found. Reason: {getattr(exc, 'message', str(exc))}",
            BadRequestError: f"\n\nError: Invalid request format. Reason: {getattr(exc, 'message', str(exc))}",
            UnprocessableEntityError: f"\n\nError: Unprocessable entity. Reason: {getattr(exc, 'message', str(exc))}",
        }

        for error_type, suffix in non_retry_map.items():
            if isinstance(exc, error_type):
                await self.handle_errors(exc, request_ctx.event_emitter)
                return (False, retry_attempts, suffix)

        retryable_with_status: list[tuple[type[Exception], str, str]] = [
            (OverloadedError, "⏳ API overloaded, retrying...", "🔧 API overloaded"),
            (InternalServerError, "⏳ Server error, retrying...", "🔧 Server error"),
            (APIConnectionError, "🌐 Connection error, retrying...", "🌐 Network connection failed"),
        ]

        for error_type, status_label, fail_label in retryable_with_status:
            if isinstance(exc, error_type):
                retry_attempts += 1
                if retry_attempts <= max_retries:
                    await status.activity(f"{status_label} ({retry_attempts}/{max_retries})")
                    return (True, retry_attempts, "")

                await self.handle_errors(exc, request_ctx.event_emitter)
                if isinstance(exc, APIConnectionError):
                    return (
                        False,
                        retry_attempts,
                        f"\n\n{fail_label} after {max_retries} attempts. Please check your connection.",
                    )
                return (
                    False,
                    retry_attempts,
                    f"\n\n{fail_label} - maximum retries ({max_retries}) reached. Please try again later.",
                )

        if isinstance(exc, APIStatusError):
            error_body = getattr(exc, "body", None) or {}
            error_info = error_body.get("error", {}) if isinstance(error_body, dict) else {}
            is_overloaded = error_info.get("type") == "overloaded_error"

            if is_overloaded and retry_attempts < max_retries:
                retry_attempts += 1
                await status.activity(
                    f"⏳ API overloaded (streaming), retrying... ({retry_attempts}/{max_retries})"
                )
                return (True, retry_attempts, "")

            await self.handle_errors(exc, request_ctx.event_emitter)
            if is_overloaded:
                return (
                    False,
                    retry_attempts,
                    f"\n\n🔧 API overloaded (streaming) - maximum retries ({max_retries}) reached. Please try again later.",
                )
            return (
                False,
                retry_attempts,
                f"\n\nError: Anthropic API error. Reason: {getattr(exc, 'message', str(exc))}",
            )

        await self.handle_errors(exc, request_ctx.event_emitter)
        return (
            False,
            retry_attempts,
            f"\n\nError: {type(exc).__name__} occurred. Reason: {exc}",
        )

    async def _apply_sdk_stop_reason_fallback(
        self,
        *,
        sdk_final_message: Any,
        conversation_ended: bool,
        has_pending_tool_calls: bool,
        tool_calls: list[dict[str, Any]],
        tool_loop_iteration: int,
        payload_for_stream: dict[str, Any],
        stream_event_counts: dict[str, int],
        request_ctx: PipeRequestContext,
    ) -> tuple[bool, bool, list[dict[str, Any]]]:
        """Apply fallback stop-reason logic when message_delta was missing."""

        if not sdk_final_message or conversation_ended or has_pending_tool_calls:
            return conversation_ended, has_pending_tool_calls, tool_calls

        status = StatusEmitter(request_ctx.emit_event)

        sdk_stop = getattr(sdk_final_message, "stop_reason", None)
        sdk_content = getattr(sdk_final_message, "content", [])

        if sdk_stop:
            logger.info(f"📍 Fallback stop_reason from SDK message: {sdk_stop}")
            if sdk_stop == "end_turn":
                conversation_ended = True
            elif sdk_stop == "tool_use":
                has_pending_tool_calls = True
                if not tool_calls:
                    for block in sdk_content:
                        if getattr(block, "type", None) == "tool_use":
                            logger.warning(
                                f"📍 Rebuilding tool_call from SDK: {getattr(block, 'name', '?')}"
                            )
                            tool_calls.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": getattr(block, "id", ""),
                                    "content": "Error: tool call was not processed during streaming",
                                    "is_error": True,
                                }
                            )
            elif sdk_stop == "pause_turn":
                has_pending_tool_calls = True
                await status.activity("⏳ Long-running turn paused, continuing...")
            elif sdk_stop in (
                "max_tokens",
                "refusal",
                "stop_sequence",
                "model_context_window_exceeded",
            ):
                conversation_ended = True
                if sdk_stop == "max_tokens":
                    await request_ctx.emit_delta("\n\n⚠️ Maximum token limit reached.")
                elif sdk_stop == "model_context_window_exceeded":
                    await request_ctx.emit_delta("\n\n⚠️ Context window exceeded.")
                elif sdk_stop == "refusal":
                    _stop_details = getattr(sdk_final_message, "stop_details", None)
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
                    await request_ctx.emit_block(_ref_msg)
        elif not sdk_content:
            logger.warning(
                f"⚠️ Empty API response (no stop_reason, no content). "
                f"Container: {payload_for_stream.get('container', 'NONE')}. "
                f"Events: {stream_event_counts}. Treating as end_turn."
            )
            conversation_ended = True
            if tool_loop_iteration > 1:
                await request_ctx.emit_delta(
                    "\n\n⚠️ Code execution continuation returned empty response. "
                    "The container may have timed out."
                )
        else:
            # stop_reason is None but content exists (e.g. thinking + server_tool blocks
            # without any text). This typically happens when the API is overloaded and
            # returns a truncated stream after 200 OK. Anthropic warns:
            # "When receiving a streaming response via SSE, it's possible that an error
            # can occur after returning a 200 response."
            # We leave conversation_ended=False here so the main loop's safety-break
            # section can detect this and trigger an auto-retry.
            block_types = [getattr(b, "type", "?") for b in sdk_content]
            has_text = any(
                getattr(b, "type", None) == "text"
                and len(getattr(b, "text", "") or "") > 0
                for b in sdk_content
            )
            logger.warning(
                f"⚠️ Truncated stream: no stop_reason but content present. "
                f"Blocks: {block_types}. has_text={has_text}. "
                f"Container: {payload_for_stream.get('container', 'NONE')}. "
                f"Events: {stream_event_counts}."
            )
            # Don't set conversation_ended — let the safety-break handle retry logic

        return conversation_ended, has_pending_tool_calls, tool_calls

    async def handle_errors(
        self,
        exception,
        __event_emitter__: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ):
        """Map an exception to a user-facing message and emit error/status events."""
        # Determine specific error message based on exception type
        if isinstance(exception, RateLimitError):
            error_msg = "Rate limit exceeded. Please wait before making more requests."
            user_msg = "⚠️ Rate limit reached. Please try again in a moment."
        elif isinstance(exception, AuthenticationError):
            error_msg = "Authentication failed. Please check your API key."
            user_msg = (
                "🔑 Invalid API key. Please verify your Anthropic API key is correct."
            )
        elif isinstance(exception, PermissionDeniedError):
            error_msg = (
                "Permission denied. Your API key may not have access to this resource."
            )
            user_msg = "🚫 Access denied. Your API key doesn't have permission for this request."
        elif isinstance(exception, NotFoundError):
            error_msg = (
                "Resource not found. The requested model or endpoint may not exist."
            )
            user_msg = "❓ Resource not found. Please check if the model is available."
        elif isinstance(exception, BadRequestError):
            error_msg = f"Bad request: {str(exception)}"
            user_msg = (
                "📝 Invalid request format. Please check your input and try again."
            )
        elif isinstance(exception, UnprocessableEntityError):
            error_msg = f"Unprocessable entity: {str(exception)}"
            user_msg = "📄 Request format issue. Please check your message structure and try again."
        elif isinstance(exception, InternalServerError):
            error_msg = "Anthropic server error. Please try again later."
            user_msg = (
                "🔧 Server temporarily unavailable. Please try again in a few moments."
            )
        elif isinstance(exception, APIConnectionError):
            error_msg = (
                "Network connection error. Please check your internet connection."
            )
            user_msg = "🌐 Connection error. Please check your network and try again."
        elif isinstance(exception, APIStatusError):
            status_code = getattr(exception, "status_code", "Unknown")
            error_msg = f"API Error ({status_code}): {str(exception)}"
            user_msg = (
                f"⚡ API Error ({status_code}). Please try again or contact support."
            )
        else:
            error_msg = f"Unexpected error: {str(exception)}"
            user_msg = "💥 An unexpected error occurred. Please try again."

        logger.error(f"Exception: {error_msg}")
        # Add request ID if available for debugging
        if isinstance(exception, APIStatusError) and hasattr(exception, "response"):
            try:
                request_id = exception.response.headers.get("request-id")
                if request_id:
                    logger.info(f"Request ID: %s", request_id)
            except Exception:
                pass  # Ignore if we can't get request ID

        await self.emit_event(
            {
                "type": "notification",
                "data": {
                    "type": "error",
                    "content": user_msg,
                },
            },
            __event_emitter__,
        )

        tb = traceback.format_exc()

        await self.emit_event(
            {
                "type": "source",
                "data": {
                    "source": {"name": "Anthropic Error", "url": None},
                    "document": [tb],
                    "metadata": [
                        {
                            "source": "anthropic api",
                            "type": "error",
                            "date_accessed": datetime.utcnow().isoformat(),
                        }
                    ],
                },
            },
            __event_emitter__,
        )
        await self.emit_event(
            {
                "type": "status",
                "data": {
                    "description": "❌ Response with Errors",
                    "done": True,
                },
            },
            __event_emitter__,
        )

    async def handle_citation(self, event, __event_emitter__, citation_counter=None):
        """
        Handle web search citation events from Anthropic API and emit appropriate source events to OpenWebUI.

        Args:
            event: The citation event from Anthropic (content_block_delta with citations_delta)
            __event_emitter__: OpenWebUI event emitter function
            citation_counter: Optional citation number for inline citations
        """
        try:
            logger.debug(
                f" Processing citation event type: {getattr(event, 'type', 'unknown')}"
            )

            # Extract citation from delta within content_block_delta event
            delta = getattr(event, "delta", None)
            citation = None

            if delta and hasattr(delta, "citation"):
                citation = delta.citation
            elif hasattr(event, "citation"):
                # Fallback: direct citation in event
                citation = event.citation

            if not citation:
                logger.debug(f"No citation data found in event")
                return

            logger.debug(f" Citation data found: {citation}")

            # Only handle web search result citations
            citation_type = getattr(citation, "type", "")
            if citation_type != "web_search_result_location":
                logger.debug(f" Skipping non-web-search citation type: {citation_type}")
                return

            # Extract web search citation information
            url = getattr(citation, "url", "")
            title = getattr(citation, "title", "Unknown Source")
            cited_text = getattr(citation, "cited_text", "")

            # CRITICAL: metadata.source is used by OpenWebUI as the grouping ID
            # Must be unique for each citation to prevent Citation merging
            metadata = {
                "source": f"{url}#{citation_counter}",
                "date_accessed": datetime.now().isoformat(),
                "name": f"[{citation_counter}]",
            }

            source_data = {
                "source": {
                    "name": title,
                    "url": url,
                    "id": f"{citation_counter}",  # Unique source ID
                },
                "document": [cited_text],
                "metadata": [metadata],
            }

            # Emit the source event
            await self.emit_event(
                {"type": "source", "data": source_data}, __event_emitter__
            )

        except Exception as e:
            logger.error(f"Error handling citation: {str(e)}")
            await self.handle_errors(e, __event_emitter__)

    async def emit_event(
        self,
        event: Dict[str, Any],
        __event_emitter__: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> None:
        """
        Safely emit an event, handling None __event_emitter__ (e.g., in Channel contexts).

        In OpenWebUI Channels, when models are mentioned, __event_emitter__ is None
        because the channel context doesn't provide a socket connection for status updates.
        This helper prevents 'NoneType' object is not callable errors.
        """
        if __event_emitter__ is None:
            return
        try:
            await __event_emitter__(event)
        except Exception as e:
            logger.warning(f"Event emitter failed: {e}")

    def _convert_sdk_message_to_api_blocks(self, message) -> list:
        """Convert SDK accumulated BetaMessage content to API-compatible block dicts.

        Mirrors the SDK's own tool runner behavior: keeps ALL content blocks
        (including server_tool_use, *_tool_result, compaction) to preserve
        thinking block positions and compaction boundaries. Skips structural
        meta-events (context_cleared).

        Strict key sanitization is applied ONLY to thinking/redacted_thinking
        blocks (to prevent cache_control from being sent). All other blocks
        are passed through with minimal processing.
        """
        blocks = []
        for block in message.content:
            block_dict = block.model_dump(exclude_none=True)
            block_type = block_dict.get("type", "")

            # Skip structural meta-events (not real content blocks)
            if block_type in self._SKIP_BLOCK_TYPES:
                continue

            # Compaction: preserve as {type: "compaction"} so the API
            # recognises the boundary and drops all prior content blocks.
            if block_type == "compaction":
                content = block_dict.get("content", "")
                if content:
                    blocks.append({"type": "compaction", "content": content})
                continue

            # Thinking/redacted_thinking: strict key sanitization
            sanitize_keys = self._SANITIZE_BLOCK_KEYS.get(block_type)
            if sanitize_keys is not None:
                blocks.append({k: v for k, v in block_dict.items() if k in sanitize_keys})
                continue

            # Text blocks: strip citations (response-only presentation data)
            if block_type == "text":
                block_dict.pop("citations", None)
                blocks.append(block_dict)
                continue

            # tool_use blocks: strip "direct" caller (API rejects it),
            # but preserve programmatic caller (needed for code_execution routing)
            if block_type == "tool_use":
                caller = block_dict.get("caller")
                if caller and caller.get("type") == "direct":
                    block_dict.pop("caller", None)
                blocks.append(block_dict)
                continue

            # All other blocks (server_tool_use, *_tool_result, etc.):
            # pass through as-is to preserve thinking block positions
            blocks.append(block_dict)

        return blocks

