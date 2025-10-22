"""
title: Anthropic Thinking Toggle
author: Podden (https://github.com/Podden/)
github: https://github.com/Podden/openwebui_anthropic_api_manifold_pipe
id: anthropic_pipe_thinking_toggle_filter
description: Instruct the Anthropic model to use reasoning for the next message. Use in combination with my Anthropic Pipe: https://openwebui.com/f/podden/anthropic_pipe
version: 0.3
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

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
        if __metadata__:
            __metadata__["anthropic_thinking"] = True
        return body