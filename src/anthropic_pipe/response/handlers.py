"""Content-block handlers, one class per Anthropic content_block family.

Each class declares the ``block_types`` it owns and overrides only the lifecycle
methods that block actually has. Everything a handler needs arrives on ``ctx``
(a ``PipeRequestContext``): emit helpers, request-scoped dependencies, and the
mutable ``ctx.state``.

Handler bodies delegate to the ``handle_*`` functions in the sibling block
modules. That keeps this file a readable map of "which block type goes where"
instead of a second place where block logic hides.

Annotations stay untyped (``Any``) on purpose — the build compiles this module
into the single-file artifact and strips imports, so the real types would not
resolve there.
"""
from __future__ import annotations

from typing import Any


class BaseHandler:
    """Default handler: claims its block types but ignores every lifecycle event.

    Subclasses override only the lifecycle hooks their block type emits — a
    result-only block needs `on_start` alone, and inheriting the rest as
    "unhandled" is the intended behaviour, not an omission.
    """

    block_types: tuple[str, ...] = ()

    async def on_start(self, event: Any, ctx: Any) -> bool:
        """Handle content_block_start; return True when the event was consumed."""
        return False

    async def on_delta(self, event: Any, ctx: Any) -> bool:
        """Handle content_block_delta; return True when the event was consumed."""
        return False

    async def on_stop(self, event: Any, ctx: Any) -> bool:
        """Handle content_block_stop; return True when the event was consumed."""
        return False


class TextBlockHandler(BaseHandler):
    """Assistant prose. Buffers deltas and flushes them on stop, with citation markers."""

    block_types = ("text",)

    async def on_start(self, event: Any, ctx: Any) -> bool:
        """Seed the buffer with any text the block already carries."""
        await handle_text_block_start(getattr(event, "content_block", None), ctx)
        return True

    async def on_delta(self, event: Any, ctx: Any) -> bool:
        """Buffer a text delta, or record a citation marker."""
        delta = getattr(event, "delta", None)
        delta_type = getattr(delta, "type", None)
        if delta_type == "text_delta":
            await handle_text_delta(delta, ctx)
            return True
        if delta_type == "citations_delta":
            await handle_citations_delta(event, ctx)
            return True
        return False

    async def on_stop(self, event: Any, ctx: Any) -> bool:
        """Flush the buffered text as one delta."""
        await handle_text_block_stop(ctx)
        return True


class ThinkingBlockHandler(BaseHandler):
    """Extended thinking, including redacted variants and the signature carrier."""

    block_types = ("thinking", "redacted_thinking")

    async def on_start(self, event: Any, ctx: Any) -> bool:
        """Start tracking a thinking block; redacted blocks carry no text to stream."""
        block_type = getattr(getattr(event, "content_block", None), "type", None)
        if block_type == "redacted_thinking":
            await handle_redacted_thinking_block_start(ctx)
        else:
            await handle_thinking_block_start(ctx)
        return True

    async def on_delta(self, event: Any, ctx: Any) -> bool:
        """Stream reasoning text, or accumulate the signature that authenticates it."""
        delta = getattr(event, "delta", None)
        delta_type = getattr(delta, "type", None)
        if delta_type == "thinking_delta":
            await handle_thinking_delta(delta, ctx)
            return True
        if delta_type == "signature_delta":
            handle_signature_delta(delta, ctx)
            return True
        return False

    async def on_stop(self, event: Any, ctx: Any) -> bool:
        """Finalize the block, stamping it with its duration."""
        block = getattr(event, "content_block", None)
        block_type = getattr(block, "type", None) or ctx.state.tool_use.current_block_type
        await handle_thinking_block_stop(block_type, ctx)
        return True


class CompactionBlockHandler(BaseHandler):
    """Server-side context compaction summary."""

    block_types = ("compaction",)

    async def on_start(self, event: Any, ctx: Any) -> bool:
        """Reset the compaction buffer and tell the user compaction began."""
        await handle_compaction_block_start(ctx)
        return True

    async def on_delta(self, event: Any, ctx: Any) -> bool:
        """Stream the summary as it arrives; ignore deltas of any other kind."""
        delta = getattr(event, "delta", None)
        if getattr(delta, "type", None) != "compaction_delta":
            return False
        await handle_compaction_delta(delta, ctx)
        return True

    async def on_stop(self, event: Any, ctx: Any) -> bool:
        """Report the finished summary size."""
        await handle_compaction_block_stop(ctx)
        return True


