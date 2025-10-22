"""
title: Anthropic Web Search Toggle
author: Podden (https://github.com/Podden/)
id: anthropic_pipe_web_search_toggle_filter
description: Enforce web search for the next Claude message.  Use in combination with my Anthropic Pipe: https://openwebui.com/f/podden/anthropic_pipe
version: 0.1
"""

from __future__ import annotations
from typing import Any, Awaitable, Callable, Optional
from pydantic import BaseModel

class Filter:
    class Valves(BaseModel):
        pass

    def __init__(self):
        self.valves = self.Valves()
        self.toggle = True
        # Simple magnifying glass SVG icon (base64)
        self.icon = (
            "data:image/svg+xml;base64,"
            "PHN2ZyBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgdmlld0JveD0iMCAwIDI0IDI0IiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjxjaXJjbGUgY3g9IjExIiBjeT0iMTEiIHI9IjgiIHN0cm9rZT0iIzAwMCIgc3Ryb2tlLXdpZHRoPSIxLjUiLz48bGluZSB4MT0iMjAiIHkxPSIyMCIgeDI9IjE2LjY1IiB5Mj0iMTYuNjUiIHN0cm9rZT0iIzAwMCIgc3Ryb2tlLXdpZHRoPSIxLjUiLz48L3N2Zz4="
        )

    async def inlet(
        self,
        body: dict,
        __metadata__: Optional[dict] = None,
    ) -> dict:
        if self.toggle and __metadata__ is not None:
            __metadata__["web_search_enforced"] = True
        return body

    async def outlet(
        self,
        body: dict,
        __metadata__: Optional[dict] = None,
    ) -> dict:
        # No special outlet logic needed
        return body
