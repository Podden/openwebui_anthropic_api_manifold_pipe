"""Self-check regression test for the v0.9.33 fast-mode 429 fallback.

``Pipe.pipe()`` sends a fast-speed request (``payload["speed"] == "fast"``)
without SDK retries (``client.with_options(max_retries=0)``). If that call
gets a 429 (``RateLimitError``), the fallback in the ``except Exception as e:``
handler must retry the same turn at standard speed instead of failing after
the usual backoff/retry machinery: it pops ``payload_for_stream["speed"]``,
strips ``"fast-mode-2026-02-01"`` from ``payload_for_stream["betas"]``, emits a
warning notification, and ``continue``s the tool loop WITHOUT incrementing
``retry_attempts``.

Runs without OpenWebUI and without network access: loads the compiled,
fully-assembled artifact (``anthropic_pipe.py`` at the repo root -- the one
that actually ships) and replaces the module-global ``AsyncAnthropic`` with a
fake that records every ``beta.messages.stream(**kwargs)`` call. The first
call raises ``RateLimitError`` (429); the second call returns a minimal clean
stream (one ``message_delta`` with ``stop_reason="end_turn"``, then
``message_stop``) so the turn ends normally and no third call happens.

Usage:
    python helpers/test_fast_mode_fallback.py
"""
from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import httpx

ARTIFACT = Path(__file__).resolve().parents[1] / "anthropic_pipe.py"


