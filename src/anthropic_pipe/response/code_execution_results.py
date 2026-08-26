"""Code-execution server tool-result content-block handlers.

Covers the bash, text-editor, and generic code_execution result variants. All of
them close out a code block that ``server_tool.py`` opened, so they read the same
``ctx.state.server_tool`` group.
"""
from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def _suppressed_as_web_filtering(server_tool: Any) -> bool:
    """Whether this result belongs to Anthropic's dynamic web-filtering pass.

    That pass runs code internally to filter search results; showing it would
    surface plumbing the user never asked for.
    """
    return server_tool.is_web_filtering and server_tool.had_web_tools


async def _download_links_for(files_output: Any, ctx: Any) -> list[str]:
    """Turn container file outputs into OpenWebUI download links."""
    links: list[str] = []
    for file_obj in files_output or []:
        file_id = (
            file_obj.get("file_id")
            if isinstance(file_obj, dict)
            else getattr(file_obj, "file_id", None)
        )
        if file_id:
            links.append(
                await ctx.pipe._generate_file_download_link(
                    file_id=file_id,
                    api_key=ctx.api_key,
                    user_id=ctx.user.get("id", "unknown"),
                )
            )
    return links


async def _handle_bash_result(content_block: Any, ctx: Any) -> None:
    """Close the bash code block with its stdout/stderr/return code and any files."""
    server_tool = ctx.state.server_tool
    logger.debug("Processing bash_code_execution_tool_result: %s", content_block)
    await ctx.pipe._persist_server_tool_result(
        content_block,
        "bash_code_execution_tool_result",
        ctx.emit_delta,
        summary_text="🖥️ bash result",
    )
    result_block = getattr(content_block, "content", None)
    if not result_block:
        return

    if getattr(result_block, "type", "") == "bash_code_execution_tool_result_error":
        error_code = getattr(result_block, "error_code", "unknown")
        logger.warning("bash_code_execution error: %s", error_code)
        await ctx.emit_block(f"⚠️ Code execution error: {error_code}")
        server_tool.last_code_content = ""
        return

    stdout = getattr(result_block, "stdout", "")
    stderr = getattr(result_block, "stderr", "")
    return_code = getattr(result_block, "return_code", None)
    download_links = await _download_links_for(getattr(result_block, "content", []), ctx)

    if not (stdout or stderr or return_code is not None or download_links):
        return

    if _suppressed_as_web_filtering(server_tool):
        logger.debug("Suppressed bash code execution block (web filtering)")
    else:
        duration = time.time() - server_tool.start_time if server_tool.start_time else None
        block = ctx.pipe._format_code_execution_block(
            server_tool.last_code_content,
            "bash",
            done=True,
            duration=duration,
            stdout=stdout,
            stderr=stderr,
            return_code=return_code,
            download_links=download_links,
        )
        await ctx.update_content_block(server_tool.last_block, block)
        server_tool.last_block = ""
    server_tool.last_code_content = ""


async def _handle_text_editor_result(content_block: Any, ctx: Any) -> None:
    """Render the outcome of a text_editor call: created file, viewed file, or error."""
    server_tool = ctx.state.server_tool
    logger.debug("Processing text_editor_code_execution_tool_result: %s", content_block)
    await ctx.pipe._persist_server_tool_result(
        content_block,
        "text_editor_code_execution_tool_result",
        ctx.emit_delta,
        summary_text="✏️ text_editor result",
    )
    result_block = getattr(content_block, "content", None)
    if not result_block:
        return

    result_type = getattr(result_block, "type", "")
    logger.debug("Text editor result type: %s", result_type)

    if result_type == "text_editor_code_execution_tool_result_error":
        error_code = getattr(result_block, "error_code", "unknown")
        logger.warning("text_editor_code_execution error: %s", error_code)
        await ctx.emit_block(f"⚠️ Text editor error: {error_code}")
        server_tool.last_code_content = ""
        return

    if _suppressed_as_web_filtering(server_tool):
        logger.debug("Suppressed text editor block (web filtering)")
        server_tool.last_code_content = ""
    elif result_type == "text_editor_code_execution_create_result":
        if server_tool.last_code_content and server_tool.last_code_language == "__inline_text__":
            # Plain-text files read better as prose than inside a code block.
            await ctx.emit_delta(f"\n\n{server_tool.last_code_content}\n\n")
            server_tool.last_code_content = ""
            server_tool.last_code_language = ""
        elif server_tool.last_code_content:
            duration = time.time() - server_tool.start_time if server_tool.start_time else None
            block = ctx.pipe._format_code_execution_block(
                server_tool.last_code_content,
                server_tool.last_code_language or "python",
                done=True,
                duration=duration,
            )
            await ctx.update_content_block(server_tool.last_block, block)
            server_tool.last_block = ""
            server_tool.last_code_content = ""
    elif result_type == "text_editor_code_execution_view_result":
        content = getattr(result_block, "content", "")
        if content:
            await ctx.emit_delta(
                f"\n<details>\n<summary>📄 File Content</summary>\n\n```\n{content}\n```\n</details>\n"
            )