class ClientToolUseBlockHandler(BaseHandler):
    """OpenWebUI-side tool calls: the pipe executes these and feeds results back."""

    block_types = ("tool_use",)

    async def on_start(self, event: Any, ctx: Any) -> bool:
        """Open an in-progress tool-call block and start buffering the call JSON."""
        await handle_tool_use_block_start(getattr(event, "content_block", None), ctx)
        return True

    async def on_delta(self, event: Any, ctx: Any) -> bool:
        """Buffer the streamed input JSON, re-rendering the block as it becomes parseable."""
        delta = getattr(event, "delta", None)
        if getattr(delta, "type", None) != "input_json_delta":
            return False
        await handle_client_tool_input_delta(getattr(delta, "partial_json", ""), ctx)
        return True

    async def on_stop(self, event: Any, ctx: Any) -> bool:
        """Dispatch the completed call as a background task."""
        await handle_tool_use_block_stop(ctx)
        return True


class ServerToolUseBlockHandler(BaseHandler):
    """Anthropic-hosted tool invocations (web search/fetch, code execution, editor)."""

    block_types = ("server_tool_use",)

    async def on_start(self, event: Any, ctx: Any) -> bool:
        """Announce the tool and, for code execution, close any block still open."""
        await handle_server_tool_use_block_start(getattr(event, "content_block", None), ctx)
        return True

    async def on_delta(self, event: Any, ctx: Any) -> bool:
        """Stream the live code/query preview as the input JSON accumulates."""
        delta = getattr(event, "delta", None)
        if getattr(delta, "type", None) != "input_json_delta":
            return False
        await handle_server_tool_input_delta(getattr(delta, "partial_json", ""), ctx)
        return True

    async def on_stop(self, event: Any, ctx: Any) -> bool:
        """Emit the carrier block the matching result will later merge into."""
        await handle_server_tool_use_block_stop(ctx)
        return True


class WebSearchResultBlockHandler(BaseHandler):
    """Results for a web_search server tool call."""

    block_types = ("web_search_tool_result",)

    async def on_start(self, event: Any, ctx: Any) -> bool:
        """Merge the search results into the carrier block opened by server_tool_use."""
        block = getattr(event, "content_block", None)
        await handle_web_tool_result_block_start("web_search_tool_result", block, ctx)
        return True


class WebFetchResultBlockHandler(BaseHandler):
    """Results for a web_fetch server tool call."""

    block_types = ("web_fetch_tool_result",)

    async def on_start(self, event: Any, ctx: Any) -> bool:
        """Merge the fetched page into the carrier block opened by server_tool_use."""
        block = getattr(event, "content_block", None)
        await handle_web_tool_result_block_start("web_fetch_tool_result", block, ctx)
        return True


class CodeExecutionResultBlockHandler(BaseHandler):
    """Results for code execution, covering the bash and text-editor variants."""

    block_types = (
        "code_execution_tool_result",
        "bash_code_execution_tool_result",
        "text_editor_code_execution_tool_result",
    )

    async def on_start(self, event: Any, ctx: Any) -> bool:
        """Close the running code block with the output this result carries."""
        block = getattr(event, "content_block", None)
        await handle_code_execution_result_block_start(
            getattr(block, "type", ""), block, ctx
        )
        return True


class ToolSearchResultBlockHandler(BaseHandler):
    """Results for a tool_search server tool call."""

    block_types = ("tool_search_tool_result",)

    async def on_start(self, event: Any, ctx: Any) -> bool:
        """Merge the found tool references into the carrier block, or emit standalone."""
        await handle_tool_search_result_block_start(getattr(event, "content_block", None), ctx)
        return True


class AdvisorResultBlockHandler(BaseHandler):
    """Results for an advisor tool call."""

    block_types = ("advisor_tool_result",)

    async def on_start(self, event: Any, ctx: Any) -> bool:
        """Merge the advice (or error/redacted state) into the carrier block, or emit standalone."""
        await handle_advisor_result_block_start(getattr(event, "content_block", None), ctx)
        return True


class ContextClearedBlockHandler(BaseHandler):
    """Notice that context editing dropped earlier tool results or thinking."""

    block_types = ("context_cleared",)

    async def on_start(self, event: Any, ctx: Any) -> bool:
        """Report how many tokens context editing removed."""
        await handle_context_cleared_block_start(getattr(event, "content_block", None), ctx)
        return True


def default_handlers() -> list[Any]:
    """Every handler the pipe registers, one per content_block family."""
    return [
        TextBlockHandler(),
        ThinkingBlockHandler(),
        CompactionBlockHandler(),
        ClientToolUseBlockHandler(),
        ServerToolUseBlockHandler(),
        WebSearchResultBlockHandler(),
        WebFetchResultBlockHandler(),
        CodeExecutionResultBlockHandler(),
        ToolSearchResultBlockHandler(),
        AdvisorResultBlockHandler(),
        ContextClearedBlockHandler(),
    ]
