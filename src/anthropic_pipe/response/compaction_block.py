"""``compaction`` content-block handling.

Server-side compaction summarizes earlier turns; the summary streams into one
collapsible block while a status line tells the user why the pause is happening.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def handle_compaction_block_start(ctx: Any) -> None:
    """Handle a ``compaction`` content_block_start; emits a "Compacting..." status to OpenWebUI."""
    ctx.state.compaction.content = ""
    ctx.state.compaction.last_block = ""
    await ctx.status.compacting()
    logger.info("Compaction block started")


async def handle_compaction_delta(delta: Any, ctx: Any) -> None:
    """Handle a ``compaction_delta`` content_block_delta; streams the formatted compaction summary via update_content_block."""
    compaction = ctx.state.compaction
    compaction.content += getattr(delta, "content", "")
    formatted = ctx.pipe._format_compaction_block(compaction.content)
    await ctx.update_content_block(compaction.last_block, formatted)
    compaction.last_block = formatted


async def handle_compaction_block_stop(ctx: Any) -> None:
    """Handle a ``compaction`` content_block_stop; reports the compacted summary size.

    Uses `activity`, not `complete`: the turn continues after compaction, and a
    `done=True` status mid-stream closes the line while work is still running.
    """
    content = ctx.state.compaction.content
    logger.info("Compaction summary complete: %d chars", len(content))
    await ctx.status.activity(f"📦 Context compacted ({len(content)} chars summary)")
