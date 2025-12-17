"""
title: Anthropic API Integration
author: Podden (https://github.com/Podden/)
github: https://github.com/Podden/openwebui_anthropic_api_manifold_pipe
original_author: Balaxxe (Updated by nbellochi)
version: 0.5.7
license: MIT
requirements: pydantic>=2.0.0, anthropic>=0.75.0
environment_variables:
    - ANTHROPIC_API_KEY (required)

Supports:
- Uses Anthropic Python SDK
- Fetch Claude Models from API Endpoint
- Tool Call Loop (call multiple Tools in the same response)
- web_search Tool
- citations for web_search
- Streaming responses
- Prompt caching (server-side) compatible with Openwebui Memory and RAG System
- Prompt Caching of System Prompts, Messages- and Tools Array (controllable via Valve)
- Comprehensive error
- Image processing
- Web_Search Toggle Action
- Fine Grained Tool Streaming
- Extended Thinking Toggle Action
- Code Execution Tool
- Vision
- Context Editing (clear tool results and thinking blocks)
- Tool Search (BM25/Regex)

Changelog:
v0.5.7
- Added Valve to exclude specific tools from deferred loading when tool search is enabled (web_search excluded by default)
- Web Search Toogle Filter overrides WEB_SEARCH Valve
- Fixed a Bug in Tool Search return

v0.5.6
- Added Context Editing feature (clear_tool_uses, clear_thinking) with configurable strategies
- Added Tool Search feature (BM25/Regex) with deferred tool loading
- Status events for context clearing with token counts
- Warning notification for thinking+cache conflict

v0.5.5
- Fixed effort parameter support by upgrading Anthropic SDK from 0.60.0 to 0.75.0

v0.5.4
- Fixed Message Caching Problems when using RAG or Memories

v0.5.3
- Added Support for Anthropic Effort Levels (low, medium, high)
- Added Support for Opus 4.5
- Use correct logger for logging
- Removed DEBUG Valve
- Introduced UserValves for setting user-specific options like thinking, effort, web search limits and location

v0.5.2
- Fixed usage statistics accumulation for multi-step tool calls
- Correctly sums input and output tokens across all turns in a request

v0.5.1
- Fixed caching issue in tool execution loops where cache_control marker could be lost
- Optimized caching for multi-step tool calls by moving cache breakpoint to the latest tool result

v0.5.0
- **CRITICAL FIX**: Eliminated cross-talk between concurrent users/requests
- Removed shared instance state (self.eventemitter, self.request_id) that caused response mixing

v0.4.9
- Performance optimization: Moved local imports to top level
- Fixed fallback logic for model fetching when API fails

v0.4.8
- Added configurable MAX_TOOL_CALLS valve (default: 15, range: 1-50)
- Moved tool execution status events to content_block_start for immediate feedback (prevents stalling on long parameters)
- Added proactive warning to Claude when only 1 tool call remains before limit
- System message injected before final call to encourage text response instead of more tool calls
- Added user notifications when approaching limit (≤3 calls) and when limit is reached
- Improved event loop yielding with asyncio.sleep() for reliable status event delivery on heavy tool calls loads

v0.4.7
- Fixed potential data leakage between concurrent users
- Code cleanup and stability improvements

v0.4.6
- Tool results now display input parameters at the top
- Shows "Input:" section with tool parameters before "Output:" section
- Improves visibility of what parameters were passed to each tool call

v0.4.5
- Added status events for local tool execution (AIT-102)
- Tools now show "Executing tool: {tool_name}" when they start
- Tools show "Waiting for X tool(s) to complete..." during execution
- Tools show "Tool execution complete" when finished
- Improves UX for long-running tools - users now see activity instead of apparent hanging

v0.4.4
- Tool calls now execute in parallel and start immediately when detected
- Server tools (e.g., web_search) are no longer misidentified as local tools
- Web search now emits correct status events during execution
- Fixed final message chunk not being flushed in some streaming scenarios

v0.4.3
- Fixed compatibility with OpenWebUI "Chat with Notes" feature
- Added filtering for empty text content blocks to prevent API errors
- Messages with empty content arrays are now skipped (fixes empty assistant messages from Notes chat)

v0.4.2
- Fixed NoneType error in OpenWebUI Channels when models are mentioned (@model)
- Added safe event emitter wrapper to handle missing __event_emitter__ in channel contexts
- All status/notification/citation events now gracefully handle None event emitter

v0.4.1
- Added a Valve to Show Token Count in the final status message
- Auto-enable native function calling when tools are present (prevents OpenWebUI's function_calling task system)

v0.4.0
- Added Task Support (sorry, I forgot). Follow Ups, Titles and Tags are now generated.
- Fix "invalid_request_error ", when a response contains both, a server tool and a local tool use (eg. web search and a local tool).

v0.3.9
- Added fine grained cache control valve with 4 levels: disabled, tools only, tools + system prompt, tools + system prompt + user messages

v0.3.8
- Removed MAX_OUTPUT_TOKENS valve - now always respects requested max_tokens up to model limit
- Simplified token calculation logic
- Reworked the caching with active Openwebui Memory System, Memories are now extracted from system prompt and injected into user messages as context blocks
- Refactored Model Info structure for maintainability
- Pipe is now retrying request on overloaded, rate_limit or transient errors up to MAX_RETRIES valve
- Status indicator is now shown while waiting for the first response (first response took very long when using eg. web_search tool)
- Removed unused aiohttp and random imports

v0.3.7
- Fixed Extended Thinking compatibility with Tool Use (API now requires thinking blocks before tool_use blocks)
- Added automatic placeholder thinking blocks when needed for API compliance
- Added validation for all assistant messages with tool_use when Extended Thinking is enabled

v0.3.6
- Added 4.5 Haiku Model
- Restructured Model Capabilities for more Maintainability

v0.3.5
- Fixed a bug where the last chunk was not sent in some cases
- Improved error handling and logging
- Added Correct Citation Handling for Web Search

v0.3.4
- Added Claude 4.5 Sonnet
- Small Bugfix with final_message
- Added OpenWebUI Token Usage Compatibility
- Added a Check for Duplicate Tool Names and private tool name (starting with "_") to avoid API errors

v0.3.3
- Fixed Tool Call error

v0.3.2
- Fixed type and added changelog

v0.3.1
- Fixed a bug where message would disappear after Error occurs

v0.3
- Added Vision support (__files__ handling & image processing improvements)
- Added Extended Thinking filter & metadata override with clamped budget logic (default 10K, safe min/max enforcement)
- Added Web Search Enforcement toggle (one‑shot metadata flag forces web_search tool_choice)
- Added Anthropic Code Execution Tool with toggle filter & beta header
- Enabled fine‑grained tool streaming beta by default
- Added metadata & valve controlled injection of code execution tool spec
- Improved cache control: auto‑disables cache when dynamic Memory / RAG blocks detected; ephemeral caching for stable blocks
- Refined tool_choice precedence (enforced web search before auto)
- Added 1M context optional beta header for supported Sonnet 4 models
- Improved malformed tool_use JSON salvage (_finalize_tool_buffer) & robust final chunk flush
- Misc debug output refinements & system prompt cleanup

v0.2
- Fixed caching by moving Memories to Messages instead of system prompt
- You can show Cache Usage Statistics with a Valve as Source Event
- Fixed error where last chunk is not shown in frontend
- Fixed defective event_emitters and removed unneeded method
- Fixed unnecessary requirements
- Implemented Web Search Valves and error handling
- Robust error handling
- Added Cache_Control for System_Prompt, Tools, and Message Array
- Refactored for readability and support for new models
"""

import re
import base64
import traceback
from datetime import datetime
from collections.abc import Awaitable
import asyncio
import inspect
import json
import logging
from typing import Any, Callable, List, Union, Dict, Optional
from pydantic import BaseModel, Field
from anthropic import (
    APIStatusError,
    AsyncAnthropic,
    RateLimitError,
    APIConnectionError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    PermissionDeniedError,
    NotFoundError,
    UnprocessableEntityError,
)
from typing import Literal


logger = logging.getLogger(__name__)

# Import OpenWebUI Models for auto-enabling native function calling
try:
    from open_webui.models.models import Models, ModelForm
    MODELS_AVAILABLE = True
except ImportError:
    Models = None
    ModelForm = None
    MODELS_AVAILABLE = False