def _load_module():
    """Load the compiled single-file artifact as a fresh module.

    ``pipe()`` cannot be loaded from ``src/anthropic_pipe/pipe_orchestrator.py``
    in isolation -- it needs names (``RateLimitError``, ``AsyncAnthropic``,
    ``StatusEmitter``, ``PipeRequestContext``, the response handlers, ...)
    that only exist once everything is assembled. The artifact already
    imports cleanly without ``open_webui`` installed: every ``open_webui``
    import in it is wrapped in its own ``try/except`` with an ``*_AVAILABLE``
    flag (see ``helpers/test_valve_encryption.py`` for the same assumption).
    """
    spec = importlib.util.spec_from_file_location("_fast_mode_fallback_pipe", ARTIFACT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_fast_mode_fallback_pipe"] = module
    spec.loader.exec_module(module)
    return module


def _build_fake_async_anthropic(module, stream_calls: List[Dict[str, Any]], with_options_calls: List[Dict[str, Any]]):
    """Build a fake ``AsyncAnthropic`` replacement.

    ``stream_calls`` records the full kwargs of every
    ``beta.messages.stream(**kwargs)`` call, in order. Call #1 (index 0) is
    the fast-mode request and raises ``RateLimitError`` (429) on
    ``__aenter__``. Call #2 (index 1) is the standard-speed retry and returns
    a minimal clean stream that ends the turn with ``stop_reason="end_turn"``
    -- no tool calls, so the tool loop does not fire a third call.

    ``with_options_calls`` records every ``client.with_options(**kwargs)``
    call. ``pipe()`` only calls it for the fast attempt
    (``max_retries=0``, so a fast request fails fast into the fallback
    instead of being retried transparently by the SDK); the standard-speed
    retry uses the plain client. ``with_options`` returns ``self`` so the
    retry still shares the same recorded ``.beta.messages.stream``.
    """

    class _RateLimitStreamCM:
        """Async context manager whose __aenter__ raises a 429."""

        async def __aenter__(self):
            request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
            response = httpx.Response(429, request=request)
            raise module.RateLimitError(
                "Number of request tokens has exceeded your rate limit",
                response=response,
                body={
                    "error": {
                        "type": "rate_limit_error",
                        "message": "Number of request tokens has exceeded your rate limit",
                    }
                },
            )

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _CleanStream:
        """Minimal stand-in for the SDK's MessageStreamManager result.

        Only what ``pipe()`` actually reads for a tool-free end_turn: an
        async iterator of two events, and ``current_message_snapshot`` read
        once after the ``async for`` loop finishes.
        """

        def __init__(self):
            self.current_message_snapshot = SimpleNamespace(stop_reason="end_turn", content=[])

        async def _events(self):
            yield SimpleNamespace(
                type="message_delta",
                delta=SimpleNamespace(stop_reason="end_turn", container=None),
                usage=None,
            )
            yield SimpleNamespace(type="message_stop")

        def __aiter__(self):
            return self._events()

    class _CleanStreamCM:
        async def __aenter__(self):
            return _CleanStream()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _FakeMessages:
        def stream(self, **kwargs):
            stream_calls.append(kwargs)
            call_index = len(stream_calls) - 1
            if call_index == 0:
                return _RateLimitStreamCM()
            return _CleanStreamCM()

    class _FakeBeta:
        def __init__(self):
            self.messages = _FakeMessages()

    class FakeAsyncAnthropic:
        def __init__(self, **kwargs):
            self._init_kwargs = kwargs
            self.beta = _FakeBeta()

        def with_options(self, **kwargs):
            with_options_calls.append(kwargs)
            # Same recorder underneath -- the retry client still routes
            # through the same (shared) .beta.messages.stream.
            return self

    return FakeAsyncAnthropic


def _build_pipe(module, *, stream_calls, with_options_calls):
    """A real ``Pipe()`` instance, wired to the fake Anthropic client.

    Fast mode is forced on without a live model-list fetch: ``get_model_info``
    is overridden on the instance to report ``supports_fast_mode=True`` (plus
    the other keys ``create_request_payload`` indexes directly:
    ``max_tokens``, ``supports_effort``, ``supports_thinking``, and
    ``supports_adaptive_thinking``, which is read whenever
    ``ENABLE_INTERLEAVED_THINKING`` -- on by default -- is combined with
    ``supports_thinking``).
    """
    module.AsyncAnthropic = _build_fake_async_anthropic(module, stream_calls, with_options_calls)

    pipe = module.Pipe()
    pipe.valves.ANTHROPIC_API_KEY = "sk-test-123"
    pipe.valves.ENABLE_FAST_MODE = True
    # Keep the payload to the minimum needed to exercise the fallback: no
    # server tools, no prompt-cache breakpoints to maintain across the retry.
    pipe.valves.WEB_SEARCH = False
    pipe.valves.WEB_FETCH = False
    pipe.valves.CACHE_CONTROL = "cache disabled"

    pipe.get_model_info = lambda model_name: {
        "max_tokens": 64000,
        "context_length": 200000,
        "supports_effort": False,
        "supports_thinking": False,
        "supports_adaptive_thinking": False,
        "supports_fast_mode": True,
    }
    return pipe


async def test_fast_mode_falls_back_to_standard_speed_on_429(module):
    stream_calls: List[Dict[str, Any]] = []
    with_options_calls: List[Dict[str, Any]] = []
    events: List[Dict[str, Any]] = []

    pipe = _build_pipe(module, stream_calls=stream_calls, with_options_calls=with_options_calls)

    async def event_emitter(event: Dict[str, Any]) -> None:
        events.append(event)

    body = {
        "model": "anthropic/claude-test-fast",
        "messages": [{"role": "user", "content": "Hello"}],
    }
    user = {"id": "test-user", "valves": module.Pipe.UserValves()}

    result = await pipe.pipe(body, user, event_emitter, {})

    # Guard 1: exactly one retry, no more (no runaway loop, no third call).
    assert len(stream_calls) == 2, (
        f"expected exactly 2 beta.messages.stream() calls (fast + fallback "
        f"retry), got {len(stream_calls)}"
    )

    # Guard 2: the first (fast) call actually requested fast mode.
    first_call = stream_calls[0]
    assert first_call.get("speed") == "fast", (
        f"expected the first call to request speed='fast', got {first_call.get('speed')!r}"
    )
    assert "fast-mode-2026-02-01" in (first_call.get("betas") or []), (
        f"expected the first call's betas to include fast-mode-2026-02-01, "
        f"got {first_call.get('betas')!r}"
    )

    # Guard 3: the second (fallback) call dropped both the speed field and
    # the fast-mode beta -- this is the actual regression the fix guards.
    second_call = stream_calls[1]
    assert not second_call.get("speed"), (
        f"fallback retry must not carry payload['speed'], got {second_call.get('speed')!r}"
    )
    assert "fast-mode-2026-02-01" not in (second_call.get("betas") or []), (
        f"fallback retry must drop the fast-mode beta, got betas={second_call.get('betas')!r}"
    )

    # Guard 4: a warning notification told the user about the fallback.
    warnings = [
        e
        for e in events
        if e.get("type") == "notification" and e.get("data", {}).get("type") == "warning"
    ]
    assert any(
        "falling back to standard speed" in w.get("data", {}).get("content", "")
        for w in warnings
    ), f"expected a 'falling back to standard speed' warning notification, got: {warnings}"

    # Guard 5: with_options(max_retries=0) was used only for the fast (1st)
    # attempt -- the retry at standard speed uses the plain client.
    assert with_options_calls == [{"max_retries": 0}], (
        f"expected with_options(max_retries=0) exactly once (fast attempt only), "
        f"got {with_options_calls}"
    )

    # Sanity: the turn actually completed (no exception propagated out of pipe()).
    assert isinstance(result, str)


async def main():
    module = _load_module()
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        await test(module)
        print(f"  ok  {test.__name__}")
    print(f"\n{len(tests)} checks passed")


if __name__ == "__main__":
    asyncio.run(main())
