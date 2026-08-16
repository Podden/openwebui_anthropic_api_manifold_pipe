"""Client-side Anthropic ``tool_use`` content-block handlers."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


async def handle_tool_use_block_start(content_block: Any, ctx: Any) -> None:
    """Handle a ``tool_use`` content_block_start; emits an in-progress tool-call block to OpenWebUI (unless inside code execution)."""
    tool_use = ctx.state.tool_use
    server_tool = ctx.state.server_tool
    tool_name = getattr(content_block, "name", "unknown")
    logger.debug("🔧 Tool use block started: %s", tool_name)

    # A client tool firing inside code execution means the model is calling our
    # tools programmatically, not doing the dynamic web filtering pass.
    if server_tool.in_code_execution and server_tool.is_web_filtering:
        server_tool.is_web_filtering = False
        server_tool.has_user_tools = True

    initial_input = getattr(content_block, "input", None) or {}
    tool_use.tool_name_at_start = tool_name
    tool_use.tool_id_at_start = getattr(content_block, "id", "")
    tool_use.input_buffer = ""
    if initial_input:
        logger.debug(
            "🔧 Tool input pre-populated at start: %s",
            json.dumps(initial_input, ensure_ascii=False)[:200],
        )
        tool_use.tools_buffer = json.dumps(
            {
                "type": content_block.type,
                "id": content_block.id,
                "name": content_block.name,
                "input": initial_input,
            },
            ensure_ascii=False,
        )
    else:
        tool_use.tools_buffer = (
            "{"
            f'"type": "{content_block.type}", '
            f'"id": "{content_block.id}", '
            f'"name": "{content_block.name}", '
            f'"input": '
        )

    if not server_tool.in_code_execution:
        # Inside code execution the call is the model's own plumbing and already
        # shown in the code block; announcing it would just churn the status line.
        await ctx.status.running_tool(tool_name)
        in_progress_block = ctx.pipe._format_tool_result_block(
            tool_use.tool_id_at_start, tool_name, initial_input or {}, "", done=False
        )
        tool_use.progress_blocks[tool_use.tool_id_at_start] = in_progress_block
        text = ctx.pipe._append_block_to_text(ctx.text(), in_progress_block)
        await ctx.emit_replace(text)


async def handle_client_tool_input_delta(partial: str, ctx: Any) -> None:
    """Handle an ``input_json_delta`` content_block_delta for a client tool_use; re-renders the partial tool-call block to OpenWebUI as JSON completes."""
    tool_use = ctx.state.tool_use
    tool_use.tools_buffer += partial
    tool_use.input_buffer += partial

    if ctx.state.server_tool.in_code_execution:
        return
    if tool_use.tool_id_at_start not in tool_use.progress_blocks:
        return

    parsed_input = ctx.pipe._try_parse_partial_json(tool_use.input_buffer)
    if parsed_input is None:
        return
    old_block = tool_use.progress_blocks[tool_use.tool_id_at_start]
    new_block = ctx.pipe._format_tool_result_block(
        tool_use.tool_id_at_start, tool_use.tool_name_at_start, parsed_input, "", done=False
    )
    text = ctx.text().replace(old_block, new_block, 1)
    tool_use.progress_blocks[tool_use.tool_id_at_start] = new_block
    await ctx.emit_replace(text)


async def handle_tool_use_block_stop(ctx: Any) -> None:
    """Handle a ``tool_use`` content_block_stop; parses the completed tool call and dispatches it as a background task (bash/text-editor bridge, user/builtin tool, API passthrough, or error result)."""
    tool_use = ctx.state.tool_use
    pipe = ctx.pipe
    tools = ctx.tools
    builtin_tools = ctx.builtin_tools
    api_tool_names = ctx.api_tool_names
    running_tool_tasks = tool_use.running_tasks
    emit_delta = ctx.emit_delta
    emit_event = ctx.event_emitter
    tools_buffer = tool_use.tools_buffer

    if not tools_buffer:
        return

    try:
        json.loads(tools_buffer)
        logger.debug(" tools_buffer already valid JSON: %s", tools_buffer)
    except json.JSONDecodeError:
        if tools_buffer.rstrip().endswith('"input":') or tools_buffer.rstrip().endswith(
            '"input": '
        ):
            tools_buffer += " {}"
            logger.debug(" Added empty input object: %s", tools_buffer)
        tools_buffer += "}"
        logger.debug(" Closed tools_buffer in content_block_stop: %s", tools_buffer)

    logger.debug("Parsed tool call: %s", tools_buffer)

    try:
        tool_call_data = json.loads(tools_buffer)
        tool_name = tool_call_data.get("name", "")
        tool_input = tool_call_data.get("input", {})

        tool = tools.get(tool_name) if tools else None
        if (
            tool_name == "bash"
            and pipe.valves.ENABLE_BASH_TOOL
            and tools
            and "run_command" in tools
        ):
            args = tool_input if isinstance(tool_input, dict) else {}
            task = asyncio.create_task(
                pipe._await_tool_task_result(
                    tool_call_data,
                    pipe._dispatch_bash_tool(args, tools, emit_event),
                    timeout_s=pipe.valves.BASH_TOOL_TIMEOUT + 15,
                )
            )
            running_tool_tasks.append(task)
            logger.debug("🚀 Started bash bridge → run_command (task #%d)", len(running_tool_tasks))
        elif (
            tool_name == "str_replace_based_edit_tool"
            and pipe.valves.ENABLE_TEXT_EDITOR_TOOL
            and tools
            and "write_file" in tools
            and "replace_file_content" in tools
        ):
            args = tool_input if isinstance(tool_input, dict) else {}
            task = asyncio.create_task(
                pipe._await_tool_task_result(
                    tool_call_data,
                    pipe._dispatch_text_editor_tool(args, tools, emit_event),
                    timeout_s=pipe.valves.BASH_TOOL_TIMEOUT + 15,
                )
            )
            running_tool_tasks.append(task)
            logger.debug(
                "🚀 Started text_editor bridge (cmd=%s, task #%d)",
                args.get("command", "?"),
                len(running_tool_tasks),
            )
        elif tool and tool.get("callable"):
            args = tool_input if isinstance(tool_input, dict) else {}
            task = asyncio.create_task(
                pipe._await_tool_task_result(tool_call_data, tool["callable"](**args))
            )
            running_tool_tasks.append(task)
            logger.debug(
                "🚀 Started immediate execution for user tool '%s' (task #%d)",
                tool_name,
                len(running_tool_tasks),
            )
        elif tool_name in builtin_tools and builtin_tools[tool_name].get("callable"):
            args = tool_input if isinstance(tool_input, dict) else {}
            task = asyncio.create_task(
                pipe._await_tool_task_result(
                    tool_call_data,
                    builtin_tools[tool_name]["callable"](**args),
                )
            )
            running_tool_tasks.append(task)
            logger.debug(
                "🚀 Started immediate execution for builtin tool '%s' (task #%d)",
                tool_name,
                len(running_tool_tasks),
            )
        elif tool_name in api_tool_names:
            logger.info(
                "🔄 API tool passthrough for '%s': returning tool input as response",
                tool_name,
            )
            await emit_delta(json.dumps(tool_input, ensure_ascii=False))
            tool_use.api_passthrough = True
        else:
            logger.warning("Tool '%s' not found in __tools__ or builtin_tools", tool_name)

            async def error_result(tn=tool_name):
                """Build the JSON error payload returned when a requested tool is not available."""
                return json.dumps(
                    {
                        "error": f"Tool '{tn}' is not available. It may require server context or is not configured."
                    },
                    ensure_ascii=False,
                )

            task = asyncio.create_task(
                pipe._await_tool_task_result(tool_call_data, error_result())
            )
            running_tool_tasks.append(task)
    except Exception as e:
        logger.error("Failed to start tool execution: %s", e)

    tool_use.tools_buffer = ""
