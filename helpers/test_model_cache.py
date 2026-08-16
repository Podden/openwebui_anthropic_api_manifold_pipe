"""Self-check for model-list caching and its invalidation.

The model list is cached class-wide for MODEL_CACHE_TTL_MINUTES. The part worth
guarding is not the TTL but the invalidation: pointing the pipe at a different
endpoint, key, workspace or allow-list must refetch immediately instead of
serving the previous endpoint's models until the TTL expires.

Runs without OpenWebUI and without network access: the Anthropic client is
replaced by a fake that counts calls.

Usage:
    python helpers/test_model_cache.py
"""
from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "anthropic_pipe" / "shared" / "models.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("_models", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_models"] = module
    spec.loader.exec_module(module)
    # The compiled artifact resolves these from module scope inside class Pipe.
    module.time = time
    module.hashlib = hashlib
    module.logging = logging
    module.List = List
    module.Dict = Dict
    return module


class FakeValves:
    def __init__(self, **kwargs):
        self.ANTHROPIC_API_KEY = "key-a"
        self.ANTHROPIC_BASE_URL = "https://api.anthropic.com"
        self.ANTHROPIC_WORKSPACE_ID = ""
        self.ENABLED_MODELS = ""
        self.MODEL_CACHE_TTL_MINUTES = 1440
        self.__dict__.update(kwargs)


class FakeModel:
    def __init__(self, model_id):
        self.id = model_id
        self.display_name = model_id.replace("claude-", "Claude ")
        self.max_tokens = 64000
        self.max_input_tokens = 200000
        self.capabilities = None


class FakeClient:
    """Minimal stand-in for AsyncAnthropic; models.list() is an async iterator."""

    def __init__(self, model_ids, counter):
        self._model_ids = model_ids
        self._counter = counter
        self.models = self

    def list(self):
        self._counter["calls"] += 1
        model_ids = self._model_ids

        async def _gen():
            for model_id in model_ids:
                yield FakeModel(model_id)

        return _gen()


def build_pipe(module, valves=None, model_ids=("claude-opus-5",), counter=None):
    counter = counter if counter is not None else {"calls": 0}

    class TestPipe(module.PipeModelSupportMethods):
        MODEL_CAPABILITY_OVERRIDES: dict = {}
        MODEL_MAX_TOKENS_FALLBACK: dict = {}
        MODEL_CONTEXT_LENGTH_FALLBACK: dict = {}
        _api_capabilities_cache: dict = {}
        _api_capabilities_cache_ts: float = 0.0
        _api_capabilities_cache_sig: str = ""
        _API_CACHE_TTL = 86400

        def __init__(self, valves):
            self.valves = valves

        def _build_anthropic_client(self, api_key, default_headers=None, timeout=None):
            return FakeClient(model_ids, counter)

    module.Pipe = TestPipe
    return TestPipe(valves or FakeValves()), counter, TestPipe


async def test_second_call_uses_cache(module):
    pipe, counter, _ = build_pipe(module)
    first = await pipe.get_anthropic_models()
    second = await pipe.get_anthropic_models()
    assert counter["calls"] == 1, f"expected one API call, got {counter['calls']}"
    assert [m["id"] for m in first] == [m["id"] for m in second]


async def test_changed_base_url_refetches(module):
    pipe, counter, cls = build_pipe(module)
    await pipe.get_anthropic_models()
    pipe.valves.ANTHROPIC_BASE_URL = "https://my-proxy.internal/v1"
    await pipe.get_anthropic_models()
    assert counter["calls"] == 2, "changing the base URL must invalidate the cache"


async def test_changed_api_key_refetches(module):
    pipe, counter, _ = build_pipe(module)
    await pipe.get_anthropic_models()
    pipe.valves.ANTHROPIC_API_KEY = "key-b"
    await pipe.get_anthropic_models()
    assert counter["calls"] == 2, "changing the API key must invalidate the cache"


async def test_changed_workspace_refetches(module):
    pipe, counter, _ = build_pipe(module)
    await pipe.get_anthropic_models()
    pipe.valves.ANTHROPIC_WORKSPACE_ID = "ws-123"
    await pipe.get_anthropic_models()
    assert counter["calls"] == 2, "changing the workspace must invalidate the cache"


async def test_ttl_zero_disables_cache(module):
    pipe, counter, _ = build_pipe(module, valves=FakeValves(MODEL_CACHE_TTL_MINUTES=0))
    await pipe.get_anthropic_models()
    await pipe.get_anthropic_models()
    await pipe.get_anthropic_models()
    assert counter["calls"] == 3, "TTL 0 must refetch every time"


async def test_expired_ttl_refetches(module):
    pipe, counter, cls = build_pipe(module, valves=FakeValves(MODEL_CACHE_TTL_MINUTES=1))
    await pipe.get_anthropic_models()
    cls._api_capabilities_cache_ts = time.time() - 120  # 2 minutes ago
    await pipe.get_anthropic_models()
    assert counter["calls"] == 2, "an expired cache must refetch"


async def test_stale_cache_used_on_api_error(module):
    pipe, counter, cls = build_pipe(module)
    await pipe.get_anthropic_models()

    def _boom(*args, **kwargs):
        raise RuntimeError("API down")

    pipe._build_anthropic_client = _boom
    cls._api_capabilities_cache_ts = 0.0  # force cache miss, then fail the fetch
    models = await pipe.get_anthropic_models()
    assert [m["id"] for m in models] == ["anthropic/claude-opus-5"], (
        "a failed refresh must fall back to the stale cache from the same endpoint"
    )


async def test_stale_cache_not_used_across_endpoints(module):
    pipe, counter, cls = build_pipe(module)
    await pipe.get_anthropic_models()

    def _boom(*args, **kwargs):
        raise RuntimeError("API down")

    pipe._build_anthropic_client = _boom
    pipe.valves.ANTHROPIC_BASE_URL = "https://other-endpoint.internal/v1"
    models = await pipe.get_anthropic_models()
    assert models == [], (
        "models cached from a different endpoint must not be served as a fallback"
    )


async def test_enabled_models_bypasses_api(module):
    pipe, counter, _ = build_pipe(
        module, valves=FakeValves(ENABLED_MODELS="claude-opus-5, claude-haiku-4-5")
    )
    models = await pipe.get_anthropic_models()
    assert counter["calls"] == 0, "an explicit allow-list must not call the API"
    assert [m["id"] for m in models] == [
        "anthropic/claude-opus-5",
        "anthropic/claude-haiku-4-5",
    ]


async def main():
    module = _load_module()
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        await test(module)
        print(f"  ok  {test.__name__}")
    print(f"\n{len(tests)} checks passed")


if __name__ == "__main__":
    asyncio.run(main())
