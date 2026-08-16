"""Compiled Pipe method group extracted from pipe_template.py."""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


class PipeModelSupportMethods:
    @classmethod
    def _parse_api_capabilities(cls, model) -> dict:
        """Parse capabilities from an Anthropic API ModelInfo object into our internal format."""
        caps = getattr(model, "capabilities", None)
        _sup = lambda obj, attr="supported": getattr(obj, attr, False) if obj else False

        thinking = getattr(caps, "thinking", None) if caps else None
        thinking_types = getattr(thinking, "types", None) if thinking else None
        effort = getattr(caps, "effort", None) if caps else None
        ctx_mgmt = getattr(caps, "context_management", None) if caps else None

        max_tokens = getattr(model, "max_tokens", 0) or 0
        max_input = getattr(model, "max_input_tokens", 0) or 0

        info = {
            "max_tokens": max_tokens if max_tokens > 0 else 4096,
            "context_length": max_input if max_input > 0 else 200000,
            "supports_thinking": _sup(thinking),
            "supports_adaptive_thinking": _sup(getattr(thinking_types, "adaptive", None)) if thinking_types else False,
            "supports_effort": _sup(effort),
            "supports_effort_max": _sup(getattr(effort, "max", None)) if effort else False,
            "supports_effort_xhigh": _sup(getattr(effort, "xhigh", None)) if effort else False,
            "supports_vision": _sup(getattr(caps, "image_input", None)) if caps else True,
            "supports_programmatic_calling": _sup(getattr(caps, "code_execution", None)) if caps else False,
            "supports_compaction": _sup(getattr(ctx_mgmt, "compact_20260112", None)) if ctx_mgmt else False,
            "supports_structured_outputs": _sup(getattr(caps, "structured_outputs", None)) if caps else False,
            # All Claude 4+ models support memory
            "supports_memory": True,
            # Defaults for fields not in API — overridden by MODEL_CAPABILITY_OVERRIDES
            "supports_dynamic_filtering": False,
            "supports_fast_mode": False,
            "thinking_on_by_default": False,
        }

        # Apply model-specific overrides for fields not available from API
        model_id = model.id if hasattr(model, "id") else ""
        overrides = cls.MODEL_CAPABILITY_OVERRIDES.get(model_id, {})
        info.update(overrides)

        return info

    @classmethod
    def get_model_info(cls, model_name: str) -> dict:
        """
        Get model capabilities by name. Reads from API cache first,
        falls back to safe defaults for unknown models.
        """
        if model_name in cls._api_capabilities_cache:
            return cls._api_capabilities_cache[model_name]

        # Endpoints that don't serve dated aliases (Azure/custom proxies) may hand
        # us a dated id like "claude-opus-4-6-20251022". Strip the -YYYYMMDD suffix
        # and retry both the API cache and the capability overrides with the base id.
        normalized = re.sub(r"-\d{8}$", "", model_name)
        if normalized != model_name and normalized in cls._api_capabilities_cache:
            return cls._api_capabilities_cache[normalized]

        # Return conservative defaults for unknown models, then apply identity
        # overrides for beta features whose API capability metadata can lag.
        info = {
            "max_tokens": cls.MODEL_MAX_TOKENS_FALLBACK.get(model_name)
            or cls.MODEL_MAX_TOKENS_FALLBACK.get(normalized, 4096),
            "context_length": cls.MODEL_CONTEXT_LENGTH_FALLBACK.get(model_name)
            or cls.MODEL_CONTEXT_LENGTH_FALLBACK.get(normalized, 200000),
            "supports_thinking": True,
            "supports_memory": False,
            "supports_vision": True,
            "supports_effort": False,
            "supports_programmatic_calling": False,
            "supports_compaction": False,
            "supports_structured_outputs": False,
            "supports_dynamic_filtering": False,
            "supports_adaptive_thinking": False,
            "supports_effort_max": False,
            "supports_effort_xhigh": False,
            "supports_fast_mode": False,
            "thinking_on_by_default": False,
        }
        overrides = cls.MODEL_CAPABILITY_OVERRIDES.get(model_name)
        if overrides is None:
            overrides = cls.MODEL_CAPABILITY_OVERRIDES.get(normalized, {})
        info.update(overrides)
        return info

    def _model_cache_signature(self) -> str:
        """Fingerprint of the settings the model list depends on.

        The API key is hashed rather than stored so the signature can be logged
        safely. Any change here means the cached list came from a different
        endpoint or allow-list and must not be reused.
        """
        parts = [
            (self.valves.ANTHROPIC_API_KEY or "").strip(),
            (self.valves.ANTHROPIC_BASE_URL or "").strip(),
            (getattr(self.valves, "ANTHROPIC_WORKSPACE_ID", "") or "").strip(),
            (getattr(self.valves, "ENABLED_MODELS", "") or "").strip(),
        ]
        return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()

    async def get_anthropic_models(self) -> List[dict]:
        """
        Fetches the current list of Anthropic models using the official Anthropic Python SDK.
        Parses capabilities from the API response and caches them.
        Returns OpenWebUI model dicts.
        """
        # Explicit allow-list bypass: endpoints without a /v1/models route (Azure,
        # some proxies) can't be auto-discovered. When ENABLED_MODELS is set, build
        # entries directly from the listed ids plus their capability overrides.
        enabled_raw = getattr(self.valves, "ENABLED_MODELS", "") or ""
        if enabled_raw.strip():
            enabled_list = [m.strip() for m in enabled_raw.split(",") if m.strip()]
            return [
                self._build_openwebui_model_entry(name, self.get_model_info(name))
                for name in enabled_list
            ]

        # Return cached result if still fresh AND fetched with the same
        # connection settings. A TTL of 0 disables caching entirely.
        cache_sig = self._model_cache_signature()
        ttl = int(getattr(self.valves, "MODEL_CACHE_TTL_MINUTES", 1440)) * 60
        cache_valid = (
            self._api_capabilities_cache
            and cache_sig == self._api_capabilities_cache_sig
            and ttl > 0
            and time.time() - self._api_capabilities_cache_ts < ttl
        )
        if cache_valid:
            models = []
            for name, info in self._api_capabilities_cache.items():
                models.append(self._build_openwebui_model_entry(name, info))
            return models

        from anthropic import AsyncAnthropic

        models = []
        new_cache: Dict[str, dict] = {}
        try:
            api_key = self.valves.ANTHROPIC_API_KEY
            client = self._build_anthropic_client(api_key)
            async for m in client.models.list():
                name = m.id
                display_name = getattr(m, "display_name", name)

                # Parse capabilities directly from API response
                info = self._parse_api_capabilities(m)
                info["_display_name"] = display_name
                new_cache[name] = info

                entry = self._build_openwebui_model_entry(name, info, display_name)
                models.append(entry)

            # Endpoint served no models (some proxies answer 200 with an empty
            # list) — fall back to the static override-derived list.
            if not models:
                logger.warning("Model listing returned no models; using static fallback")
                return self._static_fallback_models()

            # Update class-level cache
            Pipe._api_capabilities_cache = new_cache
            Pipe._api_capabilities_cache_ts = time.time()
            Pipe._api_capabilities_cache_sig = cache_sig
            logger.info(f"Cached capabilities for {len(new_cache)} models from API")
            return models
        except Exception as e:
            logging.warning(
                f"Could not fetch models from SDK/API: {e}"
            )
            # If we have stale cache from the same endpoint, use it. A cache from
            # different connection settings would advertise the wrong endpoint's
            # models, which is worse than showing none.
            if (
                self._api_capabilities_cache
                and self._api_capabilities_cache_sig == cache_sig
            ):
                logging.info("Using stale capability cache as fallback")
                for name, info in self._api_capabilities_cache.items():
                    models.append(self._build_openwebui_model_entry(name, info))
                return models
            # No cache available — return empty (API key likely invalid)
            return models

    @staticmethod
    def _build_openwebui_model_entry(
        name: str, info: dict, display_name: str = ""
    ) -> dict:
        """Build an OpenWebUI model dict from a model name and its capability info."""
        return {
            "id": f"anthropic/{name}",
            "name": display_name or name,
            "context_length": info["context_length"],
            "supports_vision": info["supports_vision"],
            "supports_thinking": info["supports_thinking"],
            "is_hybrid_model": info["supports_thinking"],
            "max_output_tokens": info["max_tokens"],
            "info": {
                "meta": {
                    "capabilities": {
                        "status_updates": True
                    }
                }
            },
        }

    def _build_anthropic_client(
        self,
        api_key: str,
        default_headers: Optional[dict] = None,
        timeout: Optional[float] = None,
    ):
        """Central Anthropic async client factory.

        All client creation routes through here so ANTHROPIC_BASE_URL and the
        ANTHROPIC_WORKSPACE_ID header (required by the AWS 'Claude on AWS'
        aws-external-anthropic endpoints) stay consistent across every request
        path (model listing, tasks, file downloads, main pipe loop).

        Resolves ``AsyncAnthropic`` from module scope on purpose: a function-local
        ``from anthropic import AsyncAnthropic`` shadows the module global and makes
        the class unpatchable, which silently sends every mocked test to the live API.
        """
        base_url = self.valves.ANTHROPIC_BASE_URL.strip() or None
        # The SDK derives its own "X-Api-Key" from api_key and merges default_headers
        # with a case-sensitive dict merge, so a lowercase "x-api-key" here survives
        # alongside it and httpx emits the header twice -> 401 "API key is invalid.".
        headers = {
            k: v
            for k, v in (default_headers or {}).items()
            if k.lower() != "x-api-key"
        }
        ws_id = (getattr(self.valves, "ANTHROPIC_WORKSPACE_ID", "") or "").strip()
        if ws_id:
            headers.setdefault("anthropic-workspace-id", ws_id)

        kwargs: Dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        if headers:
            kwargs["default_headers"] = headers
        if timeout is not None:
            kwargs["timeout"] = timeout
        return AsyncAnthropic(**kwargs)

    def _static_fallback_models(self) -> List[dict]:
        """Model list used when live discovery fails or returns nothing.

        Derives entries from MODEL_CAPABILITY_OVERRIDES so custom/proxy endpoints
        without a /v1/models route still surface the known Claude models.
        """
        return [
            self._build_openwebui_model_entry(name, self.get_model_info(name))
            for name in self.MODEL_CAPABILITY_OVERRIDES
        ]

    async def pipes(self) -> List[dict]:
        """OpenWebUI entry point returning the list of available Anthropic models."""
        return await self.get_anthropic_models()
