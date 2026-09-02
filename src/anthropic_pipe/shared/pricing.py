"""Compiled module-level section: Anthropic list prices and turn cost estimation."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ModelPricing:
    # Rate card in USD per million tokens, keyed by base (suffix-stripped) id.
    # Source: platform.claude.com/docs/en/about-claude/pricing (verified
    # 2026-10-08). The API does not expose pricing anywhere (/v1/models carries
    # capabilities and limits only), so this table is the only source and the
    # MODEL_PRICING_OVERRIDES valve is how admins patch it between releases.
    #
    # Only `input` and `output` are mandatory. The cache rates default to
    # Anthropic's standard multipliers on the input price and are spelled out
    # only where a model deviates. `fast_input` / `fast_output` are the
    # fast-mode rates for the models that offer it.
    #
    # Models priced by prompt length add `long_context_threshold` plus
    # `long_input` / `long_output` (cache rates again derive from
    # `long_input`). A call whose full prompt -- uncached input, cache writes
    # and cache reads -- exceeds the threshold bills ALL its tokens, output
    # included, at the long rates.
    RATES = {
        # Cache reads on Fable/Mythos 5.1 are 0.025x instead of 0.1x.
        "claude-fable-5-1": {"input": 10.0, "output": 50.0, "cache_read": 0.25},
        "claude-mythos-5-1": {"input": 10.0, "output": 50.0, "cache_read": 0.25},
        "claude-fable-5": {"input": 10.0, "output": 50.0},
        "claude-mythos-5": {"input": 10.0, "output": 50.0},
        # Cache reads on Opus/Sonnet 5.5 are 0.05x instead of 0.1x.
        "claude-opus-5-5": {
            "input": 4.0,
            "output": 20.0,
            "cache_read": 0.20,
            "fast_input": 8.0,
            "fast_output": 40.0,
        },
        "claude-sonnet-5-5": {"input": 2.0, "output": 10.0, "cache_read": 0.10},
        "claude-haiku-5-5": {
            "input": 0.10,
            "output": 0.50,
            "long_context_threshold": 100_000,
            "long_input": 0.50,
            "long_output": 2.50,
        },
        "claude-opus-5": {"input": 5.0, "output": 25.0, "fast_input": 10.0, "fast_output": 50.0},
        "claude-opus-4-8": {"input": 5.0, "output": 25.0, "fast_input": 10.0, "fast_output": 50.0},
        "claude-opus-4-7": {"input": 5.0, "output": 25.0},
        "claude-opus-4-6": {"input": 5.0, "output": 25.0},
        "claude-opus-4-5": {"input": 5.0, "output": 25.0},
        "claude-sonnet-5": {"input": 2.0, "output": 10.0},
        "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
        "claude-sonnet-4-5": {"input": 3.0, "output": 15.0},
        "claude-haiku-4-5": {"input": 1.0, "output": 5.0},
        # Retired on the Claude API but still served by Bedrock / Google Cloud
        # proxies. Haiku 3.5 is listed under both id orderings Anthropic used.
        "claude-opus-4-1": {"input": 15.0, "output": 75.0},
        "claude-opus-4": {"input": 15.0, "output": 75.0},
        "claude-sonnet-4": {"input": 3.0, "output": 15.0},
        "claude-haiku-3-5": {"input": 0.8, "output": 4.0},
        "claude-3-5-haiku": {"input": 0.8, "output": 4.0},
    }

    # Multipliers relative to the base input price.
    CACHE_WRITE_5M_MULTIPLIER = 1.25
    CACHE_WRITE_1H_MULTIPLIER = 2.0
    CACHE_READ_MULTIPLIER = 0.1
    # `inference_geo: "us"` applies to every token category.
    US_RESIDENCY_MULTIPLIER = 1.1
    # Web search is billed per request on top of tokens ($10 per 1,000).
    # Web fetch and code execution alongside web tools are free.
    WEB_SEARCH_REQUEST_USD = 0.01

    RATE_KEYS = (
        "input",
        "output",
        "cache_write_5m",
        "cache_write_1h",
        "cache_read",
        "fast_input",
        "fast_output",
        "long_context_threshold",
        "long_input",
        "long_output",
        "long_cache_write_5m",
        "long_cache_write_1h",
        "long_cache_read",
    )

    # Token categories of one API call, as recorded in `_call_log`.
    TOKEN_KEYS = ("input", "output", "cache_write_5m", "cache_write_1h", "cache_read")

    def __init__(self, overrides_json: str = ""):
        self._overrides = self._parse_overrides(overrides_json)

    @classmethod
    def _parse_overrides(cls, raw: str) -> dict:
        """Parse the MODEL_PRICING_OVERRIDES valve; a broken value is ignored, not fatal."""
        raw = (raw or "").strip()
        if not raw:
            return {}
        try:
            overrides = json.loads(raw)
            if not isinstance(overrides, dict):
                raise ValueError("top level must be an object keyed by model id")
            parsed: dict = {}
            for model_id, patch in overrides.items():
                if not isinstance(patch, dict):
                    raise ValueError(f"{model_id!r}: expected an object of rates")
                parsed[model_id] = {
                    k: float(v) for k, v in patch.items() if k in cls.RATE_KEYS and v is not None
                }
            return parsed
        except (ValueError, TypeError) as e:
            logger.warning(f"Ignoring MODEL_PRICING_OVERRIDES: {e}")
            return {}

    @staticmethod
    def _normalize(model_name: str) -> str:
        # Endpoints without aliases hand out dated ids ("claude-opus-5-20260301").
        # Same rule as Pipe._normalize_model_name; duplicated because this class
        # is a module-level section compiled above `class Pipe`.
        return re.sub(r"-\d{8}$", "", model_name)

    def rates_for(self, model_name: str) -> Optional[dict]:
        """Resolve the rate card for a model, or None if unknown.

        Built-in RATES first, then the admin overrides merged on top per key, so
        an override may touch a single rate or add a model the table has never
        heard of. Missing cache rates are derived from `input` *after* the
        merge, so overriding `input` alone keeps the cache rates consistent.
        """
        normalized = self._normalize(model_name)
        base = self.RATES.get(model_name) or self.RATES.get(normalized)
        rates: dict = dict(base) if base else {}
        patch = self._overrides.get(model_name) or self._overrides.get(normalized)
        if patch:
            rates.update(patch)

        if "input" not in rates or "output" not in rates:
            return None
        self._derive_cache_rates(rates, "")
        if rates.get("long_context_threshold") and "long_input" in rates and "long_output" in rates:
            self._derive_cache_rates(rates, "long_")
        else:
            for key in [k for k in rates if k.startswith("long_")]:
                del rates[key]
        return rates

    @classmethod
    def _derive_cache_rates(cls, rates: dict, prefix: str) -> None:
        base = rates[f"{prefix}input"]
        rates.setdefault(f"{prefix}cache_write_5m", base * cls.CACHE_WRITE_5M_MULTIPLIER)
        rates.setdefault(f"{prefix}cache_write_1h", base * cls.CACHE_WRITE_1H_MULTIPLIER)
        rates.setdefault(f"{prefix}cache_read", base * cls.CACHE_READ_MULTIPLIER)

    @staticmethod
    def record_call(
        total_usage: dict,
        *,
        input_tokens: int,
        output_tokens: int,
        cache_write_5m: int,
        cache_write_1h: int,
        cache_read: int,
    ) -> None:
        """Log one API call's own token counts on the turn's usage tally.

        The turn aggregates cannot say which call a token came from, and both
        a prompt-length tier (Haiku 5.5) and the speed are decided per call:
        a fast-mode 429 drops the rest of the turn to standard speed. Output
        keeps growing after message_start, so the streaming loop updates the
        last entry's `output` from each message_delta.
        """
        total_usage.setdefault("_call_log", []).append(
            {
                "prompt": input_tokens + cache_write_5m + cache_write_1h + cache_read,
                "input": input_tokens,
                "output": output_tokens,
                "cache_write_5m": cache_write_5m,
                "cache_write_1h": cache_write_1h,
                "cache_read": cache_read,
            }
        )

    @staticmethod
    def update_call_output(total_usage: dict, output_tokens: int) -> None:
        """Set the cumulative output of the call currently streaming."""
        call_log = total_usage.get("_call_log")
        if call_log:
            call_log[-1]["output"] = output_tokens

    @staticmethod
    def record_billing_modifiers(usage: Any, total_usage: dict) -> None:
        """Note the response-reported billing modifiers of the call currently streaming.

        Read from the response rather than from the valves that requested them:
        `speed: fast` on a model without fast mode runs (and bills) at standard
        speed, and only the API knows which geo actually served the call. Speed
        is flagged on the call's `_call_log` entry, so call `record_call` first.
        The geo is a valve that holds for the whole turn, so one turn-level
        flag is exact for it.
        """
        if not usage:
            return
        if getattr(usage, "speed", None) == "fast":
            call_log = total_usage.get("_call_log")
            if call_log:
                call_log[-1]["fast"] = True
        if getattr(usage, "inference_geo", None) == "us":
            total_usage["_geo_us"] = 1

    def _call_rates(self, rates: dict, *, fast: bool, long: bool) -> dict:
        """Per-token-category rates for one call's speed and prompt-length tier.

        Fast mode replaces the input/output rates and the cache multipliers
        apply on top of it, so the cache rates scale with the input ratio.
        """
        prefix = "long_" if long else ""
        call_rates = {key: rates[f"{prefix}{key}"] for key in self.TOKEN_KEYS}
        if fast and "fast_input" in rates and "fast_output" in rates:
            input_scale = rates["fast_input"] / rates["input"] if rates["input"] else 1.0
            output_scale = rates["fast_output"] / rates["output"] if rates["output"] else 1.0
            call_rates = {
                key: rate * (output_scale if key == "output" else input_scale)
                for key, rate in call_rates.items()
            }
        return call_rates

    def breakdown(self, model_name: str, total_usage: dict) -> Optional[dict]:
        """Per-component USD cost of a whole turn, or None if the model's rates are unknown.

        Keys: input, output, cache_write_5m, cache_write_1h, cache_read,
        web_search -- only the components that actually cost something, so
        the usage tooltip stays short on a plain turn. Modifiers are baked into
        the token components, mirroring Anthropic's stacking rules: fast mode
        and a prompt-length tier are priced per API call (`_call_log`), with
        the cache multipliers on top of the call's base rates; the US
        data-residency multiplier applies to every token category; web
        searches are a flat per-request fee that no multiplier touches.
        """
        rates = self.rates_for(model_name)
        if not rates:
            return None

        # Cache writes split by TTL when the API reported the breakdown; the
        # undifferentiated counter is the fallback for endpoints that do not.
        write_5m = total_usage.get("_cache_write_5m", 0)
        write_1h = total_usage.get("_cache_write_1h", 0)
        if not write_5m and not write_1h:
            write_5m = total_usage.get("cache_creation_input_tokens", 0)

        tokens = {
            "input": total_usage.get("input_tokens", 0),
            "output": total_usage.get("output_tokens", 0),
            "cache_write_5m": write_5m,
            "cache_write_1h": write_1h,
            "cache_read": total_usage.get("cache_read_input_tokens", 0),
        }

        # The aggregates stay the source of truth for the totals; the call log
        # only identifies the calls billed at a non-standard rate (fast, or
        # over the prompt-length threshold). Whatever it does not claim is
        # billed at the standard rates.
        token_components = dict.fromkeys(self.TOKEN_KEYS, 0.0)
        claimed = dict.fromkeys(self.TOKEN_KEYS, 0)
        threshold = rates.get("long_context_threshold")
        for call in total_usage.get("_call_log", ()):
            fast = bool(call.get("fast"))
            long = bool(threshold) and call.get("prompt", 0) > threshold
            if not fast and not long:
                continue
            call_rates = self._call_rates(rates, fast=fast, long=long)
            for key in self.TOKEN_KEYS:
                token_components[key] += call.get(key, 0) * call_rates[key]
                claimed[key] += call.get(key, 0)
        standard = self._call_rates(rates, fast=False, long=False)
        for key in self.TOKEN_KEYS:
            token_components[key] += max(tokens[key] - claimed[key], 0) * standard[key]

        geo = self.US_RESIDENCY_MULTIPLIER if total_usage.get("_geo_us") else 1.0
        components = {
            name: amount * geo / 1_000_000 for name, amount in token_components.items()
        }
        components["web_search"] = (
            total_usage.get("_web_search_requests", 0) * self.WEB_SEARCH_REQUEST_USD
        )
        return {name: round(amount, 6) for name, amount in components.items() if amount}

    def estimate(self, model_name: str, total_usage: dict) -> Optional[float]:
        """Estimate the USD list price of a whole turn, or None if the model's rates are unknown."""
        components = self.breakdown(model_name, total_usage)
        if components is None:
            return None
        return round(sum(components.values()), 6)

    @staticmethod
    def format_usd(cost: float) -> str:
        """Format a cost so sub-cent turns stay legible without padding dollar turns."""
        if cost >= 1:
            return f"${cost:.2f}"
        if cost >= 0.01:
            return f"${cost:.3f}"
        return f"${cost:.4f}"
