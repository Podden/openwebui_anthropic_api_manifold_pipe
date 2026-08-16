"""``thinking`` / ``redacted_thinking`` content-block handling.

The block is re-rendered in place on every delta (one collapsible, not one per
delta) and stamped with its duration on stop. The signature accumulated from
``signature_delta`` must survive into the emitted block: it is what authenticates
the reasoning for replay on the next turn, and a signed block with empty text
(``THINKING_DISPLAY=omitted``) still has to be persisted.
"""
from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


async def handle_thinking_block_start(ctx: Any) -> None:
    """Handle a ``thinking`` content_block_start; initializes thinking-state tracking and announces the phase."""
    await ctx.status.thinking()
    thinking = ctx.state.thinking
    thinking.is_active = True
    thinking.start_time = time.time()
    thinking.message = ""
    thinking.signature = ""
    thinking.stream_start_idx = len(ctx.final_message)


async def handle_redacted_thinking_block_start(ctx: Any) -> None:
    """Handle a ``redacted_thinking`` content_block_start; marks the model as thinking.

    Redacted reasoning has no readable text, so the status line is the only signal
    the user gets that the model is working.
    """
    await ctx.status.thinking()
    ctx.state.thinking.is_active = True


async def handle_thinking_delta(delta: Any, ctx: Any) -> None:
    """Handle a ``thinking_delta`` content_block_delta; streams the formatted thinking block via update_content_block."""
    thinking = ctx.state.thinking
    thinking_text = getattr(delta, "thinking", "")
    thinking.message += thinking_text
    if thinking_text:
        formatted = ctx.pipe._format_thinking_block(thinking.message, duration=None)
        await ctx.update_content_block(thinking.last_block, formatted)
        thinking.last_block = formatted


def handle_signature_delta(delta: Any, ctx: Any) -> None:
    """Handle a ``signature_delta`` content_block_delta; appends to the thinking signature buffer, no emission."""
    ctx.state.thinking.signature += getattr(delta, "signature", "") or ""


async def handle_thinking_block_stop(content_type: str, ctx: Any) -> None:
    """Handle a ``thinking``/``redacted_thinking`` content_block_stop; finalizes and emits the thinking block with duration."""
    thinking = ctx.state.thinking
    if not thinking.is_active or content_type not in ("thinking", "redacted_thinking"):
        return

    if content_type == "thinking" and (thinking.message or thinking.signature):
        duration = time.time() - (thinking.start_time or time.time())
        formatted = ctx.pipe._format_thinking_block(
            thinking.message, duration, signature=thinking.signature
        )
        await ctx.update_content_block(thinking.last_block, formatted)
        thinking.last_block = ""
        logger.debug(
            "Finalized thinking block (%d chars, %.1fs, sig=%dc)",
            len(thinking.message),
            duration,
            len(thinking.signature),
        )
    elif content_type == "redacted_thinking":
        logger.debug("Redacted thinking block completed (preserved by SDK)")

    thinking.is_active = False
    thinking.message = ""
    thinking.signature = ""
    thinking.stream_start_idx = -1
