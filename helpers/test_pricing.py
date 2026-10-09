"""Self-check regression tests for ``ModelPricing`` turn-cost estimation.

``src/anthropic_pipe/shared/pricing.py`` is a hand-maintained rate card plus
the arithmetic that turns a turn's token tally into a USD estimate. It will
drift with every Anthropic price change, and a wrong factor (per-million vs
per-thousand, a cache multiplier, a fast/long rate) is a silent
mis-calculation in the usage report and status line, not a crash. These checks
pin the behaviour that is easy to break by accident:

  * rate derivation -- cache rates derived from ``input`` via the multipliers,
    explicit overrides on the table left intact, long-context rates derived
    and dropped together;
  * the ``MODEL_PRICING_OVERRIDES`` merge -- per-key, derive-after-merge, add a
    brand-new model, and a broken valve ignored rather than fatal;
  * fast-mode and long-context per-call attribution from ``_call_log``;
  * the cache-write TTL fallback (API ``_cache_write_*`` breakdown vs the
    undifferentiated ``cache_creation_input_tokens`` counter);
  * the per-million divisor, the US data-residency multiplier and the flat
    web-search fee;
  * dated-id normalization, the unknown-model ``None`` path and ``format_usd``.

Runs without OpenWebUI and without network access: ``pricing.py`` is a
self-contained module-level section, loaded directly.

Usage:
    python helpers/test_pricing.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "anthropic_pipe" / "shared" / "pricing.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("_pricing", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_pricing"] = module
    spec.loader.exec_module(module)
    return module


def _approx(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol


# --------------------------------------------------------------------------- #
# Rate derivation
# --------------------------------------------------------------------------- #
def test_cache_rates_derived_from_input(module):
    rates = module.ModelPricing().rates_for("claude-opus-5")
    assert _approx(rates["input"], 5.0) and _approx(rates["output"], 25.0)
    # 1.25x / 2.0x / 0.1x of the base input price.
    assert _approx(rates["cache_write_5m"], 6.25), rates["cache_write_5m"]
    assert _approx(rates["cache_write_1h"], 10.0), rates["cache_write_1h"]
    assert _approx(rates["cache_read"], 0.5), rates["cache_read"]


def test_explicit_cache_read_override_on_table_kept(module):
    # Fable 5.1 spells out a cheaper cache_read (0.25); derivation must not clobber it.
    rates = module.ModelPricing().rates_for("claude-fable-5-1")
    assert _approx(rates["cache_read"], 0.25), rates["cache_read"]
    # The write rates are still derived from input (10.0).
    assert _approx(rates["cache_write_5m"], 12.5)
    assert _approx(rates["cache_write_1h"], 20.0)


def test_long_context_rates_derived(module):
    rates = module.ModelPricing().rates_for("claude-haiku-5-5")
    assert rates["long_context_threshold"] == 100_000
    assert _approx(rates["long_input"], 0.5) and _approx(rates["long_output"], 2.5)
    # Long cache rates derive from long_input, not the base input.
    assert _approx(rates["long_cache_write_5m"], 0.625), rates["long_cache_write_5m"]
    assert _approx(rates["long_cache_write_1h"], 1.0)
    assert _approx(rates["long_cache_read"], 0.05)


def test_long_keys_dropped_without_threshold(module):
    rates = module.ModelPricing().rates_for("claude-opus-5")
    assert not any(k.startswith("long_") for k in rates), rates


def test_unknown_model_returns_none(module):
    p = module.ModelPricing()
    assert p.rates_for("gpt-4") is None
    assert p.breakdown("gpt-4", {"input_tokens": 100}) is None
    assert p.estimate("gpt-4", {"input_tokens": 100}) is None


def test_dated_id_normalized(module):
    p = module.ModelPricing()
    assert p.rates_for("claude-opus-5-20260301") == p.rates_for("claude-opus-5")


# --------------------------------------------------------------------------- #
# Overrides merge
# --------------------------------------------------------------------------- #
def test_override_input_alone_rederives_cache_rates(module):
    p = module.ModelPricing('{"claude-opus-5": {"input": 6.0}}')
    rates = p.rates_for("claude-opus-5")
    assert _approx(rates["input"], 6.0) and _approx(rates["output"], 25.0)
    # Cache rates must follow the overridden input (derive AFTER merge).
    assert _approx(rates["cache_write_5m"], 7.5), rates["cache_write_5m"]
    assert _approx(rates["cache_read"], 0.6), rates["cache_read"]
    # Untouched keys survive the merge.
    assert _approx(rates["fast_input"], 10.0)


def test_override_is_per_key(module):
    p = module.ModelPricing('{"claude-opus-5": {"cache_read": 0.99}}')
    rates = p.rates_for("claude-opus-5")
    assert _approx(rates["cache_read"], 0.99)
    # Other rates are untouched / still derived from the unchanged input.
    assert _approx(rates["input"], 5.0)
    assert _approx(rates["cache_write_5m"], 6.25)


def test_override_adds_new_model(module):
    p = module.ModelPricing('{"my-proxy-model": {"input": 1.0, "output": 2.0}}')
    rates = p.rates_for("my-proxy-model")
    assert rates is not None
    assert _approx(rates["input"], 1.0) and _approx(rates["output"], 2.0)
    assert _approx(rates["cache_write_5m"], 1.25)


def test_override_without_input_or_output_is_none(module):
    # A model the table never heard of needs both mandatory rates.
    p = module.ModelPricing('{"my-proxy-model": {"input": 1.0}}')
    assert p.rates_for("my-proxy-model") is None


def test_broken_override_ignored(module):
    for raw in ('{not json', "[]", '{"m": 3}', ""):
        p = module.ModelPricing(raw)
        # Falls back to the built-in table instead of raising.
        assert _approx(p.rates_for("claude-opus-5")["input"], 5.0), raw


# --------------------------------------------------------------------------- #
# Per-call attribution: fast mode and long context
# --------------------------------------------------------------------------- #
def test_standard_turn_per_million(module):
    # One million input tokens on opus-5 ($5/M) must cost exactly $5 --
    # guards the per-million vs per-thousand divisor.
    usage = {"input_tokens": 1_000_000, "output_tokens": 0}
    assert _approx(module.ModelPricing().estimate("claude-opus-5", usage), 5.0)


def test_fast_call_billed_at_fast_rates(module):
    p = module.ModelPricing()
    base = {"input_tokens": 1000, "output_tokens": 500}
    standard = p.estimate("claude-opus-5", dict(base))
    fast = p.estimate(
        "claude-opus-5",
        {
            **base,
            "_call_log": [
                {"prompt": 1000, "input": 1000, "output": 500,
                 "cache_write_5m": 0, "cache_write_1h": 0, "cache_read": 0, "fast": True}
            ],
        },
    )
    # opus-5 fast rates are 2x the standard input/output rates.
    assert _approx(standard, 0.0175), standard
    assert _approx(fast, 0.035), fast


def test_long_context_call_billed_at_long_rates(module):
    p = module.ModelPricing()
    # 200k-token prompt on haiku-5-5 crosses the 100k long-context threshold.
    usage = {
        "input_tokens": 200_000,
        "output_tokens": 1000,
        "_call_log": [
            {"prompt": 200_000, "input": 200_000, "output": 1000,
             "cache_write_5m": 0, "cache_write_1h": 0, "cache_read": 0}
        ],
    }
    comps = p.breakdown("claude-haiku-5-5", usage)
    # long_input 0.5/M, long_output 2.5/M.
    assert _approx(comps["input"], 0.1), comps["input"]
    assert _approx(comps["output"], 0.0025), comps["output"]


def test_untracked_tokens_billed_standard(module):
    # Aggregates are the source of truth: a fast call only claims its own
    # tokens; the rest of the turn falls back to standard rates.
    p = module.ModelPricing()
    usage = {
        "input_tokens": 2000,
        "output_tokens": 0,
        "_call_log": [
            {"prompt": 1000, "input": 1000, "output": 0,
             "cache_write_5m": 0, "cache_write_1h": 0, "cache_read": 0, "fast": True}
        ],
    }
    comps = p.breakdown("claude-opus-5", usage)
    # 1000 fast (10/M) + 1000 standard (5/M) = 0.01 + 0.005.
    assert _approx(comps["input"], 0.015), comps["input"]


# --------------------------------------------------------------------------- #
# Cache-write TTL breakdown vs fallback
# --------------------------------------------------------------------------- #
def test_cache_write_ttl_breakdown_used(module):
    usage = {
        "input_tokens": 0, "output_tokens": 0,
        "_cache_write_5m": 1000, "_cache_write_1h": 2000,
    }
    comps = module.ModelPricing().breakdown("claude-opus-5", usage)
    assert _approx(comps["cache_write_5m"], 0.00625), comps.get("cache_write_5m")
    assert _approx(comps["cache_write_1h"], 0.02), comps.get("cache_write_1h")


def test_cache_write_fallback_to_undifferentiated_counter(module):
    # Endpoints without the TTL breakdown report only cache_creation_input_tokens;
    # it is billed as the 5m tier.
    usage = {"input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 3000}
    comps = module.ModelPricing().breakdown("claude-opus-5", usage)
    assert _approx(comps["cache_write_5m"], 0.01875), comps.get("cache_write_5m")
    assert "cache_write_1h" not in comps, comps


def test_ttl_breakdown_takes_precedence_over_fallback(module):
    # When both are present, the explicit breakdown wins and the counter is ignored.
    usage = {
        "input_tokens": 0, "output_tokens": 0,
        "_cache_write_5m": 1000, "cache_creation_input_tokens": 9_999_999,
    }
    comps = module.ModelPricing().breakdown("claude-opus-5", usage)
    assert _approx(comps["cache_write_5m"], 0.00625), comps.get("cache_write_5m")


# --------------------------------------------------------------------------- #
# Turn-level modifiers and formatting
# --------------------------------------------------------------------------- #
def test_us_residency_multiplier(module):
    p = module.ModelPricing()
    plain = p.estimate("claude-opus-5", {"input_tokens": 1000, "output_tokens": 0})
    us = p.estimate("claude-opus-5", {"input_tokens": 1000, "output_tokens": 0, "_geo_us": 1})
    assert _approx(plain, 0.005)
    assert _approx(us, 0.0055), us  # 1.1x on every token category


def test_web_search_flat_fee(module):
    comps = module.ModelPricing().breakdown(
        "claude-opus-5", {"input_tokens": 0, "output_tokens": 0, "_web_search_requests": 3}
    )
    assert _approx(comps["web_search"], 0.03), comps


def test_breakdown_drops_zero_components(module):
    comps = module.ModelPricing().breakdown(
        "claude-opus-5", {"input_tokens": 1000, "output_tokens": 0}
    )
    assert set(comps) == {"input"}, comps


def test_format_usd_bands(module):
    f = module.ModelPricing.format_usd
    assert f(1.5) == "$1.50"
    assert f(0.05) == "$0.050"
    assert f(0.0012) == "$0.0012"


def main():
    module = _load_module()
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test(module)
        print(f"  ok  {test.__name__}")
    print(f"\n{len(tests)} checks passed")


if __name__ == "__main__":
    main()