class Pipe:
    API_VERSION = "2023-06-01"  # Current API version as of May 2025
    MODEL_URL = "https://api.anthropic.com/v1/messages"

    # Centralized model capabilities database
    # Note: Anthropic's /v1/models API only returns id, display_name, created_at, and type.
    # It does NOT provide max_tokens, context_length, or capability flags.
    # Therefore, we must maintain this static configuration.
    MODEL_CAPABILITIES = {
        # Claude 3 family
        "claude-3-opus-20240229": {
            "max_tokens": 4096,
            "context_length": 200000,
            "supports_thinking": False,
            "supports_1m_context": False,
            "supports_memory": False,
            "supports_vision": True,
            "supports_effort": False,
            "supports_programmatic_calling": False,
        },
        "claude-3-sonnet-20240229": {
            "max_tokens": 4096,
            "context_length": 200000,
            "supports_thinking": False,
            "supports_1m_context": False,
            "supports_memory": False,
            "supports_vision": True,
            "supports_effort": False,
            "supports_programmatic_calling": False,
        },
        "claude-3-haiku-20240307": {
            "max_tokens": 4096,
            "context_length": 200000,
            "supports_thinking": False,
            "supports_1m_context": False,
            "supports_memory": False,
            "supports_vision": True,
            "supports_effort": False,
            "supports_programmatic_calling": False,
        },
        # Claude 3.5 family
        "claude-3-5-sonnet-20240620": {
            "max_tokens": 8192,
            "context_length": 200000,
            "supports_thinking": False,
            "supports_1m_context": False,
            "supports_memory": False,
            "supports_vision": True,
            "supports_effort": False,
            "supports_programmatic_calling": False,
        },
        "claude-3-5-sonnet-20241022": {
            "max_tokens": 8192,
            "context_length": 200000,
            "supports_thinking": False,
            "supports_1m_context": False,
            "supports_memory": False,
            "supports_vision": True,
            "supports_effort": False,
            "supports_programmatic_calling": False,
        },
        "claude-3-5-haiku-20241022": {
            "max_tokens": 8192,
            "context_length": 200000,
            "supports_thinking": False,
            "supports_1m_context": False,
            "supports_memory": False,
            "supports_vision": True,
            "supports_effort": False,
            "supports_programmatic_calling": False,
        },
        # Claude 3.7 family
        "claude-3-7-sonnet-20250219": {
            "max_tokens": 64000,
            "context_length": 200000,
            "supports_thinking": True,
            "supports_1m_context": False,
            "supports_memory": False,
            "supports_vision": True,
            "supports_effort": False,
            "supports_programmatic_calling": False,
        },
        # Claude 4 family
        "claude-sonnet-4-20250514": {
            "max_tokens": 64000,
            "context_length": 200000,
            "supports_thinking": True,
            "supports_1m_context": True,
            "supports_memory": True,
            "supports_vision": True,
            "supports_effort": False,
            "supports_programmatic_calling": False,
        },
        "claude-opus-4-20250514": {
            "max_tokens": 32000,
            "context_length": 200000,
            "supports_thinking": True,
            "supports_1m_context": False,
            "supports_memory": True,
            "supports_vision": True,
            "supports_effort": False,
            "supports_programmatic_calling": False,
        },
        "claude-opus-4-1-20250805": {
            "max_tokens": 32000,
            "context_length": 200000,
            "supports_thinking": True,
            "supports_1m_context": False,
            "supports_memory": True,
            "supports_vision": True,
            "supports_effort": False,
            "supports_programmatic_calling": False,
        },
        "claude-sonnet-4-5-20250929": {
            "max_tokens": 64000,
            "context_length": 200000,
            "supports_thinking": True,
            "supports_1m_context": True,
            "supports_memory": True,
            "supports_vision": True,
            "supports_effort": False,
            "supports_programmatic_calling": True,
        },
        "claude-haiku-4-5-20251001": {
            "max_tokens": 64000,
            "context_length": 200000,
            "supports_thinking": True,
            "supports_1m_context": False,
            "supports_memory": True,
            "supports_vision": True,
            "supports_effort": False,
            "supports_programmatic_calling": False,  # Haiku 4.5 only supports allowed_callers=['direct']
        },
        "claude-opus-4-5-20251101": {
            "max_tokens": 64000,
            "context_length": 200000,
            "supports_thinking": True,
            "supports_1m_context": False,
            "supports_memory": True,
            "supports_vision": True,
            "supports_effort": True,
            "supports_programmatic_calling": True,
        }
    }
    
    # Aliases map to dated model versions
    MODEL_ALIASES = {
        "claude-3-opus-latest": "claude-3-opus-20240229",
        "claude-3-sonnet-latest": "claude-3-sonnet-20240229",
        "claude-3-haiku-latest": "claude-3-haiku-20240307",
        "claude-3-5-sonnet-latest": "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-latest": "claude-3-5-haiku-20241022",
        "claude-3-7-sonnet-latest": "claude-3-7-sonnet-20250219",
        "claude-sonnet-4": "claude-sonnet-4-20250514",
        "claude-opus-4": "claude-opus-4-20250514",
        "claude-opus-4-1": "claude-opus-4-1-20250805",
        "claude-sonnet-4-5": "claude-sonnet-4-5-20250929",
        "claude-haiku-4-5": "claude-haiku-4-5-20251001",
        "claude-opus-4-5": "claude-opus-4-5-20251101",
    }

    REQUEST_TIMEOUT = (
        300  # Increased timeout for longer responses with extended thinking
    )
    THINKING_BUDGET_TOKENS = 4096  # Default thinking budget tokens (max 16K)
    TOOL_CALL_TIMEOUT = 120  # Seconds before a tool call is treated as timed out

    @classmethod
    def get_model_info(cls, model_name: str) -> dict:
        """
        Get model capabilities by name, resolving aliases automatically.
        Returns default capabilities if model is unknown.
        """
        # Resolve alias to actual model name
        resolved_name = cls.MODEL_ALIASES.get(model_name, model_name)

        # Get capabilities or return defaults
        return cls.MODEL_CAPABILITIES.get(
            resolved_name,
            {
                "max_tokens": 4096,
                "context_length": 200000,
                "supports_thinking": True,
                "supports_1m_context": False,
                "supports_memory": False,
                "supports_vision": True,
                "supports_effort": False,
                "supports_programmatic_calling": False,
            },
        )

    class Valves(BaseModel):
        ANTHROPIC_API_KEY: str = "Your API Key Here"
        # ENABLE_CLAUDE_MEMORY: bool = Field(
        #     default=False,
        #     description="Enable Claude memory tool",
        # )
        ENABLE_1M_CONTEXT: bool = Field(
            default=False,
            description="Enable 1M token context window for Claude Sonnet 4 (requires Tier 4 API access)",
        )
        WEB_SEARCH: bool = Field(
            default=True,
            description="Enable web search tool for Claude models. Use Anthropic Web Search Toggle Function for fine grained control",
        )
        MAX_TOOL_CALLS: int = Field(
            default=15,
            ge=1,
            le=50,
            description="Maximum number of tool execution loops allowed per request. Each loop involves Claude generating tool calls, executing them, and feeding results back. Prevents infinite loops.",
        )
        MAX_RETRIES: int = Field(
            default=3,
            ge=0,
            le=50,
            description="Maximum number of retries for failed requests (due to rate limiting, transient errors or connection issues)",
        )
        CACHE_CONTROL: Literal[
            "cache disabled",
            "cache tools array only",
            "cache tools array and system prompt",
            "cache tools array, system prompt and messages",
        ] = Field(
            default="cache disabled",
            description="Cache control scope for prompts",
        )
        WEB_SEARCH_USER_CITY: str = Field(
            default="",
            description="User's city for web search.",
        )
        WEB_SEARCH_USER_REGION: str = Field(
            default="",
            description="User's region/state for web search",
        )
        WEB_SEARCH_USER_COUNTRY: str = Field(
            default="",
            description="User's country code for web search",
        )
        WEB_SEARCH_USER_TIMEZONE: str = Field(
            default="",
            description="User's timezone for web search.",
        )
        # # Programmatic Tool Calling
        # ENABLE_PROGRAMMATIC_TOOL_CALLING: bool = Field(
        #     default=False,
        #     description="Enable programmatic tool calling. Claude can call tools from within code execution.",
        # )
        # Tool Search
        ENABLE_TOOL_SEARCH: bool = Field(
            default=False,
            description="Enable tool search. Allows Claude to search for tools by name/description when many tools are available.",
        )
        TOOL_SEARCH_TYPE: Literal["regex", "bm25"] = Field(
            default="bm25",
            description="Type of tool search: 'regex' for pattern matching or 'bm25' for natural language search.",
        )
        TOOL_SEARCH_MAX_DESCRIPTION_LENGTH: int = Field(
            default=100,
            ge=10,
            le=10000,
            description="Maximum tool description length. Tools with longer JSON definitions will be deferred for lazy loading.",
        )
        TOOL_SEARCH_EXCLUDE_TOOLS: List[str] = Field(
           default=["web_search"],
            description="Tools to exclude from defer_loading when tool search is enabled. These tools will always be loaded immediately.",
        )
        # Context Editing
        CONTEXT_EDITING_STRATEGY: Literal[
            "none", "clear_tool_results", "clear_thinking", "clear_both"
        ] = Field(
            default="none",
            description="Context editing strategy: none (disabled), clear_tool_results, clear_thinking, or clear_both.",
        )
        # Thinking block clearing parameters
        CONTEXT_EDITING_THINKING_KEEP: int = Field(
            default=5,
            ge=0,
            le=9999,
            description="How many thinking blocks to keep",
        )
        # Tool result clearing parameters
        CONTEXT_EDITING_TOOL_TRIGGER: int = Field(
            default=50000,
            ge=1000,
            le=500000,
            description="Token count threshold that triggers tool result clearing.",
        )
        CONTEXT_EDITING_TOOL_KEEP: int = Field(
            default=5,
            ge=0,
            le=100,
            description="Number of recent tool results to preserve when clearing.",
        )
        CONTEXT_EDITING_TOOL_CLEAR_AT_LEAST: int = Field(
            default=10000,
            ge=0,
            le=100000,
            description="Minimum tokens to clear when triggered (helps with cache optimization).",
        )
        CONTEXT_EDITING_TOOL_CLEAR_TOOL_INPUT: bool = Field(
            default=False,
            description="Also clear tool input parameters when clearing tool results.",
        )

    class UserValves(BaseModel):
        ENABLE_THINKING: bool = Field(
            default=False,
            description="Enable Extended Thinking",
        )
        THINKING_BUDGET_TOKENS: int = Field(
            default=4096,
            ge=0,
            le=32000,
            description="Thinking budget tokens",
        )
        EFFORT: Literal["low", "medium", "high"] = Field(
            default="high",
            description="Effort level for this user. Also Controllable with OpenWebUI's reasoning_effort parameter.",
        )
        SHOW_TOKEN_COUNT: bool = Field(
            default=False,
            description="Show Context Window Progress",
        )
        WEB_SEARCH_MAX_USES: int = Field(
            default=5,
            ge=1,
            le=20,
            description="Maximum number of web searches",
        )
        WEB_SEARCH_USER_CITY: str = Field(
            default="",
            description="User's city for web search.",
        )
        WEB_SEARCH_USER_REGION: str = Field(
            default="",
            description="User's region/state for web search",
        )
        WEB_SEARCH_USER_COUNTRY: str = Field(
            default="",
            description="User's country code for web search",
        )
        WEB_SEARCH_USER_TIMEZONE: str = Field(
            default="",
            description="User's timezone for web search.",
        )

    def __init__(self):
        self.type = "manifold"
        self.id = "anthropic"
        self.valves = self.Valves()
        self.logger = logger
        # Track if we've warned about thinking+cache conflict per chat_id
        self._warned_thinking_cache_conflict: set = set()

    async def get_anthropic_models(self) -> List[dict]:
        """
        Fetches the current list of Anthropic models using the official Anthropic Python SDK.
        Fallback to static list on error. Returns OpenWebUI model dicts.
        """
        from anthropic import AsyncAnthropic

        models = []
        try:
            api_key = self.valves.ANTHROPIC_API_KEY
            client = AsyncAnthropic(api_key=api_key)
            async for m in client.models.list():
                name = m.id
                display_name = getattr(m, "display_name", name)

                # Get capabilities from centralized config
                info = self.get_model_info(name)

                models.append(
                    {
                        "id": f"anthropic/{name}",
                        "name": display_name,
                        "context_length": info["context_length"],
                        "supports_vision": info["supports_vision"],
                        "supports_thinking": info["supports_thinking"],
                        "is_hybrid_model": info["supports_thinking"],
                        "max_output_tokens": info["max_tokens"],
                        "info": {
                            "meta": {
                                "capabilities": {
                                    "status_updates": True  # Enable status events in OpenWebUI 0.6.33+
                                }
                            }
                        },
                    }
                )
            return models
        except Exception as e:
            logging.warning(
                f"Could not fetch models from SDK/API, using static list. Reason: {e}"
            )
            # Fallback to static list
            for name, info in self.MODEL_CAPABILITIES.items():
                models.append(
                    {
                        "id": f"anthropic/{name}",
                        "name": name,
                        "context_length": info["context_length"],
                        "supports_vision": info["supports_vision"],
                        "supports_thinking": info["supports_thinking"],
                        "is_hybrid_model": info["supports_thinking"],
                        "max_output_tokens": info["max_tokens"],
                        "info": {"meta": {"capabilities": {"status_updates": True}}},
                    }
                )
        return models

    async def pipes(self) -> List[dict]:
        return await self.get_anthropic_models()

    def _is_rag_message(
        self, content: List[dict], __files__: Optional[Any] = None
    ) -> bool:
        """
        Detect if a message contains RAG context or transient data that shouldn't be cached.
        Returns True if RAG (Retrieval) is detected.
        Returns False if only Full Context files, Images, Audio, or no files are present.
        """
        if __files__:
            for file in __files__:
                # Check for RAG types
                file_type = file.get("type", "file")
                if file_type in ["collection", "web_search"]:
                    return True

                # 'file' is RAG unless context is explicitly 'full'
                if file_type == "file" and file.get("context") != "full":
                    return True

            # If we get here, all files are safe (Full Context, Images, Audio)
            return False

        for block in content:
            if block.get("type") == "text":
                text = block.get("text", "")
                # Check for common RAG markers
                if "<context>" in text or ("### Task:" in text and "<source" in text):
                    return True
        return False

    async def _create_payload(
        self,
        body: Dict,
        __metadata__: dict[str, Any],
        __user__: Dict[str, Any],
        __tools__: Optional[Dict[str, Dict[str, Any]]],
        __event_emitter__: Callable[[Dict[str, Any]], Awaitable[None]],
        __files__: Optional[Dict[str, Any]] = None,
    ) -> tuple[dict, dict]:
        actual_model_name = body["model"].split("/")[-1]
        model_info = self.get_model_info(actual_model_name)
        max_tokens_limit = model_info["max_tokens"]
        requested_max_tokens = body.get("max_tokens", max_tokens_limit)
        max_tokens = min(requested_max_tokens, max_tokens_limit)
        payload: dict[str, Any] = {
            "model": actual_model_name,
            "max_tokens": max_tokens,
            "stream": body.get("stream", True),
            "metadata": body.get("metadata", {}),
        }
        if body.get("temperature") is not None:
            payload["temperature"] = float(body.get("temperature", 0))
        if body.get("top_k") is not None:
            payload["top_k"] = float(body.get("top_k", 0))
        if body.get("top_p") is not None:
            payload["top_p"] = float(body.get("top_p", 0))

        try:
            logger.debug(f" Thinking Filter: {__metadata__.get('anthropic_thinking')}")
            logger.debug(f"Tools: {json.dumps(__tools__, indent=2)}")
        except Exception as e:
            logger.debug(f"JSON dump failed: {e}")
            logger.debug(f"raw __metadata__: {__metadata__}")

        enable_thinking = __user__["valves"].ENABLE_THINKING
        thinking_budget_tokens = __user__["valves"].THINKING_BUDGET_TOKENS

        # Check for metadata overrides (highest priority)
        if "anthropic_thinking" in __metadata__:
            should_enable_thinking = __metadata__.get("anthropic_thinking", False)
        else:
            should_enable_thinking = enable_thinking

        if should_enable_thinking and model_info["supports_thinking"]:
            # Ensure thinking.budget_tokens < max_tokens and at least 1024
            requested_thinking_budget = thinking_budget_tokens
            # Clamp thinking budget to valid range
            max_valid_thinking_budget = max(max_tokens - 1, 1023)
            thinking_budget = max(
                1024, min(requested_thinking_budget, max_valid_thinking_budget)
            )
            # If max_tokens is too low, set thinking_budget to max_tokens - 1
            if max_tokens <= 1024:
                thinking_budget = max_tokens - 1 if max_tokens > 1 else 1
            payload["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}

        # Handle effort parameter (maps from OpenWebUI's reasoning_effort or user valves)
        # Priority: reasoning_effort param > user valve
        # Note: output_config is a beta feature and must be passed via extra_body
        effort_config = None
        if model_info["supports_effort"]:
            effort_level = __user__["valves"].EFFORT
            if body.get("reasoning_effort") in ["low", "medium", "high"]:
                effective_effort = body.get("reasoning_effort")
            else:
                effective_effort = effort_level
            effort_config = {"effort": effective_effort}

        raw_messages = body.get("messages", []) or []
        system_messages = []
        processed_messages: list[dict] = []
        extracted_user_context = None

        # Check if user has memory system enabled
        user_has_memory_system_enabled = False
        try:
            user_has_memory_system_enabled = (
                __user__.get("settings", {}).get("ui", {}).get("memory", False)
            )
        except (AttributeError, TypeError):
            pass

        logger.debug(f"Memory system enabled: {user_has_memory_system_enabled}")

        for msg in raw_messages:
            role = msg.get("role")
            raw_content = msg.get("content")

            processed_content = self._process_content(raw_content)
            if not processed_content:
                continue
            if role == "system":
                for block in processed_content:
                    text = block["text"]

                    # Only extract memory if user has memory system enabled
                    if user_has_memory_system_enabled and "\nUser Context:\n" in text:
                        # Extract and remove User Context
                        cleaned_text, extracted_user_context = (
                            self._extract_and_remove_memorys(text)
                        )

                        if extracted_user_context:
                            logger.debug(
                                f"✓ Extracted User Context: {extracted_user_context[:100]}..."
                            )
                            logger.debug(
                                f"✓ System prompt after removal (last 200 chars): ...{cleaned_text[-200:]}"
                            )

                        # Update block with cleaned text
                        block["text"] = cleaned_text

                    # Only add non-empty blocks to system (cache_control will be added later to last block only)
                    if block["text"].strip():
                        system_messages.append(block)
            else:
                # Only add messages with non-empty content (fixes Chat with Notes empty assistant messages)
                if processed_content:
                    processed_messages.append(
                        {"role": role, "content": processed_content}
                    )
                else:
                    logger.debug(f"Skipped message with empty content (role: {role})")

        # Append extracted user context to last user message
        if extracted_user_context and processed_messages:
            # Find last user message
            for i in range(len(processed_messages) - 1, -1, -1):
                if processed_messages[i]["role"] == "user":
                    content = processed_messages[i]["content"]
                    if isinstance(content, list):
                        # Add context as new text block
                        content.append(
                            {
                                "type": "text",
                                "text": f"\n\n---\n**IMPORTANT:** The following is NOT part of the user's message, but context from a memory system to help answer the user's questions:\n\n{extracted_user_context}",
                            }
                        )
                    break

        if not processed_messages:
            raise ValueError("No valid messages to process")

        # Check feature flags
        enable_programmatic_calling = False
        enable_tool_search = self.valves.ENABLE_TOOL_SEARCH
        tool_search_type = self.valves.TOOL_SEARCH_TYPE
        max_tool_description_length = self.valves.TOOL_SEARCH_MAX_DESCRIPTION_LENGTH

        # Correct Order for Caching: Tools, System, Messages
        tools_list = self._convert_tools_to_claude_format(
            __tools__,
            actual_model_name,
            __user__,
            __metadata__,
            enable_programmatic_calling=enable_programmatic_calling,
            enable_tool_search=enable_tool_search,
            max_tool_description_length=max_tool_description_length,
        )

        # Decide on code execution inclusion early so we can set beta headers later
        activate_code_execution = __metadata__.get(
            "activate_code_execution_tool", False
        )

        # Programmatic tool calling uses code_execution_20250825 (newer version)
        if enable_programmatic_calling:
            code_exec_tool = {
                "type": "code_execution_20250825",
                "name": "code_execution",
            }
            # Avoid duplicates if already added
            if not any(t.get("name") == "code_execution" for t in tools_list):
                tools_list.insert(0, code_exec_tool)  # Insert at beginning

        # Regular code execution toggle (older version)
        elif activate_code_execution:
            code_exec_tool = {
                "type": "code_execution_20250522",
                "name": "code_execution",
            }
            # Avoid duplicates if already added
            if not any(t.get("name") == "code_execution" for t in tools_list):
                tools_list.append(code_exec_tool)

        # Add tool search tool if enabled
        if enable_tool_search:
            # Determine the tool search type
            if tool_search_type == "regex":
                tool_search_tool = {
                    "type": "tool_search_tool_regex_20251119",
                    "name": "tool_search_tool_regex",
                }
            else:  # bm25 (default)
                tool_search_tool = {
                    "type": "tool_search_tool_bm25_20251119",
                    "name": "tool_search_tool_bm25",
                }

            # Add tool search tool at the beginning so Claude sees it first
            if not any(t.get("name") in ["tool_search_tool_regex", "tool_search_tool_bm25"] for t in tools_list):
                tools_list.insert(0, tool_search_tool)

        if tools_list and len(tools_list) > 0:
            # Add cache control to last tool when caching tools (alone or with system)
            # "cache tools only" = cache breakpoint at tools
            # "cache tools and system" = cache breakpoint at tools AND system (hierarchical)
            # Don't add cache_control to deferred tools (incompatible with defer_loading)
            if self.valves.CACHE_CONTROL in [
                "cache tools array only",
                "cache tools array and system prompt",
            ]:
                last_tool = tools_list[-1]
                # Only add cache_control if tool doesn't have defer_loading
                if not last_tool.get("defer_loading", False):
                    last_tool["cache_control"] = {"type": "ephemeral"}
                else:
                    # Find the last non-deferred tool to add cache_control
                    for i in range(len(tools_list) - 1, -1, -1):
                        if not tools_list[i].get("defer_loading", False):
                            tools_list[i]["cache_control"] = {"type": "ephemeral"}
                            break

        if tools_list:
            # Check if web_search is actually in the tools list
            has_web_search = any(t.get("name") == "web_search" for t in tools_list)
            
            # Check for enforced web search in metadata
            # If thinking is active, web_search cannot be enforced (API limitation)
            # but it should still be available in the tools list
            if __metadata__.get("web_search_enforced") and has_web_search:
                if "thinking" not in payload:
                    # No thinking active - enforce web_search
                    payload["tool_choice"] = {"type": "tool", "name": "web_search"}
                    logger.debug("Enforcing web_search via tool_choice")
                else:
                    # Thinking is active - cannot enforce web_search, but it's still available
                    payload["tool_choice"] = {"type": "auto"}
                    logger.debug("Thinking active - web_search added but not enforced (tool_choice=auto)")
                    # Notify user about the conflict
                    await self.emit_event(
                        {
                            "type": "notification",
                            "data": {
                                "type": "info",
                                "content": "🧠 Thinking mode is active - Web search was added but not enforced. Claude can use it if needed.",
                            },
                        },
                        __event_emitter__,
                    )
                __metadata__["web_search_enforced"] = False  # one-shot, clear the flag
            else:
                # No enforcement - use auto tool choice
                payload["tool_choice"] = {"type": "auto"}
                # Clear the flag even if web_search wasn't in tools (prevents repeated checks)
                if __metadata__.get("web_search_enforced"):
                    __metadata__["web_search_enforced"] = False
                    logger.debug("web_search_enforced was set but web_search not in tools list - cleared flag")
            payload["tools"] = tools_list

        if system_messages and len(system_messages) > 0:
            # Add cache_control to last system message block ONLY if caching up to system (not messages)
            # Support both old typo and corrected spelling for backward compatibility
            if self.valves.CACHE_CONTROL in ["cache tools array and system prompt"]:
                last_system_block = system_messages[-1]
                # Only add if block has non-empty text
                if (
                    last_system_block.get("type") == "text"
                    and last_system_block.get("text", "").strip()
                ):
                    last_system_block["cache_control"] = {"type": "ephemeral"}
            payload["system"] = system_messages

        if processed_messages and len(processed_messages) > 0:
            # Determine where to place the cache breakpoint
            target_msg_index = -1

            # Check if last message has RAG content
            last_msg = processed_messages[-1]
            if self._is_rag_message(last_msg.get("content", []), __files__):
                logger.debug(
                    "RAG content detected in last message. Moving cache breakpoint to previous message."
                )
                # If we have history, cache the previous message
                if len(processed_messages) > 1:
                    target_msg_index = -2
                else:
                    # If no history, we can't cache messages (only system/tools)
                    target_msg_index = None

            # Apply cache control to the target message
            if (
                target_msg_index is not None
                and self.valves.CACHE_CONTROL
                == "cache tools array, system prompt and messages"
            ):
                target_msg = processed_messages[target_msg_index]
                content_blocks = target_msg.get("content", [])
                if content_blocks:
                    last_content_block = content_blocks[-1]
                    # Only add cache_control if the block has non-empty text
                    if (
                        last_content_block.get("type") == "text"
                        and last_content_block.get("text", "").strip()
                    ):
                        last_content_block.setdefault(
                            "cache_control", {"type": "ephemeral"}
                        )

            payload["messages"] = processed_messages

        # Get API key from valves
        api_key = self.valves.ANTHROPIC_API_KEY

        headers = {
            "x-api-key": api_key,
            "anthropic-version": self.API_VERSION,
            "content-type": "application/json",
        }
        beta_headers: list[str] = []

        # Enable prompt caching if not disabled
        if self.valves.CACHE_CONTROL != "cache disabled":
            beta_headers.append("prompt-caching-2024-07-31")

        # Enable fine-grained tool streaming beta unconditionally for now (AIT-86)
        # This only affects chunking of tool input JSON; execution logic unchanged.
        beta_headers.append("fine-grained-tool-streaming-2025-05-14")

        # Add code execution beta if valve or metadata enforcement active
        if activate_code_execution:
            beta_headers.append("code-execution-2025-05-22")

        # Add advanced tool use beta (for programmatic calling and tool search)
        if enable_programmatic_calling or enable_tool_search:
            beta_headers.append("advanced-tool-use-2025-11-20")

        # Add context editing strategies if enabled
        context_editing_strategy = self.valves.CONTEXT_EDITING_STRATEGY
        if context_editing_strategy != "none":
            beta_headers.append("context-management-2025-06-27")

            # Build context_management array for payload
            # IMPORTANT: clear_thinking must be FIRST if present (API requirement)
            context_management = []

            # Add clear_thinking FIRST if needed
            if (
                context_editing_strategy in ["clear_thinking", "clear_both"]
                and should_enable_thinking
                and model_info["supports_thinking"]
            ):
                clear_thinking = {
                    "type": "clear_thinking_20251015",
                    "keep": {
                        "type": "thinking_turns",
                        "value": self.valves.CONTEXT_EDITING_THINKING_KEEP,
                    },
                }
                context_management.append(clear_thinking)

            # Add clear_tool_uses SECOND
            if (
                context_editing_strategy in ["clear_tool_results", "clear_both"]
                and len(tools_list) > 2
            ):
                clear_tool_uses = {
                    "type": "clear_tool_uses_20250919",
                    "trigger": {
                        "type": "input_tokens",
                        "value": self.valves.CONTEXT_EDITING_TOOL_TRIGGER,
                    },
                    "keep": {
                        "type": "tool_uses",
                        "value": self.valves.CONTEXT_EDITING_TOOL_KEEP,
                    },
                }
                if self.valves.CONTEXT_EDITING_TOOL_CLEAR_AT_LEAST > 0:
                    clear_tool_uses["clear_at_least"] = {
                        "type": "input_tokens",
                        "value": self.valves.CONTEXT_EDITING_TOOL_CLEAR_AT_LEAST,
                    }
                if self.valves.CONTEXT_EDITING_TOOL_CLEAR_TOOL_INPUT:
                    clear_tool_uses["clear_tool_inputs"] = True
                context_management.append(clear_tool_uses)

                # Check for thinking + cache conflict and warn once per conversation
            if (
                context_editing_strategy in ["clear_thinking", "clear_both"]
                and self.valves.CACHE_CONTROL
                == "cache tools array, system prompt and messages"
            ):
                chat_id = __metadata__.get("chat_id", "")
                if chat_id and chat_id not in self._warned_thinking_cache_conflict:
                    self._warned_thinking_cache_conflict.add(chat_id)
                    await self.emit_event(
                        {
                            "type": "notification",
                            "data": {
                                "type": "warning",
                                "content": "⚠️ Thinking block clearing is enabled with message caching. This may invalidate cached content when thinking blocks are cleared.",
                            },
                        },
                        __event_emitter__,
                    )
            if context_management:
                payload["context_management"] = {"edits": context_management}

        # Add 1M context header if enabled and model supports it
        if self.valves.ENABLE_1M_CONTEXT and model_info["supports_1m_context"]:
            beta_headers.append("context-1m-2025-08-07")

        # Add effort beta header and output_config if effort is configured
        if model_info["supports_effort"] and effort_config:
            beta_headers.append("effort-2025-11-24")
            payload["output_config"] = effort_config

        if beta_headers and len(beta_headers) > 0:
            headers["anthropic-beta"] = ",".join(beta_headers)
            # Add betas list to payload for beta.messages.stream
            payload["betas"] = beta_headers

        logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
        logger.debug(f"Headers: {headers}")

        return payload, headers

    def _convert_tools_to_claude_format(
        self,
        __tools__,
        actual_model_name: str,
        __user__: Dict[str, Any],
        __metadata__: dict[str, Any],
        enable_programmatic_calling: bool = False,
        enable_tool_search: bool = False,
        max_tool_description_length: int = 100,
    ) -> List[dict]:
        """
        Convert OpenWebUI tools format to Claude API format.
        Args:
            __tools__: Dict of tools from OpenWebUI
            actual_model_name: Model name for capability checking
            __user__: User dict for valve overrides
            __metadata__: Metadata dict for checking enforcement flags
            enable_programmatic_calling: If True, add allowed_callers to tools
            enable_tool_search: If True, defer tools with long descriptions
            max_tool_description_length: Max length before deferring a tool
        Returns:
            list: Tools in Claude API format
        """
        claude_tools = []
        tool_names_seen = set()  # Track unique tool names
        deferred_tools_count = 0

        if __tools__:
            try:
                logger.debug(f" Converting tools: {json.dumps(__tools__, indent=2)}")
            except Exception as e:
                logger.debug(f" JSON dump failed, printing tools directly: {__tools__}")
                logger.debug(f"Error was: {e}")
        else:
            logger.debug("No tools to convert")

        # Add web search tool if enabled OR if metadata enforces it (even if valve is disabled)
        web_search_enabled = self.valves.WEB_SEARCH or __metadata__.get("web_search_enforced", False)
        if web_search_enabled:
            # Get user location values with fallback to global valves
            city = (
                __user__["valves"].WEB_SEARCH_USER_CITY
                or self.valves.WEB_SEARCH_USER_CITY
            )
            region = (
                __user__["valves"].WEB_SEARCH_USER_REGION
                or self.valves.WEB_SEARCH_USER_REGION
            )
            country = (
                __user__["valves"].WEB_SEARCH_USER_COUNTRY
                or self.valves.WEB_SEARCH_USER_COUNTRY
            )
            timezone = (
                __user__["valves"].WEB_SEARCH_USER_TIMEZONE
                or self.valves.WEB_SEARCH_USER_TIMEZONE
            )

            # Build web search tool config
            web_search_tool = {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": __user__["valves"].WEB_SEARCH_MAX_USES,
            }

            # Only add user_location if at least one field has a value
            if city or region or country or timezone:
                web_search_tool["user_location"] = {
                    "type": "approximate",
                    "city": city,
                    "region": region,
                    "country": country,
                    "timezone": timezone,
                }

            claude_tools.append(web_search_tool)
            tool_names_seen.add("web_search")

        # Add Claude Memory tool if enabled and supported by model
        # if self.valves.ENABLE_CLAUDE_MEMORY and actual_model_name in self.MODELS_SUPPORTING_MEMORY_TOOL:
        #     claude_tools.append(
        #         {
        #             "type": "memory_20250818",
        #             "name": "memory"
        #         }
        #     )
        #     tool_names_seen.add("memory")

        if not __tools__ or len(__tools__) == 0:
            logger.debug(f"No tools provided, using default Claude tools")
            return claude_tools

        for tool_name, tool_data in __tools__.items():
            if not isinstance(tool_data, dict) or "spec" not in tool_data:
                logger.debug(f"Skipping invalid tool: {tool_name} - missing spec")
                continue

            spec = tool_data["spec"]

            # Extract basic tool info
            name = spec.get("name", tool_name)

            # Skip if tool name already exists
            if name in tool_names_seen:
                logger.info(f"Skipping duplicate tool: {name}")
                continue

            # Skip if toolname starts with _ or __
            if name.startswith("_"):
                logger.debug(f"Skipping private tool: {name}")
                continue

            description = spec.get("description", f"Tool: {name}")
            parameters = spec.get("parameters", {})

            # Convert OpenWebUI parameters to Claude input_schema format
            # OpenWebUI parameters are typically already in JSON Schema format
            input_schema = {
                "type": "object",
                "properties": parameters.get("properties", {}),
            }

            # Add required fields if they exist
            if "required" in parameters:
                input_schema["required"] = parameters["required"]

            # Create Claude tool format
            claude_tool = {
                "name": name,
                "description": description,
                "input_schema": input_schema,
            }

            # Add allowed_callers for programmatic tool calling (only if model supports it)
            # When enabled, tools can ONLY be called from code execution, not directly by Claude
            # This enables Claude to write code that calls tools programmatically for:
            # - Large data processing (filter/aggregate before returning to context)
            # - Multi-step workflows (save tokens by chaining tool calls in code)
            # - Conditional logic based on intermediate results
            if enable_programmatic_calling:
                model_info = self.get_model_info(actual_model_name)
                if model_info.get("supports_programmatic_calling", False):
                    claude_tool["allowed_callers"] = ["code_execution_20250825"]

            # Check if tool should be deferred for tool search
            if enable_tool_search:
                # Skip deferring if tool is in exclusion list
                if name not in self.valves.TOOL_SEARCH_EXCLUDE_TOOLS:
                    # Calculate tool definition size (JSON representation)
                    tool_json = json.dumps(claude_tool)
                    if len(tool_json) > max_tool_description_length:
                        claude_tool["defer_loading"] = True
                        deferred_tools_count += 1
                        logger.debug(
                            f"Tool '{name}' deferred (size: {len(tool_json)} > {max_tool_description_length})"
                        )
                else:
                    logger.debug(f"Tool '{name}' excluded from deferring (in TOOL_SEARCH_EXCLUDE_TOOLS)")

            claude_tools.append(claude_tool)
            tool_names_seen.add(name)

        if deferred_tools_count > 0:
            logger.debug(f"Deferred {deferred_tools_count} tools for tool search")

        logger.debug(f"Total tools converted: {len(claude_tools)}")

        return claude_tools

    async def pipe(
        self,
        body: dict[str, Any],
        __user__: Dict[str, Any],
        __event_emitter__: Callable[[Dict[str, Any]], Awaitable[None]],
        __metadata__: dict[str, Any] = {},
        __tools__: Optional[Dict[str, Dict[str, Any]]] = None,
        __files__: Optional[Dict[str, Any]] = None,
        __task__: Optional[dict[str, Any]] = None,
        __task_body__: Optional[dict[str, Any]] = None,
    ):
        """
        OpenWebUI Claude streaming pipe with integrated streaming logic.
        """
        final_message: list[str] = []

        # Create request-local wrapper for emit_event to prevent cross-talk between parallel requests
        # This ensures each request uses its own __event_emitter__ instead of shared self.eventemitter
        async def emit_event_local(event: dict):
            """Request-local event emitter wrapper"""
            await self.emit_event(event, __event_emitter__)

        def final_text() -> str:
            return "".join(final_message)

        try:
            # Get API key
            api_key = self.valves.ANTHROPIC_API_KEY
            if not api_key:
                error_msg = "Error: No API key configured"
                logger.error(f"{error_msg}")
                await emit_event_local(
                    {
                        "type": "status",
                        "data": {
                            "description": "No API Key Set!",
                            "done": False,
                        },
                    }
                )
                return error_msg

            # STEP 1: Detect if task model (generate title, tags, follow-ups etc.), handle it separately
            if __task__:
                logger.debug(f"Detected task model: {__task__}")
                return await self._run_task_model_request(body, __event_emitter__)

            # STEP 2: Await tools if needed
            if inspect.isawaitable(__tools__):
                __tools__ = await __tools__

            # STEP 3: Auto-enable native function calling if tools are present
            # This prevents OpenWebUI's function_calling task system from being triggered
            if __tools__ and MODELS_AVAILABLE:
                try:
                    # Get the OpenWebUI model ID from metadata
                    openwebui_model_id = (
                        __metadata__.get("model_id") if __metadata__ else None
                    )
                    if not openwebui_model_id and body and "model" in body:
                        openwebui_model_id = body["model"]

                    if openwebui_model_id:
                        model = Models.get_model_by_id(openwebui_model_id)
                        if model:
                            params = dict(model.params or {})
                            if params.get("function_calling") != "native":
                                logger.debug(
                                    f"Auto-enabling native function calling for model: {openwebui_model_id}"
                                )

                                # Notify user
                                await emit_event_local(
                                    {
                                        "type": "notification",
                                        "data": {
                                            "type": "info",
                                            "content": f"Enabling native function calling for model: {openwebui_model_id}. Please re-run your query.",
                                        },
                                    }
                                )

                                params["function_calling"] = "native"
                                form_data = model.model_dump()
                                form_data["params"] = params
                                Models.update_model_by_id(
                                    openwebui_model_id, ModelForm(**form_data)
                                )
                except Exception as e:
                    logger.warning(
                        f"Could not auto-enable native function calling: {e}"
                    )

            payload, headers = await self._create_payload(
                body, __metadata__, __user__, __tools__, __event_emitter__, __files__
            )

            api_key = headers.get("x-api-key", self.valves.ANTHROPIC_API_KEY)
            client = AsyncAnthropic(api_key=api_key, default_headers=headers)
            payload_for_stream = {k: v for k, v in payload.items() if k != "stream"}

            # Stream loop variables
            token_buffer_size = getattr(self.valves, "TOKEN_BUFFER_SIZE", 1)
            is_model_thinking = False
            current_block_type = None  # Track current block type for stop events
            conversation_ended = False
            max_function_calls = self.valves.MAX_TOOL_CALLS
            current_function_calls = 0
            has_pending_tool_calls = False
            tools_buffer = ""
            tool_calls = []
            running_tool_tasks = []  # Async tasks for executing tools immediately
            tool_call_data_list = []  # Store tool metadata for result matching
            tool_use_blocks = []  # Store tool_use blocks for assistant message
            chunk = ""
            chunk_count = 0
            thinking_message = ""
            thinking_blocks = []  # Preserve thinking blocks for multi-turn
            current_thinking_block = {}  # Track current thinking block
            current_search_query = ""  # Track the current web search query
            citation_counter = 0  # Track citation numbers for inline citations
            citations_list = []  # Store citations for reference list
            retry_attempts = 0
            total_usage = {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            }
            first_text_emitted = False  # Track if we've emitted "Responding..." status
            # Track active server tool use block
            active_server_tool_name = None
            active_server_tool_id = None
            server_tool_input_buffer = ""  # Accumulate server tool input JSON

            # Track the block with cache_control to ensure it persists across tool loops
            cached_block = None
            if payload_for_stream.get("messages"):
                for msg in reversed(payload_for_stream["messages"]):
                    content = msg.get("content")
                    if isinstance(content, list):
                        for block in reversed(content):
                            if isinstance(block, dict) and "cache_control" in block:
                                cached_block = block
                                break
                    if cached_block:
                        break

            await emit_event_local(
                {
                    "type": "status",
                    "data": {
                        "description": "Waiting for response...",
                        "done": False,
                        "hidden": False,
                    },
                }
            )
            while (
                current_function_calls < max_function_calls
                and not conversation_ended
                and retry_attempts <= self.valves.MAX_RETRIES
            ):
                # Track output tokens for this specific stream iteration to handle cumulative updates
                stream_output_tokens = 0

                try:
                    # Ensure cache_control is preserved (some SDKs/APIs might strip it or we might lose it in loop)
                    if cached_block and "cache_control" not in cached_block:
                        logger.debug("Restoring missing cache_control marker")
                        cached_block["cache_control"] = {"type": "ephemeral"}

                    async with client.beta.messages.stream(
                        **payload_for_stream
                    ) as stream:
                        async for event in stream:
                            event_type = getattr(event, "type", None)
                            # Only log event_type and minimal event info, skip snapshot fields
                            if hasattr(event, "__dict__"):
                                event_dict = {
                                    k: v
                                    for k, v in event.__dict__.items()
                                    if k != "snapshot"
                                }
                                logger.debug(
                                    f"Received event: %s with %s",
                                    event_type,
                                    str(event_dict)[:200]
                                    + ("..." if len(str(event_dict)) > 200 else ""),
                                )
                            else:
                                logger.debug(
                                    f"Received event: %s with %s",
                                    event_type,
                                    str(event)[:200]
                                    + ("..." if len(str(event)) > 200 else ""),
                                )
                            if event_type == "message_start":
                                message = getattr(event, "message", None)
                                if message:
                                    request_id = getattr(message, "id", None)
                                    logger.debug(
                                        f" Message started with ID: {request_id}"
                                    )
                                    usage = getattr(message, "usage", {})
                                    if usage:
                                        input_tokens = getattr(usage, "input_tokens", 0)
                                        # Output tokens in message_start are usually 0 or small, but we track them
                                        current_output_tokens = getattr(
                                            usage, "output_tokens", 0
                                        )
                                        cache_creation_input_tokens = getattr(
                                            usage,
                                            "cache_creation_input_tokens",
                                            0,
                                        )
                                        cache_read_input_tokens = getattr(
                                            usage, "cache_read_input_tokens", 0
                                        )

                                        # Accumulate billable tokens (for cost tracking)
                                        total_usage["input_tokens"] += input_tokens
                                        total_usage[
                                            "cache_creation_input_tokens"
                                        ] += cache_creation_input_tokens

                                        # Set last-turn values (non-accumulating)
                                        total_usage["cache_read_input_tokens"] = (
                                            cache_read_input_tokens
                                        )

                                        # Handle output tokens (cumulative within stream)
                                        diff = (
                                            current_output_tokens - stream_output_tokens
                                        )
                                        total_usage["output_tokens"] += diff
                                        stream_output_tokens = current_output_tokens

                                        # Calculate total context size from last turn
                                        total_usage["total_tokens"] = (
                                            input_tokens
                                            + current_output_tokens
                                            + cache_creation_input_tokens
                                            + cache_read_input_tokens
                                        )

                                        logger.debug(
                                            f" Usage stats: input={input_tokens}, output={current_output_tokens}, cache_creation={cache_creation_input_tokens}, cache_read={cache_read_input_tokens}"
                                        )
                                        logger.debug(
                                            f" Accumulated usage: {total_usage}"
                                        )

                            elif event_type == "content_block_start":
                                content_block = getattr(event, "content_block", None)
                                content_type = getattr(content_block, "type", None)
                                current_block_type = content_type
                                if not content_block:
                                    continue
                                if content_type == "text":
                                    chunk += content_block.text or ""
                                if content_type == "thinking":
                                    is_model_thinking = True
                                    thinking_message = "\n<details>\n<summary>🧠 Thoughts</summary>\n\n"
                                    current_thinking_block = {
                                        "type": "thinking",
                                        "thinking": "",
                                    }
                                    await emit_event_local(
                                        {
                                            "type": "status",
                                            "data": {
                                                "description": "Thinking...",
                                                "done": False,
                                            },
                                        }
                                    )
                                if content_type == "tool_use":
                                    tool_name = getattr(
                                        content_block, "name", "unknown"
                                    )

                                    logger.debug(
                                        f"🔧 Tool use block started: {tool_name}"
                                    )

                                    # Emit status immediately when tool_use block starts (before input generation)
                                    await emit_event_local(
                                        {
                                            "type": "status",
                                            "data": {
                                                "description": f"🔧 Executing tool: {tool_name}",
                                                "done": False,
                                            },
                                        }
                                    )
                                    # Give UI time to update
                                    await asyncio.sleep(0.05)

                                    tools_buffer = (
                                        "{"
                                        f'"type": "{content_block.type}", '
                                        f'"id": "{content_block.id}", '
                                        f'"name": "{content_block.name}", '
                                        f'"input": '
                                    )

                                if content_type == "server_tool_use":
                                    # Track active server tool (web_search, code_execution)
                                    # No need for tools_buffer - server handles execution
                                    active_server_tool_name = getattr(
                                        content_block, "name", ""
                                    )
                                    active_server_tool_id = getattr(
                                        content_block, "id", ""
                                    )
                                    server_tool_input_buffer = (
                                        ""  # Reset buffer for new tool
                                    )

                                    logger.debug(
                                        f"Server tool started: {active_server_tool_name} (ID: {active_server_tool_id})"
                                    )

                                    if active_server_tool_name == "code_execution":
                                        await emit_event_local(
                                            {
                                                "type": "status",
                                                "data": {
                                                    "description": "Executing Code...",
                                                    "done": False,
                                                },
                                            }
                                        )
                                    elif active_server_tool_name == "web_search":
                                        await emit_event_local(
                                            {
                                                "type": "status",
                                                "data": {
                                                    "description": "Starting Web Search...",
                                                    "done": False,
                                                },
                                            }
                                        )
                                    elif active_server_tool_name in [
                                        "tool_search_tool_regex",
                                        "tool_search_tool_bm25",
                                    ]:
                                        await emit_event_local(
                                            {
                                                "type": "status",
                                                "data": {
                                                    "description": "🔍 Searching for tools...",
                                                    "done": False,
                                                },
                                            }
                                        )

                                if content_type == "code_execution_tool_result":
                                    result_block = getattr(content_block, "content", {})
                                    stdout = result_block.get("stdout", "")
                                    stderr = result_block.get("stderr", "")
                                    if stdout or stderr:
                                        code_result_msg = (
                                            f"\n<details>\n"
                                            f"<summary>Code Execution Result</summary>\n\n"
                                            + (
                                                f"```\n{stdout}\n```\n"
                                                if stdout
                                                else ""
                                            )
                                            + (f"```\n{stderr}\n```" if stderr else "")
                                            + f"</details>\n"
                                        )
                                        await self.emit_message_delta(
                                            code_result_msg,
                                            final_message,
                                            __event_emitter__,
                                        )
                                if content_type == "web_search_tool_result":
                                    logger.debug(
                                        f" Processing web search result event: {event}"
                                    )
                                    content_items = getattr(
                                        content_block, "content", []
                                    )
                                    if content_items and len(content_items) > 0:
                                        error_code = getattr(
                                            content_block, "error_code", None
                                        )
                                        if error_code:
                                            await self.handle_errors(
                                                Exception(
                                                    f"Web search error: {error_code}"
                                                )
                                            )
                                        else:
                                            # Extract first result title for status
                                            first_result = (
                                                content_items[0]
                                                if content_items
                                                else None
                                            )
                                            result_title = (
                                                getattr(first_result, "title", "")
                                                if first_result
                                                else ""
                                            )
                                            result_count = len(content_items)

                                            if result_title and result_count > 0:
                                                status_desc = f"Found {result_count} results - {result_title}"
                                                if result_count > 1:
                                                    status_desc += (
                                                        f" +{result_count-1} more"
                                                    )
                                            else:
                                                status_desc = "Web Search Complete"

                                            await emit_event_local(
                                                {
                                                    "type": "status",
                                                    "data": {
                                                        "description": status_desc,
                                                        "done": True,
                                                    },
                                                }
                                            )

                                # Handle tool search results (only if tool search is enabled)
                                if content_type == "tool_search_tool_result":
                                    logger.debug(
                                        f" Processing tool search result event: {event}"
                                    )
                                    # Only show status events if tool search valve is enabled
                                    if self.valves.ENABLE_TOOL_SEARCH:
                                        # Access nested structure: content_block.content.tool_references
                                        content = getattr(
                                            content_block, "content", None
                                        )
                                        tool_references = []
                                        if content:
                                            # Handle both dict and object access patterns
                                            if hasattr(content, "tool_references"):
                                                tool_references = getattr(
                                                    content, "tool_references", []
                                                )
                                            elif isinstance(content, dict):
                                                tool_references = content.get(
                                                    "tool_references", []
                                                )

                                        logger.debug(
                                            f"Tool search result - found {len(tool_references)} tool references"
                                        )

                                        if tool_references and len(tool_references) > 0:
                                            # Extract tool names from references
                                            tool_names = []
                                            for ref in tool_references[:5]:
                                                if hasattr(ref, "tool_name"):
                                                    tool_names.append(
                                                        getattr(
                                                            ref, "tool_name", "unknown"
                                                        )
                                                    )
                                                elif isinstance(ref, dict):
                                                    tool_names.append(
                                                        ref.get("tool_name", "unknown")
                                                    )

                                            status_desc = f"🔍 Found {len(tool_references)} tool(s): {', '.join(tool_names)}"
                                            logger.debug(
                                                f"Tool search success: {status_desc}"
                                            )
                                            await emit_event_local(
                                                {
                                                    "type": "status",
                                                    "data": {
                                                        "description": status_desc,
                                                        "done": True,
                                                    },
                                                }
                                            )
                                        else:
                                            logger.debug(
                                                "Tool search returned no results"
                                            )
                                            await emit_event_local(
                                                {
                                                    "type": "status",
                                                    "data": {
                                                        "description": "🔍 Tool search: No matching tools found",
                                                        "done": True,
                                                    },
                                                }
                                            )

                                # Handle context cleared events
                                if content_type == "context_cleared":
                                    cleared_info = getattr(content_block, "cleared", {})
                                    cleared_type = (
                                        getattr(cleared_info, "type", "unknown")
                                        if hasattr(cleared_info, "type")
                                        else cleared_info.get("type", "unknown")
                                    )
                                    cleared_tokens = (
                                        getattr(cleared_info, "tokens_cleared", 0)
                                        if hasattr(cleared_info, "tokens_cleared")
                                        else cleared_info.get("tokens_cleared", 0)
                                    )

                                    if cleared_type == "tool_uses":
                                        status_desc = f"🧹 Cleared tool results: ~{cleared_tokens:,} tokens removed"
                                    elif cleared_type == "thinking":
                                        status_desc = f"🧹 Cleared thinking blocks: ~{cleared_tokens:,} tokens removed"
                                    else:
                                        status_desc = f"🧹 Context cleared: ~{cleared_tokens:,} tokens removed"

                                    await emit_event_local(
                                        {
                                            "type": "status",
                                            "data": {
                                                "description": status_desc,
                                                "done": True,
                                            },
                                        }
                                    )
                                    logger.debug(
                                        f"Context cleared: type={cleared_type}, tokens={cleared_tokens}"
                                    )

                            elif event_type == "content_block_delta":
                                delta = getattr(event, "delta", None)
                                if delta:
                                    delta_type = getattr(delta, "type", None)
                                    if delta_type == "thinking_delta":
                                        thinking_text = getattr(delta, "thinking", "")
                                        thinking_message += thinking_text
                                        # Preserve thinking for API
                                        if current_thinking_block:
                                            current_thinking_block[
                                                "thinking"
                                            ] += thinking_text
                                    elif delta_type == "signature_delta":
                                        # Capture signature for thinking block preservation
                                        signature = getattr(delta, "signature", "")
                                        if current_thinking_block and signature:
                                            current_thinking_block["signature"] = (
                                                signature
                                            )
                                    elif delta_type == "text_delta":
                                        text_delta = getattr(delta, "text", "")

                                        # Emit "Responding..." status on first text delta (only once)
                                        if (
                                            not first_text_emitted
                                            and not is_model_thinking
                                            and not active_server_tool_name
                                        ):
                                            await emit_event_local(
                                                {
                                                    "type": "status",
                                                    "data": {
                                                        "description": "Responding...",
                                                        "done": False,
                                                    },
                                                }
                                            )
                                            first_text_emitted = True

                                        chunk += text_delta
                                        chunk_count += 1
                                    elif delta_type == "input_json_delta":
                                        partial = getattr(delta, "partial_json", "")

                                        # Handle server tool input separately from client tools
                                        if active_server_tool_name:
                                            # Server tool (web_search, code_execution) - accumulate and extract query
                                            server_tool_input_buffer += partial

                                            if active_server_tool_name == "web_search":
                                                try:
                                                    # Try to parse the accumulated JSON to extract query
                                                    parsed = json.loads(
                                                        server_tool_input_buffer
                                                    )
                                                    if "query" in parsed:
                                                        new_query = parsed["query"]
                                                        logger.debug(
                                                            f"Web search query complete: '{new_query}'"
                                                        )

                                                        # Emit status only once when we get the complete query
                                                        if (
                                                            new_query
                                                            and new_query
                                                            != current_search_query
                                                        ):
                                                            current_search_query = (
                                                                new_query
                                                            )
                                                            await emit_event_local(
                                                                {
                                                                    "type": "status",
                                                                    "data": {
                                                                        "description": f"🔍 Searching for: {current_search_query}",
                                                                        "done": False,
                                                                    },
                                                                }
                                                            )
                                                except json.JSONDecodeError:
                                                    # Partial JSON not complete yet, will get more in next delta
                                                    logger.debug(
                                                        f"Partial web_search JSON: {server_tool_input_buffer}"
                                                    )
                                                except Exception as e:
                                                    logger.debug(
                                                        f"Web search query extraction error: {e}"
                                                    )
                                            elif (
                                                active_server_tool_name
                                                == "code_execution"
                                            ):
                                                # Code execution input - just log it
                                                logger.debug(
                                                    f"Code execution input: {server_tool_input_buffer[:100]}..."
                                                )
                                            elif (
                                                active_server_tool_name == "tool_search"
                                            ):
                                                # Tool search input - extract and show query
                                                try:
                                                    parsed = json.loads(
                                                        server_tool_input_buffer
                                                    )
                                                    if "query" in parsed:
                                                        search_query = parsed["query"]
                                                        logger.debug(
                                                            f"Tool search query: '{search_query}'"
                                                        )
                                                        await emit_event_local(
                                                            {
                                                                "type": "status",
                                                                "data": {
                                                                    "description": f"🔍 Tool search: {search_query}",
                                                                    "done": False,
                                                                },
                                                            }
                                                        )
                                                except json.JSONDecodeError:
                                                    logger.debug(
                                                        f"Partial tool_search JSON: {server_tool_input_buffer}"
                                                    )
                                                except Exception as e:
                                                    logger.debug(
                                                        f"Tool search query extraction error: {e}"
                                                    )
                                        else:
                                            # Client-side tool - accumulate in tools_buffer
                                            tools_buffer += partial
                                            logger.debug(
                                                f"Client tool input accumulated: {len(tools_buffer)} chars"
                                            )
                                    elif delta_type == "citations_delta":
                                        # Handle citations within content_block_delta AND add inline citation number
                                        citation_counter += 1
                                        # Add inline citation number to chunk
                                        chunk += f"[{citation_counter}]"
                                        chunk_count += 1

                                        # Process and store citation
                                        await self.handle_citation(
                                            event, __event_emitter__, citation_counter
                                        )

                            elif event_type == "content_block_stop":
                                content_block = getattr(event, "content_block", None)
                                content_type = (
                                    getattr(content_block, "type", None)
                                    if content_block
                                    else None
                                )
                                # Fallback to tracked type if event doesn't have it (common in SDK)
                                if not content_type and current_block_type:
                                    content_type = current_block_type

                                event_name = getattr(event, "name", "")

                                # When a text block ends, emit any remaining chunk
                                if content_type == "text" and chunk.strip():
                                    await self.emit_message_delta(
                                        chunk + "\n", final_message, __event_emitter__
                                    )
                                    chunk = ""
                                    chunk_count = 0

                                # Reset server tool tracking when block stops
                                if content_type == "server_tool_use":
                                    logger.debug(
                                        f"Server tool block stopped: {active_server_tool_name}"
                                    )
                                    # Add line break after server tool use
                                    await self.emit_message_delta(
                                        "\n", final_message, __event_emitter__
                                    )
                                    active_server_tool_name = None
                                    active_server_tool_id = None
                                    server_tool_input_buffer = ""

                                # Close tools_buffer for normal tool_use content blocks AND execute immediately
                                if content_type == "tool_use" and tools_buffer:
                                    # Check if it's valid JSON already, if not close it
                                    try:
                                        json.loads(tools_buffer)
                                        # Already valid JSON, no need to close
                                        logger.debug(
                                            f" tools_buffer already valid JSON: {tools_buffer}"
                                        )
                                    except json.JSONDecodeError:
                                        # Check if input is empty (ends with "input": )
                                        if tools_buffer.rstrip().endswith(
                                            '"input":'
                                        ) or tools_buffer.rstrip().endswith(
                                            '"input": '
                                        ):
                                            # Add empty object for input
                                            tools_buffer += " {}"
                                            logger.debug(
                                                f" Added empty input object: {tools_buffer}"
                                            )
                                        # Invalid JSON, need to close the main object
                                        tools_buffer += "}"
                                        logger.debug(
                                            f" Closed tools_buffer in content_block_stop: {tools_buffer}"
                                        )

                                    # Parse and store this tool_use block
                                    logger.debug(f"Parsed tool call: {tools_buffer}")

                                    # Parse and start tool execution immediately!
                                    try:
                                        tool_call_data = json.loads(tools_buffer)
                                        tool_name = tool_call_data.get("name", "")
                                        tool_input = tool_call_data.get("input", {})
                                        tool_id = tool_call_data.get("id", "")

                                        # Store tool_use block for assistant message
                                        tool_use_blocks.append(
                                            {
                                                "type": "tool_use",
                                                "id": tool_id,
                                                "name": tool_name,
                                                "input": tool_input,
                                            }
                                        )

                                        # Look up tool
                                        tool = __tools__.get(tool_name)
                                        if tool:
                                            # Store metadata for later result matching
                                            tool_call_data_list.append(tool_call_data)

                                            # Start execution immediately as async task (no extra status event needed)
                                            args = (
                                                tool_input
                                                if isinstance(tool_input, dict)
                                                else {}
                                            )
                                            task = asyncio.create_task(
                                                tool["callable"](**args)
                                            )
                                            running_tool_tasks.append(task)

                                            logger.debug(
                                                f"🚀 Started immediate execution for '%s' (task #%d)",
                                                tool_name,
                                                len(running_tool_tasks),
                                            )
                                    except Exception as e:
                                        logger.error(
                                            f"Failed to start tool execution: {e}"
                                        )

                                    # Reset buffer for next tool
                                    tools_buffer = ""

                                if is_model_thinking:
                                    thinking_message += "\n</details>"
                                    # Preserve thinking block for multi-turn (API auto-filters)
                                    if (
                                        current_thinking_block
                                        and current_thinking_block.get("thinking")
                                    ):
                                        thinking_blocks.append(current_thinking_block)
                                        logger.debug(
                                            f"Preserved thinking block with {len(current_thinking_block.get('thinking', ''))} chars"
                                        )
                                    # Send closing tag to complete the details block
                                    await self.emit_message_delta(
                                        thinking_message,
                                        final_message,
                                        __event_emitter__,
                                    )
                                    is_model_thinking = False
                                    current_thinking_block = {}

                                # Reset tracked type
                                current_block_type = None

                            elif event_type == "message_delta":
                                # Extract usage from message_delta
                                usage = getattr(event, "usage", None)
                                if usage:
                                    current_output_tokens = getattr(
                                        usage, "output_tokens", 0
                                    )

                                    # Calculate difference from last known output count for this stream
                                    diff = current_output_tokens - stream_output_tokens
                                    total_usage["output_tokens"] += diff
                                    stream_output_tokens = current_output_tokens

                                    # Note: total_tokens is already set in message_start based on last turn
                                    # We don't recalculate it here as it represents the context size of the last API call

                                    logger.debug(
                                        f" Delta usage: output={current_output_tokens}, Accumulated: {total_usage}"
                                    )

                                delta = getattr(event, "delta", None)
                                if delta:
                                    stop_reason = getattr(delta, "stop_reason", None)
                                    if stop_reason == "tool_use":
                                        # Emit any remaining text chunk before tool results
                                        if chunk.strip():
                                            await self.emit_message_delta(
                                                chunk, final_message, __event_emitter__
                                            )
                                            chunk = ""
                                            chunk_count = 0

                                        # Wait for all running tool tasks to complete
                                        if running_tool_tasks:
                                            logger.debug(
                                                f"⏳ Waiting for %d tool tasks to complete...",
                                                len(running_tool_tasks),
                                            )

                                            # Emit status event only when multiple tools are executing
                                            if len(running_tool_tasks) > 1:
                                                await emit_event_local(
                                                    {
                                                        "type": "status",
                                                        "data": {
                                                            "description": f"⏳ Waiting for {len(running_tool_tasks)} tool(s) to complete...",
                                                            "done": False,
                                                        },
                                                    }
                                                )
                                                # Give UI time to update
                                                await asyncio.sleep(0.05)

                                            try:
                                                results = await asyncio.gather(
                                                    *running_tool_tasks
                                                )
                                                logger.debug(
                                                    f"✅ All %d tool tasks completed",
                                                    len(results),
                                                )

                                                # Build tool_result messages and emit to UI
                                                for tool_call_data, tool_result in zip(
                                                    tool_call_data_list, results
                                                ):
                                                    tool_use_id = tool_call_data.get(
                                                        "id", ""
                                                    )
                                                    tool_name = tool_call_data.get(
                                                        "name", ""
                                                    )

                                                    # Determine if error
                                                    is_error = isinstance(
                                                        tool_result, str
                                                    ) and tool_result.startswith(
                                                        "Error:"
                                                    )

                                                    # Build result block for API
                                                    result_block = {
                                                        "type": "tool_result",
                                                        "tool_use_id": tool_use_id,
                                                        "content": str(tool_result),
                                                    }
                                                    if is_error:
                                                        result_block["is_error"] = True
                                                    tool_calls.append(result_block)

                                                    # Format and emit result to UI immediately
                                                    try:
                                                        parsed_json = json.loads(
                                                            tool_result
                                                        )
                                                        formatted_result = f"```json\n{json.dumps(parsed_json, indent=2, ensure_ascii=False)}\n```"
                                                    except Exception:
                                                        formatted_result = str(
                                                            tool_result
                                                        )

                                                    # Format tool input/parameters for display
                                                    tool_input = tool_call_data.get(
                                                        "input", {}
                                                    )
                                                    if tool_input:
                                                        try:
                                                            formatted_input = f"```json\n{json.dumps(tool_input, indent=2, ensure_ascii=False)}\n```"
                                                        except Exception:
                                                            formatted_input = f"```\n{str(tool_input)}\n```"
                                                        input_section = f"**Input:**\n{formatted_input}\n\n"
                                                    else:
                                                        input_section = "**Input:** _(no parameters)_\n\n"

                                                    tool_result_msg = (
                                                        f"\n\n<details>\n"
                                                        f"<summary>🔧 Results for {tool_name}</summary>\n\n"
                                                        f"{input_section}"
                                                        f"**Output:**\n{formatted_result}\n"
                                                        f"</details>\n"
                                                    )
                                                    await self.emit_message_delta(
                                                        tool_result_msg,
                                                        final_message,
                                                        __event_emitter__,
                                                    )
                                            except Exception as ex:
                                                logger.error(
                                                    f"❌ Tool execution failed: %s", ex
                                                )
                                                # Create error results
                                                for (
                                                    tool_call_data
                                                ) in tool_call_data_list:
                                                    tool_use_id = tool_call_data.get(
                                                        "id", ""
                                                    )
                                                    tool_name = tool_call_data.get(
                                                        "name", "unknown"
                                                    )
                                                    error_result = f"Error executing tool '{tool_name}': {str(ex)}"
                                                    tool_calls.append(
                                                        {
                                                            "type": "tool_result",
                                                            "tool_use_id": tool_use_id,
                                                            "content": error_result,
                                                            "is_error": True,
                                                        }
                                                    )

                                        logger.debug(
                                            f" Tool use detected, collected {len(tool_calls)} tool results:\nTool_Call JSON: {tool_calls}"
                                        )

                                        # Reset for next iteration
                                        running_tool_tasks = []
                                        tool_call_data_list = []
                                        has_pending_tool_calls = True
                                    elif stop_reason == "max_tokens":
                                        chunk += "Claude has Reached the maximum token limit!"
                                    elif stop_reason == "end_turn":
                                        conversation_ended = True
                                    elif stop_reason == "pause_turn":
                                        conversation_ended = True
                                        chunk += (
                                            "Claude was unable to process this request"
                                        )

                            elif event_type == "message_stop":
                                pass

                            elif event_type == "message_error":
                                error = getattr(event, "error", None)
                                if error:
                                    # Handle stream errors through handle_errors method
                                    error_details = f"Stream Error: {getattr(error, 'message', str(error))}"
                                    if hasattr(error, "type"):
                                        error_details = f"Stream Error ({error.type}): {getattr(error, 'message', str(error))}"

                                    # Create a mock exception for consistent error handling
                                    stream_error = Exception(error_details)
                                    await self.handle_errors(
                                        stream_error, __event_emitter__
                                    )
                                    return (
                                        final_text()
                                        + f"\n\nAn error occurred: {error_details}"
                                    )

                            if chunk_count > token_buffer_size:
                                if chunk.strip():
                                    await self.emit_message_delta(
                                        chunk, final_message, __event_emitter__
                                    )
                                    chunk = ""
                                    chunk_count = 0

                    # Sende letzten Chunk, falls noch etwas übrig ist
                    if chunk.strip():
                        await self.emit_message_delta(
                            chunk, final_message, __event_emitter__
                        )
                        chunk = ""
                        chunk_count = 0
                    # Handle tool use at the end of the stream
                    if has_pending_tool_calls and tool_calls:
                        # Check if we've reached the max tool call limit
                        current_function_calls += 1
                        if current_function_calls >= max_function_calls:
                            await emit_event_local(
                                {
                                    "type": "status",
                                    "data": {
                                        "description": f"⚠️ Maximum tool call limit ({max_function_calls}) reached. Stopping tool execution.",
                                        "done": True,
                                    },
                                }
                            )
                            await self.emit_message_delta(
                                f"\n\n⚠️ **SYSTEM MESSAGE**: Maximum tool call limit ({max_function_calls}) reached. Some tool results may not have been processed.",
                                final_message,
                                __event_emitter__,
                            )
                            break

                        # Tools were already executed during stream (in message_delta)
                        # tool_calls now contains tool_result blocks ready for API
                        # UI output was already emitted during message_delta

                        # Build assistant message with tool_use blocks
                        assistant_content = []

                        # Add preserved thinking blocks first (for multi-turn reasoning)
                        # API will auto-filter & cache only relevant blocks
                        if thinking_blocks:
                            assistant_content.extend(thinking_blocks)
                            logger.debug(
                                f"Adding {len(thinking_blocks)} thinking block(s) to assistant message for API"
                            )

                        # Add final text message if exists (important for context)
                        final_message_snapshot = final_text()
                        if final_message_snapshot.strip():
                            assistant_content.append(
                                {"type": "text", "text": final_message_snapshot}
                            )
                        elif chunk.strip():
                            assistant_content.append({"type": "text", "text": chunk})

                        # Add tool_use blocks to assistant message (ONLY client-side tools)
                        # Server-side tools (web_search, code_execution) are executed by Anthropic
                        # and don't need tool_use/tool_result blocks in subsequent messages
                        for tool_use_block in tool_use_blocks:
                            tool_id = tool_use_block.get("id", "")
                            tool_name = tool_use_block.get("name", "")

                            # Skip server-side tools - they're already handled in the stream
                            if tool_id.startswith("srvtoolu_") or tool_name in [
                                "web_search",
                                "code_execution",
                            ]:
                                logger.debug(
                                    f"🔧 Skipping server-side tool %s (ID: %s) in assistant message",
                                    tool_name,
                                    tool_id,
                                )
                                continue

                            assistant_content.append(tool_use_block)
                            logger.debug(
                                f"🔧 Added tool_use block for %s to assistant message",
                                tool_name,
                            )

                        # Add assistant message to conversation
                        if assistant_content:
                            payload_for_stream["messages"].append(
                                {"role": "assistant", "content": assistant_content}
                            )

                        # Add user message with tool results (tool_calls already contains tool_result blocks)
                        user_content = tool_calls.copy()
                        if user_content:
                            # Optimization: Move cache_control to the end for multi-step tool loops
                            # This ensures we cache the tool results for the next iteration
                            if (
                                self.valves.CACHE_CONTROL
                                == "cache tools array, system prompt and messages"
                            ):
                                # Remove from old block to avoid exceeding 4 blocks limit
                                if cached_block and "cache_control" in cached_block:
                                    del cached_block["cache_control"]

                                # Add to new last block
                                last_tool_result = user_content[-1]
                                last_tool_result["cache_control"] = {
                                    "type": "ephemeral"
                                }
                                cached_block = last_tool_result

                            payload_for_stream["messages"].append(
                                {"role": "user", "content": user_content}
                            )

                        # Ensure we added at least one message, otherwise break the loop
                        if not assistant_content and not user_content:
                            logger.debug(
                                f"🔧 No valid content to add, ending conversation"
                            )
                            break

                        # Reset state for next iteration
                        current_function_calls += len(tool_calls)

                        # Check if we're approaching the limit BEFORE next iteration
                        remaining = max_function_calls - current_function_calls
                        if remaining <= 0:
                            # Hard limit reached - this shouldn't happen as we check above, but safety first
                            break
                        elif remaining == 1:
                            # Only 1 call left - warn Claude this is the final chance
                            await emit_event_local(
                                {
                                    "type": "status",
                                    "data": {
                                        "description": f"⚠️ Final tool call available - after next tool use, conversation will be terminated",
                                        "done": False,
                                    },
                                }
                            )
                            await asyncio.sleep(0.05)

                            # Add system message to warn Claude
                            payload_for_stream["messages"].append(
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": "⚠️ SYSTEM WARNING: This is your final tool call. After this next tool use, the conversation will be automatically terminated due to the tool call limit. Please provide a comprehensive text response instead of calling more tools, and suggest the user continue manually if needed.",
                                        }
                                    ],
                                }
                            )
                        elif remaining <= 3:
                            # Approaching limit - inform user
                            await emit_event_local(
                                {
                                    "type": "status",
                                    "data": {
                                        "description": f"⚠️ Only {remaining} tool call(s) remaining before limit",
                                        "done": False,
                                    },
                                }
                            )
                            await asyncio.sleep(0.05)

                        has_pending_tool_calls = False
                        tool_calls = []
                        tool_use_blocks = []
                        thinking_blocks = []  # Reset after adding to messages
                        chunk = ""
                        chunk_count = 0
                        current_search_query = (
                            ""  # Reset search query for next iteration
                        )
                        citation_counter = (
                            0  # Reset citation counter for next iteration
                        )
                        continue

                except RateLimitError as e:
                    # Rate limit error (429) - retryable
                    await self.handle_errors(e, __event_emitter__)
                    return final_text() + (
                        f"\n\n⚠️ Rate limit exceeded - maximum retries ({self.valves.MAX_RETRIES}) reached. Please try again later."
                    )
                except AuthenticationError as e:
                    # API key issues (401)
                    await self.handle_errors(e, __event_emitter__)
                    return final_text() + (
                        f"\n\nError: API key issues. Reason: {e.message}"
                    )
                except PermissionDeniedError as e:
                    # Permission issues (403)
                    await self.handle_errors(e, __event_emitter__)
                    return final_text() + (
                        f"\n\nError: Permission denied. Reason: {e.message}"
                    )
                except NotFoundError as e:
                    # Resource not found (404)
                    await self.handle_errors(e, __event_emitter__)
                    return final_text() + (
                        f"\n\nError: Resource not found. Reason: {e.message}"
                    )
                except BadRequestError as e:
                    # Invalid request format (400)
                    await self.handle_errors(e, __event_emitter__)
                    return final_text() + (
                        f"\n\nError: Invalid request format. Reason: {e.message}"
                    )

                except UnprocessableEntityError as e:
                    # Unprocessable entity (422)
                    await self.handle_errors(e, __event_emitter__)
                    return final_text() + (
                        f"\n\nError: Unprocessable entity. Reason: {e.message}"
                    )
                except InternalServerError as e:
                    # Server errors (500, 529) - 529 is overloaded_error - retryable
                    status_code = getattr(e, "status_code", 500)
                    retry_attempts += 1
                    if retry_attempts <= self.valves.MAX_RETRIES:
                        error_type = (
                            "overloaded" if status_code == 529 else "server error"
                        )
                        logger.debug(
                            f"{error_type} ({status_code}), retry {retry_attempts}/{self.valves.MAX_RETRIES}"
                        )

                        await emit_event_local(
                            {
                                "type": "status",
                                "data": {
                                    "description": f"⏳ API {error_type}, retrying...)",
                                    "done": False,
                                },
                            }
                        )
                        continue  # Retry the request
                    else:
                        # Max retries exceeded
                        await self.handle_errors(e, __event_emitter__)
                        error_type = (
                            "overloaded" if status_code == 529 else "server error"
                        )
                        return final_text() + (
                            f"\n\n🔧 API {error_type} - maximum retries ({self.valves.MAX_RETRIES}) reached. Please try again later."
                        )
                except APIConnectionError as e:
                    # Network/connection issues - potentially transient - retryable
                    retry_attempts += 1
                    if retry_attempts <= self.valves.MAX_RETRIES:
                        logger.debug(
                            f"Connection error, retry {retry_attempts}/{self.valves.MAX_RETRIES}"
                        )

                        await emit_event_local(
                            {
                                "type": "status",
                                "data": {
                                    "description": f"🌐 Connection error, retrying... ({retry_attempts}/{self.valves.MAX_RETRIES})",
                                    "done": False,
                                },
                            }
                        )
                        continue  # Retry the request
                    else:
                        # Max retries exceeded
                        await self.handle_errors(e, __event_emitter__)
                        return final_text() + (
                            f"\n\n🌐 Network connection failed after {self.valves.MAX_RETRIES} attempts. Please check your connection."
                        )
                except APIStatusError as e:
                    # Catch any other Anthropic API errors
                    await self.handle_errors(e, __event_emitter__)
                    return final_text() + (
                        f"\n\nError: Anthropic API error. Reason: {e.message}"
                    )
                except Exception as e:
                    # Catch all other exceptions
                    await self.handle_errors(e, __event_emitter__)
                    return (
                        final_text()
                        + f"\n\nError: {type(e).__name__} occurred. Reason: {e}"
                    )
        except Exception as e:
            await self.handle_errors(e, __event_emitter__)

        # Preserve existing generated content; append completion marker
        final_status = "✅ Response processing complete."
        show_token_count = __user__["valves"].SHOW_TOKEN_COUNT
        if show_token_count and total_usage:
            # Use total_tokens from total_usage which now represents the last turn (Context Size)
            total_tokens = total_usage.get("total_tokens", 0)

            # Percentage of assumed 200k context window (Claude 3.5 Sonnet extended)
            percentage = min((total_tokens / 200000) * 100, 100)

            # Progress bar (10 segments)
            filled = int(percentage / 10)
            bar = "█" * filled + "░" * (10 - filled)

            def format_num(n: int) -> str:
                if n >= 1_000_000:
                    return f"{n/1_000_000:.1f}M"
                if n >= 1_000:
                    return f"{n/1_000:.1f}K"
                return str(n)

            final_status += (
                f" [{bar}] {format_num(total_tokens)}/200k ({percentage:.1f}%)"
            )

        await emit_event_local(
            {
                "type": "status",
                "data": {
                    "description": final_status,
                    "done": True,
                },
            }
        )

        await emit_event_local(
            {
                "type": "chat:completion",
                "data": {
                    "usage": total_usage,
                    "done": True,
                },
            }
        )
        return final_text()

    async def _run_task_model_request(
        self,
        body: dict[str, Any],
        __event_emitter__: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> str:
        """
        Handle task model requests (title generation, tags, follow-ups etc.) by making a
        non-streaming request to Anthropic API and returning only the text response.

        Task models should return plain text without any JSON formatting or status updates
        mixed into the response.
        """
        try:
            # Extract model and messages from body
            actual_model_name = body["model"].split("/")[-1]
            messages = body.get("messages", [])

            # Build simple payload for task request (non-streaming)
            task_payload = {
                "model": actual_model_name,
                "max_tokens": body.get("max_tokens", 4096),
                "messages": self._process_messages_for_task(messages),
                "stream": False,
            }

            # Add system message if present
            system_messages = [msg for msg in messages if msg.get("role") == "system"]
            if system_messages:
                task_payload["system"] = [
                    {"type": "text", "text": msg.get("content", "")}
                    for msg in system_messages
                ]

            logger.debug(f"Task payload: {json.dumps(task_payload, indent=2)}")

            # Make synchronous request to Anthropic API
            # For task requests, we don't have __user__ context, so use default key
            api_key = self.valves.ANTHROPIC_API_KEY
            client = AsyncAnthropic(api_key=api_key)

            response = await client.messages.create(**task_payload)

            # Extract text from response
            text_parts = []
            for content_block in response.content:
                if content_block.type == "text":
                    text_parts.append(content_block.text)

            # Join without adding line breaks - preserve original formatting
            result = "".join(text_parts).strip()

            logger.debug(f"Task response: {result}")

            return result

        except Exception as e:
            logger.debug(f"Task model error: {e}")
            await self.handle_errors(e, __event_emitter__)
            return ""

    def _process_messages_for_task(self, messages: List[dict]) -> List[dict]:
        """
        Process messages for task requests - convert to simple Anthropic format.
        Task requests don't need complex content processing.
        """
        processed = []
        for msg in messages:
            role = msg.get("role")
            if role == "system":
                continue  # System messages handled separately

            content = msg.get("content", "")
            if isinstance(content, str):
                processed.append({"role": role, "content": content})
            elif isinstance(content, list):
                # Extract text from content blocks
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                if text_parts:
                    processed.append({"role": role, "content": " ".join(text_parts)})

        return processed

    async def handle_errors(
        self,
        exception,
        __event_emitter__: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ):
        # Determine specific error message based on exception type
        if isinstance(exception, RateLimitError):
            error_msg = "Rate limit exceeded. Please wait before making more requests."
            user_msg = "⚠️ Rate limit reached. Please try again in a moment."
        elif isinstance(exception, AuthenticationError):
            error_msg = "Authentication failed. Please check your API key."
            user_msg = (
                "🔑 Invalid API key. Please verify your Anthropic API key is correct."
            )
        elif isinstance(exception, PermissionDeniedError):
            error_msg = (
                "Permission denied. Your API key may not have access to this resource."
            )
            user_msg = "🚫 Access denied. Your API key doesn't have permission for this request."
        elif isinstance(exception, NotFoundError):
            error_msg = (
                "Resource not found. The requested model or endpoint may not exist."
            )
            user_msg = "❓ Resource not found. Please check if the model is available."
        elif isinstance(exception, BadRequestError):
            error_msg = f"Bad request: {str(exception)}"
            user_msg = (
                "📝 Invalid request format. Please check your input and try again."
            )
        elif isinstance(exception, UnprocessableEntityError):
            error_msg = f"Unprocessable entity: {str(exception)}"
            user_msg = "📄 Request format issue. Please check your message structure and try again."
        elif isinstance(exception, InternalServerError):
            error_msg = "Anthropic server error. Please try again later."
            user_msg = (
                "🔧 Server temporarily unavailable. Please try again in a few moments."
            )
        elif isinstance(exception, APIConnectionError):
            error_msg = (
                "Network connection error. Please check your internet connection."
            )
            user_msg = "🌐 Connection error. Please check your network and try again."
        elif isinstance(exception, APIStatusError):
            status_code = getattr(exception, "status_code", "Unknown")
            error_msg = f"API Error ({status_code}): {str(exception)}"
            user_msg = (
                f"⚡ API Error ({status_code}). Please try again or contact support."
            )
        else:
            error_msg = f"Unexpected error: {str(exception)}"
            user_msg = "💥 An unexpected error occurred. Please try again."

        logger.error(f"Exception: {error_msg}")
        # Add request ID if available for debugging
        if isinstance(exception, APIStatusError) and hasattr(exception, "response"):
            try:
                request_id = exception.response.headers.get("request-id")
                if request_id:
                    logger.info(f"Request ID: %s", request_id)
            except Exception:
                pass  # Ignore if we can't get request ID

        await self.emit_event(
            {
                "type": "notification",
                "data": {
                    "type": "error",
                    "content": user_msg,
                },
            },
            __event_emitter__,
        )

        tb = traceback.format_exc()

        await self.emit_event(
            {
                "type": "source",
                "data": {
                    "source": {"name": "Anthropic Error", "url": None},
                    "document": [tb],
                    "metadata": [
                        {
                            "source": "anthropic api",
                            "type": "error",
                            "date_accessed": datetime.utcnow().isoformat(),
                        }
                    ],
                },
            },
            __event_emitter__,
        )
        await self.emit_event(
            {
                "type": "status",
                "data": {
                    "description": "❌ Response with Errors",
                    "done": True,
                },
            },
            __event_emitter__,
        )

    async def _run_tool_callable(
        self,
        tool_callable: Callable[..., Awaitable[Any]],
        args: Dict[str, Any],
        tool_name: str,
    ) -> Any:
        try:
            return await asyncio.wait_for(
                tool_callable(**args),
                timeout=self.TOOL_CALL_TIMEOUT,
            )
        except asyncio.TimeoutError:
            message = f"Error: Tool '{tool_name}' timed out after {self.TOOL_CALL_TIMEOUT} seconds"
            self.logger.debug(message)
            return message
        except Exception as exc:
            self.logger.debug(f"Tool '%s' failed", tool_name, exc_info=exc)
            return f"Error executing tool '{tool_name}': {exc}"

    def _remove_thinking_blocks(self, content: str) -> str:
        """
        Remove thinking blocks from message content to prevent them from being
        re-sent to the API in subsequent requests.

        Removes HTML details blocks containing thinking content, e.g.:
        <details><summary>🧠 Thinking...</summary>\n...\n</details>

        Note: Does not strip whitespace - stripping is handled elsewhere as needed.
        """
        # Pattern to match details blocks with thinking content
        # Non-greedy match to handle multiple blocks
        pattern = r"<details>\s*<summary>🧠.*?</summary>.*?</details>\s*"
        cleaned = re.sub(pattern, "", content, flags=re.DOTALL)
        return cleaned

    def _process_content(self, content: Union[str, List[dict], None]) -> List[dict]:
        """
        Process content from OpenWebUI format to Claude API format.
        Handles text, images, PDFs, tool_calls, and tool_results according to
        Anthropic API documentation.
        Filters out empty text blocks to prevent API errors.
        """
        if content is None:
            return []

        if isinstance(content, str):
            # Remove thinking blocks from historical messages
            content = self._remove_thinking_blocks(content)
            # Only return non-empty text blocks
            if content.strip():
                return [{"type": "text", "text": content}]
            else:
                return []

        processed_content = []
        for item in content:
            if item.get("type") == "text":
                text_content = item.get("text", "")
                # Only add non-empty text blocks (Anthropic API requirement)
                if text_content.strip():
                    processed_content.append({"type": "text", "text": text_content})

            elif item.get("type") == "image_url":
                image_url = item.get("image_url", {}).get("url", "")

                if image_url.startswith("data:image"):
                    # Handle base64 encoded image data
                    try:
                        header, encoded = image_url.split(",", 1)
                        mime_type = header.split(":")[1].split(";")[0]

                        # Validate supported image formats according to Anthropic docs
                        supported_formats = [
                            "image/jpeg",
                            "image/png",
                            "image/gif",
                            "image/webp",
                        ]

                        if mime_type not in supported_formats:
                            logger.debug(f" Unsupported image mime type: {mime_type}")
                            processed_content.append(
                                {
                                    "type": "text",
                                    "text": f"[Image type {mime_type} not supported. Supported formats: JPEG, PNG, GIF, WebP]",
                                }
                            )
                            continue

                        # Check image size - API has 32MB request limit, but be conservative
                        # Also check for API limits: 8000x8000 px for single image
                        MAX_IMAGE_SIZE = 25 * 1024 * 1024  # 25 MB (conservative)
                        try:
                            decoded_bytes = base64.b64decode(encoded)
                            if len(decoded_bytes) > MAX_IMAGE_SIZE:
                                logger.debug(
                                    f" Image too large: {len(decoded_bytes)} bytes"
                                )
                                processed_content.append(
                                    {
                                        "type": "text",
                                        "text": f"[Image too large for Anthropic API. Max size: 25MB, received: {len(decoded_bytes)//1024//1024}MB]",
                                    }
                                )
                                continue
                        except Exception as decode_ex:
                            logger.debug(f" Image base64 decode failed: {decode_ex}")
                            processed_content.append(
                                {
                                    "type": "text",
                                    "text": "[Image data could not be decoded - invalid base64 format]",
                                }
                            )
                            continue

                        processed_content.append(
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": mime_type,
                                    "data": encoded,
                                },
                            }
                        )

                    except ValueError as e:
                        logger.debug(f"Error parsing image data URL: {e}")
                        processed_content.append(
                            {
                                "type": "text",
                                "text": "[Error processing image - invalid data URL format]",
                            }
                        )
                    except Exception as e:
                        logger.debug(f"Unexpected error processing image: {e}")
                        processed_content.append(
                            {
                                "type": "text",
                                "text": "[Unexpected error processing image]",
                            }
                        )
                else:
                    # For image URLs (not base64), Claude API supports URL references
                    # but we need to validate the URL format
                    if image_url.startswith(("http://", "https://")):
                        processed_content.append(
                            {
                                "type": "image",
                                "source": {"type": "url", "url": image_url},
                            }
                        )
                    else:
                        processed_content.append(
                            {
                                "type": "text",
                                "text": f"[Invalid image URL format: {image_url}. Only HTTP/HTTPS URLs are supported]",
                            }
                        )

            elif item.get("type") == "tool_calls":
                # Convert OpenWebUI tool_calls to Claude tool_use format
                converted_calls = self._process_tool_calls(item)
                processed_content.extend(converted_calls)

            elif item.get("type") == "tool_results":
                # Convert OpenWebUI tool_results to Claude tool_result format
                converted_results = self._process_tool_results(item)
                processed_content.extend(converted_results)

            # Handle any other content types by converting to text
            else:
                logger.debug(
                    f" Unknown content type: {item.get('type')}, converting to text"
                )
                # Convert unknown types to text representation
                processed_content.append(
                    {
                        "type": "text",
                        "text": f"[Unsupported content type: {item.get('type')}]",
                    }
                )

        return processed_content

    def _process_tool_calls(self, tool_calls_item):
        """
        Convert OpenWebUI tool_calls format to Claude tool_use format.
        """
        claude_tool_uses = []

        if "tool_calls" in tool_calls_item:
            for tool_call in tool_calls_item["tool_calls"]:
                if tool_call.get("type") == "function" and "function" in tool_call:
                    function_def = tool_call["function"]

                    claude_tool_use = {
                        "type": "tool_use",
                        "id": tool_call.get("id", ""),
                        "name": function_def.get("name", ""),
                        "input": function_def.get("arguments", {}),
                    }
                    claude_tool_uses.append(claude_tool_use)

        return claude_tool_uses

    def _process_tool_results(self, tool_results_item):
        """
        Convert OpenWebUI tool_results format to Claude tool_result format.
        """
        claude_tool_results = []

        if "results" in tool_results_item:
            for result_item in tool_results_item["results"]:
                if "call" in result_item and "result" in result_item:
                    tool_call = result_item["call"]
                    result_content = result_item["result"]

                    # Extract tool_use_id from the call
                    tool_use_id = tool_call.get("id", "")

                    if tool_use_id:
                        claude_result = {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": str(result_content),
                        }
                        claude_tool_results.append(claude_result)

        return claude_tool_results

    def _extract_and_remove_memorys(self, text: str) -> tuple[str, Optional[str]]:
        """
        Extract User Context from Openwebui Memory System from system prompt and remove it.
        Takes everything after "\nUser Context:\n" until end of string.

        Returns:
            tuple[str, Optional[str]]: (cleaned_text, extracted_context)
            - cleaned_text: Original text with User Context removed (stripped)
            - extracted_context: The extracted User Context block with label, or None if not found
        """
        # Simple: Everything after "\nUser Context:\n" is memory content
        pattern = r"\nUser Context:\n(.*)$"
        match = re.search(pattern, text, re.DOTALL)

        if match:
            context_content = match.group(1).strip()
            extracted_context = (
                f"User Context:\n{context_content}" if context_content else None
            )
            # Remove "\nUser Context:\n" and everything after it
            cleaned_text = text[: match.start()].strip()
            return cleaned_text, extracted_context

        # No User Context found
        return text.strip(), None

    async def handle_citation(self, event, __event_emitter__, citation_counter=None):
        """
        Handle web search citation events from Anthropic API and emit appropriate source events to OpenWebUI.

        Args:
            event: The citation event from Anthropic (content_block_delta with citations_delta)
            __event_emitter__: OpenWebUI event emitter function
            citation_counter: Optional citation number for inline citations
        """
        try:
            logger.debug(
                f" Processing citation event type: {getattr(event, 'type', 'unknown')}"
            )

            # Extract citation from delta within content_block_delta event
            delta = getattr(event, "delta", None)
            citation = None

            if delta and hasattr(delta, "citation"):
                citation = delta.citation
            elif hasattr(event, "citation"):
                # Fallback: direct citation in event
                citation = event.citation

            if not citation:
                logger.debug(f"No citation data found in event")
                return

            logger.debug(f" Citation data found: {citation}")

            # Only handle web search result citations
            citation_type = getattr(citation, "type", "")
            if citation_type != "web_search_result_location":
                logger.debug(f" Skipping non-web-search citation type: {citation_type}")
                return

            # Extract web search citation information
            url = getattr(citation, "url", "")
            title = getattr(citation, "title", "Unknown Source")
            cited_text = getattr(citation, "cited_text", "")

            # CRITICAL: metadata.source is used by OpenWebUI as the grouping ID
            # Must be unique for each citation to prevent Citation merging
            metadata = {
                "source": f"{url}#{citation_counter}",
                "date_accessed": datetime.now().isoformat(),
                "name": f"[{citation_counter}]",
            }

            source_data = {
                "source": {
                    "name": title,
                    "url": url,
                    "id": f"{citation_counter}",  # Unique source ID
                },
                "document": [cited_text],
                "metadata": [metadata],
            }

            # Emit the source event
            await self.emit_event(
                {"type": "source", "data": source_data}, __event_emitter__
            )

        except Exception as e:
            logger.error(f"Error handling citation: {str(e)}")
            await self.handle_errors(e, __event_emitter__)

    async def emit_event(
        self,
        event: Dict[str, Any],
        __event_emitter__: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> None:
        """
        Safely emit an event, handling None __event_emitter__ (e.g., in Channel contexts).

        In OpenWebUI Channels, when models are mentioned, __event_emitter__ is None
        because the channel context doesn't provide a socket connection for status updates.
        This helper prevents 'NoneType' object is not callable errors.
        """
        if __event_emitter__ is None:
            return
        try:
            await __event_emitter__(event)
        except Exception as e:
            logger.warning(f"Event emitter failed: {e}")

    async def emit_message_delta(
        self,
        content: str,
        final_message: list[str] | None = None,
        __event_emitter__: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> None:
        """
        Emit content as chat:message:delta and automatically append to final message.
        Convenience wrapper for the most common emit pattern.

        Args:
            content: The content to emit
            final_message: The request-local final_message list to append to (prevents cross-user contamination)
            __event_emitter__: Event emitter function for this specific request
        """
        await self.emit_event(
            {"type": "chat:message:delta", "data": {"content": content}},
            __event_emitter__,
        )
        if content and final_message is not None:
            final_message.append(content)
