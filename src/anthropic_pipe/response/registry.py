"""Dispatch table mapping Anthropic content_block types to their handler.

The dispatcher stays boring: resolve a handler by block type and call one
lifecycle method. Every provider/OpenWebUI quirk lives in the handlers, grouped
by content block kind.

Handlers receive ``(event, ctx)`` — one ``PipeRequestContext`` carrying the emit
helpers, the request-scoped dependencies, and the mutable ``ctx.state``. There is
deliberately no separate handler-context type: one central object is the whole
point, so nothing has to be threaded through call after call.

Annotations stay untyped (``Any``) on purpose — the build compiles this module
into the single-file artifact and strips imports, so ``Protocol``/``StreamState``
would not resolve there.
"""
from __future__ import annotations

from typing import Any


class NoopHandler:
    """Fallback for content block types nothing handles; claims no event."""

    block_types: tuple[str, ...] = ()

    async def on_start(self, event: Any, ctx: Any) -> bool:
        """Ignore the block start."""
        return False

    async def on_delta(self, event: Any, ctx: Any) -> bool:
        """Ignore the block delta."""
        return False

    async def on_stop(self, event: Any, ctx: Any) -> bool:
        """Ignore the block stop."""
        return False


class HandlerRegistry:
    """Maps content_block type -> handler and drives its lifecycle methods.

    Each lifecycle method returns True when the handler took responsibility for
    the event, so a caller can tell "handled" from "nobody claimed it".
    """

    def __init__(self, handlers: list[Any] | None = None) -> None:
        """Build a registry, registering each handler for every type it claims."""
        self._handlers: dict[str, Any] = {}
        self._noop = NoopHandler()
        for handler in handlers or []:
            self.register(handler)

    def register(self, handler: Any) -> None:
        """Claim every block type the handler declares; a duplicate claim is a bug, not a merge."""
        for block_type in handler.block_types:
            if block_type in self._handlers:
                raise ValueError(f"Duplicate content block handler for {block_type!r}")
            self._handlers[block_type] = handler

    def for_block_type(self, block_type: str | None) -> Any:
        """Resolve the handler for a block type, or the no-op fallback."""
        if not block_type:
            return self._noop
        return self._handlers.get(block_type, self._noop)

    async def handle_start(self, event: Any, ctx: Any) -> bool:
        """Route a content_block_start, recording the block type for later deltas."""
        block = getattr(event, "content_block", None)
        block_type = getattr(block, "type", None)
        ctx.state.tool_use.current_block_type = block_type
        return await self.for_block_type(block_type).on_start(event, ctx)

    async def handle_delta(self, event: Any, ctx: Any) -> bool:
        """Route a content_block_delta using the block type recorded at start.

        Delta events carry no content_block of their own, which is why the start
        event has to stash the type.
        """
        return await self.for_block_type(ctx.state.tool_use.current_block_type).on_delta(event, ctx)

    async def handle_stop(self, event: Any, ctx: Any) -> bool:
        """Route a content_block_stop and clear the tracked block type.

        Raw SDK stop events can omit content_block, so fall back to the type
        recorded at start.
        """
        block = getattr(event, "content_block", None)
        block_type = getattr(block, "type", None) or ctx.state.tool_use.current_block_type
        handled = await self.for_block_type(block_type).on_stop(event, ctx)
        ctx.state.reset_current_block()
        return handled
