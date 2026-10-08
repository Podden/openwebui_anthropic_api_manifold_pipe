"""Self-check regression test for the Fast Mode beta-header bug.

``create_request_payload`` sets ``payload["speed"] = "fast"`` whenever fast
mode is requested either via the admin valve (``ENABLE_FAST_MODE``) OR the
per-message toggle (``__metadata__["anthropic_fast"]``), gated on the model
supporting it. The ``anthropic-beta`` header must follow that same decision
(``fast-mode-2026-02-01``). The bug being guarded here: the beta header was
previously gated on the valve alone, so a per-message toggle set
``payload["speed"] = "fast"`` without sending the beta header the API needs
to honour it.

Runs without OpenWebUI and without network access: ``create_request_payload``
is exercised directly, with a minimal fake ``pipe``/``__user__``/body that
walks the function down to the beta-header assembly without raising.

Usage:
    python helpers/test_fast_mode_header.py
"""
from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "anthropic_pipe" / "request" / "payload.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("_payload", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_payload"] = module
    spec.loader.exec_module(module)
    # The compiled artifact resolves this from module scope. Our fake calls
    # never actually reach the branch that reads it (no __files__ passed),
    # but set it defensively so the name always exists.
    module.FILES_AVAILABLE = False
    return module


class FakeValves:
    """Admin-level valves touched by create_request_payload before the
    beta-header assembly."""

    def __init__(self, **kwargs):
        self.DATA_RESIDENCY = "global"
        self.ENABLE_FAST_MODE = False
        self.CACHE_CONTROL = "cache disabled"
        self.ENABLE_PROGRAMMATIC_TOOL_CALLING = False
        self.ENABLE_INTERLEAVED_THINKING = False
        self.WEB_FETCH = False
        self.ANTHROPIC_API_KEY = "sk-admin-key"
        self.REFUSAL_FALLBACK = "off"
        self.ENABLE_CACHE_DIAGNOSTICS = False
        self.__dict__.update(kwargs)


class FakeUserValves:
    """Per-user valves touched by create_request_payload before the
    beta-header assembly."""

    def __init__(self, **kwargs):
        self.ENABLE_THINKING = False
        self.SKILLS: List[str] = []
        self.USE_FILES_API = False
        self.USE_PDF_NATIVE_UPLOAD = False
        self.ENABLE_TOOL_SEARCH = False
        self.ENABLE_ADVISOR_TOOL = False
        self.CONTEXT_EDITING_STRATEGY = "none"
        self.ENABLE_COMPACTION = False
        self.__dict__.update(kwargs)


class FakePipe:
    """Minimal stand-in exposing only what create_request_payload touches
    before (and up to) the beta-header assembly for a fast-mode-only path:
    no files, no tools, no thinking, no skills, no compaction."""

    API_VERSION = "2026-01-01"

    def __init__(self, valves: FakeValves, supports_fast_mode: bool):
        self.valves = valves
        self._supports_fast_mode = supports_fast_mode

    def get_model_info(self, actual_model_name: str) -> Dict[str, Any]:
        return {
            "max_tokens": 64000,
            "supports_effort": False,
            "supports_thinking": False,
            "supports_fast_mode": self._supports_fast_mode,
        }

    def _convert_messages_to_claude_format(self, raw_messages):
        # (system_messages, processed_messages, previous_marker_metadata)
        return [], [], []

    async def _get_full_context_texts(self, *args, **kwargs):
        # (blocks_by_user_msg, markers, filenames) -- nothing to anchor.
        return {}, [], []

    def _convert_tools_to_claude_format(self, *args, **kwargs):
        # (tools_list, api_tool_names)
        return [], []

    def _canonicalize_block(self, block):
        return block


async def _noop_event_emitter(event: Dict[str, Any]) -> None:
    """Async no-op standing in for OpenWebUI's __event_emitter__."""


def build_pipe(
    module,
    *,
    enable_fast_mode_valve: bool,
    supports_fast_mode: bool,
) -> FakePipe:
    valves = FakeValves(ENABLE_FAST_MODE=enable_fast_mode_valve)
    return FakePipe(valves, supports_fast_mode)


async def _call(
    module,
    pipe: FakePipe,
    *,
    anthropic_fast_metadata: Optional[bool] = None,
):
    body = {"model": "anthropic/claude-test-fast", "messages": []}
    metadata: Dict[str, Any] = {}
    if anthropic_fast_metadata is not None:
        metadata["anthropic_fast"] = anthropic_fast_metadata
    user = {"valves": FakeUserValves()}
    return await module.create_request_payload(
        pipe, body, metadata, user, None, _noop_event_emitter, None
    )


async def test_metadata_toggle_without_valve_sends_beta_header(module):
    """The bug: ENABLE_FAST_MODE off, but the per-message toggle requests
    fast mode on a fast-capable model -- the beta header must be sent."""
    pipe = build_pipe(module, enable_fast_mode_valve=False, supports_fast_mode=True)
    payload, headers, _marker_metadata, _api_tool_names = await _call(
        module, pipe, anthropic_fast_metadata=True
    )
    assert payload.get("speed") == "fast", (
        f"expected payload['speed'] == 'fast', got {payload.get('speed')!r}"
    )
    beta_header = headers.get("anthropic-beta", "")
    assert "fast-mode-2026-02-01" in beta_header.split(","), (
        "per-message fast-mode toggle must send the fast-mode beta header, "
        f"got anthropic-beta={beta_header!r}"
    )


async def test_no_fast_request_omits_speed_and_header(module):
    """Negative: neither the valve nor the per-message toggle requests fast
    mode -- no speed field, no beta header, even though the model supports
    fast mode."""
    pipe = build_pipe(module, enable_fast_mode_valve=False, supports_fast_mode=True)
    payload, headers, _marker_metadata, _api_tool_names = await _call(module, pipe)
    assert "speed" not in payload, f"expected no payload['speed'], got {payload.get('speed')!r}"
    beta_header = headers.get("anthropic-beta", "")
    assert "fast-mode-2026-02-01" not in beta_header.split(","), (
        f"fast-mode beta header must be absent, got anthropic-beta={beta_header!r}"
    )


async def test_admin_valve_alone_still_sends_beta_header(module):
    """The valve-only path (admin turns fast mode on for every request) must
    keep working after the fix."""
    pipe = build_pipe(module, enable_fast_mode_valve=True, supports_fast_mode=True)
    payload, headers, _marker_metadata, _api_tool_names = await _call(module, pipe)
    assert payload.get("speed") == "fast", (
        f"expected payload['speed'] == 'fast', got {payload.get('speed')!r}"
    )
    beta_header = headers.get("anthropic-beta", "")
    assert "fast-mode-2026-02-01" in beta_header.split(","), (
        f"admin-valve fast mode must send the fast-mode beta header, got anthropic-beta={beta_header!r}"
    )


async def main():
    module = _load_module()
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        await test(module)
        print(f"  ok  {test.__name__}")
    print(f"\n{len(tests)} checks passed")


if __name__ == "__main__":
    asyncio.run(main())
