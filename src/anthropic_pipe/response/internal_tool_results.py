"""Advisor, tool-search, and context-management result handlers."""
from __future__ import annotations

import html
import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


def _serialize_content_payload(content: Any) -> Any:
    """Convert an SDK model or dict content payload into a plain JSON-serializable dict, or None."""
    if content is not None:
        if hasattr(content, "model_dump"):
            try:
                return content.model_dump(exclude_none=True, mode="json")
            except Exception:
                try:
                    return content.model_dump(exclude_none=True)
                except Exception:
                    return None
        if isinstance(content, dict):
            return content
    return None


def _extract_advisor_text(content: Any) -> str:
    """Pull the plaintext advice out of an ``advisor_result`` content payload.

    The advisor does not stream; its result arrives in a single
    ``advisor_tool_result`` block whose ``content`` is normally a
    ``{"type": "advisor_result", "text": ...}`` object (SDK model or dict).
    Handle object, dict, and the defensive list-wrapped shape so an unexpected
    SDK variant never renders an empty details block.
    """
    if content is None:
        return ""
    if isinstance(content, list):
        return "".join(_extract_advisor_text(part) for part in content)
    text = getattr(content, "text", None)
    if text is None and isinstance(content, dict):
        text = content.get("text")
    return (text or "").strip()



async def handle_advisor_result_block_start(content_block: Any, ctx: Any) -> None:
    """Handle an ``advisor_tool_result`` content_block_start; merges the advisor's advice (or error/redacted state) into the matching carrier block, or emits a standalone block, to OpenWebUI."""
    pipe = ctx.pipe
    server_tool_use_carriers = ctx.state.server_tool.use_carriers
    update_content_block = ctx.update_content_block
    emit_delta = ctx.emit_delta
    logger.debug(" Processing advisor result event: %s", content_block)
    tool_use_id = getattr(content_block, "tool_use_id", "") or ""
    content = getattr(content_block, "content", None)
    inner_type = (
        getattr(content, "type", "")
        if content is not None and hasattr(content, "type")
        else (content.get("type", "") if isinstance(content, dict) else "")
    )
    serialized_content = _serialize_content_payload(content) or {}

    if inner_type == "advisor_tool_result_error":
        error_code = (
            getattr(content, "error_code", "unknown")
            if hasattr(content, "error_code")
            else (content.get("error_code", "unknown") if isinstance(content, dict) else "unknown")
        )
        status_desc = f"🧑‍⚖️ Advisor error: {error_code}"
        display_body = f"**{status_desc}** `{html.escape(error_code)}`"
        logger.warning("advisor error: %s", error_code)
    elif inner_type == "advisor_redacted_result":
        status_desc = "🧑‍⚖️ Advisor: (redacted)"
        display_body = (
            "**🧑‍⚖️ Advisor consulted** _(encrypted output; "
            "content is decrypted server-side on the next turn)_"
        )
    else:
        advice_text = _extract_advisor_text(content)
        logger.info(
            "advisor result: inner_type=%s text_len=%d", inner_type, len(advice_text)
        )
        preview = advice_text.strip().splitlines()[0] if advice_text.strip() else ""
        status_desc = f"🧑‍⚖️ Advisor: {preview[:80]}" if preview else "🧑‍⚖️ Advisor consulted"
        display_body = advice_text.strip() if advice_text.strip() else "**🧑‍⚖️ Advisor consulted** _(empty response)_"

    if tool_use_id:
        carrier_info = server_tool_use_carriers.pop(tool_use_id, None)
        if carrier_info:
            merged = pipe._format_server_tool_use_block(
                tool_name=carrier_info["tool_name"],
                tool_use_id=tool_use_id,
                tool_input=carrier_info["tool_input"],
                result_payload=serialized_content,
                result_block_type="advisor_tool_result",
                result_summary=status_desc,
                result_display_body=display_body,
            )
            await update_content_block(carrier_info["block"], merged)
        else:
            standalone = pipe._format_server_tool_result_block(
                block_type="advisor_tool_result",
                tool_use_id=tool_use_id,
                content_payload=serialized_content,
                display_body=display_body,
                summary_text=status_desc,
            )
            await ctx.emit_block(standalone)


