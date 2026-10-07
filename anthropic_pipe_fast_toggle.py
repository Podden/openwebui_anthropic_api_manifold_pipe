"""
title: Anthropic Fast Mode Toggle
author: Podden (https://github.com/Podden/)
github: https://github.com/Podden/openwebui_anthropic_api_manifold_pipe
id: anthropic_pipe_fast_toggle_filter
description: Request a faster, shallower response for the next message. Opus 5 / Opus 4.8 only. Use in combination with my Anthropic Pipe: https://openwebui.com/f/podden/anthropic_pipe
version: 0.1
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel


class Filter:
    class Valves(BaseModel):
        pass

    def __init__(self) -> None:
        self.valves = self.Valves()
        self.toggle = True

    async def inlet(
        self,
        body: Dict[str, Any],
        __metadata__: Optional[dict] = None,
    ) -> Dict[str, Any]:
        # The pipe gates this on the model actually supporting fast mode, so
        # leaving the toggle on while switching to a model without it is a
        # no-op rather than a 400.
        # `is not None`, not truthiness: an empty metadata dict is falsy but
        # still the dict the pipe will read.
        if __metadata__ is not None:
            __metadata__["anthropic_fast"] = True
        return body
