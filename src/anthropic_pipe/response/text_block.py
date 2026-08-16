"""``text`` content-block handling, including its citation markers.

Text is buffered rather than emitted per delta and flushed once on block stop:
OpenWebUI persists the last emitted message, so one flush per block keeps the
rebuild cheap and the citation markers correctly placed.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def handle_text_block_start(content_block: Any, ctx: Any) -> None:
    """Handle a ``text`` content_block_start; seeds the chunk buffer with any pre-populated text."""
    await ctx.status.responding()
    ctx.state.text.chunk += getattr(content_block, "text", "") or ""


async def handle_text_delta(delta: Any, ctx: Any) -> None:
    """Handle a ``text_delta`` content_block_delta; appends to the chunk buffer, flushed on stop."""
    text = ctx.state.text
    text.chunk += getattr(delta, "text", "")
    text.chunk_count += 1


async def handle_citations_delta(event: Any, ctx: Any) -> None:
    """Handle a ``citations_delta``; defers the marker so it lands after the text it cites.

    Web-search citations arrive BEFORE the text they annotate, so the marker for the
    previous citation is flushed into the chunk only once the next one shows up.
    """
    text = ctx.state.text
    if text.pending_citation_markers:
        text.chunk += "".join(f"[{n}]" for n in text.pending_citation_markers)
        text.pending_citation_markers = []
    text.citation_counter += 1
    text.pending_citation_markers.append(text.citation_counter)
    await ctx.pipe.handle_citation(event, ctx.event_emitter, text.citation_counter)


async def handle_text_block_stop(ctx: Any) -> None:
    """Handle a ``text`` content_block_stop; flushes buffered text (with citation markers) as a delta to OpenWebUI."""
    text = ctx.state.text
    if text.pending_citation_markers:
        text.chunk += "".join(f"[{n}]" for n in text.pending_citation_markers)
        text.pending_citation_markers = []
    if text.chunk:
        # Flushed verbatim. A text content_block is NOT a paragraph boundary: on a
        # cited answer Anthropic splits the prose around every citation, and those
        # splits land mid-table-row ("| "), mid-bullet ("- ") and mid-bold ("**").
        # Appending a separator newline here therefore breaks the markdown it was
        # meant to protect. Blocks that need their own line prepend it themselves
        # (ctx.emit_block / _append_block_to_text).
        await ctx.emit_delta(text.chunk)
        text.chunk = ""
        text.chunk_count = 0
