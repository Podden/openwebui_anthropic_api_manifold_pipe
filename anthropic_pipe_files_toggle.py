"""
title: Anthropic Files API Toggle
author: Podden (https://github.com/Podden/)
github: https://github.com/Podden/openwebui_anthropic_api_manifold_pipe
id: anthropic_pipe_files_toggle_filter
description: Enforces Files API mode for Anthropic Pipe, enabling Skills (pptx, xlsx, docx, pdf) and Code Execution. The pipe handles all file processing. Use with: https://openwebui.com/f/podden/anthropic_pipe
version: 0.3.0
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Filter:
    class Valves(BaseModel):
        DEBUG: bool = Field(
            default=False,
            description="Enable debug logging",
        )

    def __init__(self) -> None:
        self.valves = self.Valves()
        self.toggle = True
        # When True, tells OpenWebUI to skip its RAG file processing
        self.file_handler = True
        # File upload icon (document with arrow)
        self.icon = (
            "data:image/svg+xml;base64,"
            "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0xNCAySDZhMiAyIDAgMCAwLTIgMnYxNmEyIDIgMCAwIDAgMiAyaDEyYTIgMiAwIDAgMCAyLTJWOHoiPjwvcGF0aD48cG9seWxpbmUgcG9pbnRzPSIxNCAyIDE0IDggMjAgOCI+PC9wb2x5bGluZT48bGluZSB4MT0iMTIiIHkxPSIxOCIgeDI9IjEyIiB5Mj0iMTIiPjwvbGluZT48bGluZSB4MT0iOSIgeTE9IjE1IiB4Mj0iMTUiIHkyPSIxNSI+PC9saW5lPjwvc3ZnPg=="
        )

    async def inlet(
        self,
        body: Dict[str, Any],
        __event_emitter__: Callable[[Dict[str, Any]], Awaitable[None]] = None,
        __metadata__: Optional[Dict] = None,
        __user__: Optional[Dict] = None,
        __request__: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Enforces Files API mode when this filter is active.
        The pipe will handle all file processing, uploading, and Skills/Code Execution.
        """
        if not self.toggle:
            return body

        if __metadata__ is None:
            __metadata__ = {}

        # Enforce Files API mode - the pipe will handle everything
        __metadata__["enforce_files_api"] = True

        if self.valves.DEBUG:
            logger.debug("Files API enforcement enabled - pipe will handle file processing")

        # Notify user that Files API mode is active
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": "📄 Files API mode active - pipe will process files",
                        "done": True,
                    },
                }
            )

        return body
