"""
title: Anthropic Code Execution Toggle
author: Podden (https://github.com/Podden/)
github: https://github.com/Podden/openwebui_anthropic_api_manifold_pipe
id: anthropic_pipe_code_execution_toggle_filter
description: Toggles Anthropic code execution tool for the next Claude message. Use in combination with my Anthropic Pipe: https://openwebui.com/f/podden/anthropic_pipe
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
        # Simple terminal/gear icon (base64 SVG)
        self.icon = (
            "data:image/svg+xml;base64,"  # terminal with gear
            "PHN2ZyB2aWV3Qm94PSIwIDAgMjQgMjQiIGZpbGw9Im5vbmUiIHN0cm9rZT0iY3VycmVudENvbG9yIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPiAgPHBhdGggc3Ryb2tlLXdpZHRoPSIxLjUiIGQ9Ik0zIDVoMTh2MTRIM1oiLz4gIDxwYXRoIHN0cm9rZS13aWR0aD0iMS41IiBkPSJNNSA5aDQiLz4gIDxwYXRoIHN0cm9rZS13aWR0aD0iMS41IiBkPSJNNSA3aDQiLz4gIDxwYXRoIHN0cm9rZS13aWR0aD0iMS41IiBkPSJNMTAgMTNoNCIvPiAgPHBhdGggc3Ryb2tlLXdpZHRoPSIxLjUiIGQ9Ik0xNiAxNC4xMmE0IDQgMCAxIDEgMCAxLjc2Ii8+ICA8cGF0aCBzdHJva2Utd2lkdGg9IjEuNSIgZD0iTTE4LjI1IDE1LjI1bDEuMDctLjUzTTIxIDE1LjEyQTQgNCAwIDAgMCAxNiAxNC4xMiIvPiAgPC9zdmc+"
        )

    async def inlet(
        self,
        body: dict,
        __event_emitter__: Callable[[dict[str, Any]], Awaitable[None]],
        __metadata__: Optional[dict] = None,
    ) -> dict:
        if self.toggle and __metadata__ is not None:
            __metadata__["activate_code_execution_tool"] = True
        return body

    async def outlet(
        self,
        body: dict,
        __metadata__: Optional[dict] = None,
    ) -> dict:
        return body
