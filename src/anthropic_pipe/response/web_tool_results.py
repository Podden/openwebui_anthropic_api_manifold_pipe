"""Web search/fetch server tool-result content-block handlers."""
from __future__ import annotations

import html
import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


async def handle_web_tool_result_block_start(
    content_type: str,
    content_block: Any,
    ctx: Any,
) -> None:
    """Handle ``web_search_tool_result`` and ``web_fetch_tool_result`` content_block_start events; merges the result into the matching server-tool-use carrier block and pushes it to OpenWebUI via update_content_block."""
    pipe = ctx.pipe
    server_tool_use_carriers = ctx.state.server_tool.use_carriers
    update_content_block = ctx.update_content_block
    if content_type == "web_search_tool_result":
        logger.debug(" Processing web search result event: %s", content_block)
        content_items = getattr(content_block, "content", None)
        tool_use_id = getattr(content_block, "tool_use_id", "") or ""
        error_code = None
        if content_items and not isinstance(content_items, list):
            content_inner_type = getattr(content_items, "type", "")
            if content_inner_type == "web_search_tool_result_error":
                error_code = getattr(content_items, "error_code", "unknown")
        if error_code:
            error_msg = f"⚠️ Web search error: {error_code}"
            logger.warning("web_search error: %s", error_code)
            err_payload = {"type": "web_search_tool_result_error", "error_code": error_code}
            carrier_info = server_tool_use_carriers.pop(tool_use_id, None) if tool_use_id else None
            if carrier_info:
                merged = pipe._format_server_tool_use_block(
                    tool_name=carrier_info["tool_name"],
                    tool_use_id=tool_use_id,
                    tool_input=carrier_info["tool_input"],
                    result_payload=err_payload,
                    result_block_type="web_search_tool_result",
                    result_summary=error_msg,
                    result_display_body=f"**{error_msg}** `{error_code}`",
                )
                await update_content_block(carrier_info["block"], merged)
        elif content_items and isinstance(content_items, list) and len(content_items) > 0:
            first_result = content_items[0] if content_items else None
            result_title = getattr(first_result, "title", "") if first_result else ""
            result_count = len(content_items)
            if result_title and result_count > 0:
                status_desc = f"Found {result_count} results - {result_title}"
                if result_count > 1:
                    status_desc += f" +{result_count-1} more"
            else:
                status_desc = "Web Search Complete"

            if tool_use_id:
                serialized_items = []
                display_lines = []
                for item in content_items:
                    if hasattr(item, "model_dump"):
                        item_d = item.model_dump(exclude_none=True)
                    elif isinstance(item, dict):
                        item_d = item
                    else:
                        continue
                    serialized_items.append(item_d)
                    title = item_d.get("title") or ""
                    url = item_d.get("url") or ""
                    if url:
                        display_lines.append(f"- [{html.escape(title or url)}]({url})")
                display_body = "\n".join(display_lines[:10])
                if status_desc:
                    display_body = f"**{status_desc}**\n\n{display_body}" if display_body else f"**{status_desc}**"
                # Hand the result urls to OpenWebUI's native web_search renderer so
                # the status line becomes a clickable source list instead of prose.
                await ctx.status.web_search_done(
                    [d.get("url") for d in serialized_items if d.get("url")],
                    query=ctx.state.text.current_search_query,
                )
                carrier_info = server_tool_use_carriers.pop(tool_use_id, None)
                if carrier_info:
                    merged = pipe._format_server_tool_use_block(
                        tool_name=carrier_info["tool_name"],
                        tool_use_id=tool_use_id,
                        tool_input=carrier_info["tool_input"],
                        result_payload=serialized_items,
                        result_block_type="web_search_tool_result",
                        result_summary=status_desc,
                        result_display_body=display_body,
                    )
                    await update_content_block(carrier_info["block"], merged)
        return

    if content_type == "web_fetch_tool_result":
        logger.debug("Processing web_fetch_tool_result")
        result_content = getattr(content_block, "content", None)
        tool_use_id = getattr(content_block, "tool_use_id", "") or ""
        error_code = None
        if result_content:
            content_type_inner = getattr(result_content, "type", "")
            if content_type_inner == "web_fetch_tool_error":
                error_code = getattr(result_content, "error_code", "unknown")
        if error_code:
            if tool_use_id:
                err_payload = {"type": "web_fetch_tool_error", "error_code": error_code}
                carrier_info = server_tool_use_carriers.pop(tool_use_id, None)
                if carrier_info:
                    merged = pipe._format_server_tool_use_block(
                        tool_name=carrier_info["tool_name"],
                        tool_use_id=tool_use_id,
                        tool_input=carrier_info["tool_input"],
                        result_payload=err_payload,
                        result_block_type="web_fetch_tool_result",
                        result_summary=f"🌐 Fetch failed: {error_code}",
                        result_display_body=f"**🌐 Fetch failed:** `{error_code}`",
                    )
                    await update_content_block(carrier_info["block"], merged)
        elif tool_use_id and result_content is not None:
            if hasattr(result_content, "model_dump"):
                serialized = result_content.model_dump(exclude_none=True)
            elif isinstance(result_content, dict):
                serialized = result_content
            else:
                serialized = None
            if serialized is not None:
                fetch_url = serialized.get("url") or "" if isinstance(serialized, dict) else ""
                display_body = f"**🌐 URL fetched:** {fetch_url}" if fetch_url else "**🌐 URL fetched**"
                carrier_info = server_tool_use_carriers.pop(tool_use_id, None)
                if carrier_info:
                    merged = pipe._format_server_tool_use_block(
                        tool_name=carrier_info["tool_name"],
                        tool_use_id=tool_use_id,
                        tool_input=carrier_info["tool_input"],
                        result_payload=serialized,
                        result_block_type="web_fetch_tool_result",
                        result_summary=f"🌐 URL fetched: {fetch_url}" if fetch_url else "🌐 URL fetched",
                        result_display_body=display_body,
                    )
                    await update_content_block(carrier_info["block"], merged)
