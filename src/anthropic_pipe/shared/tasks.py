"""Compiled Pipe method group extracted from pipe_template.py."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class PipeTaskSupportMethods:
    # OpenWebUI's background memory review arrives as a task whose name is not in
    # the TASKS enum — functions.py forwards metadata.task verbatim.
    MEMORY_REVIEW_TASK = "memory_review"

    # Upper bound on max_tokens for the non-streaming task request.
    #
    # The SDK refuses a non-streaming call outright -- before any network I/O --
    # when max_tokens implies a response that could take over 10 minutes:
    # `3600 * max_tokens / 128000 > 600`, i.e. anything above ~21.3k. It also
    # keeps a stricter per-model table (8192 for the Opus 4 generation).
    # Handing it the model's full output limit therefore raised ValueError for
    # every current model -- 64k on Haiku 4.5, 128k on the rest -- and the
    # blanket except returned "", so EVERY task silently produced nothing.
    #
    # 8192 clears both thresholds and is still far more than a title, a tag
    # list or a memory-operations array will ever need.
    TASK_MAX_TOKENS_CAP = 8192

    # Response schemas for the task requests whose prompt asks for raw JSON.
    #
    # OpenWebUI parses these answers with json.loads and drops the whole task
    # when it fails, so every one of its prompts spends several lines begging
    # for "no markdown fences, no preamble". Structured outputs make that a
    # guarantee instead of a plea: the model cannot emit anything but a
    # conforming object.
    #
    # Keys are the task names OpenWebUI passes in metadata.task. Deliberately
    # absent: emoji_generation and moa_response_generation (their prompts ask
    # for prose, not JSON) and function_calling (the pipe uses native tools).
    #
    # `additionalProperties: false` everywhere -- OpenWebUI reads exactly one
    # key out of each of these and extra keys are pure token cost.
    TASK_RESPONSE_SCHEMAS = {
        "title_generation": {
            "type": "object",
            "properties": {"title": {"type": "string"}},
            "required": ["title"],
            "additionalProperties": False,
        },
        "tags_generation": {
            "type": "object",
            "properties": {"tags": {"type": "array", "items": {"type": "string"}}},
            "required": ["tags"],
            "additionalProperties": False,
        },
        "follow_up_generation": {
            "type": "object",
            "properties": {"follow_ups": {"type": "array", "items": {"type": "string"}}},
            "required": ["follow_ups"],
            "additionalProperties": False,
        },
        "query_generation": {
            "type": "object",
            "properties": {"queries": {"type": "array", "items": {"type": "string"}}},
            "required": ["queries"],
            "additionalProperties": False,
        },
        "image_prompt_generation": {
            "type": "object",
            "properties": {"prompt": {"type": "string"}},
            "required": ["prompt"],
            "additionalProperties": False,
        },
        "autocomplete_generation": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
        MEMORY_REVIEW_TASK: {
            "type": "object",
            "properties": {
                "operations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["add", "replace", "move", "remove"],
                            },
                            "id": {"type": "string"},
                            "type": {"type": "string", "enum": ["user", "context"]},
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        # One flat object rather than a per-action union: the
                        # required field set differs per action, and structured
                        # outputs does not accept anyOf/oneOf. OpenWebUI
                        # validates the per-action requirements itself
                        # (validate_memory_operations), so pinning the action
                        # vocabulary and the field names is the useful part --
                        # it is what stops the model from inventing the
                        # "score"/"importance"/"stability" keys the prompt
                        # explicitly warns against.
                        "required": ["action"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["operations"],
            "additionalProperties": False,
        },
    }

    async def _run_task_model_request(
        self,
        body: dict[str, Any],
        task: Optional[str] = None,
    ) -> str:
        """
        Handle task model requests (title generation, tags, follow-ups etc.) by making a
        non-streaming request to Anthropic API and returning only the text response.

        Task models should return plain text without any JSON formatting or status updates
        mixed into the response.
        """
        try:
            # Extract model and messages from body
            actual_model_name = self._resolve_task_model(body, task)
            messages = body.get("messages", [])
            model_info = self.get_model_info(actual_model_name)

            # Build simple payload for task request (non-streaming)
            task_payload = {
                "model": actual_model_name,
                # The model's real output limit, but capped: a non-streaming
                # request may not ask for more than TASK_MAX_TOKENS_CAP.
                "max_tokens": min(
                    body.get("max_tokens") or model_info.get("max_tokens", 4096),
                    self.TASK_MAX_TOKENS_CAP,
                ),
                "messages": self._process_messages_for_task(messages),
                "stream": False,
            }

            # Pin the response shape for the JSON-answering tasks, so a stray
            # markdown fence or a polite preamble can no longer cost OpenWebUI
            # the entire task.
            response_schema = (
                self.TASK_RESPONSE_SCHEMAS.get(task) if isinstance(task, str) else None
            )
            if response_schema and model_info.get("supports_structured_outputs"):
                task_payload["output_config"] = {
                    "format": {"type": "json_schema", "schema": response_schema}
                }
                logger.debug(f"Structured output enabled for task {task}")

            # Some task callers rely on their system prompt: OpenWebUI's memory
            # background review (metadata.task == "memory_review") instructs the
            # model to answer with valid JSON only, and drops the whole turn when
            # the answer is prose. Forward it instead of silently discarding it.
            task_system = self._extract_task_system(messages)
            if task_system:
                task_payload["system"] = task_system

            logger.debug(f"Task payload: {json.dumps(task_payload, indent=2)}")
            try:
                logger.debug(
                    "[PAYLOAD] task %s",
                    json.dumps(
                        self._strip_payload(task_payload),
                        ensure_ascii=False,
                        separators=(",", ":"),
                        default=str,
                    ),
                )
            except Exception as _pl_err:
                logger.debug(f"[PAYLOAD] task strip/log failed: {_pl_err}")

            # Make synchronous request to Anthropic API
            # For task requests, we don't have __user__ context, so use default key
            api_key = self.valves.ANTHROPIC_API_KEY
            client = self._build_anthropic_client(api_key)

            try:
                response = await client.messages.create(**task_payload)
            except Exception as struct_err:
                # Self-healing fallback. `supports_structured_outputs` can be
                # wrong in the optimistic direction on a proxy endpoint that
                # serves an Anthropic model id without implementing
                # output_config. Losing the schema costs a markdown fence;
                # losing the request costs the whole task, so retry plain
                # rather than let the outer handler swallow it.
                if "output_config" not in task_payload:
                    raise
                logger.warning(
                    f"Task {task} rejected with structured outputs, retrying "
                    f"without: {struct_err}"
                )
                task_payload.pop("output_config", None)
                response = await client.messages.create(**task_payload)

            # Extract text from response
            text_parts = []
            for content_block in response.content:
                if content_block.type == "text":
                    text_parts.append(content_block.text)

            # Join without adding line breaks - preserve original formatting
            result = "".join(text_parts).strip()

            logger.debug(f"Task response: {result}")

            return result

        except Exception as e:
            # Warning, not debug: returning "" makes OpenWebUI drop the task
            # silently, so at debug level a total task outage left no trace at
            # default log settings. That is how the max_tokens ValueError above
            # went unnoticed.
            logger.warning(f"Task model error ({task}): {e}")
            return ""

    def _process_messages_for_task(self, messages: List[dict]) -> List[dict]:
        """
        Process messages for task requests - convert to simple Anthropic format.
        Task requests don't need complex content processing, but they do need the
        UI artefacts stripped (see _sanitize_task_text).
        """
        processed = []
        for msg in messages:
            role = msg.get("role")
            if role == "system":
                continue  # Hoisted into the payload's top-level `system` field

            content = msg.get("content", "")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                # Extract text from content blocks
                text = " ".join(
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                )
            else:
                continue

            text = self._sanitize_task_text(text)
            # A message whose entire content was a collapsible sanitises to "".
            # The API rejects empty text blocks, so drop it rather than send it.
            if not text:
                continue

            # Dropping a message can leave two same-role messages adjacent, which
            # the API rejects. Merge instead of emitting an invalid sequence.
            if processed and processed[-1]["role"] == role:
                processed[-1]["content"] = f"{processed[-1]['content']}\n\n{text}"
            else:
                processed.append({"role": role, "content": text})

        return processed

    def _resolve_task_model(self, body: dict, task: Optional[str]) -> str:
        """Pick the model for a task request, honouring MEMORY_REVIEW_MODEL.

        OpenWebUI runs the background memory review on whatever model the chat
        uses, so an Opus conversation pays Opus rates to maintain its own memory
        bookkeeping. Every other task keeps the requested model.
        """
        requested = body["model"].split("/")[-1]
        if task != self.MEMORY_REVIEW_TASK:
            return requested

        override = getattr(self.valves, "MEMORY_REVIEW_MODEL", "same as chat model")
        if not override or override == "same as chat model":
            return requested

        logger.debug(f"Memory review routed to {override} instead of {requested}")
        return override

    @classmethod
    def _sanitize_task_text(cls, text: str) -> str:
        """Reduce persisted chat content to the prose a task model actually needs.

        OpenWebUI hands task requests the stored message content, which carries
        every collapsible this pipe ever wrote — tool calls, reasoning, cache
        diagnostics, code interpreter output — plus the invisible carriers and
        inline metadata markers used for replay. None of it round-trips: task
        requests are one-shot. Stripping it cuts the bill and stops the task model
        from reasoning about its own UI artefacts. It matters most for the memory
        review, which truncates each message to 1600 characters and would
        otherwise spend that budget on a token-usage dump.
        """
        if not text or ("<" not in text and "[" not in text):
            return text

        cleaned = PATTERN_ANY_DETAILS.sub("\n", text)
        cleaned = PATTERN_HIDDEN_BLOCK.sub("", cleaned)
        cleaned = PATTERN_INLINE_METADATA_MARKER.sub(" ", cleaned)
        cleaned = PATTERN_TRAILING_SPACES.sub("", cleaned)
        return PATTERN_EXCESS_BLANK_LINES.sub("\n\n", cleaned).strip()

    @classmethod
    def _extract_task_system(cls, messages: List[dict]) -> str:
        """Collect the system messages of a task request into a single string.

        Returned as plain text rather than a block list: task requests are
        one-shot and never cached, so there is nothing to attach cache_control to.
        """
        parts = []
        for msg in messages:
            if msg.get("role") != "system":
                continue
            content = msg.get("content", "")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text = " ".join(
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                )
            else:
                continue
            if text.strip():
                parts.append(text.strip())

        return "\n\n".join(parts)
