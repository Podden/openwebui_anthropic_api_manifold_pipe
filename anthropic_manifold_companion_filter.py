"""
title: Anthropic Manifold Companion
id: anthropic_manifold_companion
version: 1.0.1
description: Optional since Anthropic Pipe 0.11.2, which handles the Web Search / Code Interpreter buttons itself. Still needed with function calling set to "legacy", where OpenWebUI would run its own search before the pipe. Use with Podden's Anthropic Pipe.
author: Podden (https://github.com/Podden/)
"""
from typing import Any, Optional, Dict
from pydantic import BaseModel

class Filter:
    class Valves(BaseModel):
        pass

    def __init__(self):
        self.valves = self.Valves()
    async def inlet(
        self,
        body: Dict[str, Any],
        __metadata__: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        if __metadata__ is None:
            __metadata__ = {}
        features = body.get("features", {})
        if features.get("web_search"):
            features["web_search"] = False
            __metadata__["web_search_enforced"] = True
        if features.get("code_interpreter"):
            features["code_interpreter"] = False
            __metadata__["activate_code_execution_tool"] = True
        return body