async def _handle_generic_code_result(content_block: Any, ctx: Any) -> None:
    """Close the python code block and end the code-execution session."""
    server_tool = ctx.state.server_tool
    logger.debug("Processing code_execution_tool_result")
    await ctx.pipe._persist_server_tool_result(
        content_block,
        "code_execution_tool_result",
        ctx.emit_delta,
        summary_text="🐍 code_execution result",
    )
    result_block = getattr(content_block, "content", None)
    stdout = ""
    stderr = ""
    return_code = None
    download_links: list[str] = []

    if result_block:
        as_dict = isinstance(result_block, dict)
        result_block_type = (
            result_block.get("type", "") if as_dict else getattr(result_block, "type", "")
        )
        if result_block_type == "code_execution_tool_result_error":
            error_code = (
                result_block.get("error_code", "unknown") if as_dict
                else getattr(result_block, "error_code", "unknown")
            )
            logger.warning("code_execution error: %s", error_code)
            await ctx.emit_block(f"⚠️ Code execution error: {error_code}")
            server_tool.last_code_content = ""
            server_tool.in_code_execution = False
            server_tool.is_web_filtering = False
            return

        if as_dict:
            stdout = result_block.get("stdout", "")
            stderr = result_block.get("stderr", "")
            return_code = result_block.get("return_code", None)
            files_output = result_block.get("content", []) or []
        else:
            stdout = getattr(result_block, "stdout", "")
            stderr = getattr(result_block, "stderr", "")
            return_code = getattr(result_block, "return_code", None)
            files_output = getattr(result_block, "content", []) or []

        if files_output:
            logger.debug("Found %d generic code_execution file outputs", len(files_output))
        download_links = await _download_links_for(files_output, ctx)

    has_output = (
        stdout or stderr or return_code is not None
        or server_tool.tool_calls_info or download_links
    )
    if _suppressed_as_web_filtering(server_tool):
        logger.debug("Suppressed code_execution_tool_result (web filtering)")
        server_tool.last_code_content = ""
    elif has_output:
        duration = time.time() - server_tool.start_time if server_tool.start_time else None
        block = ctx.pipe._format_code_execution_block(
            server_tool.last_code_content or server_tool.current_code,
            "python",
            done=True,
            duration=duration,
            stdout=stdout,
            stderr=stderr,
            return_code=return_code,
            tool_calls_info=server_tool.tool_calls_info,
            download_links=download_links,
        )
        await ctx.update_content_block(server_tool.last_block, block)
        server_tool.last_block = ""
        server_tool.last_code_content = ""

    server_tool.end_code_execution()


_RESULT_HANDLERS = {
    "bash_code_execution_tool_result": _handle_bash_result,
    "text_editor_code_execution_tool_result": _handle_text_editor_result,
    "code_execution_tool_result": _handle_generic_code_result,
}


async def handle_code_execution_result_block_start(
    content_type: str, content_block: Any, ctx: Any
) -> None:
    """Handle ``bash_code_execution_tool_result``, ``text_editor_code_execution_tool_result``, and ``code_execution_tool_result`` content_block_start events; finalizes the running code block with stdout/stderr/return_code (and file download links) via update_content_block/emit_delta."""
    handler = _RESULT_HANDLERS.get(content_type)
    if handler:
        await handler(content_block, ctx)