async def handle_tool_search_result_block_start(content_block: Any, ctx: Any) -> None:
    """Handle a ``tool_search_tool_result`` content_block_start; merges the found tool references into the matching carrier block, or emits a standalone block, to OpenWebUI."""
    pipe = ctx.pipe
    server_tool_use_carriers = ctx.state.server_tool.use_carriers
    update_content_block = ctx.update_content_block
    emit_delta = ctx.emit_delta
    logger.debug(" Processing tool search result event: %s", content_block)
    tool_use_id = getattr(content_block, "tool_use_id", "") or ""
    content_obj = getattr(content_block, "content", None)
    tool_references = []
    if content_obj:
        if hasattr(content_obj, "tool_references"):
            tool_references = getattr(content_obj, "tool_references", []) or []
        elif isinstance(content_obj, dict):
            tool_references = content_obj.get("tool_references", []) or []
    tool_names = []
    for ref in tool_references:
        if hasattr(ref, "tool_name"):
            tool_names.append(getattr(ref, "tool_name", "unknown"))
        elif isinstance(ref, dict):
            tool_names.append(ref.get("tool_name", "unknown"))

    if tool_names:
        status_desc = (
            f"🧰 Found {len(tool_names)} tool(s): "
            f"{', '.join(tool_names[:5])}"
            + (f" +{len(tool_names)-5} more" if len(tool_names) > 5 else "")
        )
    else:
        status_desc = "🧰 Tool search: no matching tools"
    display_body = status_desc

    serialized_content = _serialize_content_payload(content_obj)
    if serialized_content is None:
        serialized_content = {
            "tool_references": [
                {"type": "tool_reference", "tool_name": name}
                for name in tool_names
            ],
        }

    if tool_use_id:
        carrier_info = server_tool_use_carriers.pop(tool_use_id, None)
        if carrier_info:
            merged = pipe._format_server_tool_use_block(
                tool_name=carrier_info["tool_name"],
                tool_use_id=tool_use_id,
                tool_input=carrier_info["tool_input"],
                result_payload=serialized_content,
                result_block_type="tool_search_tool_result",
                result_summary=status_desc,
                result_display_body=display_body,
            )
            await update_content_block(carrier_info["block"], merged)
        else:
            standalone = pipe._format_server_tool_result_block(
                block_type="tool_search_tool_result",
                tool_use_id=tool_use_id,
                content_payload=serialized_content,
                display_body=display_body,
                summary_text=status_desc,
            )
            await ctx.emit_block(standalone)


async def handle_context_cleared_block_start(content_block: Any, ctx: Any) -> None:
    """Handle a ``context_management`` content_block_start (context_cleared event); emits a status describing how many tokens were cleared."""
    cleared_info = getattr(content_block, "cleared", {})
    cleared_type = (
        getattr(cleared_info, "type", "unknown")
        if hasattr(cleared_info, "type")
        else cleared_info.get("type", "unknown")
    )
    cleared_tokens = (
        getattr(cleared_info, "tokens_cleared", 0)
        if hasattr(cleared_info, "tokens_cleared")
        else cleared_info.get("tokens_cleared", 0)
    )

    if cleared_type == "tool_uses":
        status_desc = f"🧹 Cleared tool results: ~{cleared_tokens:,} tokens removed"
    elif cleared_type == "thinking":
        status_desc = f"🧹 Cleared thinking blocks: ~{cleared_tokens:,} tokens removed"
    else:
        status_desc = f"🧹 Context cleared: ~{cleared_tokens:,} tokens removed"

    # activity, not complete: context editing happens mid-turn, and a done=True
    # status would close the line while the model keeps generating.
    await ctx.status.activity(status_desc)
    logger.debug("Context cleared: type=%s, tokens=%s", cleared_type, cleared_tokens)
