"""Server-side Anthropic tool-use content-block handlers.

Covers ``server_tool_use`` start / input delta / stop.  Tool-result blocks live
in ``server_tool_results.py`` because those are large, content-specific UI and
replay carriers.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

TEXT_EXTENSIONS = {
    ".md", ".txt", ".csv", ".json", ".xml", ".yaml", ".yml", ".toml",
    ".ini", ".cfg", ".log", ".rst", ".html", ".htm", ".css",
}
EXT_TO_LANG = {
    ".py": "python", ".js": "javascript", ".ts": "typescript", ".sh": "bash",
    ".sql": "sql", ".r": "r", ".rb": "ruby", ".java": "java", ".c": "c",
    ".cpp": "cpp", ".go": "go", ".rs": "rust",
}
SERVER_TOOLS_TO_PERSIST = (
    "web_search", "web_fetch", "code_execution", "bash_code_execution",
    "text_editor_code_execution", "tool_search_tool_regex", "tool_search_tool_bm25",
    "advisor",
)


async def _finalize_open_code_block(ctx: Any) -> None:
    """Close the code block a previous server tool left open, stamping its duration.

    Consecutive code_execution / bash / text_editor calls each open their own block;
    without this the earlier one would stay stuck in its "Analyzing…" state.
    """
    server_tool = ctx.state.server_tool
    if not server_tool.current_code:
        return
    duration = time.time() - server_tool.start_time if server_tool.start_time else None
    block = ctx.pipe._format_code_execution_block(
        server_tool.current_code,
        server_tool.current_lang,
        done=True,
        duration=duration,
    )
    await ctx.update_content_block(server_tool.last_block, block)
    server_tool.last_block = ""


async def handle_server_tool_use_block_start(content_block: Any, ctx: Any) -> None:
    """Handle a ``server_tool_use`` content_block_start; emits a status hint (searching/running/consulting) and, for code_execution, finalizes any prior code block."""
    server_tool = ctx.state.server_tool
    tool_name = getattr(content_block, "name", "")
    server_tool.active_name = tool_name
    server_tool.active_id = getattr(content_block, "id", "")
    server_tool.input_buffer = ""

    logger.debug(
        "Server tool started: %s (ID: %s)", server_tool.active_name, server_tool.active_id
    )
    server_tool.start_time = None

    if tool_name in ("web_search", "web_fetch"):
        # Deliberately silent here: the query/url arrives a few deltas later, and the
        # status history keeps every line, so announcing a generic "Searching the
        # web..." now would leave a placeholder line stranded above the real one.
        if server_tool.in_code_execution:
            server_tool.had_web_tools = True

    elif tool_name == "code_execution":
        await ctx.status.running_code()
        await _finalize_open_code_block(ctx)

        server_tool.in_code_execution = True
        # Assume the dynamic web-filtering pass until a client tool_use proves the
        # model is calling our tools programmatically instead.
        server_tool.is_web_filtering = True
        server_tool.has_user_tools = False
        server_tool.had_web_tools = False
        server_tool.tool_calls_info = []
        server_tool.stream_start_idx = len(ctx.final_message)
        server_tool.current_code = ""
        server_tool.current_lang = "python"
        server_tool.start_time = time.time()

    elif tool_name in ("bash_code_execution", "text_editor_code_execution"):
        if tool_name == "bash_code_execution":
            await ctx.status.running_command()
        else:
            await ctx.status.editing_file()
        await _finalize_open_code_block(ctx)

        server_tool.current_code = ""
        server_tool.current_lang = "bash" if tool_name == "bash_code_execution" else "python"
        server_tool.start_time = time.time()

    elif tool_name == "advisor":
        await ctx.status.consulting_advisor()


async def _stream_code_preview(ctx: Any, code: str, lang: str) -> None:
    """Re-render the live code preview block as more input JSON arrives."""
    server_tool = ctx.state.server_tool
    server_tool.current_code = code
    server_tool.current_lang = lang
    block = ctx.pipe._format_code_execution_block(code, lang)
    await ctx.update_content_block(server_tool.last_block, block)
    server_tool.last_block = block


def _shows_code_preview(server_tool: Any) -> bool:
    """Whether the code being streamed is the model's own, worth previewing.

    Code produced by the dynamic web-filtering pass is Anthropic's internal
    plumbing, not something the user asked for, so it stays hidden.
    """
    return not server_tool.is_web_filtering or not server_tool.had_web_tools


async def handle_server_tool_input_delta(partial: str, ctx: Any) -> None:
    """Handle an ``input_json_delta`` content_block_delta for a server tool_use; streams live code/query preview to OpenWebUI via update_content_block as the input JSON accumulates."""
    server_tool = ctx.state.server_tool
    server_tool.input_buffer += partial
    tool_name = server_tool.active_name

    # The buffer is only parseable once the JSON is complete; every earlier delta
    # raises and is skipped.
    try:
        parsed = json.loads(server_tool.input_buffer)
    except (json.JSONDecodeError, ValueError):
        return

    if tool_name == "web_search":
        query = parsed.get("query")
        if query:
            # Announced here rather than at block start: this is the first moment the
            # status can say what is actually being searched for. emit()'s dedup
            # absorbs the repeats as the remaining deltas re-parse the same JSON.
            await ctx.status.searching_web(query)
            if query != ctx.state.text.current_search_query:
                logger.debug("Web search query complete: '%s'", query)
                ctx.state.text.current_search_query = query

    elif tool_name == "web_fetch":
        if parsed.get("url"):
            await ctx.status.fetching_url(parsed["url"])

    elif tool_name == "code_execution":
        if "code" in parsed:
            server_tool.code_execution_code = parsed["code"]
            if _shows_code_preview(server_tool):
                await _stream_code_preview(
                    ctx, parsed["code"], parsed.get("language", "python")
                )

    elif tool_name == "bash_code_execution":
        if "command" in parsed:
            server_tool.bash_command = parsed["command"]
            logger.debug("Bash execution command: %s...", server_tool.bash_command[:100])
            if _shows_code_preview(server_tool):
                await _stream_code_preview(ctx, parsed["command"], "bash")

    elif tool_name == "text_editor_code_execution":
        if "command" in parsed:
            server_tool.text_editor_command = parsed["command"]
        if "path" in parsed:
            server_tool.text_editor_file_path = parsed["path"]
        if "file_text" in parsed:
            server_tool.text_editor_file_content = parsed["file_text"]
            if server_tool.text_editor_command == "create" and server_tool.text_editor_file_content:
                file_ext = (
                    os.path.splitext(server_tool.text_editor_file_path)[1].lower()
                    if server_tool.text_editor_file_path
                    else ""
                )
                # Plain-text files render as prose further down, not as a code block.
                if file_ext not in TEXT_EXTENSIONS:
                    await _stream_code_preview(
                        ctx,
                        server_tool.text_editor_file_content,
                        EXT_TO_LANG.get(file_ext, "python"),
                    )

    elif tool_name in ("tool_search_tool_regex", "tool_search_tool_bm25"):
        if "query" in parsed:
            logger.debug("Tool search query: '%s'", parsed["query"])
            await ctx.status.searching_tools(parsed["query"])


def _capture_last_code(server_tool: Any) -> None:
    """Remember the code this tool ran, so its result block can show it.

    The result block arrives separately and carries only the output; without this
    the rendered block would show output with no code above it.

    Only overwrites on a tool that actually carried code: a web_search stop landing
    between the code call and its result must leave the captured code intact.
    """
    tool_name = server_tool.active_name
    language = ""
    content = ""

    if tool_name == "bash_code_execution" and server_tool.bash_command:
        language = "bash"
        content = server_tool.bash_command
    elif (
        tool_name == "text_editor_code_execution"
        and server_tool.text_editor_command == "create"
        and server_tool.text_editor_file_content
    ):
        file_ext = (
            os.path.splitext(server_tool.text_editor_file_path)[1].lower()
            if server_tool.text_editor_file_path
            else ""
        )
        content = server_tool.text_editor_file_content
        # The sentinel makes the result renderer show prose rather than a code block.
        language = (
            "__inline_text__" if file_ext in TEXT_EXTENSIONS else EXT_TO_LANG.get(file_ext, "python")
        )
    elif tool_name == "code_execution" and server_tool.code_execution_code:
        language = "python"
        content = server_tool.code_execution_code

    if content:
        server_tool.last_code_language = language
        server_tool.last_code_content = content


async def handle_server_tool_use_block_stop(ctx: Any) -> None:
    """Handle a ``server_tool_use`` content_block_stop; emits the persisted server-tool-use carrier block to OpenWebUI for later result merging."""
    server_tool = ctx.state.server_tool
    logger.debug("Server tool block stopped: %s", server_tool.active_name)

    _capture_last_code(server_tool)

    if server_tool.active_name in SERVER_TOOLS_TO_PERSIST and server_tool.active_id:
        try:
            tool_input = json.loads(server_tool.input_buffer) if server_tool.input_buffer else {}
        except (json.JSONDecodeError, ValueError):
            tool_input = {}
        persisted_block = ctx.pipe._format_server_tool_use_block(
            tool_name=server_tool.active_name,
            tool_use_id=server_tool.active_id,
            tool_input=tool_input,
        )
        await ctx.emit_block(persisted_block)
        # The matching *_tool_result block pops this to merge its output into the
        # same collapsible instead of emitting a second one next to it.
        server_tool.use_carriers[server_tool.active_id] = {
            "block": persisted_block,
            "tool_name": server_tool.active_name,
            "tool_input": tool_input,
        }

    server_tool.active_name = None
    server_tool.active_id = None
    server_tool.input_buffer = ""
    server_tool.text_editor_file_content = ""
    server_tool.text_editor_file_path = ""
    server_tool.text_editor_command = ""
    server_tool.bash_command = ""
    server_tool.code_execution_code = ""
