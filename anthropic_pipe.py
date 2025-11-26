"""
title: Anthropic API Integration
author: Podden (https://github.com/Podden/)
github: https://github.com/Podden/openwebui_anthropic_api_manifold_pipe
original_author: Balaxxe (Updated by nbellochi)
version: 0.4.7
license: MIT
requirements: pydantic>=2.0.0, aiohttp>=3.8.0
environment_variables:
    - ANTHROPIC_API_KEY (required)

Supports:
- Uses Anthropic Python SDK
- Fetch Claude Models from API Endpoint
- Tool Call Loop (call multiple Tools in the same response)
- web_search Tool
- citations for web_search
- Streaming responses
- Prompt caching (server-side)
- Promt Caching of System Promts, Messages- and Tools Array (controllable via Valve)
- Comprehensive error
- Image processing
- Web_Search Toggle Action
- Fine Grained Tool Streaming
- Extended Thinking Toggle Action
- Code Execution Tool
- Vision

Todo:
- Correct Caching/Requests with RAG and Memories
- Files API support so uploaded PDFs can be used with code_execution tool
- Connect Anthropic Memory System with OpenWebUI Memory System

Changelog:
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
        },
        "claude-3-sonnet-20240229": {
            "max_tokens": 4096,
            "context_length": 200000,
            "supports_thinking": False,
            "supports_1m_context": False,
            "supports_memory": False,
            "supports_vision": True,
        },
        "claude-3-haiku-20240307": {
            "max_tokens": 4096,
            "context_length": 200000,
            "supports_thinking": False,
            "supports_1m_context": False,
            "supports_memory": False,
            "supports_vision": True,
        },
        # Claude 3.5 family
        "claude-3-5-sonnet-20240620": {
            "max_tokens": 8192,
            "context_length": 200000,
            "supports_thinking": False,
            "supports_1m_context": False,
            "supports_memory": False,
            "supports_vision": True,
        },
        "claude-3-5-sonnet-20241022": {
            "max_tokens": 8192,
            "context_length": 200000,
            "supports_thinking": False,
            "supports_1m_context": False,
            "supports_memory": False,
            "supports_vision": True,
        },
        "claude-3-5-haiku-20241022": {
            "max_tokens": 8192,
            "context_length": 200000,
            "supports_thinking": False,
            "supports_1m_context": False,
            "supports_memory": False,
            "supports_vision": True,
        },
        # Claude 3.7 family
        "claude-3-7-sonnet-20250219": {
            "max_tokens": 64000,
            "context_length": 200000,
            "supports_thinking": True,
            "supports_1m_context": False,
            "supports_memory": False,
            "supports_vision": True,
        },
        # Claude 4 family
        "claude-sonnet-4-20250514": {
            "max_tokens": 64000,
            "context_length": 200000,
            "supports_thinking": True,
            "supports_1m_context": True,
            "supports_memory": True,
            "supports_vision": True,
        },
        "claude-opus-4-20250514": {
            "max_tokens": 32000,
            "context_length": 200000,
            "supports_thinking": True,
            "supports_1m_context": False,
            "supports_memory": True,
            "supports_vision": True,
        },
        "claude-opus-4-1-20250805": {
            "max_tokens": 32000,
            "context_length": 200000,
            "supports_thinking": True,
            "supports_1m_context": False,
            "supports_memory": True,
            "supports_vision": True,
        },
        "claude-opus-4-5-20251101": {
            "max_tokens": 64000,
            "context_length": 200000,
            "supports_thinking": True,
            "supports_1m_context": False,
            "supports_memory": True,
            "supports_vision": True,
        },
        "claude-sonnet-4-5-20250929": {
            "max_tokens": 64000,
            "context_length": 200000,
            "supports_thinking": True,
            "supports_1m_context": True,
            "supports_memory": True,
            "supports_vision": True,
        },
        "claude-haiku-4-5-20251001": {
            "max_tokens": 64000,
            "context_length": 200000,
            "supports_thinking": True,
            "supports_1m_context": False,
            "supports_memory": True,
            "supports_vision": True,
        },
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
        "claude-opus-4-5": "claude-opus-4-5-20251101",
        "claude-sonnet-4-5": "claude-sonnet-4-5-20250929",
        "claude-haiku-4-5": "claude-haiku-4-5-20251001",
    }

    REQUEST_TIMEOUT = 300  # Increased timeout for longer responses with extended thinking
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
        return cls.MODEL_CAPABILITIES.get(resolved_name, {
            "max_tokens": 4096,
            "context_length": 200000,
            "supports_thinking": False,
            "supports_1m_context": False,
            "supports_memory": False,
            "supports_vision": True,
        })

    class Valves(BaseModel):
        ANTHROPIC_API_KEY: str = "Your API Key Here"
        ENABLE_THINKING: bool = Field(
            default=False,
            description="Force Enable Extended Thinking. Use Anthropic Thinking Toggle Function for fine grained control",
        )
        THINKING_BUDGET_TOKENS: int = Field(
            default=4096, ge=0, le=32000
        )
        # ENABLE_CLAUDE_MEMORY: bool = Field(
        #     default=False,
        #     description="Enable Claude memory tool",
        # )
        ENABLE_1M_CONTEXT: bool = Field(
            default=False,
            description="Enable 1M token context window for Claude Sonnet 4 (requires Tier 4 API access)",
        )
        SHOW_TOKEN_COUNT: bool = Field(
            default=False,
            description="Show token count for the current conversation",
        )
        WEB_SEARCH: bool = Field(
            default=True,
            description="Enable web search tool for Claude models. Use Anthropic Web Search Toggle Function for fine grained control",
        )
        WEB_SEARCH_MAX_USES: int = Field(
            default=5,
            ge=1,
            le=20,
            description="Maximum number of web searches allowed per conversation",
        )
        WEB_SEARCH_USER_CITY: str = Field(
            default="Leipzig",
            description="User's city for web search location context",
        )
        WEB_SEARCH_USER_REGION: str = Field(
            default="Saxony",
            description="User's region/state for web search location context",
        )
        WEB_SEARCH_USER_COUNTRY: str = Field(
            default="DE",
            description="User's country code for web search location context",
        )
        WEB_SEARCH_USER_TIMEZONE: str = Field(
            default="Europe/Berlin",
            description="User's timezone for web search location context",
        )
        MAX_RETRIES: int = Field(
            default=3,
            ge=0,
            le=50,
            description="Maximum number of retries for failed requests (due to rate limiting, transient errors or connection issues)",
        )
        CACHE_CONTROL: Literal["cache disabled", "cache tools array only", "cache tools array and system prompt", "cache tools array, system prompt and messages"] = Field(
            default="cache disabled",
            description="Cache control scope for prompts",
        )
        DEBUG: bool = Field(
            default=False,
            description="Enable debug logging to see requests and responses",
        )

    def __init__(self):
        self.type = "manifold"
        self.id = "anthropic"
        self.valves = self.Valves()
        self.request_id = None
        self.logger = logger

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
                        }
                    }
                )
            return models
        except Exception as e:
            logging.warning(
                f"Could not fetch models from SDK/API, using static list. Reason: {e}"
            )
        return models

    async def pipes(self) -> List[dict]:
        return await self.get_anthropic_models()

    async def _create_payload(
        self,
        body: Dict,
        __metadata__: dict[str, Any],
        __user__: Optional[dict],
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

        if self.valves.DEBUG:
            try:
                logger.debug(" Thinking Filter: {__metadata__.get('anthropic_thinking')}")
                logger.debug("Tools: {json.dumps(__tools__, indent=2)}")
            except Exception as e:
                logger.debug("JSON dump failed: {e}")
                logger.debug("raw __metadata__: {__metadata__}")

        if "anthropic_thinking" in __metadata__:
            should_enable_thinking = __metadata__.get("anthropic_thinking", False)
        else:
            should_enable_thinking = self.valves.ENABLE_THINKING

        if self.valves.DEBUG:
            logger.debug("Thinking Enabled?: {should_enable_thinking}")

        if (
            should_enable_thinking
            and model_info["supports_thinking"]
        ):
            # Ensure thinking.budget_tokens < max_tokens and at least 1024
            requested_thinking_budget = self.valves.THINKING_BUDGET_TOKENS
            # Clamp thinking budget to valid range
            max_valid_thinking_budget = max(max_tokens - 1, 1023)
            thinking_budget = max(
                1024, min(requested_thinking_budget, max_valid_thinking_budget)
            )
            # If max_tokens is too low, set thinking_budget to max_tokens - 1
            if max_tokens <= 1024:
                thinking_budget = max_tokens - 1 if max_tokens > 1 else 1
            payload["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}

        if "response_format" in body:
            payload["response_format"] = {"type": body["response_format"].get("type")}

        raw_messages = body.get("messages", []) or []
        system_messages = []
        processed_messages: list[dict] = []
        # Extract dynamic context from system messages for injection into user messages
        dynamic_context_blocks = []

        for msg in raw_messages:
            role = msg.get("role")
            raw_content = msg.get("content")
            
            processed_content = self._process_content(raw_content)
            if not processed_content:
                continue
            if role == "system":
                for block in processed_content:
                    text = block["text"]
                    
                    # Extract and remove User Context in one pass (also strips whitespace)
                    cleaned_text, user_context = self._extract_and_remove_memorys(text)
                    
                    if user_context:
                        if self.valves.DEBUG:
                            logger.debug("✓ Extracted User Context: {user_context[:100]}...")
                            logger.debug("✓ System prompt after removal (last 200 chars): ...{cleaned_text[-200:]}")
                        dynamic_context_blocks.append(user_context)
                    else:
                        if self.valves.DEBUG:
                            logger.debug("✗ No User Context found in this block")
                    
                    # Update block with cleaned text
                    block["text"] = cleaned_text
                    
                    # Only add non-empty blocks to system (cache_control will be added later to last block only)
                    system_messages.append(block)
            else:
                # Only add messages with non-empty content (fixes Chat with Notes empty assistant messages)
                if processed_content:
                    processed_messages.append({"role": role, "content": processed_content})
                elif self.valves.DEBUG:
                    logger.debug("Skipped message with empty content (role: {role})")

        if not processed_messages:
            raise ValueError("No valid messages to process")

        # Correct Order for Caching: Tools, System, Messages
        tools_list = self._convert_tools_to_claude_format(__tools__, actual_model_name)
        # Decide on code execution inclusion early so we can set beta headers later
        activate_code_execution = __metadata__.get(
            "activate_code_execution_tool", False
        )
        # Append code execution tool (no parameters) if enabled
        if activate_code_execution:
            code_exec_tool = {
                "type": "code_execution_20250522",
                "name": "code_execution",
            }
            # Avoid duplicates if already added
            if not any(t.get("name") == "code_execution" for t in tools_list):
                tools_list.append(code_exec_tool)

        if tools_list and len(tools_list) > 0:
            # Add cache control to last tool when caching tools (alone or with system)
            # "cache tools only" = cache breakpoint at tools
            # "cache tools and system" = cache breakpoint at tools AND system (hierarchical)
            if self.valves.CACHE_CONTROL in ["cache tools array only", "cache tools array and system prompt"]:
                tools_list[-1]["cache_control"] = {"type": "ephemeral"}

        if tools_list:
            # Check for enforced web search or code execution in metadata (precedence: specific enforcement first)
            if __metadata__.get("web_search_enforced") and "thinking" not in payload:
                payload["tool_choice"] = {"type": "tool", "name": "web_search"}
                __metadata__["web_search_enforced"] = False  # one-shot
            else:
                payload["tool_choice"] = {"type": "auto"}
                # Skip forced web search when thinking is enabled to avoid API error
                if __metadata__.get("web_search_enforced") and "thinking" in payload:
                    __metadata__["web_search_enforced"] = False  # one-shot
                    if self.valves.DEBUG:
                        logger.debug("Skipped forced web_search due to active thinking")
                    # Notify user about the conflict
                    await self.emit_event( 
                        {
                            "type": "notification",
                            "data": {
                                "type": "info",
                                "content": "🧠 Thinking mode is active - Web search enforcement was disabled to allow extended thinking. Claude can still use web search if needed.",
                            },
                        }
                    )
            payload["tools"] = tools_list

        if system_messages and len(system_messages) > 0:
            # Add cache_control to last system message block ONLY if caching up to system (not messages)
            # Support both old typo and corrected spelling for backward compatibility
            if self.valves.CACHE_CONTROL in ["cache tools array and system prompt"]:
                last_system_block = system_messages[-1]
                # Only add if block has non-empty text
                if last_system_block.get("type") == "text" and last_system_block.get("text", "").strip():
                    last_system_block["cache_control"] = {"type": "ephemeral"}
            payload["system"] = system_messages

        if processed_messages and len(processed_messages) > 0:
            last_msg = processed_messages[-1]
            content_blocks = last_msg.get("content", [])
            
            if dynamic_context_blocks and last_msg.get("role") == "user":
                # Add context blocks as text blocks with clear markers
                for ctx in dynamic_context_blocks:
                    context_block = {
                        "type": "text",
                        "text": f"\n\nTHE FOLLOWING IS CONTEXT FROM MEMORY SYSTEM, DONT MENTION TO USER, JUST USE AS NECESSARY AND RELEVANT!\n{ctx}\n"
                    }
                    content_blocks.append(context_block)
            
            # Apply cache control to last content block (only if it has text)
            if content_blocks and self.valves.CACHE_CONTROL == "cache tools array, system prompt and messages":
                last_content_block = content_blocks[-1]
                # Only add cache_control if the block has non-empty text
                if last_content_block.get("type") == "text" and last_content_block.get("text", "").strip():
                    last_content_block.setdefault("cache_control", {"type": "ephemeral"})
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

        # Add 1M context header if enabled and model supports it
        if self.valves.ENABLE_1M_CONTEXT and model_info["supports_1m_context"]:
            beta_headers.append("context-1m-2025-08-07")

        if beta_headers and len(beta_headers) > 0:
            headers["anthropic-beta"] = ",".join(beta_headers)

        if self.valves.DEBUG:
            logger.debug("Payload: {json.dumps(payload, indent=2)}")
            logger.debug("Headers: {headers}")
        
        return payload, headers

    def _convert_tools_to_claude_format(self, __tools__, actual_model_name: str) -> List[dict]:
        """
        Convert OpenWebUI tools format to Claude API format.
        Args:
            __tools__: Dict of tools from OpenWebUI
        Returns:
            list: Tools in Claude API format
        """
        claude_tools = []
        tool_names_seen = set()  # Track unique tool names

        if self.valves.DEBUG:
            # Only log tool names and specs, not the callable functions
            if __tools__:
                try:
                    logger.debug(" Converting tools: {json.dumps(__tools__, indent=2)}")
                except Exception as e:
                    logger.debug(" JSON dump failed, printing tools directly: {__tools__}")
                    logger.debug("Error was: {e}")
            else:
                logger.debug("No tools to convert")

        # Add web search tool if enabled
        if self.valves.WEB_SEARCH:
            claude_tools.append(
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": self.valves.WEB_SEARCH_MAX_USES,
                    "user_location": {
                        "type": "approximate",
                        "city": self.valves.WEB_SEARCH_USER_CITY,
                        "region": self.valves.WEB_SEARCH_USER_REGION,
                        "country": self.valves.WEB_SEARCH_USER_COUNTRY,
                        "timezone": self.valves.WEB_SEARCH_USER_TIMEZONE,
                    },
                }
            )
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
            if self.valves.DEBUG:
                logger.debug("No tools provided, using default Claude tools")
            return claude_tools

        for tool_name, tool_data in __tools__.items():
            if not isinstance(tool_data, dict) or "spec" not in tool_data:
                if self.valves.DEBUG:
                    logger.debug("Skipping invalid tool: {tool_name} - missing spec")
                continue

            spec = tool_data["spec"]

            # Extract basic tool info
            name = spec.get("name", tool_name)
            
            # Skip if tool name already exists
            if name in tool_names_seen:
                logger.info("Skipping duplicate tool: {name}")
                continue

            # Skip if toolname starts with _ or __
            if name.startswith("_"):
                if self.valves.DEBUG:
                    logger.debug("Skipping private tool: {name}")
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
            claude_tools.append(claude_tool)
            tool_names_seen.add(name)


        if self.valves.DEBUG:
            logger.debug("Total tools converted: {len(claude_tools)}")

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
        # Local variable to store the final message for this request
        # DO NOT use self.final_message as pipe instances are reused across users
        final_message: list[str] = []
        self.eventemitter = __event_emitter__

        def final_text() -> str:
            return "".join(final_message)
        try:
            # Get API key
            api_key = self.valves.ANTHROPIC_API_KEY
            if not api_key:
                error_msg = "Error: No API key configured"
                if self.valves.DEBUG:
                    logger.debug("{error_msg}")
                    await self.emit_event( 
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
                if self.valves.DEBUG:
                    logger.debug("Detected task model: {__task__}")
                return await self._run_task_model_request(body, __event_emitter__)
            
            # STEP 2: Await tools if needed
            if inspect.isawaitable(__tools__):
                __tools__ = await __tools__
            
            # STEP 3: Auto-enable native function calling if tools are present
            # This prevents OpenWebUI's function_calling task system from being triggered
            if __tools__ and MODELS_AVAILABLE:
                try:
                    # Get the OpenWebUI model ID from metadata
                    openwebui_model_id = __metadata__.get("model_id") if __metadata__ else None
                    if not openwebui_model_id and body and "model" in body:
                        openwebui_model_id = body["model"]
                    
                    if openwebui_model_id:
                        model = Models.get_model_by_id(openwebui_model_id)
                        if model:
                            params = dict(model.params or {})
                            if params.get("function_calling") != "native":
                                if self.valves.DEBUG:
                                    logger.debug("Auto-enabling native function calling for model: {openwebui_model_id}")
                                
                                # Notify user
                                await self.emit_event(
                                    {
                                        "type": "notification",
                                        "data": {
                                            "type": "info",
                                            "content": f"Enabling native function calling for model: {openwebui_model_id}. Please re-run your query."
                                        }
                                    }
                                )
                                
                                params["function_calling"] = "native"
                                form_data = model.model_dump()
                                form_data["params"] = params
                                Models.update_model_by_id(openwebui_model_id, ModelForm(**form_data))
                except Exception as e:
                    if self.valves.DEBUG:
                        logger.debug("Could not auto-enable native function calling: {e}")
                    # Continue anyway - this is not critical

            payload, headers = await self._create_payload(
                body, __metadata__, __user__, __tools__, __event_emitter__, __files__
            )

            # API key is already set in headers by _create_payload
            # Extract it from headers for client initialization
            api_key = headers.get("x-api-key", self.valves.ANTHROPIC_API_KEY)
            client = AsyncAnthropic(api_key=api_key, default_headers=headers)
            payload_for_stream = {
                k: v for k, v in payload.items() if k != "stream"
            }

            # Stream loop variables
            token_buffer_size = getattr(self.valves, "TOKEN_BUFFER_SIZE", 1)
            is_model_thinking = False
            conversation_ended = False
            max_function_calls = 5
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
            usage_data = {}
            first_text_emitted = False  # Track if we've emitted "Responding..." status
            # Track active server tool use block
            active_server_tool_name = None
            active_server_tool_id = None
            server_tool_input_buffer = ""  # Accumulate server tool input JSON
            await self.emit_event(
            {
                "type": "status",
                "data": {
                    "description": "Waiting for response...",
                    "done": False,
                    "hidden": False,
                },
            })
            while (current_function_calls < max_function_calls and not conversation_ended and retry_attempts <= self.valves.MAX_RETRIES):
                try:
                    async with client.messages.stream(**payload_for_stream) as stream:
                        async for event in stream:
                            event_type = getattr(event, "type", None)
                            if self.valves.DEBUG:
                                # Only log event_type and minimal event info, skip snapshot fields
                                if hasattr(event, "__dict__"):
                                    event_dict = {
                                        k: v
                                        for k, v in event.__dict__.items()
                                        if k != "snapshot"
                                    }
                                    logger.debug(
                                        "Received event: %s with %s", event_type, str(event_dict)[:200] + ('...' if len(str(event_dict)) > 200 else '')
                                    )
                                else:
                                    logger.debug(
                                        "Received event: %s with %s", event_type, str(event)[:200] + ('...' if len(str(event)) > 200 else '')
                                    )
                            if event_type == "message_start":
                                message = getattr(event, "message", None)
                                if message:
                                    self.request_id = getattr(
                                        message, "id", None
                                    )
                                    if self.valves.DEBUG:
                                        logger.debug(" Message started with ID: {self.request_id}")
                                    usage = getattr(message, "usage", {})
                                    if usage:
                                        input_tokens = getattr(
                                            usage, "input_tokens", 0
                                        )
                                        output_tokens = getattr(
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
                                        if self.valves.DEBUG:
                                            logger.debug(" Usage stats: input={input_tokens}, output={output_tokens}, cache_creation={cache_creation_input_tokens}, cache_read={cache_read_input_tokens}")
                                        
                                        # Normalize usage keys to snake_case (avoid space variants)
                                        usage_data = {
                                            "input_tokens": input_tokens,
                                            "output_tokens": output_tokens,
                                            "total_tokens": input_tokens + output_tokens,
                                            "cache_creation_input_tokens": cache_creation_input_tokens,
                                            "cache_read_input_tokens": cache_read_input_tokens,
                                        }
                                        
                                        await self.emit_event( 
                                            {
                                                "type": "chat:completion",
                                                "data": {
                                                    "usage": usage_data,
                                                    "done": False,
                                                },
                                            }
                                        )

                            elif event_type == "content_block_start":
                                content_block = getattr(
                                    event, "content_block", None
                                )
                                content_type = getattr(content_block, "type", None)
                                if not content_block:
                                    continue
                                if content_type == "text":
                                    chunk += content_block.text or ""
                                if content_type == "thinking":
                                    is_model_thinking = True
                                    thinking_message = "\n<details>\n<summary>🧠 Thoughts</summary>\n\n"
                                    current_thinking_block = {
                                        "type": "thinking",
                                        "thinking": ""
                                    }
                                    await self.emit_event( 
                                        {
                                            "type": "status",
                                            "data": {
                                                "description": "Thinking...",
                                                "done": False,
                                            },
                                        }
                                    )
                                if content_type == "tool_use":
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
                                    active_server_tool_name = getattr(content_block, "name", "")
                                    active_server_tool_id = getattr(content_block, "id", "")
                                    server_tool_input_buffer = ""  # Reset buffer for new tool
                                    
                                    if self.valves.DEBUG:
                                        logger.debug("Server tool started: {active_server_tool_name} (ID: {active_server_tool_id})")
                                    
                                    if active_server_tool_name == "code_execution":
                                        await self.emit_event(
                                            {
                                                "type": "status",
                                                "data": {
                                                    "description": "Executing Code...",
                                                    "done": False,
                                                },
                                            }
                                        )
                                    elif active_server_tool_name == "web_search":
                                        await self.emit_event( 
                                            {
                                                "type": "status",
                                                "data": {
                                                    "description": "Starting Web Search...",
                                                    "done": False,
                                                },
                                            }
                                        )

                                if content_type == "code_execution_tool_result":
                                    result_block = getattr(
                                        content_block, "content", {}
                                    )
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
                                            + (
                                                f"```\n{stderr}\n```"
                                                if stderr
                                                else ""
                                            )
                                            + f"</details>\n"
                                        )
                                        await self.emit_message_delta(code_result_msg, final_message)
                                if content_type == "web_search_tool_result":
                                    if self.valves.DEBUG:
                                        logger.debug(" Processing web search result event: {event}")
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
                                            first_result = content_items[0] if content_items else None
                                            result_title = getattr(first_result, "title", "") if first_result else ""
                                            result_count = len(content_items)
                                            
                                            if result_title and result_count > 0:
                                                status_desc = f"Found {result_count} results - {result_title}"
                                                if result_count > 1:
                                                    status_desc += f" +{result_count-1} more"
                                            else:
                                                status_desc = "Web Search Complete"
                                            
                                            await self.emit_event(
                                                {
                                                    "type": "status",
                                                    "data": {
                                                        "description": status_desc,
                                                        "done": True,
                                                    },
                                                }
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
                                            current_thinking_block["thinking"] += thinking_text
                                    elif delta_type == "signature_delta":
                                        # Capture signature for thinking block preservation
                                        signature = getattr(delta, "signature", "")
                                        if current_thinking_block and signature:
                                            current_thinking_block["signature"] = signature
                                    elif delta_type == "text_delta":
                                        text_delta = getattr(delta, "text", "")
                                        
                                        # Emit "Responding..." status on first text delta (only once)
                                        if not first_text_emitted and not is_model_thinking and not active_server_tool_name:
                                            await self.emit_event(
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
                                                    parsed = json.loads(server_tool_input_buffer)
                                                    if 'query' in parsed:
                                                        new_query = parsed['query']
                                                        if self.valves.DEBUG:
                                                            logger.debug("Web search query complete: '{new_query}'")
                                                        
                                                        # Emit status only once when we get the complete query
                                                        if new_query and new_query != current_search_query:
                                                            current_search_query = new_query
                                                            await self.emit_event(
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
                                                    if self.valves.DEBUG:
                                                        logger.debug("Partial web_search JSON: {server_tool_input_buffer}")
                                                except Exception as e:
                                                    if self.valves.DEBUG:
                                                        logger.debug("Web search query extraction error: {e}")
                                            elif active_server_tool_name == "code_execution":
                                                # Code execution input - just log it
                                                if self.valves.DEBUG:
                                                    logger.debug("Code execution input: {server_tool_input_buffer[:100]}...")
                                        else:
                                            # Client-side tool - accumulate in tools_buffer
                                            tools_buffer += partial
                                            if self.valves.DEBUG:
                                                logger.debug("Client tool input accumulated: {len(tools_buffer)} chars")
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
                                content_block = getattr(
                                    event, "content_block", None
                                )
                                content_type = (
                                    getattr(content_block, "type", None)
                                    if content_block
                                    else None
                                )
                                event_name = getattr(event, "name", "")

                                # When a text block ends, emit any remaining chunk
                                if content_type == "text" and chunk.strip():
                                    await self.emit_message_delta(chunk + "\n", final_message)
                                    chunk = ""
                                    chunk_count = 0

                                # Reset server tool tracking when block stops
                                if content_type == "server_tool_use":
                                    if self.valves.DEBUG:
                                        logger.debug("Server tool block stopped: {active_server_tool_name}")
                                    # Add line break after server tool use
                                    await self.emit_message_delta("\n", final_message)
                                    active_server_tool_name = None
                                    active_server_tool_id = None
                                    server_tool_input_buffer = ""

                                # Close tools_buffer for normal tool_use content blocks AND execute immediately
                                if content_type == "tool_use" and tools_buffer:
                                    # Check if it's valid JSON already, if not close it
                                    try:
                                        json.loads(tools_buffer)
                                        # Already valid JSON, no need to close
                                        if self.valves.DEBUG:
                                            logger.debug(" tools_buffer already valid JSON: {tools_buffer}")
                                    except json.JSONDecodeError:
                                        # Check if input is empty (ends with "input": )
                                        if tools_buffer.rstrip().endswith('"input":') or tools_buffer.rstrip().endswith('"input": '):
                                            # Add empty object for input
                                            tools_buffer += ' {}'
                                            if self.valves.DEBUG:
                                                logger.debug(" Added empty input object: {tools_buffer}")
                                        # Invalid JSON, need to close the main object
                                        tools_buffer += "}"
                                        if self.valves.DEBUG:
                                            logger.debug(" Closed tools_buffer in content_block_stop: {tools_buffer}")
                                    
                                    # Parse and store this tool_use block
                                    if self.valves.DEBUG:
                                        logger.debug("Parsed tool call: {tools_buffer}")
                                    
                                    # Parse and start tool execution immediately!
                                    try:
                                        tool_call_data = json.loads(tools_buffer)
                                        tool_name = tool_call_data.get("name", "")
                                        tool_input = tool_call_data.get("input", {})
                                        tool_id = tool_call_data.get("id", "")
                                        
                                        # Store tool_use block for assistant message
                                        tool_use_blocks.append({
                                            "type": "tool_use",
                                            "id": tool_id,
                                            "name": tool_name,
                                            "input": tool_input
                                        })
                                        
                                        # Look up tool
                                        tool = __tools__.get(tool_name)
                                        if tool:
                                            # Store metadata for later result matching
                                            tool_call_data_list.append(tool_call_data)
                                            
                                            # Emit status event when tool execution starts
                                            await self.emit_event({
                                                "type": "status",
                                                "data": {
                                                    "description": f"🔧 Executing tool: {tool_name}",
                                                    "done": False,
                                                },
                                            })
                                            
                                            # Start execution immediately as async task
                                            args = tool_input if isinstance(tool_input, dict) else {}
                                            task = asyncio.create_task(tool["callable"](**args))
                                            running_tool_tasks.append(task)
                                            
                                            if self.valves.DEBUG:
                                                logger.debug("🚀 Started immediate execution for '%s' (task #%d)", tool_name, len(running_tool_tasks))
                                    except Exception as e:
                                        if self.valves.DEBUG:
                                            logger.debug("Failed to start tool execution: {e}")
                                    
                                    # Reset buffer for next tool
                                    tools_buffer = ""

                                if is_model_thinking:
                                    thinking_message += "\n</details>"
                                    # Preserve thinking block for multi-turn (API auto-filters)
                                    if current_thinking_block and current_thinking_block.get("thinking"):
                                        thinking_blocks.append(current_thinking_block)
                                        if self.valves.DEBUG:
                                            logger.debug("Preserved thinking block with {len(current_thinking_block.get('thinking', ''))} chars")
                                    # Send closing tag to complete the details block
                                    await self.emit_message_delta(thinking_message, final_message)
                                    is_model_thinking = False
                                    current_thinking_block = {}

                            elif event_type == "message_delta":
                                delta = getattr(event, "delta", None)
                                if delta:
                                    stop_reason = getattr(
                                        delta, "stop_reason", None
                                    )
                                    if stop_reason == "tool_use":
                                        # Emit any remaining text chunk before tool results
                                        if chunk.strip():
                                            await self.emit_message_delta(chunk, final_message)
                                            chunk = ""
                                            chunk_count = 0
                                        
                                        # Wait for all running tool tasks to complete
                                        if running_tool_tasks:
                                            if self.valves.DEBUG:
                                                logger.debug("⏳ Waiting for %d tool tasks to complete...", len(running_tool_tasks))
                                            
                                            # Emit status event while waiting for tools
                                            await self.emit_event({
                                                "type": "status",
                                                "data": {
                                                    "description": f"⏳ Waiting for {len(running_tool_tasks)} tool(s) to complete...",
                                                    "done": False,
                                                },
                                            })
                                            
                                            try:
                                                results = await asyncio.gather(*running_tool_tasks)
                                                if self.valves.DEBUG:
                                                    logger.debug("✅ All %d tool tasks completed", len(results))
                                                
                                                # Emit completion status
                                                await self.emit_event({
                                                    "type": "status",
                                                    "data": {
                                                        "description": f"✅ Tool execution complete",
                                                        "done": True,
                                                    },
                                                })
                                                
                                                # Build tool_result messages and emit to UI
                                                for tool_call_data, tool_result in zip(tool_call_data_list, results):
                                                    tool_use_id = tool_call_data.get("id", "")
                                                    tool_name = tool_call_data.get("name", "")
                                                    
                                                    # Determine if error
                                                    is_error = isinstance(tool_result, str) and tool_result.startswith("Error:")
                                                    
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
                                                        parsed_json = json.loads(tool_result)
                                                        formatted_result = f"```json\n{json.dumps(parsed_json, indent=2, ensure_ascii=False)}\n```"
                                                    except Exception:
                                                        formatted_result = str(tool_result)
                                                    
                                                    # Format tool input/parameters for display
                                                    tool_input = tool_call_data.get("input", {})
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
                                                    await self.emit_message_delta(tool_result_msg, final_message)
                                            except Exception as ex:
                                                if self.valves.DEBUG:
                                                    logger.error("❌ Tool execution failed: %s", ex)
                                                # Create error results
                                                for tool_call_data in tool_call_data_list:
                                                    tool_use_id = tool_call_data.get("id", "")
                                                    tool_name = tool_call_data.get("name", "unknown")
                                                    error_result = f"Error executing tool '{tool_name}': {str(ex)}"
                                                    tool_calls.append({
                                                        "type": "tool_result",
                                                        "tool_use_id": tool_use_id,
                                                        "content": error_result,
                                                        "is_error": True
                                                    })
                                        
                                        if self.valves.DEBUG:
                                            logger.debug(" Tool use detected, collected {len(tool_calls)} tool results:\nTool_Call JSON: {tool_calls}")

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
                                        chunk += "Claude was unable to process this request"

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
                                        stream_error
                                    )
                                    return final_text() + f"\n\nAn error occurred: {error_details}"

                            if chunk_count > token_buffer_size:
                                if chunk.strip():
                                    await self.emit_message_delta(chunk, final_message)
                                    chunk = ""
                                    chunk_count = 0

                    # Sende letzten Chunk, falls noch etwas übrig ist
                    if chunk.strip():
                        await self.emit_message_delta(chunk, final_message)
                        chunk = ""
                        chunk_count = 0
                    # Handle tool use at the end of the stream
                    if has_pending_tool_calls and tool_calls:
                        # Tools were already executed during stream (in message_delta)
                        # tool_calls now contains tool_result blocks ready for API
                        # UI output was already emitted during message_delta
                        
                        # Build assistant message with tool_use blocks
                        assistant_content = []
                        
                        # Add preserved thinking blocks first (for multi-turn reasoning)
                        # API will auto-filter & cache only relevant blocks
                        if thinking_blocks:
                            assistant_content.extend(thinking_blocks)
                            if self.valves.DEBUG:
                                logger.debug("Adding {len(thinking_blocks)} thinking block(s) to assistant message for API")
                        
                        # Add final text message if exists (important for context)
                        final_message_snapshot = final_text()
                        if final_message_snapshot.strip():
                            assistant_content.append(
                                {"type": "text", "text": final_message_snapshot}
                            )
                        elif chunk.strip():
                            assistant_content.append(
                                {"type": "text", "text": chunk}
                            )

                        # Add tool_use blocks to assistant message (ONLY client-side tools)
                        # Server-side tools (web_search, code_execution) are executed by Anthropic
                        # and don't need tool_use/tool_result blocks in subsequent messages
                        for tool_use_block in tool_use_blocks:
                            tool_id = tool_use_block.get("id", "")
                            tool_name = tool_use_block.get("name", "")
                            
                            # Skip server-side tools - they're already handled in the stream
                            if tool_id.startswith("srvtoolu_") or tool_name in ["web_search", "code_execution"]:
                                if self.valves.DEBUG:
                                    logger.debug("🔧 Skipping server-side tool %s (ID: %s) in assistant message", tool_name, tool_id)
                                continue
                            
                            assistant_content.append(tool_use_block)
                            if self.valves.DEBUG:
                                logger.debug("🔧 Added tool_use block for %s to assistant message", tool_name)

                        # Add assistant message to conversation
                        if assistant_content:
                            payload_for_stream["messages"].append(
                                {"role": "assistant", "content": assistant_content}
                            )

                        # Add user message with tool results (tool_calls already contains tool_result blocks)
                        user_content = tool_calls.copy()
                        if user_content:
                            payload_for_stream["messages"].append(
                                {"role": "user", "content": user_content}
                            )

                        # Ensure we added at least one message, otherwise break the loop
                        if not assistant_content and not user_content:
                            if self.valves.DEBUG:
                                logger.debug("🔧 No valid content to add, ending conversation")
                            break

                        # Reset state for next iteration
                        current_function_calls += len(tool_calls)
                        has_pending_tool_calls = False
                        tool_calls = []
                        tool_use_blocks = []
                        thinking_blocks = []  # Reset after adding to messages
                        chunk = ""
                        chunk_count = 0
                        current_search_query = ""  # Reset search query for next iteration
                        citation_counter = 0  # Reset citation counter for next iteration
                        continue

                except RateLimitError as e:
                    # Rate limit error (429) - retryable
                    await self.handle_errors(e)
                    return final_text() + (f"\n\n⚠️ Rate limit exceeded - maximum retries ({self.valves.MAX_RETRIES}) reached. Please try again later.")
                except AuthenticationError as e:
                    # API key issues (401)
                    await self.handle_errors(e)
                    return final_text() + (
                        f"\n\nError: API key issues. Reason: {e.message}"
                    )
                except PermissionDeniedError as e:
                    # Permission issues (403)
                    await self.handle_errors(e)
                    return final_text() + (
                        f"\n\nError: Permission denied. Reason: {e.message}"
                    )
                except NotFoundError as e:
                    # Resource not found (404)
                    await self.handle_errors(e)
                    return final_text() + (
                        f"\n\nError: Resource not found. Reason: {e.message}"
                    )
                except BadRequestError as e:
                    # Invalid request format (400)
                    await self.handle_errors(e)
                    return final_text() + (
                        f"\n\nError: Invalid request format. Reason: {e.message}"
                    )

                except UnprocessableEntityError as e:
                    # Unprocessable entity (422)
                    await self.handle_errors(e)
                    return final_text() + (
                        f"\n\nError: Unprocessable entity. Reason: {e.message}"
                    )
                except InternalServerError as e:
                    # Server errors (500, 529) - 529 is overloaded_error - retryable
                    status_code = getattr(e, 'status_code', 500)
                    retry_attempts += 1
                    if retry_attempts <= self.valves.MAX_RETRIES:
                        error_type = "overloaded" if status_code == 529 else "server error"
                        if self.valves.DEBUG:
                            logger.debug("{error_type} ({status_code}), retry {retry_attempts}/{self.valves.MAX_RETRIES}")
                        
                        await self.emit_event({
                            "type": "status",
                            "data": {
                                "description": f"⏳ API {error_type}, retrying...)",
                                "done": False,
                            }
                        })
                        continue  # Retry the request
                    else:
                        # Max retries exceeded
                        await self.handle_errors(e)
                        error_type = "overloaded" if status_code == 529 else "server error"
                        return final_text() + (f"\n\n🔧 API {error_type} - maximum retries ({self.valves.MAX_RETRIES}) reached. Please try again later.")
                except APIConnectionError as e:
                    # Network/connection issues - potentially transient - retryable
                    retry_attempts += 1
                    if retry_attempts <= self.valves.MAX_RETRIES:
                        if self.valves.DEBUG:
                            logger.debug("Connection error, retry {retry_attempts}/{self.valves.MAX_RETRIES}")
                        
                        await self.emit_event({
                            "type": "status",
                            "data": {
                                "description": f"🌐 Connection error, retrying... ({retry_attempts}/{self.valves.MAX_RETRIES})",
                                "done": False,
                            }
                        })
                        continue  # Retry the request
                    else:
                        # Max retries exceeded
                        await self.handle_errors(e)
                        return final_text() + (
                            f"\n\n🌐 Network connection failed after {self.valves.MAX_RETRIES} attempts. Please check your connection."
                        )
                except APIStatusError as e:
                    # Catch any other Anthropic API errors
                    await self.handle_errors(e)
                    return final_text() + (
                        f"\n\nError: Anthropic API error. Reason: {e.message}"
                    )
                except Exception as e:
                    # Catch all other exceptions
                    await self.handle_errors(e)
                    return final_text() + f"\n\nError: {type(e).__name__} occurred. Reason: {e}"
        except Exception as e:
            await self.handle_errors(e)

        # Preserve existing generated content; append completion marker
        final_status = "✅ Response processing complete."
        if self.valves.SHOW_TOKEN_COUNT and usage_data:
            # Safely extract tokens
            input_tokens = usage_data.get("input_tokens", 0)
            output_tokens = usage_data.get("output_tokens", 0)
            cache_read_input_tokens = usage_data.get("cache_read_input_tokens", 0)
            cache_creation_input_tokens = usage_data.get("cache_creation_input_tokens", 0)
            total_tokens = input_tokens + output_tokens + cache_read_input_tokens + cache_creation_input_tokens
            usage_data["total_tokens"] = total_tokens  # ensure consistency

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

            final_status += f" [{bar}] {format_num(total_tokens)}/200k ({percentage:.1f}%)"

        await self.emit_event({
                            "type": "status",
                            "data": {
                                "description": final_status,
                                "done": True,
                            }
                        })
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
            
            if self.valves.DEBUG:
                logger.debug("Task payload: {json.dumps(task_payload, indent=2)}")
            
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
            
            if self.valves.DEBUG:
                logger.debug("Task response: {result}")
            
            return result
            
        except Exception as e:
            if self.valves.DEBUG:
                logger.debug("Task model error: {e}")
            await self.handle_errors(e)
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
                processed.append({
                    "role": role,
                    "content": content
                })
            elif isinstance(content, list):
                # Extract text from content blocks
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                if text_parts:
                    processed.append({
                        "role": role,
                        "content": " ".join(text_parts)
                    })
        
        return processed

    async def handle_errors(self, exception):
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

        logger.error("Exception: {error_msg}")
        # Add request ID if available for debugging
        if isinstance(exception, APIStatusError) and hasattr(exception, "response"):
            try:
                request_id = exception.response.headers.get("request-id")
                if request_id:
                    logger.info("Request ID: %s", request_id)
            except Exception:
                pass  # Ignore if we can't get request ID

        await self.emit_event({
            "type": "notification",
            "data": {
                "type": "error",
                "content": user_msg,
            },
        })
        import traceback

        tb = traceback.format_exc()
        from datetime import datetime

        await self.emit_event({
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
        })
        await self.emit_event({
            "type": "status",
            "data": {
                "description": "❌ Response with Errors",
                "done": True,
            }
        })

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
            message = (
                f"Error: Tool '{tool_name}' timed out after {self.TOOL_CALL_TIMEOUT} seconds"
            )
            if self.valves.DEBUG:
                self.logger.debug(message)
            return message
        except Exception as exc:
            if self.valves.DEBUG:
                self.logger.debug("Tool '%s' failed", tool_name, exc_info=exc)
            return f"Error executing tool '{tool_name}': {exc}"

    def _remove_thinking_blocks(self, content: str) -> str:
        """
        Remove thinking blocks from message content to prevent them from being
        re-sent to the API in subsequent requests.
        
        Removes HTML details blocks containing thinking content, e.g.:
        <details><summary>🧠 Thinking...</summary>\n...\n</details>
        
        Note: Does not strip whitespace - stripping is handled elsewhere as needed.
        """
        import re
        # Pattern to match details blocks with thinking content
        # Non-greedy match to handle multiple blocks
        pattern = r'<details>\s*<summary>🧠.*?</summary>.*?</details>\s*'
        cleaned = re.sub(pattern, '', content, flags=re.DOTALL)
        return cleaned

    def _process_content(self, content: Union[str, List[dict]]) -> List[dict]:
        """
        Process content from OpenWebUI format to Claude API format.
        Handles text, images, PDFs, tool_calls, and tool_results according to
        Anthropic API documentation.
        Filters out empty text blocks to prevent API errors.
        """
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
                            if self.valves.DEBUG:
                                logger.debug(" Unsupported image mime type: {mime_type}")
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
                            import base64

                            decoded_bytes = base64.b64decode(encoded)
                            if len(decoded_bytes) > MAX_IMAGE_SIZE:
                                if self.valves.DEBUG:
                                    logger.debug(" Image too large: {len(decoded_bytes)} bytes")
                                processed_content.append(
                                    {
                                        "type": "text",
                                        "text": f"[Image too large for Anthropic API. Max size: 25MB, received: {len(decoded_bytes)//1024//1024}MB]",
                                    }
                                )
                                continue
                        except Exception as decode_ex:
                            if self.valves.DEBUG:
                                logger.debug(" Image base64 decode failed: {decode_ex}")
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
                        if self.valves.DEBUG:
                            logger.debug("Error parsing image data URL: {e}")
                        processed_content.append(
                            {
                                "type": "text",
                                "text": "[Error processing image - invalid data URL format]",
                            }
                        )
                    except Exception as e:
                        if self.valves.DEBUG:
                            logger.debug("Unexpected error processing image: {e}")
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
                if self.valves.DEBUG:
                    logger.debug(" Unknown content type: {item.get('type')}, converting to text")
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
        Extract User Context from Openwebui Memory System from system prompt and remove it in one pass.
        Pattern (Hopefully stays that way): \nUser Context:\n ... \n\n (always followed by double newline)
        
        Returns:
            tuple[str, Optional[str]]: (cleaned_text, extracted_context)
            - cleaned_text: Original text with User Context removed (stripped)
            - extracted_context: The extracted User Context block with label, or None if not found
        """
        import re
        pattern = r'\nUser Context:\n(.*?)\n\n'
        match = re.search(pattern, text, re.DOTALL)
        
        if match:
            context_content = match.group(1).strip()
            extracted_context = f"User Context:\n{context_content}" if context_content else None
            cleaned_text = re.sub(pattern, '', text, flags=re.DOTALL).strip()
            return cleaned_text, extracted_context

        # No User Context found - still strip the text
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
            if self.valves.DEBUG:
                logger.debug(" Processing citation event type: {getattr(event, 'type', 'unknown')}")

            # Extract citation from delta within content_block_delta event
            delta = getattr(event, "delta", None)
            citation = None

            if delta and hasattr(delta, "citation"):
                citation = delta.citation
            elif hasattr(event, "citation"):
                # Fallback: direct citation in event
                citation = event.citation


            if not citation:
                if self.valves.DEBUG:
                    logger.debug("No citation data found in event")
                return
            
            logger.debug(" Citation data found: {citation}")

            # Only handle web search result citations
            citation_type = getattr(citation, "type", "")
            if citation_type != "web_search_result_location":
                if self.valves.DEBUG:
                    logger.debug(" Skipping non-web-search citation type: {citation_type}")
                return

            # Extract web search citation information
            url = getattr(citation, "url", "")
            title = getattr(citation, "title", "Unknown Source")
            cited_text = getattr(citation, "cited_text", "")
            from datetime import datetime

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
            await self.emit_event({"type": "source", "data": source_data})

        except Exception as e:
            if self.valves.DEBUG:
                logger.debug("Error handling citation: {str(e)}")
            await self.handle_errors(e)

    async def emit_event(self, event: Dict[str, Any]) -> None:
        """
        Safely emit an event, handling None __event_emitter__ (e.g., in Channel contexts).
        
        In OpenWebUI Channels, when models are mentioned, __event_emitter__ is None
        because the channel context doesn't provide a socket connection for status updates.
        This helper prevents 'NoneType' object is not callable errors.
        """
        if self.eventemitter is None:
            return
        try:
            await self.eventemitter(event)
        except Exception as e:
            logger.warning("Event emitter failed: {e}")
    
    async def emit_message_delta(
        self,
        content: str,
        final_message: list[str] | None = None,
    ) -> None:
        """
        Emit content as chat:message:delta and automatically append to final message.
        Convenience wrapper for the most common emit pattern.
        
        Args:
            content: The content to emit
            final_message: The request-local final_message list to append to (prevents cross-user contamination)
        """
        await self.emit_event({
            "type": "chat:message:delta",
            "data": {"content": content}
        })
        if content and final_message is not None:
            final_message.append(content)
    