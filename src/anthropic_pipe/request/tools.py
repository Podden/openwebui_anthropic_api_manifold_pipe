"""Compiled Pipe method group: OpenWebUI tools -> Claude tools conversion (web_search, web_fetch, advisor, bash/text_editor bridge, tool_search deferral). Compiled into class Pipe."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class PipeRequestToolsMethods:
    def _convert_tools_to_claude_format(
        self,
        __tools__,
        body: Dict[str, Any],
        actual_model_name: str,
        __user__: Dict[str, Any],
        __metadata__: dict[str, Any],
    ) -> tuple[List[dict], set]:
        """
        Convert OpenWebUI tools format to Claude API format.

        Extracts tool specs from TWO sources:
        1. body.tools - Built-in tools (OpenAI format specs only, no callables)
        2. __tools__ - User tools (specs + callables for execution)

        Args:
            __tools__: Dict of user tools with callables from OpenWebUI
            body: Request body containing body.tools (built-in tool specs)
            actual_model_name: Model name for capability checking
            __user__: User dict for valve overrides
            __metadata__: Metadata dict for checking enforcement flags
        Returns:
            tuple: (Tools in Claude API format, set of API-provided tool names without callables)
        """
        claude_tools = []
        tool_names_seen = set()  # Track unique tool names
        api_tool_names = set()  # Track tools from body.tools (no callable, API passthrough)
        forced_tool_name = None
        requested_tool_choice = body.get("tool_choice")
        if isinstance(requested_tool_choice, dict):
            if requested_tool_choice.get("type") == "function":
                forced_tool_name = (requested_tool_choice.get("function") or {}).get("name")
            elif requested_tool_choice.get("type") == "tool":
                forced_tool_name = requested_tool_choice.get("name")

        # Names reserved for Anthropic server-side tools (skip if found in body.tools)
        anthropic_server_tool_names = {"web_search", "web_fetch"}

        # Open Terminal bridge activation: if native bash / text_editor tools
        # are enabled AND the required Open Terminal callables are present,
        # route Claude's native tool calls through them and hide the raw
        # callables from the regular tool list (Claude only sees the native
        # bash / str_replace_based_edit_tool definitions).
        has_run_command = bool(__tools__ and "run_command" in __tools__ and __tools__["run_command"].get("callable"))
        has_write_file = bool(__tools__ and "write_file" in __tools__ and __tools__["write_file"].get("callable"))
        has_replace_file = bool(__tools__ and "replace_file_content" in __tools__ and __tools__["replace_file_content"].get("callable"))
        # Only bridge when Open Terminal is actually active for this request.
        # `terminal_id` is OpenWebUI's canonical signal (set from the request
        # body when a terminal session is attached); the callables can linger
        # in __tools__ without an active terminal, so gating on presence alone
        # is unreliable. No terminal_id → native tools are not injected and the
        # request falls back to code_execution (see request_payload.py).
        terminal_active = bool(__metadata__ and __metadata__.get("terminal_id"))
        bash_active = self.valves.ENABLE_BASH_TOOL and has_run_command and terminal_active
        text_editor_active = (
            self.valves.ENABLE_TEXT_EDITOR_TOOL
            and has_write_file
            and has_replace_file
            and terminal_active
        )
        terminal_hidden_names: set[str] = set()
        if bash_active:
            terminal_hidden_names.add("run_command")
        if text_editor_active:
            terminal_hidden_names.update({"write_file", "replace_file_content"})
        if terminal_hidden_names:
            logger.debug(
                f"Open Terminal bridge active: hiding {sorted(terminal_hidden_names)} "
                f"(bash={bash_active}, text_editor={text_editor_active})"
            )

        # Extract built-in tools from body.tools (OpenAI format)
        # User tools are collected separately and appended name-sorted. OpenWebUI
        # builds both `body["tools"]` and `__tools__` from a dict whose insertion
        # order follows `tool_ids` — and that order shifts on its own (toggling a
        # tool appends it to the end of `selectedToolIds`, a page reload resets it
        # to the model's own order, MCP servers return whatever order they like).
        # Same tool set, different order, whole prompt cache gone. Sorting makes
        # the tools array depend on the set, not on how the user got there.
        body_user_tools: List[dict] = []
        user_tools: List[dict] = []

        body_tools = body.get("tools", [])
        if body_tools:
            logger.debug(f"Found {len(body_tools)} built-in tools in body.tools")
            for tool_entry in body_tools:
                if tool_entry.get("type") == "function":
                    func = tool_entry.get("function", {})
                    name = func.get("name")
                    if not name or name in tool_names_seen:
                        continue

                    # Skip tools that will be handled by Anthropic server-side tools
                    if name in anthropic_server_tool_names:
                        logger.info(f"Skipping body tool '{name}' — handled by Anthropic server tool")
                        continue

                    # Skip Open Terminal callables that are being bridged to
                    # native bash / text_editor tools.
                    if name in terminal_hidden_names:
                        logger.info(f"Skipping body tool '{name}' — bridged to native Claude tool")
                        continue

                    # Convert OpenAI format to Claude format
                    claude_tool = {
                        "name": name,
                        "description": func.get("description", f"Tool: {name}"),
                        "input_schema": func.get(
                            "parameters", {"type": "object", "properties": {}}
                        ),
                    }
                    body_user_tools.append(claude_tool)
                    tool_names_seen.add(name)
                    # Track as API-provided tool (no callable — for passthrough)
                    if not (__tools__ and name in __tools__ and __tools__[name].get("callable")):
                        api_tool_names.add(name)

            claude_tools.extend(sorted(body_user_tools, key=lambda t: t["name"]))

        # Log user tools from __tools__
        if __tools__ and logger.isEnabledFor(logging.DEBUG):
            # Only attempt serialization if DEBUG is enabled
            try:
                logger.debug(
                    f"Converting {len(__tools__)} user tools: {json.dumps(__tools__, indent=2)}"
                )
            except (TypeError, ValueError):
                # Log tool names only if full serialization fails
                tool_names = list(__tools__.keys())[:10]
                logger.debug(
                    f"Converting {len(__tools__)} user tools (names): {tool_names}{'...' if len(__tools__) > 10 else ''}"
                )
        elif not __tools__:
            logger.debug("No user tools to convert")

        # Add web search tool if enabled OR if metadata enforces it (even if valve is disabled)
        web_search_enabled = self.valves.WEB_SEARCH or __metadata__.get(
            "web_search_enforced", False
        )
        if web_search_enabled:
            # Get user location values with fallback to global valves
            city = (
                __user__["valves"].WEB_SEARCH_USER_CITY
                or self.valves.WEB_SEARCH_USER_CITY
            )
            region = (
                __user__["valves"].WEB_SEARCH_USER_REGION
                or self.valves.WEB_SEARCH_USER_REGION
            )
            country = (
                __user__["valves"].WEB_SEARCH_USER_COUNTRY
                or self.valves.WEB_SEARCH_USER_COUNTRY
            )
            timezone = (
                __user__["valves"].WEB_SEARCH_USER_TIMEZONE
                or self.valves.WEB_SEARCH_USER_TIMEZONE
            )

            # Build web search tool config
            # web_search_20260209 has dynamic filtering (code execution post-processes results)
            # web_search_20250305 works on all models without dynamic filtering
            model_info_ws = self.get_model_info(actual_model_name)
            use_dynamic = __user__["valves"].ENABLE_DYNAMIC_FILTERING
            if use_dynamic and model_info_ws.get("supports_dynamic_filtering", False):
                web_search_type = "web_search_20260209"
            else:
                web_search_type = "web_search_20250305"
            web_search_tool = {
                "type": web_search_type,
                "name": "web_search",
            }
            # max_uses is only supported on web_search_20250305 (non-dynamic filtering)
            # Dynamic filtering versions (20260209) don't document max_uses support
            if web_search_type == "web_search_20250305":
                web_search_tool["max_uses"] = __user__["valves"].WEB_SEARCH_MAX_USES

            # Only add user_location if at least one field has a value.
            # Only include non-empty fields to avoid Anthropic API validation errors
            # (e.g. country must be ISO 3166-1 alpha-2, can't be empty string)
            if city or region or country or timezone:
                loc: dict = {"type": "approximate"}
                if city:
                    loc["city"] = city
                if region:
                    loc["region"] = region
                if country:
                    loc["country"] = country
                if timezone:
                    loc["timezone"] = timezone
                web_search_tool["user_location"] = loc

            claude_tools.append(web_search_tool)
            tool_names_seen.add("web_search")
            logger.debug(f"Added web_search tool: {web_search_type}")

        # Add web_fetch tool if enabled
        # web_fetch_20260209 has dynamic filtering (requires code execution)
        # web_fetch_20250910 works on all models without dynamic filtering
        model_info = self.get_model_info(actual_model_name)
        if self.valves.WEB_FETCH:
            use_dynamic_fetch = __user__["valves"].ENABLE_DYNAMIC_FILTERING
            if use_dynamic_fetch and model_info.get("supports_dynamic_filtering", False):
                web_fetch_type = "web_fetch_20260209"
            else:
                web_fetch_type = "web_fetch_20250910"
            web_fetch_tool = {
                "type": web_fetch_type,
                "name": "web_fetch",
            }
            # max_uses is only supported on web_fetch_20250910 (non-dynamic filtering)
            # Dynamic filtering versions (20260209) don't document max_uses support
            if web_fetch_type == "web_fetch_20250910":
                web_fetch_tool["max_uses"] = __user__["valves"].WEB_FETCH_MAX_USES
            claude_tools.append(web_fetch_tool)
            tool_names_seen.add("web_fetch")
            logger.debug(f"Added web_fetch tool: {web_fetch_type}")

        # Add advisor tool if enabled (beta). Executor↔advisor pair validation
        # The advisor must be at least as capable as the executor.
        # If the pair is invalid, downgrade the advisor to the next compatible model.
        if __user__["valves"].ENABLE_ADVISOR_TOOL:
            executor_model = actual_model_name
            advisor_model = __user__["valves"].ADVISOR_MODEL

            # Valid advisor models per executor (advisor must be ≥ executor in capability),
            # strongest first so allowed[0] is the best fallback. These lists already only
            # contain API-supported advisors, so a single membership check covers both
            # "unsupported" and "incompatible" cases.
            valid_advisors = {
                "claude-haiku-4-5": ["claude-opus-5", "claude-opus-4-8", "claude-opus-4-7"],
                "claude-sonnet-4-6": ["claude-opus-5", "claude-opus-4-8", "claude-opus-4-7"],
                "claude-sonnet-5": ["claude-opus-5", "claude-opus-4-8"],
                "claude-opus-4-6": ["claude-opus-5", "claude-opus-4-8", "claude-opus-4-7"],
                "claude-opus-4-7": ["claude-opus-5", "claude-opus-4-8", "claude-opus-4-7"],
                "claude-opus-4-8": ["claude-opus-5", "claude-opus-4-8"],
                "claude-opus-5": ["claude-opus-5"],
                "claude-fable-5": ["claude-fable-5"],
                "claude-mythos-5": ["claude-mythos-5"],
            }
            allowed_advisors = valid_advisors.get(executor_model, ["claude-opus-5"])

            adjusted_advisor_model = advisor_model
            if advisor_model not in allowed_advisors:
                adjusted_advisor_model = allowed_advisors[0]
                logger.warning(
                    f"Advisor '{advisor_model}' invalid for executor '{executor_model}'. "
                    f"Downgrading to '{adjusted_advisor_model}'"
                )

            advisor_tool: dict = {
                "type": "advisor_20260301",
                "name": "advisor",
                "model": adjusted_advisor_model,
            }
            if __user__["valves"].ADVISOR_MAX_USES > 0:
                advisor_tool["max_uses"] = __user__["valves"].ADVISOR_MAX_USES
            if __user__["valves"].ADVISOR_CACHING != "off":
                advisor_tool["caching"] = {
                    "type": "ephemeral",
                    "ttl": __user__["valves"].ADVISOR_CACHING,
                }
            claude_tools.append(advisor_tool)
            tool_names_seen.add("advisor")
            logger.debug(
                f"Added advisor tool: model={adjusted_advisor_model} "
                f"max_uses={__user__['valves'].ADVISOR_MAX_USES or 'unlimited'} "
                f"caching={__user__['valves'].ADVISOR_CACHING}"
            )

        # Inject native bash tool (bridged to Open Terminal's run_command)
        if bash_active:
            claude_tools.append({"type": "bash_20250124", "name": "bash"})
            tool_names_seen.add("bash")
            logger.debug("Added native bash tool (bridged to run_command)")

        # Inject native text editor tool (bridged to write_file + replace_file_content)
        if text_editor_active:
            claude_tools.append({
                "type": "text_editor_20250728",
                "name": "str_replace_based_edit_tool",
                "max_characters": self.valves.TEXT_EDITOR_MAX_CHARACTERS,
            })
            tool_names_seen.add("str_replace_based_edit_tool")
            logger.debug(
                f"Added native text_editor tool (bridged to write_file+replace_file_content, "
                f"max_characters={self.valves.TEXT_EDITOR_MAX_CHARACTERS})"
            )

        # Process user tools from __tools__ (these have callables for execution)
        if __tools__ and len(__tools__) > 0:
            for tool_name, tool_data in __tools__.items():
                if not isinstance(tool_data, dict) or "spec" not in tool_data:
                    logger.debug(f"Skipping invalid tool: {tool_name} - missing spec")
                    continue

                spec = tool_data["spec"]

                # Extract basic tool info
                name = spec.get("name", tool_name)

                # Skip if tool name already exists
                if name in tool_names_seen:
                    continue

                # Skip if toolname starts with _ or __
                if name.startswith("_"):
                    logger.debug(f"Skipping private tool: {name}")
                    continue

                # Skip Open Terminal callables that are bridged to native
                # Claude bash / text_editor tools — they must not appear as
                # regular user tools or Claude will see duplicates.
                if name in terminal_hidden_names:
                    logger.debug(f"Skipping bridged Open Terminal tool: {name}")
                    continue

                description = spec.get("description", f"Tool: {name}")
                parameters = spec.get("parameters", {})

                # Convert OpenWebUI parameters to Claude input_schema format
                # OpenWebUI parameters are typically already in JSON Schema format
                input_schema = {
                    "type": "object",
                    "properties": parameters.get("properties", {}),
                }

                # Add required fields if they exist
                if "required" in parameters:
                    input_schema["required"] = parameters["required"]

                # Create Claude tool format
                claude_tool = {
                    "name": name,
                    "description": description,
                    "input_schema": input_schema,
                }

                user_tools.append(claude_tool)
                tool_names_seen.add(name)

            claude_tools.extend(sorted(user_tools, key=lambda t: t["name"]))

        # Check if programmatic tool calling is active for this model
        # When active, tools must NOT be deferred (defer_loading) because
        # deferred tools loaded via tool_search may bypass allowed_callers enforcement
        is_programmatic_active = False
        if self.valves.ENABLE_PROGRAMMATIC_TOOL_CALLING:
            model_info_ptc = self.get_model_info(actual_model_name)
            is_programmatic_active = model_info_ptc.get("supports_programmatic_calling", False)

        _defer_active = __user__["valves"].ENABLE_TOOL_SEARCH and not is_programmatic_active

        for claude_tool in claude_tools:
            # Check if tool should be deferred for tool search
            # IMPORTANT: Skip deferring when programmatic tool calling is active.
            if _defer_active:
                # Skip deferring if tool is in exclusion list
                name = claude_tool["name"]
                user_excludes = __user__["valves"].TOOL_SEARCH_EXCLUDE_TOOLS
                if (
                    name != forced_tool_name
                    and name not in user_excludes
                ):
                    # Calculate tool definition size (JSON representation)
                    tool_json = json.dumps(claude_tool)
                    tool_len = len(tool_json)
                    if len(tool_json) > __user__["valves"].TOOL_SEARCH_MAX_DESCRIPTION_LENGTH:
                        claude_tool["defer_loading"] = True
                    else:
                        logger.debug(f"Tool '{name}' will be loaded normally")

            # Add allowed_callers for programmatic tool calling (only if model supports it)
            # When enabled, tools can be called from code execution
            # With code_execution_20260120 explicitly in the tools list, we can safely
            # add allowed_callers even alongside dynamic filtering tools (20260209) —
            # the explicit code_execution_20260120 supersedes auto-injection.
            if self.valves.ENABLE_PROGRAMMATIC_TOOL_CALLING:
                model_info = self.get_model_info(actual_model_name)
                if model_info.get("supports_programmatic_calling", False):
                    # Only add to user-defined tools (not server tools like web_search, web_fetch, memory)
                    if "type" not in claude_tool:  # Server tools have a "type" field
                        claude_tool["allowed_callers"] = ["code_execution_20260120"]

            # Enable fine-grained tool streaming for user-defined tools
            # Streams tool input JSON without buffering, reducing latency for large inputs
            # GA on all models, no beta header required
            if "type" not in claude_tool:  # Only user-defined tools (not server tools)
                claude_tool["eager_input_streaming"] = True

        if any(tool.get("defer_loading", False) for tool in claude_tools):
            if __user__["valves"].TOOL_SEARCH_TYPE == "regex":
                tool_search_tool = {
                    "type": "tool_search_tool_regex_20251119",
                    "name": "tool_search_tool_regex",
                }
            else:  # bm25 (default)
                tool_search_tool = {
                    "type": "tool_search_tool_bm25_20251119",
                    "name": "tool_search_tool_bm25",
                }
            claude_tools.insert(0, tool_search_tool)

        logger.debug(f"Total tools converted: {len(claude_tools)}")
        for t in claude_tools:
            flags = []
            if t.get("defer_loading"):
                flags.append("DEFERRED")
            if t.get("allowed_callers"):
                flags.append(f"callers={t['allowed_callers']}")
            if t.get("type"):
                flags.append(f"type={t['type']}")
            if t.get("eager_input_streaming"):
                flags.append("eager_stream")
            logger.info(f"  🔧 Tool: {t.get('name')} [{', '.join(flags) or 'normal'}]")

        return claude_tools, api_tool_names
