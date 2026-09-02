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
    # 2026-09-02). The API does not expose pricing anywhere (/v1/models carries
    # capabilities and limits only), so this table is the only source and the
    # MODEL_PRICING_OVERRIDES valve is how admins patch it between releases.
    #
    # Only `input` and `output` are mandatory. The cache rates default to
    # Anthropic's standard multipliers on the input price and are spelled out
    # only where a model deviates. `fast_input` / `fast_output` are the
    # fast-mode rates for the models that offer it.
    RATES = {
        # Cache reads on the 5.1 generation are 0.025x instead of 0.1x.
        "claude-fable-5-1": {"input": 10.0, "output": 50.0, "cache_read": 0.25},
        "claude-mythos-5-1": {"input": 10.0, "output": 50.0, "cache_read": 0.25},
        "claude-fable-5": {"input": 10.0, "output": 50.0},
        "claude-mythos-5": {"input": 10.0, "output": 50.0},
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
    )

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
        rates.setdefault("cache_write_5m", rates["input"] * self.CACHE_WRITE_5M_MULTIPLIER)
        rates.setdefault("cache_write_1h", rates["input"] * self.CACHE_WRITE_1H_MULTIPLIER)
        rates.setdefault("cache_read", rates["input"] * self.CACHE_READ_MULTIPLIER)
        return rates

    @staticmethod
    def record_billing_modifiers(usage: Any, total_usage: dict) -> None:
        """Note the response-reported billing modifiers on the turn's usage tally.

        Read from the response rather than from the valves that requested them:
        `speed: fast` on a model without fast mode runs (and bills) at standard
        speed, and only the API knows which geo actually served the call. Both
        are request-level settings, so one flag for the whole turn is exact.
        """
        if not usage:
            return
        if getattr(usage, "speed", None) == "fast":
            total_usage["_speed_fast"] = 1
        if getattr(usage, "inference_geo", None) == "us":
            total_usage["_geo_us"] = 1

    def breakdown(self, model_name: str, total_usage: dict) -> Optional[dict]:
        """Per-component USD cost of a whole turn, or None if the model's rates are unknown.

        Keys: input, output, cache_write_5m, cache_write_1h, cache_read,
        web_search -- only the components that actually cost something, so
        the usage tooltip stays short on a plain turn. Modifiers are baked into
        the token components, mirroring Anthropic's stacking rules: fast mode
        replaces the base input/output rates and the cache multipliers apply on
        top of it; the US data-residency multiplier applies to every token
        category; web searches are a flat per-request fee that no multiplier
        touches.
        """
        rates = self.rates_for(model_name)
        if not rates:
            return None

        input_rate = rates["input"]
        output_rate = rates["output"]
        write_5m_rate = rates["cache_write_5m"]
        write_1h_rate = rates["cache_write_1h"]
        read_rate = rates["cache_read"]
        if total_usage.get("_speed_fast") and "fast_input" in rates and "fast_output" in rates:
            scale = rates["fast_input"] / input_rate if input_rate else 1.0
            input_rate = rates["fast_input"]
            output_rate = rates["fast_output"]
            write_5m_rate *= scale
            write_1h_rate *= scale
            read_rate *= scale

        # Cache writes split by TTL when the API reported the breakdown; the
        # undifferentiated counter is the fallback for endpoints that do not.
        write_5m = total_usage.get("_cache_write_5m", 0)
        write_1h = total_usage.get("_cache_write_1h", 0)
        if not write_5m and not write_1h:
            write_5m = total_usage.get("cache_creation_input_tokens", 0)

        geo = self.US_RESIDENCY_MULTIPLIER if total_usage.get("_geo_us") else 1.0
        token_components = {
            "input": total_usage.get("input_tokens", 0) * input_rate,
            "output": total_usage.get("output_tokens", 0) * output_rate,
            "cache_write_5m": write_5m * write_5m_rate,
            "cache_write_1h": write_1h * write_1h_rate,
            "cache_read": total_usage.get("cache_read_input_tokens", 0) * read_rate,
        }
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
