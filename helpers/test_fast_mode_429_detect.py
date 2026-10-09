"""Self-check regression test for the Fast Mode 429 fallback detection.

The streaming orchestrator drops a fast request to standard speed when it hits
a 429. The bug being guarded here: that fallback used to fire for *any*
``RateLimitError`` on a fast request, so an org-wide/account rate limit that
merely coincided with ``speed == "fast"`` would silently pin the rest of the
turn to standard speed (``speed`` is popped, so the branch can never fire
again) and show the user a false "Fast mode rate-limited" warning.

``Pipe._is_fast_mode_rate_limit`` is the predicate the fallback now gates on.
It must return True only when the fast-mode token bucket is actually the one
that tripped, told apart via the dedicated ``anthropic-fast-*-tokens-*``
response headers (remaining 0 = exhausted, limit 0 = not enabled), and fall
back to the error text only when no fast headers are present.

Runs without OpenWebUI and without network access: the method is pure and the
orchestrator module only imports ``logging``, so it is loaded directly from
``src`` with a bare instance and fake exception objects.

Usage:
    python helpers/test_fast_mode_429_detect.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, Optional

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "anthropic_pipe"
    / "pipe_orchestrator.py"
)


def _load_pipe():
    spec = importlib.util.spec_from_file_location("_pipe_orchestrator", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_pipe_orchestrator"] = module
    spec.loader.exec_module(module)
    return module.PipeOrchestratorMethods()


class FakeResponse:
    def __init__(self, headers: Optional[Dict[str, Any]]):
        self.headers = headers


class FakeRateLimitError(Exception):
    """Mimics anthropic.RateLimitError's surface used by the predicate:
    ``response.headers``, ``message`` and ``body``."""

    def __init__(
        self,
        *,
        headers: Optional[Dict[str, Any]] = None,
        message: str = "",
        body: Any = None,
        with_response: bool = True,
    ):
        super().__init__(message or "429")
        self.message = message
        self.body = body
        self.response = FakeResponse(headers) if with_response else None


def test_fast_bucket_exhausted_is_fast_mode(pipe):
    exc = FakeRateLimitError(
        headers={
            "anthropic-fast-input-tokens-limit": "100000",
            "anthropic-fast-input-tokens-remaining": "0",
            "anthropic-ratelimit-tokens-remaining": "50000",
        }
    )
    assert pipe._is_fast_mode_rate_limit(exc) is True


def test_fast_mode_not_enabled_limit_zero_is_fast_mode(pipe):
    exc = FakeRateLimitError(
        headers={
            "anthropic-fast-input-tokens-limit": "0",
            "anthropic-fast-input-tokens-remaining": "0",
        }
    )
    assert pipe._is_fast_mode_rate_limit(exc) is True


def test_fast_output_bucket_exhausted_is_fast_mode(pipe):
    exc = FakeRateLimitError(
        headers={
            "anthropic-fast-output-tokens-limit": "32000",
            "anthropic-fast-output-tokens-remaining": "0",
        }
    )
    assert pipe._is_fast_mode_rate_limit(exc) is True


def test_org_wide_limit_with_fast_budget_remaining_is_not_fast_mode(pipe):
    """The regression case: fast bucket still has budget, a different (org-wide)
    bucket is what tripped -> must NOT be treated as fast-mode-specific."""
    exc = FakeRateLimitError(
        headers={
            "anthropic-fast-input-tokens-limit": "100000",
            "anthropic-fast-input-tokens-remaining": "80000",
            "anthropic-fast-output-tokens-remaining": "16000",
            "anthropic-ratelimit-tokens-remaining": "0",
        }
    )
    assert pipe._is_fast_mode_rate_limit(exc) is False


def test_header_case_insensitive(pipe):
    exc = FakeRateLimitError(
        headers={"Anthropic-Fast-Input-Tokens-Remaining": "0"}
    )
    assert pipe._is_fast_mode_rate_limit(exc) is True


def test_no_fast_headers_message_names_fast_is_fast_mode(pipe):
    exc = FakeRateLimitError(
        headers={"anthropic-ratelimit-tokens-remaining": "0"},
        message="This request would exceed your fast mode rate limit.",
    )
    assert pipe._is_fast_mode_rate_limit(exc) is True


def test_no_fast_headers_body_message_names_fast_is_fast_mode(pipe):
    exc = FakeRateLimitError(
        headers=None,
        with_response=False,
        body={"error": {"type": "rate_limit_error", "message": "fast mode capacity exceeded"}},
    )
    assert pipe._is_fast_mode_rate_limit(exc) is True


def test_no_fast_headers_generic_message_is_not_fast_mode(pipe):
    exc = FakeRateLimitError(
        headers={"anthropic-ratelimit-tokens-remaining": "0"},
        message="Number of request tokens has exceeded your rate limit.",
        body={"error": {"type": "rate_limit_error", "message": "rate limit exceeded"}},
    )
    assert pipe._is_fast_mode_rate_limit(exc) is False


def test_no_response_no_body_is_not_fast_mode(pipe):
    exc = FakeRateLimitError(with_response=False, message="429 Too Many Requests")
    assert pipe._is_fast_mode_rate_limit(exc) is False


def test_non_numeric_header_is_ignored(pipe):
    """A malformed/non-numeric fast header must not crash or spuriously match;
    with no other signal this is not fast-mode-specific."""
    exc = FakeRateLimitError(
        headers={"anthropic-fast-input-tokens-remaining": "n/a"},
    )
    assert pipe._is_fast_mode_rate_limit(exc) is False


def main():
    pipe = _load_pipe()
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test(pipe)
        print(f"  ok  {test.__name__}")
    print(f"\n{len(tests)} checks passed")


if __name__ == "__main__":
    main()
