"""
title: Anthropic API Integration
id: anthropic_new
author: Podden (https://github.com/Podden/)
github: https://github.com/Podden/openwebui_anthropic_api_manifold_pipe
original_author: Balaxxe (Updated by nbellochi)
version: 0.9.26
license: MIT
requirements: pydantic>=2.0.0, anthropic>=0.121.0, pillow-heif>=0.18.0
environment_variables:
    - ANTHROPIC_API_KEY (required)

Supports:
- Uses Anthropic Python SDK
- File API with Skills and Code Execution
- Fetch Claude Models from API Endpoint
- Tool Call Loop (call multiple Tools in the same response)
- web_search Tool
- web_fetch Tool (URL content retrieval)
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
- Compaction
- Vision
- Context Editing (clear tool results and thinking blocks)
- Tool Search (BM25/Regex)
- Native PDF Upload (visual PDF analysis with charts/images)
- Agent Skills (pptx, xlsx, docx, pdf and custom skills)
- Fast Mode for Opus 5 / 4.8
- Programmatic Tool Calling (tools callable from code execution)
- Server-side fallback on safety refusals

Changelog:
v0.9.26
- Added human-in-the-loop tool approval (OpenWebUI 0.11.1). OpenWebUI enforces its gate inside its own tool loop, which a manifold never enters, so the setting silently did nothing here: with approval set to "ask", every client, builtin and Open Terminal tool call now waits for allow/deny, and a denial goes back to the model as a normal tool result so the turn continues
- Fixed a client tool failing outright on an argument its schema does not declare (observed: `{"params": "{}"}` for a parameterless tool, streamed by the API itself). Undeclared keys are dropped before the call, as OpenWebUI does in its own loop
- HIDE_BLOCKS is now a multiselect instead of a comma-separated string; existing string values still load
- Fixed HIDE_BLOCKS never hiding code execution: the collapsible ignored the valve, and the bash / text editor variants were not recognised as the same block
- Fixed total_tokens double-counting cache traffic; now input + output, matching OpenWebUI's usage contract, with cache reads and writes in their own two fields
- Added ask_user (OpenWebUI 0.11.1) to the tool-search exclude list

v0.9.25
- The Anthropic API key valve (admin and per-user) is now stored encrypted, using Fernet with a key derived from WEBUI_SECRET_KEY. OpenWebUI's own valve encryption is opt-in (ENABLE_VALVE_ENCRYPTION, off by default), so on a default install the key otherwise sits in the functions table in plaintext. Where that flag is on, the pipe defers to OpenWebUI rather than encrypting twice. Existing plaintext keys keep working -- no migration step
- Debug logs now start with the detected OpenWebUI version, and no longer contain the API key in plaintext
- Added MODEL_CACHE_TTL_MINUTES valve (default 1440 = 24h, 0 disables caching). The 24h TTL was hardcoded, so a newly released Claude model could not be picked up without restarting OpenWebUI
- Fixed the model cache surviving a connection change: the cached list is now fingerprinted against API key, base URL, workspace id and ENABLED_MODELS. Repointing the pipe at a different endpoint used to keep serving the previous endpoint's models
- A failed model refresh no longer falls back to a cache that was fetched from different connection settings

v0.9.24
- Fixed the context-window reading OpenWebUI uses for auto-compaction: prompt_tokens/completion_tokens now carry the last call's full input (uncached + cache writes + cache reads) instead of being absent. input_tokens/output_tokens stay cumulative and uncached-only, so cost and the analytics page are unchanged. Under caching the old numbers understated occupancy badly, and compaction fired far too late or never
- Sub-agent runs (OpenWebUI 0.11) now return plain prose: no collapsibles, no replay carriers, no token footer, no metadata markers. Their text is pasted into the parent agent's context, where all of that is pure token cost
- Task models (title, tags, follow-ups, queries, image prompts, autocomplete, memory review) now pin their response shape with structured outputs, so a stray markdown fence can no longer cost OpenWebUI the whole task
- Added the OpenWebUI 0.11 builtin tools to the tool-search exclude list: notify, timer, delegate_task, list_chat_files, grep_chat_files, query_chat_files
- Fixed sampling params being sent to adaptive-thinking models on endpoints that report no capability metadata (Azure and other proxies, manual ENABLED_MODELS ids), which the API answers with a 400 (#36, reported by @attilaolah)
- Corrected stale static model limits: Opus 4.6/4.7/4.8 and Sonnet 4.6 serve 128k output (were listed at 64k), Sonnet 4.5 serves a 1M window, and the 1M window no longer needs a beta header
- Bumped the required Anthropic SDK to 0.121.0

v0.9.23
- Added Claude Opus 5 (claude-opus-5): 1M context, 128k output, thinking on by default, full effort ladder incl. max, fast mode
- Thinking Toggle now works on thinking-on-by-default models (Opus 5 / Sonnet 5): turning it off sends thinking:{"type":"disabled"} instead of just omitting the field, and clamps effort to 'high' because Opus 5 rejects disabled thinking at xhigh/max
- Added REFUSAL_FALLBACK valve: retry a safety-refused request server-side, either on Anthropic's per-category recommendation ('default') or on a pinned model
- Removed Fast Mode for Opus 4.7 (2026-07-24): speed:"fast" now errors there instead of falling back to standard speed
- Fixed a prompt-cache killer: user tools are now appended name-sorted. OpenWebUI's tool order shifts on its own (toggling a tool appends it to the end of selectedToolIds, a page reload resets it to the model's order, MCP servers return any order), and the same tool set in a different order rebuilt the entire cache
- Bumped the required Anthropic SDK to 0.120.0
- Advisor and memory-review model lists know about Opus 5; advisor now defaults to it

v0.9.22
- Added Compatibility for OpenWebUI's ENABLE_MEMORY_BACKGROUND_REVIEW: task requests now forward their system prompt instead of dropping it, so the memory reviewer gets its "return only valid JSON" instruction
- Added MEMORY_REVIEW_MODEL valve to run the background memory review on a cheap model (default Haiku) instead of the chat model
- Task requests (title, tags, follow-ups, memory review) are stripped down to plain prose: no collapsibles, no cache diagnostics, no replay carriers, no inline markers
- HIDE_BLOCKS moved from the admin Valves to the UserValves — hiding a collapsible is a personal display preference

v0.9.21
- Added HIDE_BLOCKS valve to individually hide details in the conversation: Known values: web_search, web_fetch, tool_search, advisor, code_execution, compaction
- Added CACHE_TTL_FOR_TOOLS_AND_SYSTEM_PROMT valve to separately cache System Prompt and Tools Array for an hour (useful for big multi-user setups)
- Added Compatibility for new OpenWebUI Memory System Format so cache stays stable
- Added cached-% and a call count for multi-call turns on Token display
- Fixed markdown breaking at text content_block boundaries
- CACHE-DIFF logging is breakpoint-aware and no longer reports the per-request memory/RAG appendix as a cache break when the API sees none

v0.9.20
- Fixed a "API key is invalid" error when using ANTHROPIC KEY Valve

v0.9.19
- Removed static ANTHROPIC_BUILTIN_TOOL_NAMES in favor of default TOOL_SEARCH_EXCLUDE_TOOLS including all openwebui internal tools
- Fixed open-terminal tool calls and read_file bugs, experimental bash and text_editor tool support seems to work now, needs further testing
- Fixed token explosion on requests containing images and binary files from older read_file tool calls from open-terminal

v0.9.18
- Client tool results containing base64 image data now correctly get's converted in Anthropic image blocks instead of raw base64 TEXT
- Use of native open-webui image compression user settings in image blocks
- Added Claude Sonnet 5 (claude-sonnet-5): 1M context, 128k output, adaptive thinking on by default
- Removed Fast Mode for Opus 4.6
- Experimental Claude on AWS Support: use ANTHROPIC_WORKSPACE_ID Valve to try it out
- Added ENABLED_MODELS valve + date-suffix normalization + static model fallback for endpoints without /v1/models (Azure/proxies)
- Added ANTHROPIC_API_KEY Enviromental Variable readout for easier configuration
- Increased the max-output-token fallback, 4096 is indeed to low :)
- Fixed File Downloading from code_execution container using Anthropic Files API

v0.9.17
- Added Fable and Mythos as advisor models
- Advisor Models is now dynamically adjusted to the next best model if not compatible

v0.9.16
- Added Claude Fable and Mythos 5 alongside new stop_reasons and refusals

v0.9.15
- Fixed Newline after Citations
- Fixed Tool calling error when tools payload changes while old tool results are still present in previous answers
- Fixed Stop Handling
- Fixed Status Emitting for Tool Search and Advisor

v0.9.14
- Added Claude Opus 4.8
- Promt caching bugfixes when using native PDF Upload and Images

v0.9.13
- Token counting is now Claude-Code-style: `total_tokens` only counts NEW tokens (uncached input + cache_creation + output) instead of all tokens
- Added `ENABLE_CACHE_DIAGNOSTICS` valve for debug purposes

v0.9.12
- Refactored the pipe into modular source files under `src/anthropic_pipe/`.
- Extracted request payload creation into `request_payload.py` for cache/debug work.
- Split streaming content-block handling into per-content modules and added a build step that compiles/minifies the OpenWebUI single-file artifact before deploy.
- Fixed Anthropic API Skills container payload shape and added clearer Files API / code execution guidance.

v0.9.11
- Added async handling for run_command <-> bash tool
- Added all anthropic server tools as TOOL_SEARCH_EXCLUDE_TOOLS

v0.9.10
- Added Experimental path for using Anthropics native (`bash_20250124`) to use with OpenTerminal. Use Valve `ENABLE_BASH_TOOL`
- Added Experimental path for using Anthripics native (`text_editor_20250728` / `str_replace_based_edit_tool`) tools to use with Open Terminal. Use Valve `ENABLE_TEXT_EDITOR_TOOL`.

v0.9.9
- Fixed Tool Search Block reconstruction as well. Displays collapsible instead of status
- Added Experimental support for the Advisor tool support (beta `advisor-tool-2026-03-01`). New valves:
  `ENABLE_ADVISOR_TOOL`, `ADVISOR_MODEL` (default claude-opus-4-7),
  `ADVISOR_MAX_USES` (0=unlimited), `ADVISOR_CACHING` (off/5m/1h ephemeral).

v0.9.8
- Complete overhaul of how message blocks are recreated for a new turn to align with
    Anthropic cache restrictions.
- Cache now should not break on new turns even when using RAG, image or PDF upload,
    memory, tools, and similar flows.
- Refactored tool / thinking output so grouped activity renders as one collapsible UI block.

v0.9.7
- Preserves thinking signatures across turns for better replay continuity and cache behavior.

v0.9.6
- Updated for Open WebUI 0.9.0+ async APIs.

v0.9.5
- Added Claude Opus 4.7 and the new xhigh effort level.

v0.9.4
- Added Cache Statistics to Token Count Message

v0.9.3
- Moved Compaction and Context Editing into UserValves.
- Upgraded token display to Off / On / With Cache.

v0.9.2
- added compaction and client-side compaction trim: drops messages before the last compaction boundary before sending
and added message trim optimization

v0.9.1
- return whole message at the end and switched from chat:completion to message:delta event to prevent empty messages

v0.9
- Fixed total_usage access bug when usage capability is not enabled on model
- Removed Sonnet 4 and Opus/Sonnet 4.5 from 1 Mio context windows support
- Fetch model capabilites like max_input_token now directly from the API
- Added support for thinking.display: "omitted" (https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking#controlling-thinking-display)

v0.8.12
- Add API tool passthrough for external function calling
- Added ANTHROPIC_BASE_URL valve to allow routing all API requests through a custom proxy URL
- Fixed Tool Result output Grouping
- Decluddered the if/else horror in event_type handling
- Fixed OpenTerminal Tools

v0.8.11
- Added Caching time CACHE_TTL valve to choose between 5 minutes (default) and 1 hour
- Fixed TTS in Call Mode
- Added chat:completion done event in PHASE 7 for proper stream termination signalling
- Fixed Tool Result and Thought Grouping for Openwebui 0.8.11
- Fixed Programmatic Tool Call Issue

v0.8.10
- Pipe can now handle HTMLResponse Results from Tools (Rich UI with embedded iframes, HTML widgets, and file attachments)
- Added Support for Openwebui Skills

v0.8.9
- Removed <details> tags from what's send to claude API to prevent hallucinations
- Added Valves for Request and Tool call Timeouts
- Increased MAX_TOOL_CALLS max limit for long agentic tasks
- Added optional API Key set via UserValves (overrides header-level key)
- Reintroduced the Ability for Claude to know how many tool calls are available until limit is hit
- Removed 1 Mio Context Window Valve as it's now generally available

v0.8.8
- Fixed a Bug with interleaved thinking and tool calls where the API does not preserve the thinking blocks resulting in invalid requests
- Tool Input and Code Execution Input is not correctly streamed in a collapsible container with spinner
- Removed Status Update for Tool Calls and Code Execution as they are now streaming live with the new streaming strategy
- Tool Call Errors get's correctly emitted now instead of silently ignored and causing unlimited spinning

v0.8.7
- Code execution blocks now use OpenWebUI native `<details type="code_interpreter">` format
  - Spinner + "Analyzing…" / "Analyzed" transitions matching built-in code interpreter
  - Duration tracking and display
  - Output (stdout, stderr, tool call results) in HTML `output` attribute for CodeBlock rendering
- Fixed live-streamed code blocks getting stuck on "Analyzing…" when new code_execution starts
- Fixed empty "Analyzed" blocks by using accumulated code as fallback
- Removed redundant status events for code execution ("Running code", "Code → Tool", "Code execution complete")
- Fixed cache_control being placed on programmatic tool_use blocks with caller field
- Removed _emit_code_execution_source calls (output now embedded in code_interpreter block)

v0.8.6
- Fixed Token Counting for new Analytics Tab
- Properly formatted and grouped Thinking and Tool Result Blocks
- Fixed Token Usage Status for 1 Mio Context Window

v0.8.6
- Fixed: Truncated streams (200 OK + no stop_reason after server tools) now auto-retry instead of silent empty response
  - Detects when API returns thinking/server_tool blocks but no text and no stop_reason
  - Auto-retries up to MAX_RETRIES times with clean state reset
  - Shows user-visible status during retry and error message if all retries fail
  - Root cause: Anthropic API overload (529) → SDK retry → 200 OK but truncated stream
- Fixed: JSON.parse frontend error caused by pipe returning dict {} instead of empty string
  - functions.py sent `data: {}` without [DONE] → frontend failed to parse as OpenAI chunk
  - Now returns "" → proper finish_reason=stop + [DONE] SSE termination

v0.8.6
- Fixed: Truncated streams (200 OK + no stop_reason after server tools) now auto-retry instead of silent empty response
  - Detects when API returns thinking/server_tool blocks but no text and no stop_reason
  - Auto-retries up to MAX_RETRIES times with clean state reset
  - Shows user-visible status during retry and error message if all retries fail
  - Root cause: Anthropic API overload (529) → SDK retry → 200 OK but truncated stream
- Fixed: JSON.parse frontend error caused by pipe returning dict {} instead of empty string
  - functions.py sent `data: {}` without [DONE] → frontend failed to parse as OpenAI chunk
  - Now returns "" → proper finish_reason=stop + [DONE] SSE termination

v0.8.5
- Refactored: Cache control logic consolidated into single `_apply_cache_control()` method
  - All scattered cache_control placement removed from `_create_payload()` and tool loop
  - Cache breakpoints now applied fresh right before every API call (initial + tool loop iterations)
  - Bug fix: Tools now cached at all non-disabled levels (was missing at "messages" level)
  - Tool loop: properly handles programmatic vs standard tool calling cache placement
- Fixed: Effort level "max" now exclusively reserved for Opus 4.6 (was incorrectly allowed for Sonnet 4.6)
- Fixed: pause_turn stop reason now auto-continues instead of ending with error message
- Fixed: bash_code_execution_tool_result missing explicit error_code check — errors were silently ignored
- Fixed: text_editor_code_execution_tool_result missing explicit error_code check
- Fixed: code_execution_tool_result missing explicit error_code check
- All server tool errors (web_search, web_fetch, code_execution, bash, text_editor) now emit user-visible error messages

v0.8.4
- Fixed: Streaming overloaded_error (HTTP 200 + SSE error) now retries instead of failing immediately (GH #19)
- Fixed: Non-streaming OverloadedError (529) was falling through to generic APIStatusError handler instead of retrying
- Added dedicated OverloadedError exception handler with proper retry logic
- APIStatusError handler now checks e.body for overloaded_error type and retries if applicable

v0.8.3
- Text files created via text_editor (md, txt, csv, json, etc.) now display inline as markdown instead of code blocks
- Code files created via text_editor use proper syntax highlighting based on file extension
- Dynamic filtering valve description updated with speed vs quality tradeoff info (~60s vs ~7s)
- Added concise API payload logging at DEBUG level (model, tools, system size, container, max_tokens, thinking mode)
- Added tool result content size logging for tool call loop debugging

v0.8.2
- Streamlined code_execution UI for web search/fetch with dynamic filtering
  - When dynamic filtering is active (without programmatic tool calling), code_execution UI is suppressed
  - Only shows clean status: "🔍 Searching the web..." / "🌐 Fetching URL..."
- Fixed max_uses not working with dynamic filtering web tools (20260209 versions don't support max_uses)
- Added web_fetch status messages (start, URL being fetched, done/error)
- Code execution output now emitted as source/citation event (visible in citation panel)
- Consecutive code execution blocks are merged into one collapsible <details> block
- Added web_fetch_tool_result handler with error detection

v0.8.1
- Added experimental Files API Support for uploading files to the Container. Feedback welcome!
- Added a Valve to control wheter Opus/Sonnet 4.6 should use the new dynamic web_fetching and web_searching (At least I have issues with that)

v0.8.0
- Major streaming refactor: uses Anthropic SDK message accumulation instead of manual block tracking
- Implemented Fine-grained tool streaming with eager_input_streaming
- Tool search status now shows the actual search query
- Added web_fetch Tool
- Finally added Programmatic Tool Calling
- Code execution blocks display code, tool calls, and output in a unified collapsible block
- Updated web_search to use latest version with dynamic filtering support
- Model capabilities updated for Sonnet 4.5/4.6 and Opus 4.6 dynamic filtering support
- Added stop_reason debug logging for tool loop diagnostics
- Citations appear AFTER the cited text again

v0.7.1
- Removed deprecated Models Sonnet 3.7 and Haiku 3

v0.7.0
- Added Sonnet 4.6 model support
- Added Fast Mode support (speed: "fast" for Opus 4.6)
- Added web_fetch tool (URL content retrieval)
- Added memory tool integration with OpenWebUI memory system
- Added programmatic tool calling (allowed_callers for code execution)
- Fixed task model bug: _run_task_model_request() was called with extra argument

v0.6.3
- Added Opus 4.6
- Added Support for effort: max
- Added Support for Data residency
- Added messages for stop_reason in case of refusal, stop_sequence or context window exceeded
- Added ENABLE_INTERLEAVED_THINKING valve for enabling Thinking between Tool Calls
- Homogenized Thinking and Tool Call/Results streaming to match build in OpenAI/Ollama system

v0.6.2
- Reordered Payload for better Caching

v0.6.1
- Full Skills Support: Users can add skills (eg. pptx, xlsx, docx, pdf) or custom skills already uploaded to the Anthropic Site
- Skills are validated against the List Skills API endpoint with caching to avoid redundant API calls
- Invalid skills are logged and users are notified via warning message

v0.6
- Thinking, Tool Results and Code Execution now streams correctly and is folded at the end of the stream
- Tool Search Tool is now working correctly
- Added a new Companion Filter that is overwriting internal web_search and code_interpreter in favor of the anthropic tools
- Adding Files to the Conversation while using code interpreter now uploads the files to Anthropic Files API so they can be used by code execution VM
- Fixed Code Execution Tool: New Anthropic bash_code_execution and text_editor_code_execution tools are used now
- Added Buildin Openwebui Tools added in 0.7.0 - Be aware that this is introducing a lot of tokens. Best use with Tool Search
- USE_PDF_NATIVE_UPLOAD is now True by default, PDF Files now are embedded in to the correct user message every conversation step, added invisible Markdown Markers for storing this data in assistant messages
- Container ID persists across multi-turn conversations for code execution state continuity
- RAG is now working correctly in conjunction with Native PDF File upload, removing all sources from the RAG message which were already uploaded as native documents

v0.5.12
- Thinking is now streamed in the UI and folded when the thought process has ended

v0.5.11
- Added Compatibility to Build-in Tools from OpenWebUI 0.7.x

v0.5.10
- Performance: Pre-compiled regex patterns at module level (5-10x faster pattern matching)
- Performance: Added debug logging guards to prevent expensive JSON serialization
- Documentation: Added comprehensive docstring and section comments to pipe() method

v0.5.9
- PDF with 'Use Full Document Content' mode will then be uploaded as base64 documents instead of RAG text extraction, use UserValve USE_PDF_NATIVE_UPLOAD to Toggle

v0.5.8
- Fixed UnboundLocalError for 'total_usage' variable when opening new chats
- Added code execution to default TOOL_SEARCH_EXCLUDE_TOOLS list

v0.5.7
- Added Valve to exclude specific tools from deferred loading when tool search is enabled (web_search excluded by default)
- Web Search Toogle Filter overrides WEB_SEARCH Valve
- Fixed a Bug in Tool Search return

v0.5.6
- Added Context Editing feature (clear_tool_uses, clear_thinking) with configurable strategies
- Added Tool Search feature (BM25/Regex) with deferred tool loading
- Status events for context clearing with token counts

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
import os
import base64
import traceback
import inspect
import hashlib
from datetime import datetime
from collections.abc import Awaitable
import asyncio
import contextvars
import html
import json
import logging
import time
from dataclasses import dataclass, field
from urllib.parse import quote, unquote
from typing import Any, Callable, List, Union, Dict, Optional, Tuple
from pydantic import BaseModel, Field, field_validator
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

try:
    from anthropic import OverloadedError
except ImportError:

    class OverloadedError(Exception):
        pass
from typing import Literal
from fastapi import Request

logger = logging.getLogger(__name__)

PATTERN_USER_CONTEXT = re.compile(r"\nUser Context:\n(.*)$", flags=re.DOTALL)

PATTERN_MEMORY_CONTEXT = re.compile(
    r"<memory_context>(.*?)</memory_context>", flags=re.DOTALL
)

MEMORY_CONTEXT_APPENDIX_HEADER = (
    "\n\n---\n**IMPORTANT:** The following is NOT part of the user's message, "
    "but context from a memory system to help answer the user's questions:\n\n"
)

PATTERN_RAG_TEMPLATE_WITH_CONTEXT = re.compile(
    r"###\s*Task:.*?<context>.*?</context>", flags=re.DOTALL | re.MULTILINE
)
PATTERN_RAG_TEMPLATE_FALLBACK = re.compile(
    r"###\s*Task:.*?$", flags=re.DOTALL | re.MULTILINE
)
PATTERN_EMPTY_CONTEXT = re.compile(r"<context>\s*</context>", flags=re.DOTALL)

PATTERN_SOURCE_TAGS = re.compile(r"<source[^>]*>.*?</source>", flags=re.DOTALL)

PATTERN_RAG_MESSAGE = re.compile(r"### Task:.*?<context>.*?</context>", re.DOTALL)

PATTERN_SOURCE_TAG = re.compile(
    r'<source[^>]*name="([^"]+)"[^>]*>.*?</source>\s*', re.DOTALL
)

PATTERN_EMPTY_ATTACHED = re.compile(
    r"<attached_files>\s*</attached_files>\s*", re.DOTALL
)

PATTERN_TOOL_CALLS_DETAILS = re.compile(
    r'\n?<details type="tool_calls"(?![^>]*data-payload-b64=)[^>]*>.*?</details>\n?',
    flags=re.DOTALL,
)

PATTERN_TOOL_CALLS_BLOCK = re.compile(
    r'\n?<details type="tool_calls"(?![^>]*data-payload-b64=)([^>]*)>.*?</details>\n?',
    flags=re.DOTALL,
)
PATTERN_TOOL_CALLS_ATTRS = re.compile(r'(\w+)="([^"]*)"')

PATTERN_REASONING_BLOCK = re.compile(
    r'\n?<details type="reasoning"([^>]*)>\s*<summary>[^<]*</summary>\s*(.*?)\s*</details>\n?',
    flags=re.DOTALL,
)

PATTERN_REASONING_QUOTED_LINE = re.compile(r'^>\s?', flags=re.MULTILINE)

PATTERN_SERVER_TOOL_USE_BLOCK = re.compile(
    r'\n?<details type="tool_calls"([^>]*?data-block-kind="server_tool_use"[^>]*)>.*?</details>\n?',
    flags=re.DOTALL,
)
PATTERN_SERVER_TOOL_RESULT_BLOCK = re.compile(
    r'\n?<details type="tool_calls"([^>]*?data-block-kind="server_tool_result"[^>]*)>.*?</details>\n?',
    flags=re.DOTALL,
)

PATTERN_DATA_ATTR = re.compile(r'data-([\w-]+)="([^"]*)"')

PATTERN_HIDDEN_BLOCK = re.compile(
    r"^[ ]{0,3}\[anthropic-hidden[^\]]*\]:[ ]*#([A-Za-z0-9+/=]+)[ ]*$\n?",
    flags=re.MULTILINE,
)

HIDDEN_BLOCKS: contextvars.ContextVar[frozenset] = contextvars.ContextVar(
    "anthropic_pipe_hidden_blocks", default=frozenset()
)

SLIM_OUTPUT: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "anthropic_pipe_slim_output", default=False
)

TOOL_APPROVAL: contextvars.ContextVar[tuple] = contextvars.ContextVar(
    "anthropic_pipe_tool_approval", default=("full", None)
)

PATTERN_CODE_INTERPRETER_DETAILS = re.compile(
    r'\n?<details type="code_interpreter"[^>]*>.*?</details>\n?',
    flags=re.DOTALL,
)

PATTERN_CACHE_TRACE_DETAILS = re.compile(
    r'\n*<details type="cache-trace"[^>]*>.*?</details>\n*',
    flags=re.DOTALL,
)

PATTERN_COMPACTION_DETAILS = re.compile(
    r'<details type="compaction"[^>]*>\s*<summary>[^<]*</summary>\s*(.*?)\s*</details>',
    flags=re.DOTALL,
)

PATTERN_TOOL_RESULT_DATA_IMAGE = re.compile(
    r"data:image/(?P<mime>jpeg|png|gif|webp);base64,(?P<data>[A-Za-z0-9+/]+=*)"
)

PATTERN_ANY_DETAILS = re.compile(r"\n?<details[^>]*>.*?</details>\n?", flags=re.DOTALL)
PATTERN_INLINE_METADATA_MARKER = re.compile(r"[ ]?\[\]\(anthropic:[^)]*\)[ ]?")

PATTERN_TRAILING_SPACES = re.compile(r"[ \t]+$", flags=re.MULTILINE)
PATTERN_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")

try:
    from open_webui.models.models import Models, ModelForm

    MODELS_AVAILABLE = True
except ImportError:
    Models = None
    ModelForm = None
    MODELS_AVAILABLE = False

try:
    from cryptography.fernet import Fernet, InvalidToken

    VALVE_ENCRYPTION_AVAILABLE = True
except ImportError:
    Fernet = None
    InvalidToken = Exception
    VALVE_ENCRYPTION_AVAILABLE = False

try:
    from pydantic_core import core_schema

    PYDANTIC_CORE_AVAILABLE = True
except ImportError:
    core_schema = None
    PYDANTIC_CORE_AVAILABLE = False

ENCRYPTED_VALVE_PREFIX = "encrypted:"

try:
    from open_webui.env import VERSION as OPENWEBUI_VERSION
except Exception:
    OPENWEBUI_VERSION = "unknown"

try:
    from open_webui.env import ENABLE_VALVE_ENCRYPTION as OPENWEBUI_ENCRYPTS_VALVES
except Exception:
    OPENWEBUI_ENCRYPTS_VALVES = False

def _valve_encryption_key() -> Optional[bytes]:
    if not VALVE_ENCRYPTION_AVAILABLE:
        return None
    secret = os.environ.get("WEBUI_SECRET_KEY", "").strip()
    if not secret:
        return None

    if len(secret) == 44:
        try:
            Fernet(secret.encode())
            return secret.encode()
        except Exception:
            pass
    return base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())

def encrypt_valve_secret(value: str) -> str:
    if not value or value.startswith(ENCRYPTED_VALVE_PREFIX):
        return value
    if OPENWEBUI_ENCRYPTS_VALVES:
        return value
    key = _valve_encryption_key()
    if not key:
        return value
    try:
        return ENCRYPTED_VALVE_PREFIX + Fernet(key).encrypt(value.encode()).decode()
    except Exception as e:
        logger.warning(f"Could not encrypt valve value, storing as-is: {e}")
        return value

def decrypt_valve_secret(value: Any) -> str:
    text = str(value or "")
    if not text.startswith(ENCRYPTED_VALVE_PREFIX):
        return text
    token = text[len(ENCRYPTED_VALVE_PREFIX) :]
    key = _valve_encryption_key()
    if not key:
        raise ValueError(
            "Stored API key is encrypted but WEBUI_SECRET_KEY is not available. "
            "Restore the original secret key, or re-enter the API key in the valves."
        )
    try:
        return Fernet(key).decrypt(token.encode()).decode()
    except InvalidToken as e:
        raise ValueError(
            "Stored API key could not be decrypted -- WEBUI_SECRET_KEY appears to "
            "have changed. Re-enter the API key in the valves."
        ) from e

if PYDANTIC_CORE_AVAILABLE:

    class EncryptedStr(str):

        @classmethod
        def _validate(cls, value: Any) -> "EncryptedStr":
            return cls(encrypt_valve_secret(str(value or "")))

        @classmethod
        def __get_pydantic_core_schema__(cls, source_type, handler):
            return core_schema.no_info_after_validator_function(
                cls._validate, core_schema.str_schema()
            )

        def get_secret(self) -> str:
            return decrypt_valve_secret(self)

else:
    EncryptedStr = str

try:
    from open_webui.utils.tools import get_builtin_tools

    BUILTIN_TOOLS_AVAILABLE = True
except ImportError:
    get_builtin_tools = None
    BUILTIN_TOOLS_AVAILABLE = False

try:
    from open_webui.utils.middleware import process_tool_result

    PROCESS_TOOL_RESULT_AVAILABLE = True
except ImportError:
    process_tool_result = None
    PROCESS_TOOL_RESULT_AVAILABLE = False

try:
    from open_webui.models.files import Files
    from open_webui.storage.provider import Storage
    from pathlib import Path

    FILES_AVAILABLE = True
except ImportError:
    Files = None
    Storage = None
    Path = None
    FILES_AVAILABLE = False

try:
    from open_webui.models.chats import Chats

    CHATS_AVAILABLE = True
except ImportError:
    Chats = None
    CHATS_AVAILABLE = False

try:
    from PIL import Image as PILImage

    PIL_AVAILABLE = True
except Exception:
    PILImage = None
    PIL_AVAILABLE = False

@dataclass
class PipeRenderStrategy:

    stream_reasoning_live: bool = True
    stream_code_execution_live: bool = False
    stream_tool_results_live: bool = False

from dataclasses import dataclass, field

@dataclass
class TextState:
    chunk: str = ""
    chunk_count: int = 0
    current_search_query: str = ""
    citation_counter: int = 0
    pending_citation_markers: list[int] = field(default_factory=list)

    def reset_for_iteration(self) -> None:
        self.chunk = ""
        self.chunk_count = 0
        self.current_search_query = ""
        self.citation_counter = 0
        self.pending_citation_markers = []

    def reset_for_retry(self) -> None:
        self.reset_for_iteration()

@dataclass
class ThinkingState:
    is_active: bool = False
    message: str = ""
    signature: str = ""
    start_time: Optional[float] = None
    stream_start_idx: int = -1
    last_block: str = ""

    def reset_for_retry(self) -> None:
        self.message = ""
        self.signature = ""
        self.start_time = None
        self.stream_start_idx = -1
        self.last_block = ""

@dataclass
class CompactionState:
    content: str = ""
    last_block: str = ""

@dataclass
class ToolUseState:
    current_block_type: Optional[str] = None
    tools_buffer: str = ""
    input_buffer: str = ""
    tool_id_at_start: str = ""
    tool_name_at_start: str = ""
    running_tasks: list[Any] = field(default_factory=list)
    progress_blocks: dict[str, str] = field(default_factory=dict)
    api_passthrough: bool = False

    def reset_for_iteration(self) -> None:
        self.running_tasks = []
        self.progress_blocks = {}
        self.api_passthrough = False

@dataclass
class ServerToolState:
    active_name: Optional[str] = None
    active_id: Optional[str] = None
    input_buffer: str = ""
    use_carriers: dict[str, dict[str, Any]] = field(default_factory=dict)

    text_editor_file_content: str = ""
    text_editor_file_path: str = ""
    text_editor_command: str = ""
    bash_command: str = ""
    code_execution_code: str = ""

    in_code_execution: bool = False
    is_web_filtering: bool = False
    has_user_tools: bool = False
    had_web_tools: bool = False
    tool_calls_info: list[dict[str, Any]] = field(default_factory=list)
    stream_start_idx: int = -1
    last_block: str = ""
    current_code: str = ""
    current_lang: str = "python"
    start_time: float = 0.0
    last_code_language: str = "bash"
    last_code_content: str = ""
    has_explicit_code_execution: bool = False

    def end_code_execution(self) -> None:
        self.in_code_execution = False
        self.is_web_filtering = False
        self.has_user_tools = False
        self.had_web_tools = False
        self.tool_calls_info = []
        self.stream_start_idx = -1

    def reset_for_retry(self) -> None:
        self.active_name = None
        self.active_id = None
        self.input_buffer = ""
        self.text_editor_file_content = ""
        self.text_editor_file_path = ""
        self.text_editor_command = ""
        self.bash_command = ""
        self.code_execution_code = ""
        self.current_code = ""
        self.last_block = ""
        self.last_code_content = ""
        self.end_code_execution()

@dataclass
class StreamState:

    text: TextState = field(default_factory=TextState)
    thinking: ThinkingState = field(default_factory=ThinkingState)
    compaction: CompactionState = field(default_factory=CompactionState)
    tool_use: ToolUseState = field(default_factory=ToolUseState)
    server_tool: ServerToolState = field(default_factory=ServerToolState)

    def reset_current_block(self) -> None:
        self.tool_use.current_block_type = None

@dataclass
class PipeRequestContext:

    pipe: Any
    event_emitter: Callable[[Dict[str, Any]], Awaitable[None]]
    render_strategy: PipeRenderStrategy = field(default_factory=PipeRenderStrategy)
    final_message: list[str] = field(default_factory=list)
    state: StreamState = field(default_factory=StreamState)

    run_id: str = field(default_factory=lambda: os.urandom(4).hex())

    status: Any = None
    user: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tools: Optional[Dict[str, Any]] = None
    builtin_tools: Dict[str, Any] = field(default_factory=dict)
    api_tool_names: List[str] = field(default_factory=list)
    api_key: str = ""

    async def emit_event(self, event: dict) -> None:
        await self.pipe.emit_event(event, self.event_emitter)

    async def emit_delta(self, content: str) -> None:
        await self.emit_event({"type": "message", "data": {"content": content}})
        self.final_message.append(content)

    async def emit_block(self, block: str) -> None:
        if (
            block
            and self.final_message
            and not self.text().endswith(("\n", "\r"))
            and not block.startswith(("\n", "\r"))
        ):
            block = "\n" + block
        await self.emit_delta(block)

    async def emit_replace(self, content: str) -> None:
        await self.emit_event({"type": "replace", "data": {"content": content}})
        self.final_message.clear()
        self.final_message.append(content)

    async def update_content_block(self, old_block: str, new_block: str) -> None:
        if not old_block and not new_block:

            return
        if old_block:
            text = self.text()
            idx = text.find(old_block)
            if idx != -1:
                text = text[:idx] + new_block + text[idx + len(old_block):]
                await self.emit_replace(text)
                return

        text = self.pipe._append_block_to_text(self.text(), new_block)
        await self.emit_replace(text)

    def text(self) -> str:
        return "".join(self.final_message)

async def create_request_payload(
    pipe,
    body: Dict,
    __metadata__: dict[str, Any],
    __user__: Dict[str, Any],
    __tools__: Optional[Dict[str, Dict[str, Any]]],
    __event_emitter__: Callable[[Dict[str, Any]], Awaitable[None]],
    __files__: Optional[List[Dict[str, Any]]] = None,
) -> tuple[dict, dict, List[str], List[str]]:

    status_cls = globals().get("StatusEmitter")
    if status_cls:
        status = status_cls(__event_emitter__)
    else:
        class _PayloadStatus:
            def __init__(self, emit_event):
                self._emit_event = emit_event

            async def activity(self, description: str) -> None:
                await self._emit_event(
                    {"type": "status", "data": {"description": description, "done": False}}
                )

            async def complete(self, description: str) -> None:
                await self._emit_event(
                    {"type": "status", "data": {"description": description, "done": True}}
                )

            async def notification(self, content: str, *, type: str = "warning") -> None:
                await self._emit_event(
                    {"type": "notification", "data": {"type": type, "content": content}}
                )

        status = _PayloadStatus(__event_emitter__)

    actual_model_name = body["model"].split("/")[-1]
    model_info = pipe.get_model_info(actual_model_name)
    max_tokens_limit = model_info["max_tokens"]
    requested_max_tokens = body.get("max_tokens", max_tokens_limit)
    max_tokens = min(requested_max_tokens, max_tokens_limit)
    payload: dict[str, Any] = {
        "model": actual_model_name,
        "max_tokens": max_tokens,
        "stream": body.get("stream", True),
        "metadata": body.get("metadata", {}),
    }

    _strip_sampling = bool(model_info.get("supports_adaptive_thinking"))
    if not _strip_sampling and body.get("temperature") is not None:
        payload["temperature"] = float(body.get("temperature", 0))
    if not _strip_sampling and body.get("top_k") is not None:
        payload["top_k"] = float(body.get("top_k", 0))
    if not _strip_sampling and body.get("top_p") is not None:
        payload["top_p"] = float(body.get("top_p", 0))

    if pipe.valves.DATA_RESIDENCY == "us":
        payload["inference_geo"] = "us"

    if pipe.valves.ENABLE_FAST_MODE and model_info.get("supports_fast_mode", False):
        payload["speed"] = "fast"
        logger.debug("Fast Mode enabled for this request")

    effort_config = None
    effective_effort = None

    if model_info["supports_effort"]:

        def _clamp_effort(value: str) -> str:
            if value == "xhigh" and not model_info.get("supports_effort_xhigh"):
                return "high"
            if value == "max" and not model_info.get("supports_effort_max"):
                return "high"
            return value

        body_effort = body.get("reasoning_effort")
        if body_effort in ("low", "medium", "high", "xhigh", "max"):
            effective_effort = _clamp_effort(body_effort)
        else:
            effective_effort = _clamp_effort(__user__["valves"].EFFORT)

        effort_config = {"effort": effective_effort}
        logger.debug(f"Effort level set to: {effective_effort}")

    enable_thinking = __user__["valves"].ENABLE_THINKING or __metadata__.get(
        "anthropic_thinking", False
    )
    if enable_thinking and model_info["supports_thinking"]:

        if model_info["supports_adaptive_thinking"]:
            thinking_config = {"type": "adaptive"}
        else:
            user_budget = __user__["valves"].THINKING_BUDGET_TOKENS
            max_tokens = min(
                body.get("max_tokens", model_info["max_tokens"]),
                model_info["max_tokens"],
            )
            context_limit = model_info.get("context_length", 200000)

            if model_info.get("supports_thinking") and model_info.get(
                "supports_programmatic_calling"
            ):
                thinking_budget = min(user_budget, context_limit)
            else:

                thinking_budget = (
                    min(user_budget, max_tokens - 1) if max_tokens > 1 else 1
                )
            thinking_config = {
                "type": "enabled",
                "budget_tokens": thinking_budget,
            }
            logger.debug(
                f"Using manual thinking with budget_tokens: {thinking_budget}, effort: {effective_effort}"
            )

        thinking_display = __user__["valves"].THINKING_DISPLAY
        if thinking_display in ("omitted", "summarized"):
            thinking_config["display"] = thinking_display

        payload["thinking"] = thinking_config
    elif model_info.get("thinking_on_by_default"):

        payload["thinking"] = {"type": "disabled"}
        if effective_effort in ("xhigh", "max"):
            logger.info(
                f"Thinking disabled on {actual_model_name}: effort "
                f"'{effective_effort}' is incompatible with thinking:disabled, "
                "clamping to 'high'"
            )
            effective_effort = "high"
            effort_config = {"effort": "high"}

    raw_messages = body.get("messages", []) or []

    system_messages, processed_messages, previous_marker_metadata = (
        pipe._convert_messages_to_claude_format(raw_messages)
    )
    new_marker_metadata: List[str] = []

    previous_container_id = None
    for metadata_entry in previous_marker_metadata:

        parts = metadata_entry.split(":", 2)
        if len(parts) >= 3 and parts[1] == "container_id":
            previous_container_id = unquote(parts[2])
            logger.debug(f"📦 Restored container_id from marker: {previous_container_id}")

    has_files_api_uploads = False
    user_valves_for_features = __user__["valves"]
    requested_skills = list(getattr(user_valves_for_features, "SKILLS", []) or [])
    use_files_api = bool(getattr(user_valves_for_features, "USE_FILES_API", False)) or bool(
        __metadata__.get("enforce_files_api")
    )
    has_full_files_attached = any(
        file.get("type") == "file" and file.get("context", "full") == "full"
        for file in (__files__ or [])
    )

    if requested_skills and has_full_files_attached and not use_files_api:
        await status.activity("Skills require Files API for attached files")
        await status.notification(
            "Anthropic API Skills cannot access attached files through OpenWebUI RAG or native PDF upload. "
            "Enable USE_FILES_API, use the Files API Toggle, or attach the Companion Filter so files are routed to Anthropic Files API."
        )

    if __files__ and use_files_api and not FILES_AVAILABLE:
        await status.complete("Files API unavailable")
        await status.notification(
            "Anthropic Files API mode was requested, but OpenWebUI Files/Storage support is unavailable in this runtime. "
            "Enable OpenWebUI Files support or disable Files API mode for this request."
        )

    has_prior_pdf_markers = any(
        len(e.split(":", 2)) >= 3 and e.split(":", 2)[1] == "pdf"
        for e in (previous_marker_metadata or [])
    )

    if __files__ and use_files_api and FILES_AVAILABLE:

        blocks_by_user_msg, uploaded_filenames = await pipe._process_files_api_data(
            __files__, __event_emitter__, processed_messages
        )
        if blocks_by_user_msg:
            has_files_api_uploads = True

            user_msg_num = 0
            for i, msg in enumerate(processed_messages):
                if msg["role"] == "user" and user_msg_num in blocks_by_user_msg:

                    if isinstance(msg["content"], str):
                        msg["content"] = [{"type": "text", "text": msg["content"]}]
                    msg["content"] = blocks_by_user_msg[user_msg_num] + msg["content"]
                if msg["role"] == "user":
                    user_msg_num += 1

            if uploaded_filenames:
                logger.debug(f"📋 RAG: Removing {len(uploaded_filenames)} file source(s) from RAG")
                pipe._remove_specific_sources_from_rag_message(processed_messages, uploaded_filenames)

    elif __user__["valves"].USE_PDF_NATIVE_UPLOAD and (__files__ or has_prior_pdf_markers):

        native_pdf_filenames = list(dict.fromkeys(
            file.get("name")
            for file in (__files__ or [])
            if (
                file.get("type") == "file"
                and file.get("context") == "full"
                and file.get("name", "").lower().endswith(".pdf")
            )
            and file.get("name")
        ))
        pdf_blocks_by_user_msg, new_marker_metadata = (
            await pipe._get_full_context_pdfs(
                __files__, previous_marker_metadata, processed_messages, raw_messages
            )
        )
        if pdf_blocks_by_user_msg:
            user_msg_num = 0
            for msg in processed_messages:
                if msg["role"] == "user":
                    if user_msg_num in pdf_blocks_by_user_msg:
                        if isinstance(msg["content"], str):
                            msg["content"] = [
                                {"type": "text", "text": msg["content"]}
                            ]
                        msg["content"] = (
                            pdf_blocks_by_user_msg[user_msg_num]
                            + msg["content"]
                        )
                    user_msg_num += 1

        if native_pdf_filenames:
            logger.debug(
                f"📋 RAG: Removing {len(native_pdf_filenames)} native PDF source(s) from RAG"
            )
            pipe._remove_specific_sources_from_rag_message(
                processed_messages, native_pdf_filenames
            )

    if not has_files_api_uploads:
        (
            full_ctx_blocks_by_user_msg,
            full_ctx_markers,
            full_ctx_filenames,
        ) = await pipe._get_full_context_texts(
            __files__,
            previous_marker_metadata,
            processed_messages,
            raw_messages,
            exclude_pdfs=bool(__user__["valves"].USE_PDF_NATIVE_UPLOAD),
        )
        if full_ctx_blocks_by_user_msg:
            user_msg_num = 0
            for msg in processed_messages:
                if msg["role"] == "user":
                    if user_msg_num in full_ctx_blocks_by_user_msg:
                        if isinstance(msg["content"], str):
                            msg["content"] = [
                                {"type": "text", "text": msg["content"]}
                            ]
                        msg["content"] = (
                            full_ctx_blocks_by_user_msg[user_msg_num]
                            + msg["content"]
                        )
                    user_msg_num += 1
            new_marker_metadata.extend(full_ctx_markers)
        if full_ctx_filenames:
            logger.debug(
                f"📋 RAG: Removing {len(full_ctx_filenames)} full-context source(s) from RAG"
            )
            pipe._remove_specific_sources_from_rag_message(
                processed_messages, full_ctx_filenames
            )

    tools_list, api_tool_names = pipe._convert_tools_to_claude_format(
        __tools__, body, actual_model_name, __user__, __metadata__
    )

    activate_code_execution = __metadata__.get(
        "activate_code_execution_tool", False
    )

    if has_files_api_uploads:
        activate_code_execution = True

    if (
        pipe.valves.ENABLE_PROGRAMMATIC_TOOL_CALLING
        and model_info.get("supports_programmatic_calling", False)
        and tools_list
    ):
        activate_code_execution = True

    has_dynamic_filtering_tools = any(
        t.get("type", "").endswith("_20260209") for t in tools_list
    )
    has_code_execution = any(
        t.get("name") == "code_execution" for t in tools_list
    )

    has_native_terminal_tools = any(
        t.get("name") in ("bash", "str_replace_based_edit_tool") for t in tools_list
    )

    use_programmatic_code_exec = (
        pipe.valves.ENABLE_PROGRAMMATIC_TOOL_CALLING
        and model_info.get("supports_programmatic_calling", False)
    )

    if activate_code_execution and not has_code_execution and not has_native_terminal_tools:
        if use_programmatic_code_exec:

            code_exec_type = "code_execution_20260120"
            tools_list.insert(0, {"type": code_exec_type, "name": "code_execution"})
            has_code_execution = True
        elif not has_dynamic_filtering_tools:

            code_exec_type = "code_execution_20250825"
            tools_list.insert(0, {"type": code_exec_type, "name": "code_execution"})
            has_code_execution = True

    if requested_skills and not has_code_execution:
        await status.activity("Skills require Anthropic code_execution")
        await status.notification(
            "Anthropic API Skills require Anthropic code_execution. Enable the Code Execution Toggle, "
            "or attach the Companion Filter so OpenWebUI code_interpreter requests set activate_code_execution_tool."
        )

    user_valves = __user__.get("valves") if __user__ else None
    user_api_key = getattr(user_valves, "ANTHROPIC_API_KEY", "") if user_valves else ""
    api_key = user_api_key.strip() if user_api_key and user_api_key.strip() else pipe.valves.ANTHROPIC_API_KEY

    headers = {
        "x-api-key": api_key,
        "anthropic-version": pipe.API_VERSION,
        "content-type": "application/json",
    }

    beta_headers: list[str] = []

    if pipe.valves.CACHE_CONTROL != "cache disabled":
        beta_headers.append("prompt-caching-2024-07-31")

    if has_code_execution:

        code_exec_is_new = any(
            t.get("type") == "code_execution_20260120" for t in tools_list
        )
        if not code_exec_is_new:
            beta_headers.append("code-execution-2025-08-25")
        if activate_code_execution:
            beta_headers.append("files-api-2025-04-14")
    if (
        pipe.valves.ENABLE_INTERLEAVED_THINKING
        and model_info["supports_thinking"]
        and not model_info["supports_adaptive_thinking"]
    ):
        beta_headers.append("interleaved-thinking-2025-05-14")

    uses_old_web_fetch = any(
        t.get("type") == "web_fetch_20250910" for t in tools_list
    )
    if pipe.valves.WEB_FETCH and uses_old_web_fetch:
        beta_headers.append("web-fetch-2025-09-10")

    if has_files_api_uploads and "files-api-2025-04-14" not in beta_headers:
        beta_headers.append("files-api-2025-04-14")

    if requested_skills and has_code_execution:
        if "skills-2025-10-02" not in beta_headers:
            beta_headers.append("skills-2025-10-02")
        if "files-api-2025-04-14" not in beta_headers:
            beta_headers.append("files-api-2025-04-14")

        validated_skills = await pipe._validate_and_get_skills(
            requested_skills,
            api_key,
            __event_emitter__,
        )
        if validated_skills:
            container: dict[str, Any] = {"skills": validated_skills}
            if previous_container_id:
                container["id"] = previous_container_id
            payload["container"] = container
            logger.debug(f"🔧 Added {len(validated_skills)} skills")
        else:
            await status.notification(
                f"No valid Anthropic API Skills found from requested list: {', '.join(requested_skills)}. Skills ignored."
            )
    elif previous_container_id:

        payload["container"] = previous_container_id
        logger.info(f"📦 Reusing container from previous turn: {previous_container_id}")

    if __user__["valves"].ENABLE_TOOL_SEARCH or pipe.valves.ENABLE_PROGRAMMATIC_TOOL_CALLING:
        beta_headers.append("advanced-tool-use-2025-11-20")

    if __user__["valves"].ENABLE_ADVISOR_TOOL:
        beta_headers.append("advisor-tool-2026-03-01")

    context_editing_strategy = __user__["valves"].CONTEXT_EDITING_STRATEGY
    if context_editing_strategy != "none":
        if "context-management-2025-06-27" not in beta_headers:
            beta_headers.append("context-management-2025-06-27")

        context_management = []

        if (
            context_editing_strategy in ["clear_thinking", "clear_both"]
            and enable_thinking
            and model_info["supports_thinking"]
        ):
            _keep_val = __user__["valves"].CONTEXT_EDITING_THINKING_KEEP
            clear_thinking = {
                "type": "clear_thinking_20251015",

                "keep": "all" if _keep_val <= 0 else {
                    "type": "thinking_turns",
                    "value": _keep_val,
                },
            }
            context_management.append(clear_thinking)

        if (
            context_editing_strategy in ["clear_tool_results", "clear_both"]
            and len(tools_list) > 2
        ):
            clear_tool_uses = {
                "type": "clear_tool_uses_20250919",
                "trigger": {
                    "type": "input_tokens",
                    "value": __user__["valves"].CONTEXT_EDITING_TOOL_TRIGGER,
                },
                "keep": {
                    "type": "tool_uses",
                    "value": __user__["valves"].CONTEXT_EDITING_TOOL_KEEP,
                },
            }
            if __user__["valves"].CONTEXT_EDITING_TOOL_CLEAR_AT_LEAST > 0:
                clear_tool_uses["clear_at_least"] = {
                    "type": "input_tokens",
                    "value": __user__["valves"].CONTEXT_EDITING_TOOL_CLEAR_AT_LEAST,
                }
            if __user__["valves"].CONTEXT_EDITING_TOOL_CLEAR_TOOL_INPUT:
                clear_tool_uses["clear_tool_inputs"] = True
            context_management.append(clear_tool_uses)

        if context_management:
            payload["context_management"] = {"edits": context_management}

    if __user__["valves"].ENABLE_COMPACTION and model_info.get("supports_compaction", False):
        if "context-management-2025-06-27" not in beta_headers:
            beta_headers.append("context-management-2025-06-27")
        beta_headers.append("compact-2026-01-12")

        compact_edit: dict[str, Any] = {
            "type": "compact_20260112",
            "trigger": {
                "type": "input_tokens",
                "value": __user__["valves"].COMPACTION_TRIGGER_TOKENS,
            },
        }
        if __user__["valves"].COMPACTION_INSTRUCTIONS.strip():
            compact_edit["instructions"] = __user__["valves"].COMPACTION_INSTRUCTIONS.strip()

        if "context_management" not in payload:
            payload["context_management"] = {"edits": []}
        payload["context_management"]["edits"].append(compact_edit)

    if model_info["supports_effort"] and effort_config:
        beta_headers.append("effort-2025-11-24")
        payload["output_config"] = effort_config

    if pipe.valves.ENABLE_FAST_MODE and model_info.get("supports_fast_mode", False):
        beta_headers.append("fast-mode-2026-02-01")

    fallback_mode = getattr(pipe.valves, "REFUSAL_FALLBACK", "off")
    if fallback_mode != "off" and pipe.valves.ANTHROPIC_BASE_URL.rstrip("/") == pipe._DEFAULT_API_BASE:
        beta_headers.append("server-side-fallback-2026-07-01")

        _fallbacks = (
            "default" if fallback_mode == "default" else [{"model": fallback_mode}]
        )
        payload.setdefault("extra_body", {})["fallbacks"] = _fallbacks
        logger.debug(f"Server-side refusal fallback: {_fallbacks}")

    if (
        getattr(pipe.valves, "ENABLE_CACHE_DIAGNOSTICS", False)
        and pipe.valves.CACHE_CONTROL != "cache disabled"
    ):
        beta_headers.append("cache-diagnosis-2026-04-07")
        chat_id_for_diag = __metadata__.get("chat_id") if __metadata__ else None

        previous_message_id = None
        for _entry in previous_marker_metadata:
            _parts = _entry.split(":", 2)
            if len(_parts) >= 3 and _parts[1] == "cachediag":
                previous_message_id = unquote(_parts[2])
        if previous_message_id is None and chat_id_for_diag:
            previous_message_id = pipe._cache_diagnostics_state.get(chat_id_for_diag)

        payload.setdefault("extra_body", {})["diagnostics"] = {
            "previous_message_id": previous_message_id
        }
        logger.debug(
            f"[CACHE-DIAG] previous_message_id={previous_message_id} chat_id={chat_id_for_diag}"
        )

    def _messages_have_compaction_block(msgs) -> bool:
        for _m in msgs or []:
            _content = _m.get("content") if isinstance(_m, dict) else None
            if isinstance(_content, list):
                for _block in _content:
                    if isinstance(_block, dict) and _block.get("type") == "compaction":
                        return True
        return False

    if _messages_have_compaction_block(processed_messages):
        if "context-management-2025-06-27" not in beta_headers:
            beta_headers.append("context-management-2025-06-27")
        if "compact-2026-01-12" not in beta_headers:
            beta_headers.append("compact-2026-01-12")

    if beta_headers and len(beta_headers) > 0:
        headers["anthropic-beta"] = ",".join(beta_headers)

        payload["betas"] = beta_headers

        if __metadata__.get("web_search_enforced"):

            has_web_search = any(t.get("name") == "web_search" for t in tools_list)
            if has_web_search:
                if "thinking" not in payload:

                    payload["tool_choice"] = {"type": "tool", "name": "web_search"}
                    logger.debug("Enforcing web_search via tool_choice")
                else:

                    payload["tool_choice"] = {"type": "auto"}
                    logger.debug(
                        "Thinking active - web_search added but not enforced (tool_choice=auto)"
                    )
            else:

                payload["tool_choice"] = {"type": "auto"}

    if "tool_choice" not in payload and body.get("tool_choice"):
        api_tc = body["tool_choice"]
        if isinstance(api_tc, dict) and "function" in api_tc:

            payload["tool_choice"] = {
                "type": "tool",
                "name": api_tc["function"]["name"],
            }
        elif isinstance(api_tc, str):

            mapping = {"auto": "auto", "none": "none", "required": "any"}
            payload["tool_choice"] = {"type": mapping.get(api_tc, api_tc)}
        else:

            payload["tool_choice"] = api_tc
        logger.debug(f"API tool_choice passthrough: {payload['tool_choice']}")

    _reserved_server_tool_names = {
        "web_search",
        "web_fetch",
        "code_execution",
        "bash",
        "str_replace_based_edit_tool",
        "str_replace_editor",
        "computer",
        "tool_search_tool_regex",
        "tool_search_tool_bm25",
        "advisor",
    }
    _present_tool_names = {
        t.get("name")
        for t in tools_list
        if isinstance(t, dict) and t.get("name")
    }
    for _msg in processed_messages:
        _content = _msg.get("content") if isinstance(_msg, dict) else None
        if not isinstance(_content, list):
            continue
        for _block in _content:
            if not isinstance(_block, dict) or _block.get("type") != "tool_search_tool_result":
                continue
            _inner = _block.get("content")
            if not isinstance(_inner, dict):
                continue
            _refs = _inner.get("tool_references")
            if not isinstance(_refs, list):
                continue
            _kept = [
                _ref
                for _ref in _refs
                if isinstance(_ref, dict)
                and (
                    _ref.get("tool_name") in _present_tool_names
                    or _ref.get("tool_name") in _reserved_server_tool_names
                )
            ]
            if len(_kept) != len(_refs):
                _dropped = [
                    _ref.get("tool_name")
                    for _ref in _refs
                    if _ref not in _kept
                ]
                _inner["tool_references"] = _kept
                logger.info(
                    f"[TOOL-FILTER] Dropped stale tool_search references "
                    f"(tool no longer enabled): {_dropped}"
                )

    payload["tools"] = tools_list

    if any(isinstance(_t, dict) and _t.get("defer_loading") for _t in tools_list):
        _tool_search_nudge = {
            "type": "text",
            "text": (
                "Some available tools are not listed directly in this request; they are "
                "loaded on demand via the tool search tool (tool_search_tool_*). Before "
                "telling the user you cannot do something or that you lack access to a tool, "
                "call the tool search tool to find a relevant tool, then use whatever it returns."
            ),
        }
        if isinstance(system_messages, list):
            system_messages = system_messages + [_tool_search_nudge]
        elif system_messages:
            system_messages = [{"type": "text", "text": str(system_messages)}, _tool_search_nudge]
        else:
            system_messages = [_tool_search_nudge]

    if system_messages and len(system_messages) > 0:
        payload["system"] = system_messages

    payload["messages"] = processed_messages

    payload["messages"] = pipe._canonicalize_block(payload["messages"])
    if payload.get("system") is not None:
        payload["system"] = pipe._canonicalize_block(payload["system"])

    return payload, headers, new_marker_metadata, api_tool_names

class BaseHandler:

    block_types: tuple[str, ...] = ()

    async def on_start(self, event: Any, ctx: Any) -> bool:
        return False

    async def on_delta(self, event: Any, ctx: Any) -> bool:
        return False

    async def on_stop(self, event: Any, ctx: Any) -> bool:
        return False

class TextBlockHandler(BaseHandler):

    block_types = ("text",)

    async def on_start(self, event: Any, ctx: Any) -> bool:
        await handle_text_block_start(getattr(event, "content_block", None), ctx)
        return True

    async def on_delta(self, event: Any, ctx: Any) -> bool:
        delta = getattr(event, "delta", None)
        delta_type = getattr(delta, "type", None)
        if delta_type == "text_delta":
            await handle_text_delta(delta, ctx)
            return True
        if delta_type == "citations_delta":
            await handle_citations_delta(event, ctx)
            return True
        return False

    async def on_stop(self, event: Any, ctx: Any) -> bool:
        await handle_text_block_stop(ctx)
        return True

class ThinkingBlockHandler(BaseHandler):

    block_types = ("thinking", "redacted_thinking")

    async def on_start(self, event: Any, ctx: Any) -> bool:
        block_type = getattr(getattr(event, "content_block", None), "type", None)
        if block_type == "redacted_thinking":
            await handle_redacted_thinking_block_start(ctx)
        else:
            await handle_thinking_block_start(ctx)
        return True

    async def on_delta(self, event: Any, ctx: Any) -> bool:
        delta = getattr(event, "delta", None)
        delta_type = getattr(delta, "type", None)
        if delta_type == "thinking_delta":
            await handle_thinking_delta(delta, ctx)
            return True
        if delta_type == "signature_delta":
            handle_signature_delta(delta, ctx)
            return True
        return False

    async def on_stop(self, event: Any, ctx: Any) -> bool:
        block = getattr(event, "content_block", None)
        block_type = getattr(block, "type", None) or ctx.state.tool_use.current_block_type
        await handle_thinking_block_stop(block_type, ctx)
        return True

class CompactionBlockHandler(BaseHandler):

    block_types = ("compaction",)

    async def on_start(self, event: Any, ctx: Any) -> bool:
        await handle_compaction_block_start(ctx)
        return True

    async def on_delta(self, event: Any, ctx: Any) -> bool:
        delta = getattr(event, "delta", None)
        if getattr(delta, "type", None) != "compaction_delta":
            return False
        await handle_compaction_delta(delta, ctx)
        return True

    async def on_stop(self, event: Any, ctx: Any) -> bool:
        await handle_compaction_block_stop(ctx)
        return True

class ClientToolUseBlockHandler(BaseHandler):

    block_types = ("tool_use",)

    async def on_start(self, event: Any, ctx: Any) -> bool:
        await handle_tool_use_block_start(getattr(event, "content_block", None), ctx)
        return True

    async def on_delta(self, event: Any, ctx: Any) -> bool:
        delta = getattr(event, "delta", None)
        if getattr(delta, "type", None) != "input_json_delta":
            return False
        await handle_client_tool_input_delta(getattr(delta, "partial_json", ""), ctx)
        return True

    async def on_stop(self, event: Any, ctx: Any) -> bool:
        await handle_tool_use_block_stop(ctx)
        return True

class ServerToolUseBlockHandler(BaseHandler):

    block_types = ("server_tool_use",)

    async def on_start(self, event: Any, ctx: Any) -> bool:
        await handle_server_tool_use_block_start(getattr(event, "content_block", None), ctx)
        return True

    async def on_delta(self, event: Any, ctx: Any) -> bool:
        delta = getattr(event, "delta", None)
        if getattr(delta, "type", None) != "input_json_delta":
            return False
        await handle_server_tool_input_delta(getattr(delta, "partial_json", ""), ctx)
        return True

    async def on_stop(self, event: Any, ctx: Any) -> bool:
        await handle_server_tool_use_block_stop(ctx)
        return True

class WebSearchResultBlockHandler(BaseHandler):

    block_types = ("web_search_tool_result",)

    async def on_start(self, event: Any, ctx: Any) -> bool:
        block = getattr(event, "content_block", None)
        await handle_web_tool_result_block_start("web_search_tool_result", block, ctx)
        return True

class WebFetchResultBlockHandler(BaseHandler):

    block_types = ("web_fetch_tool_result",)

    async def on_start(self, event: Any, ctx: Any) -> bool:
        block = getattr(event, "content_block", None)
        await handle_web_tool_result_block_start("web_fetch_tool_result", block, ctx)
        return True

class CodeExecutionResultBlockHandler(BaseHandler):

    block_types = (
        "code_execution_tool_result",
        "bash_code_execution_tool_result",
        "text_editor_code_execution_tool_result",
    )

    async def on_start(self, event: Any, ctx: Any) -> bool:
        block = getattr(event, "content_block", None)
        await handle_code_execution_result_block_start(
            getattr(block, "type", ""), block, ctx
        )
        return True

class ToolSearchResultBlockHandler(BaseHandler):

    block_types = ("tool_search_tool_result",)

    async def on_start(self, event: Any, ctx: Any) -> bool:
        await handle_tool_search_result_block_start(getattr(event, "content_block", None), ctx)
        return True

class AdvisorResultBlockHandler(BaseHandler):

    block_types = ("advisor_tool_result",)

    async def on_start(self, event: Any, ctx: Any) -> bool:
        await handle_advisor_result_block_start(getattr(event, "content_block", None), ctx)
        return True

class ContextClearedBlockHandler(BaseHandler):

    block_types = ("context_cleared",)

    async def on_start(self, event: Any, ctx: Any) -> bool:
        await handle_context_cleared_block_start(getattr(event, "content_block", None), ctx)
        return True

def default_handlers() -> list[Any]:
    return [
        TextBlockHandler(),
        ThinkingBlockHandler(),
        CompactionBlockHandler(),
        ClientToolUseBlockHandler(),
        ServerToolUseBlockHandler(),
        WebSearchResultBlockHandler(),
        WebFetchResultBlockHandler(),
        CodeExecutionResultBlockHandler(),
        ToolSearchResultBlockHandler(),
        AdvisorResultBlockHandler(),
        ContextClearedBlockHandler(),
    ]

class NoopHandler:

    block_types: tuple[str, ...] = ()

    async def on_start(self, event: Any, ctx: Any) -> bool:
        return False

    async def on_delta(self, event: Any, ctx: Any) -> bool:
        return False

    async def on_stop(self, event: Any, ctx: Any) -> bool:
        return False

class HandlerRegistry:

    def __init__(self, handlers: list[Any] | None = None) -> None:
        self._handlers: dict[str, Any] = {}
        self._noop = NoopHandler()
        for handler in handlers or []:
            self.register(handler)

    def register(self, handler: Any) -> None:
        for block_type in handler.block_types:
            if block_type in self._handlers:
                raise ValueError(f"Duplicate content block handler for {block_type!r}")
            self._handlers[block_type] = handler

    def for_block_type(self, block_type: str | None) -> Any:
        if not block_type:
            return self._noop
        return self._handlers.get(block_type, self._noop)

    async def handle_start(self, event: Any, ctx: Any) -> bool:
        block = getattr(event, "content_block", None)
        block_type = getattr(block, "type", None)
        ctx.state.tool_use.current_block_type = block_type
        return await self.for_block_type(block_type).on_start(event, ctx)

    async def handle_delta(self, event: Any, ctx: Any) -> bool:
        return await self.for_block_type(ctx.state.tool_use.current_block_type).on_delta(event, ctx)

    async def handle_stop(self, event: Any, ctx: Any) -> bool:
        block = getattr(event, "content_block", None)
        block_type = getattr(block, "type", None) or ctx.state.tool_use.current_block_type
        handled = await self.for_block_type(block_type).on_stop(event, ctx)
        ctx.state.reset_current_block()
        return handled

class StatusEmitter:
    def __init__(self, emit_event: Callable[[dict[str, Any]], Awaitable[None]]):
        self._emit_event = emit_event
        self._last_payload: dict[str, Any] | None = None

    async def emit(
        self,
        description: str,
        *,
        done: bool = False,
        hidden: bool | None = None,
        force: bool = False,
        **fields: Any,
    ) -> None:
        data: dict[str, Any] = {"description": description, "done": done}
        if hidden is not None:
            data["hidden"] = hidden
        data.update(fields)

        if not force and data == self._last_payload:
            return

        await self._emit_event({"type": "status", "data": data})
        self._last_payload = data

    async def waiting(self) -> None:
        await self.emit("Waiting for response...", hidden=False, force=True)

    async def thinking(self) -> None:
        await self.emit("💭 Thinking...")

    async def responding(self) -> None:
        await self.emit("Responding...")

    async def searching_web(self, query: str = "") -> None:
        await self.emit(f"🔍 Searching: {query}" if query else "🔍 Searching the web...")

    async def web_search_done(self, urls: list[str], query: str = "") -> None:
        if not urls:
            return
        await self.emit(
            "Searched {{count}} sites",
            action="web_search",
            urls=urls,
            query=query,
            count=len(urls),
        )

    async def fetching_url(self, url: str = "") -> None:
        await self.emit(f"🌐 Fetching {url}" if url else "🌐 Fetching URL...")

    async def running_code(self) -> None:
        await self.emit("🐍 Running code...")

    async def running_command(self) -> None:
        await self.emit("💻 Running bash command...")

    async def editing_file(self) -> None:
        await self.emit("📝 Editing file...")

    async def consulting_advisor(self) -> None:
        await self.emit("🧑‍⚖️ Consulting advisor...")

    async def searching_tools(self, query: str = "") -> None:
        await self.emit(f"🔍 Searching tools: {query}" if query else "🔍 Searching tools...")

    async def running_tool(self, tool_name: str) -> None:
        await self.emit(f"🔧 Running {tool_name}..." if tool_name else "🔧 Running tool...")

    async def compacting(self) -> None:
        await self.emit("📦 Compacting conversation context...")

    async def activity(self, description: str) -> None:
        await self.emit(description, done=False)

    async def complete(self, description: str) -> None:
        await self.emit(description, done=True, force=True)

    async def notification(self, content: str, *, type: str = "warning") -> None:
        await self._emit_event(
            {"type": "notification", "data": {"type": type, "content": content}}
        )

async def handle_text_block_start(content_block: Any, ctx: Any) -> None:
    await ctx.status.responding()
    ctx.state.text.chunk += getattr(content_block, "text", "") or ""

async def handle_text_delta(delta: Any, ctx: Any) -> None:
    text = ctx.state.text
    text.chunk += getattr(delta, "text", "")
    text.chunk_count += 1

async def handle_citations_delta(event: Any, ctx: Any) -> None:
    text = ctx.state.text
    if text.pending_citation_markers:
        text.chunk += "".join(f"[{n}]" for n in text.pending_citation_markers)
        text.pending_citation_markers = []
    text.citation_counter += 1
    text.pending_citation_markers.append(text.citation_counter)
    await ctx.pipe.handle_citation(event, ctx.event_emitter, text.citation_counter)

async def handle_text_block_stop(ctx: Any) -> None:
    text = ctx.state.text
    if text.pending_citation_markers:
        text.chunk += "".join(f"[{n}]" for n in text.pending_citation_markers)
        text.pending_citation_markers = []
    if text.chunk:

        await ctx.emit_delta(text.chunk)
        text.chunk = ""
        text.chunk_count = 0

async def handle_thinking_block_start(ctx: Any) -> None:
    await ctx.status.thinking()
    thinking = ctx.state.thinking
    thinking.is_active = True
    thinking.start_time = time.time()
    thinking.message = ""
    thinking.signature = ""
    thinking.stream_start_idx = len(ctx.final_message)

async def handle_redacted_thinking_block_start(ctx: Any) -> None:
    await ctx.status.thinking()
    ctx.state.thinking.is_active = True

async def handle_thinking_delta(delta: Any, ctx: Any) -> None:
    thinking = ctx.state.thinking
    thinking_text = getattr(delta, "thinking", "")
    thinking.message += thinking_text
    if thinking_text:
        formatted = ctx.pipe._format_thinking_block(thinking.message, duration=None)
        await ctx.update_content_block(thinking.last_block, formatted)
        thinking.last_block = formatted

def handle_signature_delta(delta: Any, ctx: Any) -> None:
    ctx.state.thinking.signature += getattr(delta, "signature", "") or ""

async def handle_thinking_block_stop(content_type: str, ctx: Any) -> None:
    thinking = ctx.state.thinking
    if not thinking.is_active or content_type not in ("thinking", "redacted_thinking"):
        return

    if content_type == "thinking" and (thinking.message or thinking.signature):
        duration = time.time() - (thinking.start_time or time.time())
        formatted = ctx.pipe._format_thinking_block(
            thinking.message, duration, signature=thinking.signature
        )
        await ctx.update_content_block(thinking.last_block, formatted)
        thinking.last_block = ""
        logger.debug(
            "Finalized thinking block (%d chars, %.1fs, sig=%dc)",
            len(thinking.message),
            duration,
            len(thinking.signature),
        )
    elif content_type == "redacted_thinking":
        logger.debug("Redacted thinking block completed (preserved by SDK)")

    thinking.is_active = False
    thinking.message = ""
    thinking.signature = ""
    thinking.stream_start_idx = -1

async def handle_compaction_block_start(ctx: Any) -> None:
    ctx.state.compaction.content = ""
    ctx.state.compaction.last_block = ""
    await ctx.status.compacting()
    logger.info("Compaction block started")

async def handle_compaction_delta(delta: Any, ctx: Any) -> None:
    compaction = ctx.state.compaction
    compaction.content += getattr(delta, "content", "")
    formatted = ctx.pipe._format_compaction_block(compaction.content)
    await ctx.update_content_block(compaction.last_block, formatted)
    compaction.last_block = formatted

async def handle_compaction_block_stop(ctx: Any) -> None:
    content = ctx.state.compaction.content
    logger.info("Compaction summary complete: %d chars", len(content))
    await ctx.status.activity(f"📦 Context compacted ({len(content)} chars summary)")

def _filter_tool_args(tool_entry: Any, args: dict) -> dict:
    if not isinstance(args, dict) or not args:
        return args if isinstance(args, dict) else {}
    spec = (tool_entry or {}).get("spec") if isinstance(tool_entry, dict) else None
    if not isinstance(spec, dict):
        return args
    params = spec.get("parameters")
    if not isinstance(params, dict) or not isinstance(params.get("properties"), dict):

        return args
    allowed = params["properties"].keys()
    kept = {k: v for k, v in args.items() if k in allowed}
    dropped = [k for k in args if k not in allowed]
    if dropped:
        logger.warning(
            "Tool '%s': dropped undeclared argument(s) %s not in its schema",
            spec.get("name", "?"),
            dropped,
        )
    return kept

async def handle_tool_use_block_start(content_block: Any, ctx: Any) -> None:
    tool_use = ctx.state.tool_use
    server_tool = ctx.state.server_tool
    tool_name = getattr(content_block, "name", "unknown")
    logger.debug("🔧 Tool use block started: %s", tool_name)

    if server_tool.in_code_execution and server_tool.is_web_filtering:
        server_tool.is_web_filtering = False
        server_tool.has_user_tools = True

    initial_input = getattr(content_block, "input", None) or {}
    tool_use.tool_name_at_start = tool_name
    tool_use.tool_id_at_start = getattr(content_block, "id", "")
    tool_use.input_buffer = ""
    if initial_input:
        logger.debug(
            "🔧 Tool input pre-populated at start: %s",
            json.dumps(initial_input, ensure_ascii=False)[:200],
        )
        tool_use.tools_buffer = json.dumps(
            {
                "type": content_block.type,
                "id": content_block.id,
                "name": content_block.name,
                "input": initial_input,
            },
            ensure_ascii=False,
        )
    else:
        tool_use.tools_buffer = (
            "{"
            f'"type": "{content_block.type}", '
            f'"id": "{content_block.id}", '
            f'"name": "{content_block.name}", '
            f'"input": '
        )

    if not server_tool.in_code_execution:

        await ctx.status.running_tool(tool_name)
        in_progress_block = ctx.pipe._format_tool_result_block(
            tool_use.tool_id_at_start, tool_name, initial_input or {}, "", done=False
        )
        tool_use.progress_blocks[tool_use.tool_id_at_start] = in_progress_block
        text = ctx.pipe._append_block_to_text(ctx.text(), in_progress_block)
        await ctx.emit_replace(text)

async def handle_client_tool_input_delta(partial: str, ctx: Any) -> None:
    tool_use = ctx.state.tool_use
    tool_use.tools_buffer += partial
    tool_use.input_buffer += partial

    if ctx.state.server_tool.in_code_execution:
        return
    if tool_use.tool_id_at_start not in tool_use.progress_blocks:
        return

    parsed_input = ctx.pipe._try_parse_partial_json(tool_use.input_buffer)
    if parsed_input is None:
        return
    old_block = tool_use.progress_blocks[tool_use.tool_id_at_start]
    new_block = ctx.pipe._format_tool_result_block(
        tool_use.tool_id_at_start, tool_use.tool_name_at_start, parsed_input, "", done=False
    )
    text = ctx.text().replace(old_block, new_block, 1)
    tool_use.progress_blocks[tool_use.tool_id_at_start] = new_block
    await ctx.emit_replace(text)

async def handle_tool_use_block_stop(ctx: Any) -> None:
    tool_use = ctx.state.tool_use
    pipe = ctx.pipe
    tools = ctx.tools
    builtin_tools = ctx.builtin_tools
    api_tool_names = ctx.api_tool_names
    running_tool_tasks = tool_use.running_tasks
    emit_delta = ctx.emit_delta
    emit_event = ctx.event_emitter
    tools_buffer = tool_use.tools_buffer

    if not tools_buffer:
        return

    try:
        json.loads(tools_buffer)
        logger.debug(" tools_buffer already valid JSON: %s", tools_buffer)
    except json.JSONDecodeError:
        if tools_buffer.rstrip().endswith('"input":') or tools_buffer.rstrip().endswith(
            '"input": '
        ):
            tools_buffer += " {}"
            logger.debug(" Added empty input object: %s", tools_buffer)
        tools_buffer += "}"
        logger.debug(" Closed tools_buffer in content_block_stop: %s", tools_buffer)

    logger.debug("Parsed tool call: %s", tools_buffer)

    try:
        tool_call_data = json.loads(tools_buffer)
        tool_name = tool_call_data.get("name", "")
        tool_input = tool_call_data.get("input", {})

        tool = tools.get(tool_name) if tools else None
        if (
            tool_name == "bash"
            and pipe.valves.ENABLE_BASH_TOOL
            and tools
            and "run_command" in tools
        ):
            args = tool_input if isinstance(tool_input, dict) else {}
            task = asyncio.create_task(
                pipe._await_tool_task_result(
                    tool_call_data,
                    pipe._dispatch_bash_tool(args, tools, emit_event),
                    timeout_s=pipe.valves.BASH_TOOL_TIMEOUT + 15,
                )
            )
            running_tool_tasks.append(task)
            logger.debug("🚀 Started bash bridge → run_command (task #%d)", len(running_tool_tasks))
        elif (
            tool_name == "str_replace_based_edit_tool"
            and pipe.valves.ENABLE_TEXT_EDITOR_TOOL
            and tools
            and "write_file" in tools
            and "replace_file_content" in tools
        ):
            args = tool_input if isinstance(tool_input, dict) else {}
            task = asyncio.create_task(
                pipe._await_tool_task_result(
                    tool_call_data,
                    pipe._dispatch_text_editor_tool(args, tools, emit_event),
                    timeout_s=pipe.valves.BASH_TOOL_TIMEOUT + 15,
                )
            )
            running_tool_tasks.append(task)
            logger.debug(
                "🚀 Started text_editor bridge (cmd=%s, task #%d)",
                args.get("command", "?"),
                len(running_tool_tasks),
            )
        elif tool and tool.get("callable"):
            args = _filter_tool_args(tool, tool_input if isinstance(tool_input, dict) else {})
            task = asyncio.create_task(
                pipe._await_tool_task_result(tool_call_data, tool["callable"](**args))
            )
            running_tool_tasks.append(task)
            logger.debug(
                "🚀 Started immediate execution for user tool '%s' (task #%d)",
                tool_name,
                len(running_tool_tasks),
            )
        elif tool_name in builtin_tools and builtin_tools[tool_name].get("callable"):
            args = _filter_tool_args(
                builtin_tools[tool_name], tool_input if isinstance(tool_input, dict) else {}
            )
            task = asyncio.create_task(
                pipe._await_tool_task_result(
                    tool_call_data,
                    builtin_tools[tool_name]["callable"](**args),
                )
            )
            running_tool_tasks.append(task)
            logger.debug(
                "🚀 Started immediate execution for builtin tool '%s' (task #%d)",
                tool_name,
                len(running_tool_tasks),
            )
        elif tool_name in api_tool_names:
            logger.info(
                "🔄 API tool passthrough for '%s': returning tool input as response",
                tool_name,
            )
            await emit_delta(json.dumps(tool_input, ensure_ascii=False))
            tool_use.api_passthrough = True
        else:
            logger.warning("Tool '%s' not found in __tools__ or builtin_tools", tool_name)

            async def error_result(tn=tool_name):
                return json.dumps(
                    {
                        "error": f"Tool '{tn}' is not available. It may require server context or is not configured."
                    },
                    ensure_ascii=False,
                )

            task = asyncio.create_task(
                pipe._await_tool_task_result(tool_call_data, error_result())
            )
            running_tool_tasks.append(task)
    except Exception as e:
        logger.error("Failed to start tool execution: %s", e)

    tool_use.tools_buffer = ""

TEXT_EXTENSIONS = {
    ".md", ".txt", ".csv", ".json", ".xml", ".yaml", ".yml", ".toml",
    ".ini", ".cfg", ".log", ".rst", ".html", ".htm", ".css",
}
EXT_TO_LANG = {
    ".py": "python", ".js": "javascript", ".ts": "typescript", ".sh": "bash",
    ".sql": "sql", ".r": "r", ".rb": "ruby", ".java": "java", ".c": "c",
    ".cpp": "cpp", ".go": "go", ".rs": "rust",
}
SERVER_TOOLS_TO_PERSIST = (
    "web_search", "web_fetch", "code_execution", "bash_code_execution",
    "text_editor_code_execution", "tool_search_tool_regex", "tool_search_tool_bm25",
    "advisor",
)

async def _finalize_open_code_block(ctx: Any) -> None:
    server_tool = ctx.state.server_tool
    if not server_tool.current_code:
        return
    duration = time.time() - server_tool.start_time if server_tool.start_time else None
    block = ctx.pipe._format_code_execution_block(
        server_tool.current_code,
        server_tool.current_lang,
        done=True,
        duration=duration,
    )
    await ctx.update_content_block(server_tool.last_block, block)
    server_tool.last_block = ""

async def handle_server_tool_use_block_start(content_block: Any, ctx: Any) -> None:
    server_tool = ctx.state.server_tool
    tool_name = getattr(content_block, "name", "")
    server_tool.active_name = tool_name
    server_tool.active_id = getattr(content_block, "id", "")
    server_tool.input_buffer = ""

    logger.debug(
        "Server tool started: %s (ID: %s)", server_tool.active_name, server_tool.active_id
    )
    server_tool.start_time = None

    if tool_name in ("web_search", "web_fetch"):

        if server_tool.in_code_execution:
            server_tool.had_web_tools = True

    elif tool_name == "code_execution":
        await ctx.status.running_code()
        await _finalize_open_code_block(ctx)

        server_tool.in_code_execution = True

        server_tool.is_web_filtering = True
        server_tool.has_user_tools = False
        server_tool.had_web_tools = False
        server_tool.tool_calls_info = []
        server_tool.stream_start_idx = len(ctx.final_message)
        server_tool.current_code = ""
        server_tool.current_lang = "python"
        server_tool.start_time = time.time()

    elif tool_name in ("bash_code_execution", "text_editor_code_execution"):
        if tool_name == "bash_code_execution":
            await ctx.status.running_command()
        else:
            await ctx.status.editing_file()
        await _finalize_open_code_block(ctx)

        server_tool.current_code = ""
        server_tool.current_lang = "bash" if tool_name == "bash_code_execution" else "python"
        server_tool.start_time = time.time()

    elif tool_name == "advisor":
        await ctx.status.consulting_advisor()

async def _stream_code_preview(ctx: Any, code: str, lang: str) -> None:
    server_tool = ctx.state.server_tool
    server_tool.current_code = code
    server_tool.current_lang = lang
    block = ctx.pipe._format_code_execution_block(code, lang)
    await ctx.update_content_block(server_tool.last_block, block)
    server_tool.last_block = block

def _shows_code_preview(server_tool: Any) -> bool:
    return not server_tool.is_web_filtering or not server_tool.had_web_tools

async def handle_server_tool_input_delta(partial: str, ctx: Any) -> None:
    server_tool = ctx.state.server_tool
    server_tool.input_buffer += partial
    tool_name = server_tool.active_name

    try:
        parsed = json.loads(server_tool.input_buffer)
    except (json.JSONDecodeError, ValueError):
        return

    if tool_name == "web_search":
        query = parsed.get("query")
        if query:

            await ctx.status.searching_web(query)
            if query != ctx.state.text.current_search_query:
                logger.debug("Web search query complete: '%s'", query)
                ctx.state.text.current_search_query = query

    elif tool_name == "web_fetch":
        if parsed.get("url"):
            await ctx.status.fetching_url(parsed["url"])

    elif tool_name == "code_execution":
        if "code" in parsed:
            server_tool.code_execution_code = parsed["code"]
            if _shows_code_preview(server_tool):
                await _stream_code_preview(
                    ctx, parsed["code"], parsed.get("language", "python")
                )

    elif tool_name == "bash_code_execution":
        if "command" in parsed:
            server_tool.bash_command = parsed["command"]
            logger.debug("Bash execution command: %s...", server_tool.bash_command[:100])
            if _shows_code_preview(server_tool):
                await _stream_code_preview(ctx, parsed["command"], "bash")

    elif tool_name == "text_editor_code_execution":
        if "command" in parsed:
            server_tool.text_editor_command = parsed["command"]
        if "path" in parsed:
            server_tool.text_editor_file_path = parsed["path"]
        if "file_text" in parsed:
            server_tool.text_editor_file_content = parsed["file_text"]
            if server_tool.text_editor_command == "create" and server_tool.text_editor_file_content:
                file_ext = (
                    os.path.splitext(server_tool.text_editor_file_path)[1].lower()
                    if server_tool.text_editor_file_path
                    else ""
                )

                if file_ext not in TEXT_EXTENSIONS:
                    await _stream_code_preview(
                        ctx,
                        server_tool.text_editor_file_content,
                        EXT_TO_LANG.get(file_ext, "python"),
                    )

    elif tool_name in ("tool_search_tool_regex", "tool_search_tool_bm25"):
        if "query" in parsed:
            logger.debug("Tool search query: '%s'", parsed["query"])
            await ctx.status.searching_tools(parsed["query"])

def _capture_last_code(server_tool: Any) -> None:
    tool_name = server_tool.active_name
    language = ""
    content = ""

    if tool_name == "bash_code_execution" and server_tool.bash_command:
        language = "bash"
        content = server_tool.bash_command
    elif (
        tool_name == "text_editor_code_execution"
        and server_tool.text_editor_command == "create"
        and server_tool.text_editor_file_content
    ):
        file_ext = (
            os.path.splitext(server_tool.text_editor_file_path)[1].lower()
            if server_tool.text_editor_file_path
            else ""
        )
        content = server_tool.text_editor_file_content

        language = (
            "__inline_text__" if file_ext in TEXT_EXTENSIONS else EXT_TO_LANG.get(file_ext, "python")
        )
    elif tool_name == "code_execution" and server_tool.code_execution_code:
        language = "python"
        content = server_tool.code_execution_code

    if content:
        server_tool.last_code_language = language
        server_tool.last_code_content = content

async def handle_server_tool_use_block_stop(ctx: Any) -> None:
    server_tool = ctx.state.server_tool
    logger.debug("Server tool block stopped: %s", server_tool.active_name)

    _capture_last_code(server_tool)

    if server_tool.active_name in SERVER_TOOLS_TO_PERSIST and server_tool.active_id:
        try:
            tool_input = json.loads(server_tool.input_buffer) if server_tool.input_buffer else {}
        except (json.JSONDecodeError, ValueError):
            tool_input = {}
        persisted_block = ctx.pipe._format_server_tool_use_block(
            tool_name=server_tool.active_name,
            tool_use_id=server_tool.active_id,
            tool_input=tool_input,
        )
        await ctx.emit_block(persisted_block)

        server_tool.use_carriers[server_tool.active_id] = {
            "block": persisted_block,
            "tool_name": server_tool.active_name,
            "tool_input": tool_input,
        }

    server_tool.active_name = None
    server_tool.active_id = None
    server_tool.input_buffer = ""
    server_tool.text_editor_file_content = ""
    server_tool.text_editor_file_path = ""
    server_tool.text_editor_command = ""
    server_tool.bash_command = ""
    server_tool.code_execution_code = ""

def _suppressed_as_web_filtering(server_tool: Any) -> bool:
    return server_tool.is_web_filtering and server_tool.had_web_tools

async def _download_links_for(files_output: Any, ctx: Any) -> list[str]:
    links: list[str] = []
    for file_obj in files_output or []:
        file_id = (
            file_obj.get("file_id")
            if isinstance(file_obj, dict)
            else getattr(file_obj, "file_id", None)
        )
        if file_id:
            links.append(
                await ctx.pipe._generate_file_download_link(
                    file_id=file_id,
                    api_key=ctx.api_key,
                    user_id=ctx.user.get("id", "unknown"),
                )
            )
    return links

async def _handle_bash_result(content_block: Any, ctx: Any) -> None:
    server_tool = ctx.state.server_tool
    logger.debug("Processing bash_code_execution_tool_result: %s", content_block)
    await ctx.pipe._persist_server_tool_result(
        content_block,
        "bash_code_execution_tool_result",
        ctx.emit_delta,
        summary_text="🖥️ bash result",
    )
    result_block = getattr(content_block, "content", None)
    if not result_block:
        return

    if getattr(result_block, "type", "") == "bash_code_execution_tool_result_error":
        error_code = getattr(result_block, "error_code", "unknown")
        logger.warning("bash_code_execution error: %s", error_code)
        await ctx.emit_delta(f"⚠️ Code execution error: {error_code}")
        server_tool.last_code_content = ""
        return

    stdout = getattr(result_block, "stdout", "")
    stderr = getattr(result_block, "stderr", "")
    return_code = getattr(result_block, "return_code", None)
    download_links = await _download_links_for(getattr(result_block, "content", []), ctx)

    if not (stdout or stderr or return_code is not None or download_links):
        return

    if _suppressed_as_web_filtering(server_tool):
        logger.debug("Suppressed bash code execution block (web filtering)")
    else:
        duration = time.time() - server_tool.start_time if server_tool.start_time else None
        block = ctx.pipe._format_code_execution_block(
            server_tool.last_code_content,
            "bash",
            done=True,
            duration=duration,
            stdout=stdout,
            stderr=stderr,
            return_code=return_code,
            download_links=download_links,
        )
        await ctx.update_content_block(server_tool.last_block, block)
        server_tool.last_block = ""
    server_tool.last_code_content = ""

async def _handle_text_editor_result(content_block: Any, ctx: Any) -> None:
    server_tool = ctx.state.server_tool
    logger.debug("Processing text_editor_code_execution_tool_result: %s", content_block)
    await ctx.pipe._persist_server_tool_result(
        content_block,
        "text_editor_code_execution_tool_result",
        ctx.emit_delta,
        summary_text="✏️ text_editor result",
    )
    result_block = getattr(content_block, "content", None)
    if not result_block:
        return

    result_type = getattr(result_block, "type", "")
    logger.debug("Text editor result type: %s", result_type)

    if result_type == "text_editor_code_execution_tool_result_error":
        error_code = getattr(result_block, "error_code", "unknown")
        logger.warning("text_editor_code_execution error: %s", error_code)
        await ctx.emit_delta(f"⚠️ Text editor error: {error_code}")
        server_tool.last_code_content = ""
        return

    if _suppressed_as_web_filtering(server_tool):
        logger.debug("Suppressed text editor block (web filtering)")
        server_tool.last_code_content = ""
    elif result_type == "text_editor_code_execution_create_result":
        if server_tool.last_code_content and server_tool.last_code_language == "__inline_text__":

            await ctx.emit_delta(f"\n\n{server_tool.last_code_content}\n\n")
            server_tool.last_code_content = ""
            server_tool.last_code_language = ""
        elif server_tool.last_code_content:
            duration = time.time() - server_tool.start_time if server_tool.start_time else None
            block = ctx.pipe._format_code_execution_block(
                server_tool.last_code_content,
                server_tool.last_code_language or "python",
                done=True,
                duration=duration,
            )
            await ctx.update_content_block(server_tool.last_block, block)
            server_tool.last_block = ""
            server_tool.last_code_content = ""
    elif result_type == "text_editor_code_execution_view_result":
        content = getattr(result_block, "content", "")
        if content:
            await ctx.emit_delta(
                f"\n<details>\n<summary>📄 File Content</summary>\n\n```\n{content}\n```\n</details>\n"
            )

async def _handle_generic_code_result(content_block: Any, ctx: Any) -> None:
    server_tool = ctx.state.server_tool
    logger.debug("Processing code_execution_tool_result")
    await ctx.pipe._persist_server_tool_result(
        content_block,
        "code_execution_tool_result",
        ctx.emit_delta,
        summary_text="🐍 code_execution result",
    )
    result_block = getattr(content_block, "content", None)
    stdout = ""
    stderr = ""
    return_code = None
    download_links: list[str] = []

    if result_block:
        as_dict = isinstance(result_block, dict)
        result_block_type = (
            result_block.get("type", "") if as_dict else getattr(result_block, "type", "")
        )
        if result_block_type == "code_execution_tool_result_error":
            error_code = (
                result_block.get("error_code", "unknown") if as_dict
                else getattr(result_block, "error_code", "unknown")
            )
            logger.warning("code_execution error: %s", error_code)
            await ctx.emit_delta(f"⚠️ Code execution error: {error_code}")
            server_tool.last_code_content = ""
            server_tool.in_code_execution = False
            server_tool.is_web_filtering = False
            return

        if as_dict:
            stdout = result_block.get("stdout", "")
            stderr = result_block.get("stderr", "")
            return_code = result_block.get("return_code", None)
            files_output = result_block.get("content", []) or []
        else:
            stdout = getattr(result_block, "stdout", "")
            stderr = getattr(result_block, "stderr", "")
            return_code = getattr(result_block, "return_code", None)
            files_output = getattr(result_block, "content", []) or []

        if files_output:
            logger.debug("Found %d generic code_execution file outputs", len(files_output))
        download_links = await _download_links_for(files_output, ctx)

    has_output = (
        stdout or stderr or return_code is not None
        or server_tool.tool_calls_info or download_links
    )
    if _suppressed_as_web_filtering(server_tool):
        logger.debug("Suppressed code_execution_tool_result (web filtering)")
        server_tool.last_code_content = ""
    elif has_output:
        duration = time.time() - server_tool.start_time if server_tool.start_time else None
        block = ctx.pipe._format_code_execution_block(
            server_tool.last_code_content or server_tool.current_code,
            "python",
            done=True,
            duration=duration,
            stdout=stdout,
            stderr=stderr,
            return_code=return_code,
            tool_calls_info=server_tool.tool_calls_info,
            download_links=download_links,
        )
        await ctx.update_content_block(server_tool.last_block, block)
        server_tool.last_block = ""
        server_tool.last_code_content = ""

    server_tool.end_code_execution()

_RESULT_HANDLERS = {
    "bash_code_execution_tool_result": _handle_bash_result,
    "text_editor_code_execution_tool_result": _handle_text_editor_result,
    "code_execution_tool_result": _handle_generic_code_result,
}

async def handle_code_execution_result_block_start(
    content_type: str, content_block: Any, ctx: Any
) -> None:
    handler = _RESULT_HANDLERS.get(content_type)
    if handler:
        await handler(content_block, ctx)

async def handle_web_tool_result_block_start(
    content_type: str,
    content_block: Any,
    ctx: Any,
) -> None:
    pipe = ctx.pipe
    server_tool_use_carriers = ctx.state.server_tool.use_carriers
    update_content_block = ctx.update_content_block
    if content_type == "web_search_tool_result":
        logger.debug(" Processing web search result event: %s", content_block)
        content_items = getattr(content_block, "content", None)
        tool_use_id = getattr(content_block, "tool_use_id", "") or ""
        error_code = None
        if content_items and not isinstance(content_items, list):
            content_inner_type = getattr(content_items, "type", "")
            if content_inner_type == "web_search_tool_result_error":
                error_code = getattr(content_items, "error_code", "unknown")
        if error_code:
            error_msg = f"⚠️ Web search error: {error_code}"
            logger.warning("web_search error: %s", error_code)
            err_payload = {"type": "web_search_tool_result_error", "error_code": error_code}
            carrier_info = server_tool_use_carriers.pop(tool_use_id, None) if tool_use_id else None
            if carrier_info:
                merged = pipe._format_server_tool_use_block(
                    tool_name=carrier_info["tool_name"],
                    tool_use_id=tool_use_id,
                    tool_input=carrier_info["tool_input"],
                    result_payload=err_payload,
                    result_block_type="web_search_tool_result",
                    result_summary=error_msg,
                    result_display_body=f"**{error_msg}** `{error_code}`",
                )
                await update_content_block(carrier_info["block"], merged)
        elif content_items and isinstance(content_items, list) and len(content_items) > 0:
            first_result = content_items[0] if content_items else None
            result_title = getattr(first_result, "title", "") if first_result else ""
            result_count = len(content_items)
            if result_title and result_count > 0:
                status_desc = f"Found {result_count} results - {result_title}"
                if result_count > 1:
                    status_desc += f" +{result_count-1} more"
            else:
                status_desc = "Web Search Complete"

            if tool_use_id:
                serialized_items = []
                display_lines = []
                for item in content_items:
                    if hasattr(item, "model_dump"):
                        item_d = item.model_dump(exclude_none=True)
                    elif isinstance(item, dict):
                        item_d = item
                    else:
                        continue
                    serialized_items.append(item_d)
                    title = item_d.get("title") or ""
                    url = item_d.get("url") or ""
                    if url:
                        display_lines.append(f"- [{html.escape(title or url)}]({url})")
                display_body = "\n".join(display_lines[:10])
                if status_desc:
                    display_body = f"**{status_desc}**\n\n{display_body}" if display_body else f"**{status_desc}**"

                await ctx.status.web_search_done(
                    [d.get("url") for d in serialized_items if d.get("url")],
                    query=ctx.state.text.current_search_query,
                )
                carrier_info = server_tool_use_carriers.pop(tool_use_id, None)
                if carrier_info:
                    merged = pipe._format_server_tool_use_block(
                        tool_name=carrier_info["tool_name"],
                        tool_use_id=tool_use_id,
                        tool_input=carrier_info["tool_input"],
                        result_payload=serialized_items,
                        result_block_type="web_search_tool_result",
                        result_summary=status_desc,
                        result_display_body=display_body,
                    )
                    await update_content_block(carrier_info["block"], merged)
        return

    if content_type == "web_fetch_tool_result":
        logger.debug("Processing web_fetch_tool_result")
        result_content = getattr(content_block, "content", None)
        tool_use_id = getattr(content_block, "tool_use_id", "") or ""
        error_code = None
        if result_content:
            content_type_inner = getattr(result_content, "type", "")
            if content_type_inner == "web_fetch_tool_error":
                error_code = getattr(result_content, "error_code", "unknown")
        if error_code:
            if tool_use_id:
                err_payload = {"type": "web_fetch_tool_error", "error_code": error_code}
                carrier_info = server_tool_use_carriers.pop(tool_use_id, None)
                if carrier_info:
                    merged = pipe._format_server_tool_use_block(
                        tool_name=carrier_info["tool_name"],
                        tool_use_id=tool_use_id,
                        tool_input=carrier_info["tool_input"],
                        result_payload=err_payload,
                        result_block_type="web_fetch_tool_result",
                        result_summary=f"🌐 Fetch failed: {error_code}",
                        result_display_body=f"**🌐 Fetch failed:** `{error_code}`",
                    )
                    await update_content_block(carrier_info["block"], merged)
        elif tool_use_id and result_content is not None:
            if hasattr(result_content, "model_dump"):
                serialized = result_content.model_dump(exclude_none=True)
            elif isinstance(result_content, dict):
                serialized = result_content
            else:
                serialized = None
            if serialized is not None:
                fetch_url = serialized.get("url") or "" if isinstance(serialized, dict) else ""
                display_body = f"**🌐 URL fetched:** {fetch_url}" if fetch_url else "**🌐 URL fetched**"
                carrier_info = server_tool_use_carriers.pop(tool_use_id, None)
                if carrier_info:
                    merged = pipe._format_server_tool_use_block(
                        tool_name=carrier_info["tool_name"],
                        tool_use_id=tool_use_id,
                        tool_input=carrier_info["tool_input"],
                        result_payload=serialized,
                        result_block_type="web_fetch_tool_result",
                        result_summary=f"🌐 URL fetched: {fetch_url}" if fetch_url else "🌐 URL fetched",
                        result_display_body=display_body,
                    )
                    await update_content_block(carrier_info["block"], merged)

def _serialize_content_payload(content: Any) -> Any:
    if content is not None:
        if hasattr(content, "model_dump"):
            try:
                return content.model_dump(exclude_none=True, mode="json")
            except Exception:
                try:
                    return content.model_dump(exclude_none=True)
                except Exception:
                    return None
        if isinstance(content, dict):
            return content
    return None

def _extract_advisor_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, list):
        return "".join(_extract_advisor_text(part) for part in content)
    text = getattr(content, "text", None)
    if text is None and isinstance(content, dict):
        text = content.get("text")
    return (text or "").strip()

async def handle_advisor_result_block_start(content_block: Any, ctx: Any) -> None:
    pipe = ctx.pipe
    server_tool_use_carriers = ctx.state.server_tool.use_carriers
    update_content_block = ctx.update_content_block
    emit_delta = ctx.emit_delta
    logger.debug(" Processing advisor result event: %s", content_block)
    tool_use_id = getattr(content_block, "tool_use_id", "") or ""
    content = getattr(content_block, "content", None)
    inner_type = (
        getattr(content, "type", "")
        if content is not None and hasattr(content, "type")
        else (content.get("type", "") if isinstance(content, dict) else "")
    )
    serialized_content = _serialize_content_payload(content) or {}

    if inner_type == "advisor_tool_result_error":
        error_code = (
            getattr(content, "error_code", "unknown")
            if hasattr(content, "error_code")
            else (content.get("error_code", "unknown") if isinstance(content, dict) else "unknown")
        )
        status_desc = f"🧑‍⚖️ Advisor error: {error_code}"
        display_body = f"**{status_desc}** `{html.escape(error_code)}`"
        logger.warning("advisor error: %s", error_code)
    elif inner_type == "advisor_redacted_result":
        status_desc = "🧑‍⚖️ Advisor: (redacted)"
        display_body = (
            "**🧑‍⚖️ Advisor consulted** _(encrypted output; "
            "content is decrypted server-side on the next turn)_"
        )
    else:
        advice_text = _extract_advisor_text(content)
        logger.info(
            "advisor result: inner_type=%s text_len=%d", inner_type, len(advice_text)
        )
        preview = advice_text.strip().splitlines()[0] if advice_text.strip() else ""
        status_desc = f"🧑‍⚖️ Advisor: {preview[:80]}" if preview else "🧑‍⚖️ Advisor consulted"
        display_body = advice_text.strip() if advice_text.strip() else "**🧑‍⚖️ Advisor consulted** _(empty response)_"

    if tool_use_id:
        carrier_info = server_tool_use_carriers.pop(tool_use_id, None)
        if carrier_info:
            merged = pipe._format_server_tool_use_block(
                tool_name=carrier_info["tool_name"],
                tool_use_id=tool_use_id,
                tool_input=carrier_info["tool_input"],
                result_payload=serialized_content,
                result_block_type="advisor_tool_result",
                result_summary=status_desc,
                result_display_body=display_body,
            )
            await update_content_block(carrier_info["block"], merged)
        else:
            standalone = pipe._format_server_tool_result_block(
                block_type="advisor_tool_result",
                tool_use_id=tool_use_id,
                content_payload=serialized_content,
                display_body=display_body,
                summary_text=status_desc,
            )
            await ctx.emit_block(standalone)

async def handle_tool_search_result_block_start(content_block: Any, ctx: Any) -> None:
    pipe = ctx.pipe
    server_tool_use_carriers = ctx.state.server_tool.use_carriers
    update_content_block = ctx.update_content_block
    emit_delta = ctx.emit_delta
    logger.debug(" Processing tool search result event: %s", content_block)
    tool_use_id = getattr(content_block, "tool_use_id", "") or ""
    content_obj = getattr(content_block, "content", None)
    tool_references = []
    if content_obj:
        if hasattr(content_obj, "tool_references"):
            tool_references = getattr(content_obj, "tool_references", []) or []
        elif isinstance(content_obj, dict):
            tool_references = content_obj.get("tool_references", []) or []
    tool_names = []
    for ref in tool_references:
        if hasattr(ref, "tool_name"):
            tool_names.append(getattr(ref, "tool_name", "unknown"))
        elif isinstance(ref, dict):
            tool_names.append(ref.get("tool_name", "unknown"))

    if tool_names:
        status_desc = (
            f"🧰 Found {len(tool_names)} tool(s): "
            f"{', '.join(tool_names[:5])}"
            + (f" +{len(tool_names)-5} more" if len(tool_names) > 5 else "")
        )
    else:
        status_desc = "🧰 Tool search: no matching tools"
    display_body = status_desc

    serialized_content = _serialize_content_payload(content_obj)
    if serialized_content is None:
        serialized_content = {
            "tool_references": [
                {"type": "tool_reference", "tool_name": name}
                for name in tool_names
            ],
        }

    if tool_use_id:
        carrier_info = server_tool_use_carriers.pop(tool_use_id, None)
        if carrier_info:
            merged = pipe._format_server_tool_use_block(
                tool_name=carrier_info["tool_name"],
                tool_use_id=tool_use_id,
                tool_input=carrier_info["tool_input"],
                result_payload=serialized_content,
                result_block_type="tool_search_tool_result",
                result_summary=status_desc,
                result_display_body=display_body,
            )
            await update_content_block(carrier_info["block"], merged)
        else:
            standalone = pipe._format_server_tool_result_block(
                block_type="tool_search_tool_result",
                tool_use_id=tool_use_id,
                content_payload=serialized_content,
                display_body=display_body,
                summary_text=status_desc,
            )
            await ctx.emit_block(standalone)

async def handle_context_cleared_block_start(content_block: Any, ctx: Any) -> None:
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

    await ctx.status.activity(status_desc)
    logger.debug("Context cleared: type=%s, tokens=%s", cleared_type, cleared_tokens)

class Pipe:
    API_VERSION = "2023-06-01"
    _DEFAULT_API_BASE = "https://api.anthropic.com"

    MODEL_MAX_TOKENS_FALLBACK = {
        "claude-opus-5": 128000,
        "claude-opus-4-8": 128000,
        "claude-opus-4-7": 128000,
        "claude-opus-4-6": 128000,
        "claude-opus-4-5": 64000,
        "claude-sonnet-5": 128000,
        "claude-sonnet-4-6": 128000,
        "claude-sonnet-4-5": 64000,
        "claude-fable-5": 128000,
        "claude-mythos-5": 128000,
        "claude-haiku-4-5": 64000,
    }

    MODEL_CONTEXT_LENGTH_FALLBACK = {
        "claude-opus-5": 1000000,
        "claude-sonnet-5": 1000000,
        "claude-fable-5": 1000000,
        "claude-mythos-5": 1000000,
        "claude-opus-4-8": 1000000,
        "claude-opus-4-7": 1000000,
        "claude-opus-4-6": 1000000,
        "claude-sonnet-4-6": 1000000,
        "claude-sonnet-4-5": 1000000,
    }

    MODEL_CAPABILITY_OVERRIDES = {
         "claude-fable-5": {
            "supports_dynamic_filtering": True,
            "supports_compaction": True,
            "supports_adaptive_thinking": True,
            "supports_structured_outputs": True,
        },

         "claude-mythos-5": {
            "supports_dynamic_filtering": True,
            "supports_compaction": True,
            "supports_adaptive_thinking": True,
            "supports_structured_outputs": True,
        },

        "claude-haiku-4-5": {
            "supports_structured_outputs": True,
        },
        "claude-opus-4-5": {
            "supports_structured_outputs": True,
        },
        "claude-sonnet-4-5": {
            "supports_structured_outputs": True,
        },
        "claude-opus-5": {
            "supports_dynamic_filtering": True,
            "supports_fast_mode": True,
            "supports_compaction": True,
            "supports_adaptive_thinking": True,
            "supports_structured_outputs": True,

            "thinking_on_by_default": True,
        },
        "claude-sonnet-5": {
            "supports_dynamic_filtering": True,
            "supports_compaction": True,
            "supports_adaptive_thinking": True,
            "supports_structured_outputs": True,
            "thinking_on_by_default": True,
        },
        "claude-opus-4-8": {
            "supports_dynamic_filtering": True,
            "supports_fast_mode": True,
            "supports_compaction": True,
            "supports_adaptive_thinking": True,
            "supports_structured_outputs": True,
        },
        "claude-opus-4-7": {
            "supports_dynamic_filtering": True,

            "supports_compaction": True,
            "supports_adaptive_thinking": True,
            "supports_structured_outputs": True,
        },
        "claude-opus-4-6": {
            "supports_dynamic_filtering": True,

            "supports_compaction": True,
            "supports_adaptive_thinking": True,
            "supports_structured_outputs": True,
        },
        "claude-sonnet-4-6": {
            "supports_dynamic_filtering": True,
            "supports_compaction": True,
            "supports_adaptive_thinking": True,
            "supports_structured_outputs": True,
        },
    }

    _api_capabilities_cache: Dict[str, dict] = {}
    _api_capabilities_cache_ts: float = 0.0
    _API_CACHE_TTL = 86400

    _api_capabilities_cache_sig: str = ""

    REQUEST_TIMEOUT = (
        300
    )
    THINKING_BUDGET_TOKENS = 4096
    TOOL_CALL_TIMEOUT = 120

    class Valves(BaseModel):
        ANTHROPIC_API_KEY: EncryptedStr = Field(
            default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "Your API Key Here"),
            description="Anthropic API key. Defaults to the ANTHROPIC_API_KEY environment variable when set. "
            "Stored encrypted when WEBUI_SECRET_KEY is set.",
        )
        ANTHROPIC_BASE_URL: str = Field(
            default="https://api.anthropic.com",
            description="Custom base URL for the Anthropic API (e.g. a proxy, Azure, or an "
            "aws-external-anthropic 'Claude on AWS' endpoint).",
        )
        ENABLED_MODELS: str = Field(
            default="",
            description="Comma-separated model ids to expose (e.g. 'claude-opus-4-8,claude-sonnet-5'). "
            "Bypasses /v1/models auto-discovery — required for endpoints without it (Azure, some proxies). "
            "Empty = auto-discover from the API.",
        )
        ANTHROPIC_WORKSPACE_ID: str = Field(
            default="",
            description="AWS 'Claude on AWS' workspace id. When set, sent as the 'anthropic-workspace-id' "
            "header on every request. Required when ANTHROPIC_BASE_URL points at an aws-external-anthropic endpoint.",
        )
        ENABLE_FAST_MODE: bool = Field(
            default=False,
            description="Enable Fast Mode for Opus Models (Opus 5 / 4.8). Up to 2.5x faster output at higher costs",
        )
        REFUSAL_FALLBACK: Literal[
            "off",
            "default",
            "claude-opus-5",
            "claude-opus-4-8",
            "claude-sonnet-5",
            "claude-haiku-4-5",
        ] = Field(
            default="off",
            description=(
                "Retry server-side on another model when the safety classifier refuses a "
                "request, instead of returning the refusal. 'default' lets Anthropic pick the "
                "recommended model per refusal category; picking a model pins that one. "
                "Claude API only — ignored on Bedrock / Vertex / Foundry endpoints."
            ),
        )
        ENABLE_INTERLEAVED_THINKING: bool = Field(
            default=True,
            description="Claude can generate thinking blocks between tool calls instead of only at the end.",
        )
        WEB_SEARCH: bool = Field(
            default=True,
            description="Enable web search tool for Claude models. Use Anthropic Web Search Toggle Function for fine grained control",
        )
        WEB_FETCH: bool = Field(
            default=True,
            description="Allows Claude to fetch and analyze content from URLs.",
        )
        MAX_TOOL_CALLS: int = Field(
            default=15,
            ge=1,
            le=9999,
            description="Maximum number of tool execution loops allowed per request.",
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
            default="cache tools array, system prompt and messages",
            description="Cache control scope for prompts",
        )
        CACHE_TTL: Literal["5 minutes", "1 hour"] = Field(
            default="5 minutes",
            description="How long should a cache be kept? 1 hour has increased costs",
        )
        CACHE_TTL_FOR_TOOLS_AND_SYSTEM_PROMT: Literal["same as CACHE_TTL", "5 minutes", "1 hour"] = Field(
            default="same as CACHE_TTL",
            description=(
                "Separate cache lifetime for the tools array and system prompt. These "
                "rarely change between turns, so a 1 hour TTL usually pays off there even "
                "when messages stay at 5 minutes. Cache writes cost 1.25x at 5 minutes and "
                "2x at 1 hour, so 1 hour needs ~3 reads to break even instead of 2."
            ),
        )
        MEMORY_REVIEW_MODEL: Literal[
            "claude-haiku-4-5",
            "claude-sonnet-5",
            "claude-opus-4-8",
            "claude-opus-5",
            "same as chat model",
        ] = Field(
            default="claude-haiku-4-5",
            description=(
                "Model used for OpenWebUI's background memory review "
                "(ENABLE_MEMORY_BACKGROUND_REVIEW). OpenWebUI runs that review on the "
                "chat model, which means Opus prices for a bookkeeping job. The task is "
                "'read a transcript, emit a small JSON patch' — Haiku handles it. "
                "Set 'same as chat model' to keep OpenWebUI's own behaviour."
            ),
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
        ENABLE_PROGRAMMATIC_TOOL_CALLING: bool = Field(
            default=False,
            description="Claude can call tools from within code execution, more latency but more efficient on long running tasks with many tool calls.",
        )
        ENABLE_BASH_TOOL: bool = Field(
            default=False,
            description="EXPERIMENTAL: Enable Claude's native bash tool (bash_20250124) in OpenTerminal",
        )
        BASH_TOOL_TIMEOUT: int = Field(
            default=120,
            ge=5,
            le=900,
            description="Max seconds to wait for an Open Terminal bash command to finish before returning the partial output. Open Terminal's run_command is async — the pipe polls get_process_status until completion or this timeout.",
        )
        ENABLE_TEXT_EDITOR_TOOL: bool = Field(
            default=False,
            description="EXPERIMENTAL: Use Claude's native text editor tool (text_editor_20250728 / str_replace_based_edit_tool) in OpenTerminal",
        )
        TEXT_EDITOR_MAX_CHARACTERS: int = Field(
            default=10000,
            ge=1000,
            le=200000,
            description="Max characters returned by text_editor `view` command before truncation (Anthropic-side truncation via `max_characters`).",
        )
        DATA_RESIDENCY: Literal["global", "us"] = Field(
            default="global",
            description='Data residency for API requests. "us" has 1.1x the Token Cost.',
        )
        REQUEST_TIMEOUT: int = Field(
            default=300,
            ge=30,
            le=9999,
            description="Request timeout in seconds for Anthropic API calls.",
        )
        TOOL_CALL_TIMEOUT: int = Field(
            default=30,
            ge=10,
            le=9999,
            description="Timeout in seconds for individual tool call execution.",
        )
        ENABLE_CACHE_DIAGNOSTICS: bool = Field(
            default=False,
            description="Enable Cache Diagnostics. For debugging and development only"
        )
        MODEL_CACHE_TTL_MINUTES: int = Field(
            default=1440,
            ge=0,
            le=43200,
            description="How long the discovered model list and its capabilities are "
            "cached, in minutes (default 1440 = 24h). Set to 0 to re-fetch on every "
            "model list render — useful right after Anthropic ships a new model. "
            "Changing the API key, base URL, workspace or ENABLED_MODELS always "
            "refreshes immediately, regardless of this setting.",
        )

    class UserValves(BaseModel):
        ANTHROPIC_API_KEY: EncryptedStr = Field(
            default="",
            description="Overrides the admin-configured API key. "
            "Stored encrypted when WEBUI_SECRET_KEY is set.",
        )
        ENABLE_THINKING: bool = Field(
            default=False,
            description="Enable Extended Thinking",
        )
        THINKING_BUDGET_TOKENS: int = Field(
            default=8192,
            ge=1024,
            le=64000,
            description="Thinking budget tokens",
        )
        THINKING_DISPLAY: Literal["summarized", "omitted"] = Field(
            default="omitted",
            description="'summarized' returns summarized thinking, 'omitted' hides thinking in favor of faster time-to-first-text.",
        )
        EFFORT: Literal["low", "medium", "high", "xhigh", "max"] = Field(
            default="high",
            description="How much effort should be applied to answer the next requestEffort level for this user. Also controllable via OpenWebUI's reasoning_effort parameter.",
        )
        USE_PDF_NATIVE_UPLOAD: bool = Field(
            default=True,
            description="Upload PDFs as native base64 documents instead of RAG text extraction. Only applies to 'Use Full Document' mode.",
        )
        HIDE_BLOCKS: List[str] = Field(
            default=[],
            json_schema_extra={
                "input": {
                    "type": "multiselect",
                    "options": [
                        "web_search",
                        "web_fetch",
                        "tool_search",
                        "advisor",
                        "code_execution",
                        "compaction",
                    ],
                }
            },
            description=(
                "Content block types to hide from your chat. A hidden block's "
                "collapsible is not rendered at all — its progress is reported by "
                "the status line instead. The block is still replayed to the API, "
                "so hiding it does not change the model's view of the conversation."
            ),
        )

        @field_validator("HIDE_BLOCKS", mode="before")
        @classmethod
        def _coerce_hide_blocks(cls, v):
            if isinstance(v, str):
                return [part.strip() for part in v.split(",") if part.strip()]
            return v
        SHOW_TOKEN_COUNT: Literal["Off", "On", "With Cache"] = Field(
            default="Off",
            description="Show context window progress after each response. 'With Cache' also shows cache read/write tokens.",
        )
        WEB_SEARCH_MAX_USES: int = Field(
            default=5,
            ge=1,
            le=20,
            description="Maximum number of web searches",
        )
        WEB_FETCH_MAX_USES: int = Field(
            default=5,
            ge=1,
            le=20,
            description="Maximum number of web fetch requests per conversation turn",
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
        ENABLE_DYNAMIC_FILTERING: bool = Field(
            default=False,
            description="Use dynamic filtering for web search/fetch. Trades speed (~60s vs ~7s) for context efficiency.",
        )
        ENABLE_TOOL_SEARCH: bool = Field(
            default=True,
            description="Enables a tool to search for tools before use. Trades latency for token efficiency.",
        )
        TOOL_SEARCH_TYPE: Literal["regex", "bm25"] = Field(
            default="bm25",
            description="Type of tool search: 'regex' for pattern matching or 'bm25' for natural language search.",
        )
        TOOL_SEARCH_MAX_DESCRIPTION_LENGTH: int = Field(
            default=100,
            ge=10,
            le=10000,
            description="Tools with longer JSON definitions characters will be deferred.",
        )
        TOOL_SEARCH_EXCLUDE_TOOLS: List[str] = Field(
            default=["""
            web_search,web_fetch,code_execution,
            bash_code_execution,
            text_editor_code_execution,
            tool_search_tool_regex,
            tool_search_tool_bm25,

            advisor,
            mcp_toolset,

            memory,
            bash,
            str_replace_based_edit_tool,
            computer,
             add_memory, ask_user, calculate_timestamp, create_automation,
            create_calendar_event, create_tasks, delegate_task,
            delete_automation, delete_calendar_event, delete_memory,
            edit_image, execute_code, fetch_url, generate_image,
            get_current_timestamp, grep_chat_files, grep_knowledge_files,
            list_automations, list_chat_files, list_knowledge,
            list_knowledge_bases, list_memories, list_memory_paths,
            notify, query_chat_files, query_knowledge_bases,
            query_knowledge_files, read_memory_path, replace_memory_content,
            replace_note_content, search_calendar_events,
            search_channel_messages, search_channels, search_chats,
            search_knowledge_bases, search_knowledge_files, search_memories,
            search_notes, search_web, timer, toggle_automation,
            update_automation, update_calendar_event, update_memory,
            update_task, view_channel_message, view_channel_thread,
            view_chat, view_file, view_knowledge_file, view_note,
            view_skill, write_note,

            kb_exec,

            display_file, get_process_status, glob_search, grep_search,
            kill_process, list_files, list_processes, read_file,
            replace_file_content, run_command, send_process_input,
            write_file"""],
            description="Excluded Tools are always loaded. Anthropic tools and OpenWebUI-native tools (builtin + Open Terminal) are excluded by default.",
        )

        ENABLE_ADVISOR_TOOL: bool = Field(
            default=False,
            description="Enable the Advisor tool. A faster executor model consults a stronger advisor model mid-generation for strategic guidance.",
        )
        ADVISOR_MODEL: Literal["claude-opus-4-7", "claude-opus-4-8", "claude-opus-5", "claude-fable-5", "claude-mythos-5"] = Field(
            default="claude-opus-5",
            description="Advisor model ID.",
        )
        ADVISOR_MAX_USES: int = Field(
            default=0,
            ge=0,
            le=100,
            description="Max advisor calls per request (0 = unlimited).",
        )
        ADVISOR_CACHING: Literal["off", "5m", "1h"] = Field(
            default="off",
            description="Enable prompt caching for the advisor's own transcript across calls within a conversation.",
        )

        USE_FILES_API: bool = Field(
            default=False,
            description="Upload files to Anthropic Files API for code execution access. Overrides native PDF upload. Required for Anthropic API Skills to access attached files; can also be forced by the Files API Toggle or Companion Filter metadata.",
        )
        SKILLS: List[str] = Field(
            default=[],
            description="Anthropic API Skills to use (e.g., 'pptx', 'xlsx', 'docx', 'pdf' or custom skill IDs). These are not OpenWebUI Skills. Skills require Anthropic code_execution; attached files require USE_FILES_API or the Files API Toggle / Companion Filter.",
        )
        ENABLE_COMPACTION: bool = Field(
            default=False,
            description="Enable automatic context compaction. When input tokens exceed the trigger threshold, the API summarizes older conversation context to save tokens.",
        )
        COMPACTION_TRIGGER_TOKENS: int = Field(
            default=50000,
            ge=50000,
            le=1000000,
            description="Token count that triggers compaction. Must be at least 50,000.",
        )
        COMPACTION_INSTRUCTIONS: str = Field(
            default="",
            description="Custom summarization instructions for compaction. Replaces the default prompt entirely when set.",
        )
        CONTEXT_EDITING_STRATEGY: Literal[
            "none", "clear_tool_results", "clear_thinking", "clear_both"
        ] = Field(
            default="none",
            description="Context editing strategy: none (disabled), clear_tool_results, clear_thinking, or clear_both.",
        )
        CONTEXT_EDITING_THINKING_KEEP: int = Field(
            default=0,
            ge=0,
            le=9999,
            description="How many recent assistant turns with thinking blocks to preserve. 0 = keep all (maximizes cache hits — recommended). N>0 = sliding window; Anthropic server-side clears oldest thinking each turn once exceeded, which INVALIDATES the prompt cache prefix on every subsequent request. Only use N>0 if context-window pressure outweighs cache savings.",
        )
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
        TOOL_RESULT_MAX_TOKENS: int = Field(
            default=50000,
            ge=0,
            description="Backstop against runaway non-image client tool results: text tool output "
            "estimated over this many tokens (len//4) is truncated with a note. 0 disables the guard. "
            "Image blocks (converted from data:image;base64 tool output) are exempt.",
        )

    def __init__(self):
        self.type = "manifold"
        self.id = "anthropic"
        self.valves = self.Valves()
        self.logger = logger
        self._validated_skills_cache: Dict[str, Dict[str, Optional[Dict[str, Any]]]] = (
            {}
        )

        self._cache_diff_state: Dict[str, List[Tuple[str, str, str]]] = {}

        self._cache_diagnostics_state: Dict[str, str] = {}

    def _cache_control_marker(self, scope: str = "messages") -> dict:
        setting = self.valves.CACHE_TTL
        if scope == "tools_system":
            override = getattr(self.valves, "CACHE_TTL_FOR_TOOLS_AND_SYSTEM_PROMT", "same as CACHE_TTL")
            if override != "same as CACHE_TTL":
                if override == "5 minutes" and self.valves.CACHE_TTL == "1 hour":
                    logger.warning(
                        "CACHE_TTL_FOR_TOOLS_AND_SYSTEM_PROMT=5 minutes with CACHE_TTL=1 hour is not a "
                        "valid ordering (longer TTLs must come first); using 1 hour for "
                        "tools/system instead."
                    )
                else:
                    setting = override

        marker = {"type": "ephemeral"}
        if setting == "1 hour":
            marker["ttl"] = "1h"
        return marker

    @staticmethod
    def _dump_sdk_obj(obj: Any) -> Any:
        if obj is None:
            return None
        if hasattr(obj, "model_dump"):
            try:
                return obj.model_dump(exclude_none=True)
            except TypeError:
                return obj.model_dump()
        if isinstance(obj, dict):
            return {k: Pipe._dump_sdk_obj(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [Pipe._dump_sdk_obj(v) for v in obj]
        if isinstance(obj, (str, int, float, bool)):
            return obj
        return str(obj)

    @staticmethod
    def _canonicalize_block(node):
        def _walk(n):
            if isinstance(n, dict):
                items = sorted(n.items(), key=lambda kv: (kv[0] != "type", kv[0]))
                return {k: _walk(v) for k, v in items}
            if isinstance(n, list):
                return [_walk(v) for v in n]
            return n

        return _walk(node)

    @staticmethod
    def _strip_payload(payload: dict, max_str: int = 20) -> dict:
        def _clip(s):
            if isinstance(s, str) and len(s) > max_str:
                import hashlib as _hl
                _h = _hl.sha1(s.encode("utf-8", "replace")).hexdigest()[:8]
                return f"{s[:max_str]}…[{len(s)}c#{_h}]"
            return s

        def _walk(node):
            if isinstance(node, dict):
                return {k: _walk(v) for k, v in node.items()}
            if isinstance(node, list):
                return [_walk(v) for v in node]
            if isinstance(node, str):
                return _clip(node)
            return node

        stripped: dict = {}
        for k, v in payload.items():
            if k == "tools":
                import hashlib as _hl
                import json as _json
                tools = v or []

                _blobs = [
                    _json.dumps(t, sort_keys=False, separators=(",", ":"), default=str)
                    for t in tools if isinstance(t, dict)
                ]
                stripped["tools"] = {
                    "__tools_count__": len(tools),
                    "__tools_bytes__": sum(len(b) for b in _blobs),
                    "__tools_sha__": _hl.sha1("".join(_blobs).encode("utf-8", "replace")).hexdigest()[:10],
                    "names": [
                        (t.get("name") or t.get("type") or "?")
                        for t in tools if isinstance(t, dict)
                    ],
                    "per_tool": [
                        f"{len(b)}c#{_hl.sha1(b.encode('utf-8', 'replace')).hexdigest()[:8]}"
                        for b in _blobs
                    ],
                    "cache_control_idx": [
                        i for i, t in enumerate(tools)
                        if isinstance(t, dict) and "cache_control" in t
                    ],
                }
            elif k == "messages":
                stripped["messages"] = _walk(v)
            else:
                stripped[k] = v
        return stripped

    def _log_message_hash_diff(self, chat_id: Optional[str], payload: dict) -> None:
        if not chat_id:
            return
        try:
            msgs = payload.get("messages", []) or []

            def _strip_cache_control(obj):
                if isinstance(obj, dict):
                    return {
                        k: _strip_cache_control(v)
                        for k, v in obj.items()
                        if k != "cache_control"
                    }
                if isinstance(obj, list):
                    return [_strip_cache_control(v) for v in obj]
                return obj

            def _preview(canon: str, limit: int = 6000) -> str:
                if len(canon) <= limit:
                    return canon
                import hashlib
                digest = hashlib.sha1(canon.encode("utf-8", "replace")).hexdigest()[:10]
                return f"{canon[:limit]}...(truncated {len(canon)}c sha1={digest})"

            def _hash_msg(m: dict) -> tuple[str, str, str]:
                import hashlib
                stripped = _strip_cache_control(m)
                try:
                    canon_ins = json.dumps(stripped, sort_keys=False, separators=(",", ":"), ensure_ascii=False,
                                           default=lambda o: repr(o))
                except Exception:
                    canon_ins = repr(stripped)
                try:
                    canon_sorted = json.dumps(stripped, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                                              default=lambda o: repr(o))
                except Exception:
                    canon_sorted = repr(stripped)
                ins_h = hashlib.sha1(canon_ins.encode("utf-8")).hexdigest()[:10]
                sort_h = hashlib.sha1(canon_sorted.encode("utf-8")).hexdigest()[:10]
                return (ins_h, sort_h, _preview(canon_ins))

            def _summarize(m: dict) -> str:
                role = m.get("role", "?")
                content = m.get("content", "")
                if isinstance(content, str):
                    return f"{role}:text({len(content)}c)"
                if isinstance(content, list):
                    parts = []
                    for b in content:
                        if not isinstance(b, dict):
                            parts.append(type(b).__name__)
                            continue
                        bt = b.get("type", "?")
                        if bt == "text":
                            parts.append(f"text({len(b.get('text', ''))}c)")
                        elif bt == "tool_use":
                            parts.append(f"tool_use({b.get('name', '?')})")
                        elif bt == "tool_result":
                            c = b.get("content", "")
                            clen = len(c) if isinstance(c, str) else len(c) if isinstance(c, list) else 0
                            parts.append(f"tool_result({clen})")
                        else:
                            parts.append(bt)
                    return f"{role}:[{','.join(parts)}]"
                return f"{role}:?"

            hash_pairs = [_hash_msg(m) for m in msgs]
            ins_hashes = [h[0] for h in hash_pairs]
            sort_hashes = [h[1] for h in hash_pairs]
            previews = [h[2] for h in hash_pairs]
            summaries = [_summarize(m) for m in msgs]

            def _breakpoint_index(messages: list):
                for idx in range(len(messages) - 1, -1, -1):
                    content = messages[idx].get("content", [])
                    if not isinstance(content, list):
                        continue
                    for bidx in range(len(content) - 1, -1, -1):
                        block = content[bidx]
                        if isinstance(block, dict) and "cache_control" in block:
                            return (idx, bidx)
                return None

            def _prefix_hash(messages: list, bp) -> Optional[str]:
                if bp is None:
                    return None
                midx, bidx = bp
                if midx >= len(messages):
                    return None
                content = messages[midx].get("content", [])
                if not isinstance(content, list):
                    return None
                return _hash_msg({"role": messages[midx].get("role"),
                                  "content": content[: bidx + 1]})[0]

            bp = _breakpoint_index(msgs)
            bp_idx = bp[0] if bp else None
            prev_state = self._cache_diff_state.get(chat_id) or {}
            prev_pairs = prev_state.get("msgs", [])
            prev_bp_pair = prev_state.get("bp_pair")
            prev_bp = prev_state.get("bp")
            prev_bp_prefix = prev_state.get("bp_prefix")
            prev_ins = [p[0] for p in prev_pairs]
            prev_sort = [p[1] for p in prev_pairs]
            prev_previews = [p[2] if len(p) > 2 else "(previous preview unavailable)" for p in prev_pairs]

            if prev_pairs:
                overlap = min(len(prev_pairs), len(hash_pairs))

                ins_first_diff = None
                for i in range(overlap):
                    if prev_ins[i] != ins_hashes[i]:
                        ins_first_diff = i
                        break

                sort_first_diff = None
                for i in range(overlap):
                    if prev_sort[i] != sort_hashes[i]:
                        sort_first_diff = i
                        break

                first_diff = ins_first_diff if ins_first_diff is not None else sort_first_diff
                if first_diff is None or prev_bp is None:
                    harmful = False
                elif first_diff < prev_bp:

                    harmful = True
                elif first_diff > prev_bp:
                    harmful = False
                else:

                    now_prefix = _prefix_hash(msgs, prev_bp_pair)
                    harmful = (
                        prev_bp_prefix is not None
                        and now_prefix is not None
                        and now_prefix != prev_bp_prefix
                    )
                _log = logger.warning if harmful else logger.info
                scope = f"prev_bp=msg[{prev_bp}]" if prev_bp is not None else "prev_bp=none"

                if ins_first_diff is None and sort_first_diff is None:
                    logger.info(
                        f"🧊 CACHE-DIFF chat={chat_id}: prefix FULLY STABLE (ins+sort) over {overlap} msgs "
                        f"(prev={len(prev_pairs)}, now={len(hash_pairs)}, appended={len(hash_pairs) - overlap}) ✓"
                    )
                elif not harmful:
                    logger.info(
                        f"🧊 CACHE-DIFF chat={chat_id}: divergence at msg[{first_diff}] is BEHIND the cached "
                        f"prefix ({scope}) — harmless, expected for per-request context on the last message ✓"
                    )
                elif ins_first_diff is not None and sort_first_diff is None:

                    logger.warning(
                        f"🔥🔑 CACHE-DIFF chat={chat_id}: KEY-ORDER drift at msg[{ins_first_diff}] "
                        f"(content identical, but dict insertion order differs → API sees different bytes)"
                    )
                elif ins_first_diff == sort_first_diff:
                    logger.warning(
                        f"🔥 CACHE-DIFF chat={chat_id}: prefix DIVERGES at msg[{ins_first_diff}] "
                        f"(content+order both differ, overlap={overlap}, prev={len(prev_pairs)}, now={len(hash_pairs)})"
                    )
                else:
                    logger.warning(
                        f"🔥 CACHE-DIFF chat={chat_id}: ins_diff@{ins_first_diff}, sort_diff@{sort_first_diff} "
                        f"(overlap={overlap})"
                    )

                if ins_first_diff is not None and harmful:
                    lo = max(0, ins_first_diff - 1)
                    hi = min(max(len(prev_pairs), len(hash_pairs)), ins_first_diff + 3)
                    for i in range(lo, hi):
                        pi = prev_ins[i] if i < len(prev_ins) else "----------"
                        ps = prev_sort[i] if i < len(prev_sort) else "----------"
                        ni = ins_hashes[i] if i < len(ins_hashes) else "----------"
                        ns = sort_hashes[i] if i < len(sort_hashes) else "----------"
                        sm = summaries[i] if i < len(summaries) else "(absent)"
                        marker = "  " if pi == ni and ps == ns else "**"
                        logger.warning(
                            f"  {marker} msg[{i}]: ins prev={pi} now={ni} | sort prev={ps} now={ns} {sm}"
                        )

                    if ins_first_diff < len(prev_previews):
                        logger.warning(
                            f"  ** msg[{ins_first_diff}] PREV-INS-ORDER: "
                            f"{prev_previews[ins_first_diff]}"
                        )
                    if ins_first_diff < len(previews):
                        logger.warning(
                            f"  ** msg[{ins_first_diff}] NOW-INS-ORDER: "
                            f"{previews[ins_first_diff]}"
                        )

            self._cache_diff_state[chat_id] = {
                "msgs": hash_pairs,
                "bp": bp_idx,
                "bp_pair": bp,
                "bp_prefix": _prefix_hash(msgs, bp),
            }

            if len(self._cache_diff_state) > 20:

                oldest = next(iter(self._cache_diff_state))
                if oldest != chat_id:
                    self._cache_diff_state.pop(oldest, None)
        except Exception as e:
            logger.debug(f"_log_message_hash_diff failed: {e}")

    TOOL_LOOP_VOLATILE_CACHE_MIN_ITERATION = 4

    def _apply_cache_control(
        self, payload: dict, is_tool_loop: bool = False, iteration: int = 1
    ) -> None:
        cache_level = self.valves.CACHE_CONTROL
        if cache_level == "cache disabled":
            return

        for tool in payload.get("tools", []):
            tool.pop("cache_control", None)
        for block in payload.get("system", []):
            block.pop("cache_control", None)
        for msg in payload.get("messages", []):
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        block.pop("cache_control", None)

        cache_marker = self._cache_control_marker("tools_system")

        tools = payload.get("tools", [])
        if tools:

            placed = False
            for i in range(len(tools) - 1, -1, -1):
                if not tools[i].get("defer_loading", False):
                    tools[i]["cache_control"] = cache_marker
                    placed = True
                    break
            if not placed:

                tools[-1]["cache_control"] = cache_marker

        if cache_level == "cache tools array only":
            return

        system = payload.get("system", [])
        if system:

            for i in range(len(system) - 1, -1, -1):
                block = system[i]
                if block.get("type") == "text" and block.get("text", "").strip():
                    block["cache_control"] = cache_marker
                    break

        if cache_level == "cache tools array and system prompt":
            return

        messages = payload.get("messages", [])
        if not messages:
            return

        if is_tool_loop:

            volatile_msg, volatile_at = None, None
            for msg in reversed(messages):
                idx = self._first_volatile_block_index(msg)
                if idx is not None:
                    volatile_msg, volatile_at = msg, idx
                    break

            if volatile_msg is None:

                place_in_turn = True
            else:

                if volatile_at > 0:
                    self._place_cache_on_last_cacheable_block(
                        volatile_msg.get("content", [])[:volatile_at]
                    )

                place_in_turn = (
                    iteration >= self.TOOL_LOOP_VOLATILE_CACHE_MIN_ITERATION
                    and self._count_message_breakpoints(messages) < 2
                )

            if not place_in_turn:
                pass
            elif self.valves.ENABLE_PROGRAMMATIC_TOOL_CALLING:

                for msg in reversed(messages):
                    if msg.get("role") == "assistant":
                        self._place_cache_on_last_cacheable_block(msg.get("content", []))
                        break
            else:

                for msg in reversed(messages):
                    if msg.get("role") == "user":
                        content = msg.get("content", [])
                        if content:

                            content[-1]["cache_control"] = self._cache_control_marker()
                        break
        else:

            self._cache_last_stable_message(messages)

    def _place_cache_on_last_cacheable_block(self, content_blocks: list) -> None:
        if not content_blocks:
            return
        for i in range(len(content_blocks) - 1, -1, -1):
            block = content_blocks[i]
            if isinstance(block, dict):
                btype = block.get("type")
                if btype in ("thinking", "redacted_thinking"):
                    continue

                if btype == "tool_use" and block.get("caller"):
                    continue
                block["cache_control"] = self._cache_control_marker()
                return

    @staticmethod
    def _message_carries_volatile_context(msg: dict) -> bool:
        return Pipe._first_volatile_block_index(msg) is not None

    @staticmethod
    def _count_message_breakpoints(messages: list) -> int:
        total = 0
        for msg in messages:
            content = msg.get("content", [])
            if not isinstance(content, list):
                continue
            total += sum(
                1 for b in content if isinstance(b, dict) and "cache_control" in b
            )
        return total

    @staticmethod
    def _first_volatile_block_index(msg: dict) -> Optional[int]:
        content = msg.get("content", [])
        if not isinstance(content, list):
            return None
        for i, block in enumerate(content):
            if not isinstance(block, dict) or block.get("type") != "text":
                continue
            text = block.get("text", "")
            if (
                "<context>" in text
                or ("### Task:" in text and "<source" in text)
                or MEMORY_CONTEXT_APPENDIX_HEADER in text
            ):
                return i
        return None

    def _cache_last_stable_message(self, messages: list) -> None:
        if not messages:
            return

        last = messages[-1]
        volatile_at = self._first_volatile_block_index(last)

        if volatile_at is None:
            self._place_cache_on_last_cacheable_block(last.get("content", []))
            return

        if volatile_at > 0:

            content = last.get("content", [])
            self._place_cache_on_last_cacheable_block(content[:volatile_at])
            return

        if len(messages) < 2:

            return

        self._place_cache_on_last_cacheable_block(messages[-2].get("content", []))

    def _convert_messages_to_claude_format(
        self, raw_messages
    ) -> tuple[list[dict], list[dict], list[str]]:
        processed_messages: list[Dict[str, Any]] = []
        extracted_memories = None
        previous_marker_metadata: list[str] = []
        system_messages = []
        if raw_messages is None or len(raw_messages) == 0:
            return system_messages, processed_messages, previous_marker_metadata

        for i, msg in enumerate(raw_messages):
            role = msg.get("role")
            raw_content = msg.get("content")

            if role == "tool":
                tool_use_id = msg.get("tool_call_id", "")
                content_str = (
                    raw_content
                    if isinstance(raw_content, str)
                    else (raw_content[0].get("text", "") if isinstance(raw_content, list) and raw_content else "")
                )
                tool_result_block: dict = {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": content_str,
                }

                if (
                    processed_messages
                    and processed_messages[-1].get("role") == "user"
                    and isinstance(processed_messages[-1].get("content"), list)
                    and processed_messages[-1]["content"]
                    and isinstance(processed_messages[-1]["content"][0], dict)
                    and processed_messages[-1]["content"][0].get("type") == "tool_result"
                ):
                    processed_messages[-1]["content"].append(tool_result_block)
                else:
                    processed_messages.append({"role": "user", "content": [tool_result_block]})
                logger.debug(f"Converted role=tool → tool_result block (id={tool_use_id!r})")
                continue

            if (
                role == "assistant"
                and isinstance(raw_content, str)
                and '<details type="tool_calls"' in raw_content
            ):
                parsed_msgs = self._parse_assistant_tool_calls_string(raw_content)
                if parsed_msgs:
                    for pmsg in parsed_msgs:
                        if pmsg["role"] == "assistant":
                            extracted_metadata = self._extract_metadata_marker_from_message(pmsg)
                            if extracted_metadata:
                                previous_marker_metadata.extend(extracted_metadata)
                        processed_messages.append(pmsg)
                    continue

            claude_message = self._convert_content_to_claude_format(raw_content, role=role)
            if not claude_message:
                continue
            if role == "system":
                for block in claude_message:
                    text = block["text"]

                    cleaned_text, extracted_memories = (
                        self._extract_and_remove_memories(text)
                    )

                    if extracted_memories:
                        logger.debug(
                            f"✓ Extracted User Context: {extracted_memories[:100]}..."
                        )
                        logger.debug(
                            f"✓ System prompt after removal (last 200 chars): ...{cleaned_text[-200:]}"
                        )

                    block["text"] = cleaned_text

                    if block["text"].strip():
                        system_messages.append(block)
            else:

                wrapped_msg = {"role": role, "content": claude_message}
                extracted_metadata = self._extract_metadata_marker_from_message(
                    wrapped_msg
                )
                if extracted_metadata:
                    previous_marker_metadata.extend(extracted_metadata)

                processed_messages.append(wrapped_msg)

                if i == len(raw_messages) - 1 and role == "user":

                    self._split_rag_into_trailing_block(processed_messages[-1])

                    if extracted_memories:
                        processed_messages[-1]["content"].append(
                            {
                                "type": "text",
                                "text": f"{MEMORY_CONTEXT_APPENDIX_HEADER}{extracted_memories}",
                            }
                        )

        last_compaction_idx = -1
        for idx, msg in enumerate(processed_messages):
            if msg.get("role") == "assistant":
                for block in msg.get("content", []):
                    if isinstance(block, dict) and block.get("type") == "compaction":
                        last_compaction_idx = idx
                        break
        if last_compaction_idx > 0:
            dropped = len(processed_messages[:last_compaction_idx])
            processed_messages = processed_messages[last_compaction_idx:]
            logger.info(
                f"Compaction trim: dropped {dropped} messages before compaction boundary"
            )

        return system_messages, processed_messages, previous_marker_metadata

    def _convert_content_to_claude_format(
        self, content: Union[str, List[dict], None], role: str = "user"
    ) -> List[dict]:
        if content is None:
            return []

        if isinstance(content, str):

            if role == "assistant":
                content = PATTERN_TOOL_CALLS_DETAILS.sub("", content)
                content = PATTERN_CODE_INTERPRETER_DETAILS.sub("", content)
                content = PATTERN_CACHE_TRACE_DETAILS.sub("", content)

                all_matches: list[tuple[int, str, re.Match]] = []
                for m in PATTERN_REASONING_BLOCK.finditer(content):
                    all_matches.append((m.start(), "reasoning", m))
                for m in PATTERN_SERVER_TOOL_USE_BLOCK.finditer(content):
                    all_matches.append((m.start(), "server_tool_use", m))
                for m in PATTERN_SERVER_TOOL_RESULT_BLOCK.finditer(content):
                    all_matches.append((m.start(), "server_tool_result", m))
                for m in PATTERN_COMPACTION_DETAILS.finditer(content):
                    all_matches.append((m.start(), "compaction", m))
                for m in PATTERN_HIDDEN_BLOCK.finditer(content):
                    all_matches.append((m.start(), "hidden", m))

                if all_matches:
                    all_matches.sort(key=lambda t: t[0])
                    blocks: list[dict] = []
                    last_end = 0
                    for _, kind, match in all_matches:
                        text_before = content[last_end:match.start()]
                        if text_before.strip():
                            blocks.append({"type": "text", "text": text_before})
                        if kind == "reasoning":
                            attrs_str = match.group(1)
                            sig_match = re.search(
                                r'data-signature="([^"]*)"', attrs_str
                            )
                            if sig_match:
                                signature = html.unescape(sig_match.group(1))
                                body = match.group(2)
                                thinking_text = html.unescape(
                                    PATTERN_REASONING_QUOTED_LINE.sub("", body)
                                ).strip()
                                blocks.append({
                                    "type": "thinking",
                                    "thinking": thinking_text,
                                    "signature": signature,
                                })

                        elif kind == "server_tool_use":
                            attrs_str = match.group(1)
                            attrs = dict(PATTERN_DATA_ATTR.findall(attrs_str))
                            payload_b64 = attrs.get("payload-b64", "")
                            decoded = self._decode_block_payload(payload_b64) if payload_b64 else None
                            if isinstance(decoded, dict) and decoded.get("type") == "server_tool_use":
                                blocks.append(decoded)

                                result_b64 = attrs.get("result-payload-b64", "")
                                if result_b64:
                                    result_decoded = self._decode_block_payload(result_b64)
                                    if (
                                        isinstance(result_decoded, dict)
                                        and result_decoded.get("type", "").endswith("_tool_result")
                                    ):
                                        blocks.append(result_decoded)

                        elif kind == "server_tool_result":
                            attrs_str = match.group(1)
                            attrs = dict(PATTERN_DATA_ATTR.findall(attrs_str))
                            payload_b64 = attrs.get("payload-b64", "")
                            decoded = self._decode_block_payload(payload_b64) if payload_b64 else None
                            if isinstance(decoded, dict) and decoded.get("type", "").endswith("_tool_result"):
                                blocks.append(decoded)

                        elif kind == "hidden":

                            decoded = self._decode_block_payload(match.group(1))
                            if isinstance(decoded, list):
                                blocks.extend(
                                    b for b in decoded if isinstance(b, dict) and b.get("type")
                                )

                        elif kind == "compaction":
                            blocks.append({
                                "type": "compaction",
                                "content": match.group(1).strip(),
                            })
                        last_end = match.end()
                    after = content[last_end:]
                    if after.strip():
                        blocks.append({"type": "text", "text": after})
                    return blocks

            if content.strip():
                return [{"type": "text", "text": content}]
            else:
                return []

        processed_content = []
        for item in content:
            if item.get("type") == "text":
                text_content = item.get("text", "")

                if text_content.strip():
                    processed_content.append({"type": "text", "text": text_content})

            elif item.get("type") == "image_url":
                image_url = item.get("image_url", {}).get("url", "")

                if image_url.startswith("data:image"):

                    try:
                        header, encoded = image_url.split(",", 1)
                        mime_type = header.split(":")[1].split(";")[0]

                        try:
                            raw_bytes = base64.b64decode(encoded)
                        except Exception as decode_ex:
                            logger.debug(f" Image base64 decode failed: {decode_ex}")
                            processed_content.append(
                                {
                                    "type": "text",
                                    "text": "[Image data could not be decoded - invalid base64 format]",
                                }
                            )
                            continue

                        mime_type, encoded, image_error = self._resolve_image_for_anthropic(
                            mime_type, encoded, raw_bytes
                        )
                        if image_error:
                            processed_content.append({"type": "text", "text": image_error})
                            continue

                        MAX_IMAGE_SIZE = 25 * 1024 * 1024
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
                converted_calls = self._process_tool_calls(item)
                processed_content.extend(converted_calls)

            elif item.get("type") == "tool_results":
                converted_results = self._process_tool_results(item)
                processed_content.extend(converted_results)

            else:
                logger.debug(
                    f" Unknown content type: {item.get('type')}, converting to text"
                )
                processed_content.append(
                    {
                        "type": "text",
                        "text": f"[Unsupported content type: {item.get('type')}]",
                    }
                )

        return processed_content

    def _process_tool_calls(self, tool_calls_item):
        claude_tool_uses = []
        if "tool_calls" in tool_calls_item:
            for tool_call in tool_calls_item["tool_calls"]:
                if tool_call.get("type") == "function" and "function" in tool_call:
                    function_def = tool_call["function"]
                    claude_tool_uses.append({
                        "type": "tool_use",
                        "id": tool_call.get("id", ""),
                        "name": function_def.get("name", ""),
                        "input": function_def.get("arguments", {}),
                    })
        return claude_tool_uses

    def _process_tool_results(self, tool_results_item):
        claude_tool_results = []
        if "results" in tool_results_item:
            for result_item in tool_results_item["results"]:
                if "call" in result_item and "result" in result_item:
                    tool_call = result_item["call"]
                    tool_use_id = tool_call.get("id", "")
                    if tool_use_id:
                        claude_tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": self._convert_tool_result_content(str(result_item["result"])),
                        })
        return claude_tool_results

    ANTHROPIC_IMAGE_TYPES = ("image/jpeg", "image/png", "image/gif", "image/webp")

    _HEIF_BRANDS = frozenset({
        b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"hevm", b"hevs",
        b"mif1", b"msf1",
    })
    _AVIF_BRANDS = frozenset({b"avif", b"avis"})

    @classmethod
    def _sniff_image_media_type(cls, raw: bytes) -> Optional[str]:
        if raw.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if raw.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if raw[:6] in (b"GIF87a", b"GIF89a"):
            return "image/gif"
        if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
            return "image/webp"

        if raw[4:8] == b"ftyp":
            brand = raw[8:12]
            if brand in cls._AVIF_BRANDS:
                return "image/avif"
            if brand in cls._HEIF_BRANDS:
                return "image/heic"
        return None

    @staticmethod
    def _transcode_image_to_jpeg(raw: bytes, media_type: str) -> Optional[bytes]:
        try:
            import io

            from PIL import Image

            if media_type == "image/heic":
                try:
                    import pillow_heif

                    pillow_heif.register_heif_opener()
                except ImportError:
                    logger.warning(
                        "HEIC image received but pillow-heif is not installed; "
                        "re-import the pipe so OpenWebUI installs its requirements"
                    )
                    return None

            img = Image.open(io.BytesIO(raw))

            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=90, optimize=True)
            return buf.getvalue()
        except Exception as e:
            logger.warning(f"Image transcode to JPEG failed ({media_type}): {e}")
            return None

    @classmethod
    def _resolve_image_for_anthropic(
        cls, declared_type: str, encoded: str, raw: bytes
    ) -> tuple[str, str, Optional[str]]:
        sniffed = cls._sniff_image_media_type(raw)

        effective = sniffed or declared_type
        if effective in cls.ANTHROPIC_IMAGE_TYPES:
            if sniffed and sniffed != declared_type:
                logger.debug(
                    f"Image declared as {declared_type} is actually {sniffed}; "
                    f"correcting media_type"
                )
            return effective, encoded, None

        if effective in ("image/heic", "image/avif"):
            jpeg = cls._transcode_image_to_jpeg(raw, effective)
            if jpeg is not None:
                logger.debug(
                    f"Transcoded {effective} -> image/jpeg "
                    f"({len(raw)} -> {len(jpeg)} bytes)"
                )
                return "image/jpeg", base64.b64encode(jpeg).decode("ascii"), None
            label = "HEIC/HEIF" if effective == "image/heic" else "AVIF"
            return effective, encoded, (
                f"[{label} image could not be converted on the server. "
                f"Anthropic accepts JPEG, PNG, GIF and WebP.]"
            )

        logger.debug(f" Unsupported image mime type: {effective}")
        return effective, encoded, (
            f"[Image type {effective} not supported. "
            f"Supported formats: JPEG, PNG, GIF, WebP]"
        )

    @staticmethod
    def _split_rag_into_trailing_block(msg: dict) -> bool:
        content = msg.get("content")
        if not isinstance(content, list):
            return False

        extracted: list[str] = []
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "text":
                continue
            text = block.get("text", "")
            match = PATTERN_RAG_MESSAGE.search(text)
            if not match:
                continue
            extracted.append(match.group(0))

            block["text"] = (text[: match.start()] + text[match.end():]).strip()

        if not extracted:
            return False

        msg["content"] = [
            b for b in content
            if not (isinstance(b, dict) and b.get("type") == "text" and not b.get("text", "").strip())
        ]
        msg["content"].append({"type": "text", "text": "\n\n".join(extracted)})
        logger.debug(
            f"📋 RAG: moved {len(extracted)} block(s) into a trailing content block"
        )
        return True

    def _parse_assistant_tool_calls_string(self, content: str) -> list[dict]:
        segments: list[tuple[str, str]] = []
        last_end = 0
        for m in PATTERN_TOOL_CALLS_BLOCK.finditer(content):
            segments.append(("text", content[last_end:m.start()]))
            segments.append(("tool_call", m.group(1)))
            last_end = m.end()
        segments.append(("text", content[last_end:]))

        messages: list[dict] = []
        current_assistant: list[dict] = []
        pending_results: list[dict] = []

        def flush() -> None:
            if current_assistant:
                messages.append({"role": "assistant", "content": list(current_assistant)})
                current_assistant.clear()
            if pending_results:
                messages.append({"role": "user", "content": list(pending_results)})
                pending_results.clear()

        for kind, data in segments:
            if kind == "text":

                if not data.strip():
                    continue

                blocks = self._convert_content_to_claude_format(data, role="assistant")
                if not blocks:
                    continue

                if pending_results and any(
                    isinstance(b, dict) and b.get("type") == "text" for b in blocks
                ):
                    flush()
                current_assistant.extend(blocks)
            else:
                attrs = dict(PATTERN_TOOL_CALLS_ATTRS.findall(data))
                tc_id = html.unescape(attrs.get("id", "") or "")
                tc_name = html.unescape(attrs.get("name", "") or "")
                if not tc_id or not tc_name:
                    logger.warning(
                        "Skipping malformed <details type='tool_calls'> "
                        "block (missing id/name) during history reconstruction"
                    )
                    continue
                tc_args_raw = html.unescape(attrs.get("arguments", "") or "")
                tc_result_raw = html.unescape(attrs.get("result", "") or "")
                tc_done = (attrs.get("done", "true") or "true") == "true"
                tc_error = (attrs.get("error", "false") or "false") == "true"
                try:
                    tc_input = json.loads(tc_args_raw) if tc_args_raw else {}
                    if not isinstance(tc_input, dict):
                        tc_input = {}
                except (json.JSONDecodeError, ValueError):
                    logger.warning(
                        f"Failed to parse tool_use arguments for "
                        f"{tc_name!r}: {tc_args_raw[:120]!r}"
                    )
                    tc_input = {}
                current_assistant.append({
                    "type": "tool_use",
                    "id": tc_id,
                    "name": tc_name,
                    "input": tc_input,
                })
                if tc_done:

                    result_content = (
                        self._convert_tool_result_content(tc_result_raw)
                        if tc_result_raw
                        else "(no result)"
                    )
                    result_block: dict = {
                        "type": "tool_result",
                        "tool_use_id": tc_id,
                        "content": result_content,
                    }
                    if tc_error:
                        result_block["is_error"] = True
                else:

                    result_block = {
                        "type": "tool_result",
                        "tool_use_id": tc_id,
                        "content": "tool execution was interrupted",
                        "is_error": True,
                    }
                pending_results.append(result_block)

        flush()
        return messages

    def _convert_tool_result_content(self, result_str, user=None):
        if not isinstance(result_str, str) or not result_str:
            return result_str

        matches = list(PATTERN_TOOL_RESULT_DATA_IMAGE.finditer(result_str))
        if not matches:
            return self._truncate_tool_result_text(result_str, user)

        blocks = []
        last_end = 0
        for match in matches:
            prefix = result_str[last_end:match.start()]
            if prefix.strip():
                blocks.append({"type": "text", "text": self._truncate_tool_result_text(prefix, user)})
            blocks.append(
                self._build_tool_result_image_block(match.group("mime"), match.group("data"), user)
            )
            last_end = match.end()

        suffix = result_str[last_end:]
        if suffix.strip():
            blocks.append({"type": "text", "text": self._truncate_tool_result_text(suffix, user)})

        return blocks if blocks else result_str

    def _truncate_tool_result_text(self, text: str, user=None) -> str:
        if not text:
            return text
        max_tokens = 50000
        try:
            user_valves = user.get("valves") if isinstance(user, dict) else None
            if user_valves is not None:
                max_tokens = getattr(user_valves, "TOOL_RESULT_MAX_TOKENS", 50000)
        except Exception:
            pass
        if not max_tokens or max_tokens <= 0:
            return text
        max_chars = max_tokens * 4
        if len(text) <= max_chars:
            return text
        logger.debug(f" Tool result text truncated: {len(text)}c > {max_chars}c limit")
        return text[:max_chars] + "\n[tool result truncated: exceeded TOOL_RESULT_MAX_TOKENS]"

    def _get_tool_result_image_max_dims(self, user=None) -> tuple[int, int]:
        default_dim = 1568
        try:
            ui_settings = (user or {}).get("settings", {}).get("ui", {}) or {}
            if ui_settings.get("imageCompression"):
                size = ui_settings.get("imageCompressionSize") or {}
                width = size.get("width")
                height = size.get("height")
                width = int(width) if width not in (None, "") else None
                height = int(height) if height not in (None, "") else None
                if width and height:
                    return width, height
        except Exception as e:
            logger.debug(f" Failed to read imageCompressionSize, using default: {e}")
        return default_dim, default_dim

    def _build_tool_result_image_block(self, mime_type: str, encoded: str, user=None) -> dict:
        media_type = f"image/{mime_type}"
        MAX_IMAGE_SIZE = 25 * 1024 * 1024

        try:
            decoded_bytes = base64.b64decode(encoded)
        except Exception as decode_ex:
            logger.debug(f" Tool result image base64 decode failed: {decode_ex}")
            return {"type": "text", "text": "[Image data could not be decoded - invalid base64 format]"}

        final_bytes = decoded_bytes
        final_media_type = media_type

        if PIL_AVAILABLE:
            try:
                import io

                max_w, max_h = self._get_tool_result_image_max_dims(user)
                with PILImage.open(io.BytesIO(decoded_bytes)) as img:
                    img.load()
                    width, height = img.size
                    if width > max_w or height > max_h:
                        scale = min(max_w / width, max_h / height)
                        new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
                        if img.mode == "P":
                            img = img.convert("RGBA")
                        resized = img.resize(new_size, PILImage.LANCZOS)
                        buf = io.BytesIO()
                        resized.save(buf, format="PNG")
                        final_bytes = buf.getvalue()
                        final_media_type = "image/png"
            except Exception as resize_ex:
                logger.debug(f" Tool result image resize failed, sending original: {resize_ex}")
                final_bytes = decoded_bytes
                final_media_type = media_type

        if len(final_bytes) > MAX_IMAGE_SIZE:
            logger.debug(f" Tool result image too large: {len(final_bytes)} bytes")
            return {
                "type": "text",
                "text": f"[Image too large for Anthropic API. Max size: 25MB, received: {len(final_bytes)//1024//1024}MB]",
            }

        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": final_media_type,
                "data": base64.b64encode(final_bytes).decode("ascii"),
            },
        }

    def _convert_tools_to_claude_format(
        self,
        __tools__,
        body: Dict[str, Any],
        actual_model_name: str,
        __user__: Dict[str, Any],
        __metadata__: dict[str, Any],
    ) -> tuple[List[dict], set]:
        claude_tools = []
        tool_names_seen = set()
        api_tool_names = set()
        forced_tool_name = None
        requested_tool_choice = body.get("tool_choice")
        if isinstance(requested_tool_choice, dict):
            if requested_tool_choice.get("type") == "function":
                forced_tool_name = (requested_tool_choice.get("function") or {}).get("name")
            elif requested_tool_choice.get("type") == "tool":
                forced_tool_name = requested_tool_choice.get("name")

        anthropic_server_tool_names = {"web_search", "web_fetch"}

        has_run_command = bool(__tools__ and "run_command" in __tools__ and __tools__["run_command"].get("callable"))
        has_write_file = bool(__tools__ and "write_file" in __tools__ and __tools__["write_file"].get("callable"))
        has_replace_file = bool(__tools__ and "replace_file_content" in __tools__ and __tools__["replace_file_content"].get("callable"))

        terminal_active = bool(__metadata__ and __metadata__.get("terminal_id"))
        bash_active = self.valves.ENABLE_BASH_TOOL and has_run_command and terminal_active
        text_editor_active = (
            self.valves.ENABLE_TEXT_EDITOR_TOOL
            and has_write_file
            and has_replace_file
            and terminal_active
        )
        terminal_hidden_names: set[str] = set()
        if bash_active:
            terminal_hidden_names.add("run_command")
        if text_editor_active:
            terminal_hidden_names.update({"write_file", "replace_file_content"})
        if terminal_hidden_names:
            logger.debug(
                f"Open Terminal bridge active: hiding {sorted(terminal_hidden_names)} "
                f"(bash={bash_active}, text_editor={text_editor_active})"
            )

        body_user_tools: List[dict] = []
        user_tools: List[dict] = []

        body_tools = body.get("tools", [])
        if body_tools:
            logger.debug(f"Found {len(body_tools)} built-in tools in body.tools")
            for tool_entry in body_tools:
                if tool_entry.get("type") == "function":
                    func = tool_entry.get("function", {})
                    name = func.get("name")
                    if not name or name in tool_names_seen:
                        continue

                    if name in anthropic_server_tool_names:
                        logger.info(f"Skipping body tool '{name}' — handled by Anthropic server tool")
                        continue

                    if name in terminal_hidden_names:
                        logger.info(f"Skipping body tool '{name}' — bridged to native Claude tool")
                        continue

                    claude_tool = {
                        "name": name,
                        "description": func.get("description", f"Tool: {name}"),
                        "input_schema": func.get(
                            "parameters", {"type": "object", "properties": {}}
                        ),
                    }
                    body_user_tools.append(claude_tool)
                    tool_names_seen.add(name)

                    if not (__tools__ and name in __tools__ and __tools__[name].get("callable")):
                        api_tool_names.add(name)

            claude_tools.extend(sorted(body_user_tools, key=lambda t: t["name"]))

        if __tools__ and logger.isEnabledFor(logging.DEBUG):

            try:
                logger.debug(
                    f"Converting {len(__tools__)} user tools: {json.dumps(__tools__, indent=2)}"
                )
            except (TypeError, ValueError):

                tool_names = list(__tools__.keys())[:10]
                logger.debug(
                    f"Converting {len(__tools__)} user tools (names): {tool_names}{'...' if len(__tools__) > 10 else ''}"
                )
        elif not __tools__:
            logger.debug("No user tools to convert")

        web_search_enabled = self.valves.WEB_SEARCH or __metadata__.get(
            "web_search_enforced", False
        )
        if web_search_enabled:

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

            model_info_ws = self.get_model_info(actual_model_name)
            use_dynamic = __user__["valves"].ENABLE_DYNAMIC_FILTERING
            if use_dynamic and model_info_ws.get("supports_dynamic_filtering", False):
                web_search_type = "web_search_20260209"
            else:
                web_search_type = "web_search_20250305"
            web_search_tool = {
                "type": web_search_type,
                "name": "web_search",
            }

            if web_search_type == "web_search_20250305":
                web_search_tool["max_uses"] = __user__["valves"].WEB_SEARCH_MAX_USES

            if city or region or country or timezone:
                loc: dict = {"type": "approximate"}
                if city:
                    loc["city"] = city
                if region:
                    loc["region"] = region
                if country:
                    loc["country"] = country
                if timezone:
                    loc["timezone"] = timezone
                web_search_tool["user_location"] = loc

            claude_tools.append(web_search_tool)
            tool_names_seen.add("web_search")
            logger.debug(f"Added web_search tool: {web_search_type}")

        model_info = self.get_model_info(actual_model_name)
        if self.valves.WEB_FETCH:
            use_dynamic_fetch = __user__["valves"].ENABLE_DYNAMIC_FILTERING
            if use_dynamic_fetch and model_info.get("supports_dynamic_filtering", False):
                web_fetch_type = "web_fetch_20260209"
            else:
                web_fetch_type = "web_fetch_20250910"
            web_fetch_tool = {
                "type": web_fetch_type,
                "name": "web_fetch",
            }

            if web_fetch_type == "web_fetch_20250910":
                web_fetch_tool["max_uses"] = __user__["valves"].WEB_FETCH_MAX_USES
            claude_tools.append(web_fetch_tool)
            tool_names_seen.add("web_fetch")
            logger.debug(f"Added web_fetch tool: {web_fetch_type}")

        if __user__["valves"].ENABLE_ADVISOR_TOOL:
            executor_model = actual_model_name
            advisor_model = __user__["valves"].ADVISOR_MODEL

            valid_advisors = {
                "claude-haiku-4-5": ["claude-opus-5", "claude-opus-4-8", "claude-opus-4-7"],
                "claude-sonnet-4-6": ["claude-opus-5", "claude-opus-4-8", "claude-opus-4-7"],
                "claude-sonnet-5": ["claude-opus-5", "claude-opus-4-8"],
                "claude-opus-4-6": ["claude-opus-5", "claude-opus-4-8", "claude-opus-4-7"],
                "claude-opus-4-7": ["claude-opus-5", "claude-opus-4-8", "claude-opus-4-7"],
                "claude-opus-4-8": ["claude-opus-5", "claude-opus-4-8"],
                "claude-opus-5": ["claude-opus-5"],
                "claude-fable-5": ["claude-fable-5"],
                "claude-mythos-5": ["claude-mythos-5"],
            }
            allowed_advisors = valid_advisors.get(executor_model, ["claude-opus-5"])

            adjusted_advisor_model = advisor_model
            if advisor_model not in allowed_advisors:
                adjusted_advisor_model = allowed_advisors[0]
                logger.warning(
                    f"Advisor '{advisor_model}' invalid for executor '{executor_model}'. "
                    f"Downgrading to '{adjusted_advisor_model}'"
                )

            advisor_tool: dict = {
                "type": "advisor_20260301",
                "name": "advisor",
                "model": adjusted_advisor_model,
            }
            if __user__["valves"].ADVISOR_MAX_USES > 0:
                advisor_tool["max_uses"] = __user__["valves"].ADVISOR_MAX_USES
            if __user__["valves"].ADVISOR_CACHING != "off":
                advisor_tool["caching"] = {
                    "type": "ephemeral",
                    "ttl": __user__["valves"].ADVISOR_CACHING,
                }
            claude_tools.append(advisor_tool)
            tool_names_seen.add("advisor")
            logger.debug(
                f"Added advisor tool: model={adjusted_advisor_model} "
                f"max_uses={__user__['valves'].ADVISOR_MAX_USES or 'unlimited'} "
                f"caching={__user__['valves'].ADVISOR_CACHING}"
            )

        if bash_active:
            claude_tools.append({"type": "bash_20250124", "name": "bash"})
            tool_names_seen.add("bash")
            logger.debug("Added native bash tool (bridged to run_command)")

        if text_editor_active:
            claude_tools.append({
                "type": "text_editor_20250728",
                "name": "str_replace_based_edit_tool",
                "max_characters": self.valves.TEXT_EDITOR_MAX_CHARACTERS,
            })
            tool_names_seen.add("str_replace_based_edit_tool")
            logger.debug(
                f"Added native text_editor tool (bridged to write_file+replace_file_content, "
                f"max_characters={self.valves.TEXT_EDITOR_MAX_CHARACTERS})"
            )

        if __tools__ and len(__tools__) > 0:
            for tool_name, tool_data in __tools__.items():
                if not isinstance(tool_data, dict) or "spec" not in tool_data:
                    logger.debug(f"Skipping invalid tool: {tool_name} - missing spec")
                    continue

                spec = tool_data["spec"]

                name = spec.get("name", tool_name)

                if name in tool_names_seen:
                    continue

                if name.startswith("_"):
                    logger.debug(f"Skipping private tool: {name}")
                    continue

                if name in terminal_hidden_names:
                    logger.debug(f"Skipping bridged Open Terminal tool: {name}")
                    continue

                description = spec.get("description", f"Tool: {name}")
                parameters = spec.get("parameters", {})

                input_schema = {
                    "type": "object",
                    "properties": parameters.get("properties", {}),
                }

                if "required" in parameters:
                    input_schema["required"] = parameters["required"]

                claude_tool = {
                    "name": name,
                    "description": description,
                    "input_schema": input_schema,
                }

                user_tools.append(claude_tool)
                tool_names_seen.add(name)

            claude_tools.extend(sorted(user_tools, key=lambda t: t["name"]))

        is_programmatic_active = False
        if self.valves.ENABLE_PROGRAMMATIC_TOOL_CALLING:
            model_info_ptc = self.get_model_info(actual_model_name)
            is_programmatic_active = model_info_ptc.get("supports_programmatic_calling", False)

        _defer_active = __user__["valves"].ENABLE_TOOL_SEARCH and not is_programmatic_active

        for claude_tool in claude_tools:

            if _defer_active:

                name = claude_tool["name"]
                user_excludes = __user__["valves"].TOOL_SEARCH_EXCLUDE_TOOLS
                if (
                    name != forced_tool_name
                    and name not in user_excludes
                ):

                    tool_json = json.dumps(claude_tool)
                    tool_len = len(tool_json)
                    if len(tool_json) > __user__["valves"].TOOL_SEARCH_MAX_DESCRIPTION_LENGTH:
                        claude_tool["defer_loading"] = True
                    else:
                        logger.debug(f"Tool '{name}' will be loaded normally")

            if self.valves.ENABLE_PROGRAMMATIC_TOOL_CALLING:
                model_info = self.get_model_info(actual_model_name)
                if model_info.get("supports_programmatic_calling", False):

                    if "type" not in claude_tool:
                        claude_tool["allowed_callers"] = ["code_execution_20260120"]

            if "type" not in claude_tool:
                claude_tool["eager_input_streaming"] = True

        if any(tool.get("defer_loading", False) for tool in claude_tools):
            if __user__["valves"].TOOL_SEARCH_TYPE == "regex":
                tool_search_tool = {
                    "type": "tool_search_tool_regex_20251119",
                    "name": "tool_search_tool_regex",
                }
            else:
                tool_search_tool = {
                    "type": "tool_search_tool_bm25_20251119",
                    "name": "tool_search_tool_bm25",
                }
            claude_tools.insert(0, tool_search_tool)

        logger.debug(f"Total tools converted: {len(claude_tools)}")
        for t in claude_tools:
            flags = []
            if t.get("defer_loading"):
                flags.append("DEFERRED")
            if t.get("allowed_callers"):
                flags.append(f"callers={t['allowed_callers']}")
            if t.get("type"):
                flags.append(f"type={t['type']}")
            if t.get("eager_input_streaming"):
                flags.append("eager_stream")
            logger.info(f"  🔧 Tool: {t.get('name')} [{', '.join(flags) or 'normal'}]")

        return claude_tools, api_tool_names

    async def _get_pdf_base64_from_file_id(self, file_id: str) -> Optional[tuple[str, str]]:
        if not FILES_AVAILABLE:
            logger.warning("Files/Storage modules not available for PDF native upload")
            return None

        try:
            file = await Files.get_file_by_id(file_id)
            if not file:
                logger.warning(f"File not found: {file_id}")
                return None

            content_type = file.meta.get("content_type", "")
            filename = file.meta.get("name", file.filename)

            if content_type != "application/pdf" and not filename.lower().endswith(
                ".pdf"
            ):
                logger.debug(f"File {file_id} is not a PDF: {content_type}")
                return None

            file_path = Storage.get_file(file.path)
            file_path = Path(file_path)

            if not file_path.is_file():
                logger.warning(f"PDF file not found on disk: {file_path}")
                return None

            with open(file_path, "rb") as pdf_file:
                pdf_data = pdf_file.read()
                encoded_data = base64.b64encode(pdf_data).decode("utf-8")

            MAX_PDF_SIZE = 25 * 1024 * 1024
            if len(pdf_data) > MAX_PDF_SIZE:
                logger.warning(
                    f"PDF too large for native upload: {len(pdf_data)} bytes"
                )
                return None

            logger.debug(
                f"Successfully encoded PDF: {filename} ({len(pdf_data)} bytes)"
            )
            return (encoded_data, filename)

        except Exception as e:
            logger.error(f"Error reading PDF file {file_id}: {e}")
            return None

    @staticmethod
    def _collect_file_ids(value: Any) -> List[str]:
        ids: List[str] = []
        if isinstance(value, dict):
            for key in ("id", "file_id"):
                file_id_value = value.get(key)
                if isinstance(file_id_value, str) and file_id_value:
                    ids.append(file_id_value)
            for key in ("file", "meta", "metadata"):
                nested = value.get(key)
                if nested is not None:
                    ids.extend(Pipe._collect_file_ids(nested))
        elif isinstance(value, list):
            for item in value:
                ids.extend(Pipe._collect_file_ids(item))
        return ids

    @classmethod
    def _resolve_full_context_anchors(
        cls,
        marker_kind: str,
        accept,
        __files__: Optional[List[Dict[str, Any]]],
        previous_marker_metadata: List[str],
        processed_messages: List[Dict[str, Any]],
        raw_messages: Optional[List[Dict[str, Any]]] = None,
    ) -> tuple[Dict[str, int], Dict[str, str]]:
        prior_msg_idx: Dict[str, int] = {}
        prior_filename: Dict[str, str] = {}
        for entry in previous_marker_metadata or []:
            parts = entry.split(":", 2)
            if len(parts) < 3 or parts[1] != marker_kind:
                continue
            try:
                msg_idx = int(parts[0])
            except ValueError:
                continue
            decoded = unquote(parts[2])
            file_id_part, _, fname_part = decoded.partition(":")
            if file_id_part:
                prior_msg_idx[file_id_part] = msg_idx
                if fname_part:
                    prior_filename[file_id_part] = fname_part

        user_msg_count = sum(1 for m in processed_messages if m.get("role") == "user")
        latest_user_msg_idx = max(0, user_msg_count - 1)

        raw_file_msg_idx: Dict[str, int] = {}
        if raw_messages:
            raw_user_msg_idx = -1
            for raw_msg in raw_messages:
                if not isinstance(raw_msg, dict) or raw_msg.get("role") != "user":
                    continue
                raw_user_msg_idx += 1
                for file_id in cls._collect_file_ids(raw_msg.get("files")):
                    raw_file_msg_idx.setdefault(file_id, raw_user_msg_idx)

        anchor: Dict[str, int] = {}
        filename: Dict[str, str] = {}

        for file in __files__ or []:
            if file.get("type") != "file" or file.get("context") != "full":
                continue
            file_id = file.get("id")
            if not file_id:
                continue
            file_name = file.get("name", "")
            if not accept(file_name):
                continue
            anchor[file_id] = prior_msg_idx.get(
                file_id, raw_file_msg_idx.get(file_id, latest_user_msg_idx)
            )
            filename[file_id] = file_name

        for file_id, msg_idx in prior_msg_idx.items():
            if file_id in anchor:
                continue
            anchor[file_id] = msg_idx
            if file_id in prior_filename:
                filename[file_id] = prior_filename[file_id]

        ordered = sorted(anchor.items(), key=lambda kv: (kv[1], kv[0]))
        return (
            {fid: idx for fid, idx in ordered},
            {fid: filename[fid] for fid, _ in ordered if fid in filename},
        )

    async def _get_file_text_from_file_id(self, file_id: str) -> Optional[str]:
        if not FILES_AVAILABLE:
            return None
        try:
            file = await Files.get_file_by_id(file_id)
        except Exception as e:
            logger.warning(f"Full-context text: could not load file {file_id}: {e}")
            return None
        if not file:
            return None
        data = getattr(file, "data", None)
        content = data.get("content") if isinstance(data, dict) else None
        if isinstance(content, str) and content.strip():
            return content.strip()
        return None

    async def _get_full_context_texts(
        self,
        __files__: Optional[List[Dict[str, Any]]],
        previous_marker_metadata: List[str],
        processed_messages: List[Dict[str, Any]],
        raw_messages: Optional[List[Dict[str, Any]]] = None,
        exclude_pdfs: bool = True,
    ) -> tuple[Dict[int, List[Dict[str, Any]]], List[str], List[str]]:
        blocks_by_user_msg: Dict[int, List[Dict[str, Any]]] = {}
        markers: List[str] = []
        filenames: List[str] = []

        if not FILES_AVAILABLE:
            return blocks_by_user_msg, markers, filenames

        anchors, names = self._resolve_full_context_anchors(
            "fctx",
            lambda name: not (exclude_pdfs and name.lower().endswith(".pdf")),
            __files__,
            previous_marker_metadata,
            processed_messages,
            raw_messages,
        )

        for file_id, anchor_msg_idx in anchors.items():
            content = await self._get_file_text_from_file_id(file_id)
            if not content:
                continue
            title = names.get(file_id) or file_id
            blocks_by_user_msg.setdefault(anchor_msg_idx, []).append(
                {
                    "type": "text",
                    "text": f'<source name="{title}">\n{content}\n</source>',
                }
            )
            filenames.append(title)
            markers.append(
                self._create_metadata_marker(
                    "fctx", f"{file_id}:{title}", messagenum=anchor_msg_idx
                )
            )

        if filenames:
            logger.debug(
                f"📎 Full-context text: anchored {len(filenames)} file(s) as cacheable blocks"
            )
        return blocks_by_user_msg, markers, filenames

    async def _get_full_context_pdfs(
        self,
        __files__: Optional[List[Dict[str, Any]]],
        previous_marker_metadata: List[str],
        processed_messages: List[Dict[str, Any]],
        raw_messages: Optional[List[Dict[str, Any]]] = None,
    ) -> tuple[Dict[int, List[Dict[str, Any]]], List[str]]:
        blocks_by_user_msg: Dict[int, List[Dict[str, Any]]] = {}
        markers: List[str] = []

        if not FILES_AVAILABLE:
            return blocks_by_user_msg, markers

        pdf_anchor, pdf_filename = self._resolve_full_context_anchors(
            "pdf",
            lambda name: name.lower().endswith(".pdf"),
            __files__,
            previous_marker_metadata,
            processed_messages,
            raw_messages,
        )

        for file_id, anchor_msg_idx in pdf_anchor.items():

            result = await self._get_pdf_base64_from_file_id(file_id)
            if not result:
                continue
            encoded_data, filename = result
            title = pdf_filename.get(file_id) or filename

            blocks_by_user_msg.setdefault(anchor_msg_idx, []).append(
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": encoded_data,
                    },
                    "title": title,
                }
            )
            markers.append(
                self._create_metadata_marker(
                    "pdf", f"{file_id}:{title}", messagenum=anchor_msg_idx
                )
            )

        return blocks_by_user_msg, markers

    async def _generate_file_download_link(
        self,
        file_id: str,
        api_key: str,
        user_id: str,
    ) -> str:
        try:
            from anthropic import AsyncAnthropic
            import hashlib
            import io
            import uuid

            client = self._build_anthropic_client(api_key)

            file_meta = await client.beta.files.retrieve_metadata(file_id=file_id)
            filename = getattr(file_meta, "filename", file_id) or file_id

            response = await client.beta.files.download(file_id=file_id)
            content = await response.read()

            owui_file_id = str(uuid.uuid4())
            storage_filename = f"code_exec_{owui_file_id}_{filename}"
            _, file_path = Storage.upload_file(io.BytesIO(content), storage_filename, {})

            file_hash = hashlib.sha256(content).hexdigest()
            await Files.insert_new_file(
                user_id=user_id,
                form_data=type("FileForm", (), {
                    "model_dump": lambda self_: {
                        "id": owui_file_id,
                        "hash": file_hash,
                        "filename": filename,
                        "path": file_path,
                        "data": {},
                        "meta": {
                            "content_type": getattr(file_meta, "mime_type", "application/octet-stream"),
                            "size": len(content),
                            "source": "anthropic_code_execution",
                            "anthropic_file_id": file_id,
                        },
                    }
                })(),
            )

            base_url = os.environ.get("WEBUI_URL", "")
            download_url = f"{base_url}/api/v1/files/{owui_file_id}/content"
            return f"[📥 {filename}]({download_url})"

        except Exception as e:
            logger.error(f"Failed to download file {file_id}: {e}")
            return f"⚠️ Failed to download file {file_id}"

    async def _process_files_api_data(
        self,
        __files__: Optional[List[Dict[str, Any]]],
        __event_emitter__: Callable[[Dict[str, Any]], Awaitable[None]],
        processed_messages: List[Dict[str, Any]],
    ) -> tuple[Dict[int, List[Dict[str, Any]]], List[str]]:
        blocks_by_user_msg: Dict[int, List[Dict[str, Any]]] = {}
        processed_filenames: List[str] = []
        status_cls = globals().get("StatusEmitter")
        status = status_cls(__event_emitter__) if status_cls else None

        async def emit_status(description: str, *, done: bool = False) -> None:
            if status:
                if done:
                    await status.complete(description)
                else:
                    await status.activity(description)
                return
            await self.emit_event(
                {"type": "status", "data": {"description": description, "done": done}},
                __event_emitter__,
            )

        async def emit_notification(content: str, *, type: str = "warning") -> None:
            if status and hasattr(status, "notification"):
                await status.notification(content, type=type)
                return
            await self.emit_event(
                {"type": "notification", "data": {"type": type, "content": content}},
                __event_emitter__,
            )

        if not __files__:
            return blocks_by_user_msg, processed_filenames
        if not FILES_AVAILABLE:
            await emit_status("Files API unavailable", done=True)
            await emit_notification(
                "Anthropic Files API mode was requested, but OpenWebUI Files/Storage support is unavailable in this runtime."
            )
            return blocks_by_user_msg, processed_filenames

        import io

        user_msg_count = sum(1 for m in processed_messages if m["role"] == "user")
        current_user_msg_num = max(0, user_msg_count - 1)

        client = None
        try:
            from anthropic import AsyncAnthropic
            client = self._build_anthropic_client(self.valves.ANTHROPIC_API_KEY)
        except ImportError:
            logger.warning("Anthropic SDK not available for file upload")
            return blocks_by_user_msg, processed_filenames

        for file in __files__:

            if (
                file.get("type") != "file"
                or file.get("context") != "full"
                or file.get("collection_name")
                or file.get("docs")
            ):
                continue

            file_id_owui = file.get("id")
            file_name = file.get("name", "unknown")
            if not file_id_owui:
                continue

            content_type = file.get("content_type", "")
            if not content_type:

                file_record_check = await Files.get_file_by_id(file_id_owui)
                if file_record_check and file_record_check.meta:
                    content_type = file_record_check.meta.get("content_type", "")
            if content_type and content_type.startswith("image/"):
                logger.debug(f"Skipping image file for Files API: {file_name} ({content_type})")
                continue

            file_record = await Files.get_file_by_id(file_id_owui)
            if not file_record:
                logger.warning(f"File not found in DB: {file_id_owui}")
                continue

            meta = file_record.meta or {}
            anthropic_file_id = meta.get("anthropic_file_id")
            msg_num = meta.get("anthropic_file_msg_idx")

            if anthropic_file_id:

                if msg_num is None:
                    msg_num = current_user_msg_num
                logger.debug(f"♻️ Reusing cached file {file_name} → {anthropic_file_id} (msg {msg_num})")
            else:

                try:
                    file_path = Storage.get_file(file_record.path)
                    if not file_path or not Path(file_path).is_file():
                        logger.warning(f"File not on disk: {file_id_owui}")
                        continue

                    with open(file_path, "rb") as f:
                        file_content = f.read()

                    await emit_status(f"☁️ Uploading {file_name}...")

                    upload_result = await client.beta.files.upload(
                        file=(file_name, io.BytesIO(file_content)),
                    )
                    anthropic_file_id = upload_result.id
                    msg_num = current_user_msg_num

                    await Files.update_file_metadata_by_id(file_id_owui, {
                        "anthropic_file_id": anthropic_file_id,
                        "anthropic_file_msg_idx": msg_num,
                    })

                    logger.info(f"☁️ Uploaded {file_name} → {anthropic_file_id} (msg {msg_num})")

                    await emit_status(f"☁️ Uploaded {file_name}", done=True)
                except Exception as e:
                    logger.error(f"Failed to upload {file_name}: {e}")
                    await emit_notification(f"Failed to upload {file_name}: {str(e)[:100]}")
                    continue

            if msg_num not in blocks_by_user_msg:
                blocks_by_user_msg[msg_num] = []
            blocks_by_user_msg[msg_num].append({
                "type": "container_upload",
                "file_id": anthropic_file_id,
            })
            processed_filenames.append(file_name)

        return blocks_by_user_msg, processed_filenames

    async def _validate_and_get_skills(
        self,
        skill_names: List[str],
        api_key: str,
        __event_emitter__: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> List[Dict[str, Any]]:
        if not skill_names:
            return []

        status = None
        if __event_emitter__:
            status_cls = globals().get("StatusEmitter")
            status = status_cls(__event_emitter__) if status_cls else None

        async def emit_status(description: str, *, done: bool = False, hidden: bool | None = None) -> None:
            if not __event_emitter__:
                return
            if status:
                await status.emit(description, done=done, hidden=hidden)
                return
            data: dict[str, Any] = {"description": description, "done": done}
            if hidden is not None:
                data["hidden"] = hidden
            await self.emit_event({"type": "status", "data": data}, __event_emitter__)

        async def emit_notification(content: str, *, type: str = "warning") -> None:
            if not __event_emitter__:
                return
            if status and hasattr(status, "notification"):
                await status.notification(content, type=type)
                return
            await self.emit_event(
                {"type": "notification", "data": {"type": type, "content": content}},
                __event_emitter__,
            )

        if api_key not in self._validated_skills_cache:
            self._validated_skills_cache[api_key] = {}

        cache = self._validated_skills_cache[api_key]

        skills_to_validate = [s for s in skill_names if s not in cache]

        if skills_to_validate:
            logger.debug(
                f"🔧 Validating {len(skills_to_validate)} skills via API: {skills_to_validate}"
            )

            await emit_status("🔧 Validating Skills...", hidden=True)

            try:
                from anthropic import AsyncAnthropic

                client = self._build_anthropic_client(api_key)

                available_skills = {}

                def index_skill(info: dict[str, Any]) -> None:
                    skill_id = info.get("id", "")
                    display_title = info.get("display_title", "") or skill_id
                    for key in (skill_id, skill_id.lower(), display_title.lower()):
                        if key:
                            available_skills[key] = info
                    haystack = f"{skill_id} {display_title}".lower()
                    if "xlsx" in haystack or "excel" in haystack or "spreadsheet" in haystack:
                        available_skills.setdefault("xlsx", info)
                    if "pptx" in haystack or "powerpoint" in haystack or "presentation" in haystack:
                        available_skills.setdefault("pptx", info)
                    if "docx" in haystack or "word" in haystack or "document" in haystack:
                        available_skills.setdefault("docx", info)
                    if "pdf" in haystack:
                        available_skills.setdefault("pdf", info)

                try:
                    anthropic_skills = await client.beta.skills.list(
                        source="anthropic", betas=["skills-2025-10-02"]
                    )
                    for skill in anthropic_skills.data:

                        info = {
                            "id": skill.id,
                            "type": "anthropic",
                            "source": "anthropic",
                            "display_title": getattr(skill, "display_title", skill.id),
                            "latest_version": getattr(
                                skill, "latest_version", "latest"
                            ),
                        }
                        index_skill(info)
                except Exception as e:
                    logger.warning(f"Failed to fetch Anthropic skills: {e}")

                try:
                    custom_skills = await client.beta.skills.list(
                        source="custom", betas=["skills-2025-10-02"]
                    )
                    for skill in custom_skills.data:
                        info = {
                            "id": skill.id,
                            "type": "custom",
                            "source": "custom",
                            "display_title": getattr(skill, "display_title", skill.id),
                            "latest_version": getattr(
                                skill, "latest_version", "latest"
                            ),
                        }
                        index_skill(info)
                except Exception as e:
                    logger.warning(f"Failed to fetch custom skills: {e}")

                logger.debug(f"🔧 Found {len(available_skills)} available skills")

                for skill_name in skills_to_validate:
                    skill_lower = skill_name.lower().strip()

                    if skill_name in available_skills:
                        cache[skill_name] = available_skills[skill_name]
                        logger.debug(f"✓ Validated skill '{skill_name}' (exact match)")

                    elif skill_lower in available_skills:
                        cache[skill_name] = available_skills[skill_lower]
                        logger.debug(
                            f"✓ Validated skill '{skill_name}' (case-insensitive match)"
                        )
                    else:

                        cache[skill_name] = None
                        logger.warning(
                            f"✗ Invalid skill '{skill_name}' - not found in available skills"
                        )

            except Exception as e:
                logger.error(f"Failed to validate skills: {e}")

                for skill_name in skills_to_validate:
                    cache[skill_name] = None

        validated_skills = []
        invalid_skills = []

        for skill_name in skill_names:
            skill_info = cache.get(skill_name)
            if skill_info:
                requested_short_id = skill_name.lower().strip()
                skill_id = (
                    requested_short_id
                    if skill_info.get("type") == "anthropic"
                    and requested_short_id in {"pptx", "xlsx", "docx", "pdf"}
                    else skill_info["id"]
                )
                validated_skills.append(
                    {
                        "type": skill_info["type"],
                        "skill_id": skill_id,
                        "version": "latest",
                    }
                )
            else:
                invalid_skills.append(skill_name)

        if invalid_skills:
            await emit_notification(
                f"⚠️ Invalid Anthropic API Skills ignored: {', '.join(invalid_skills)}. "
                "These are Anthropic API Skills, not OpenWebUI Skills."
            )

        logger.debug(f"🔧 Returning {len(validated_skills)} validated skills")
        return validated_skills

    def _remove_sources_from_rag(
        self, rag_content: str, filenames_to_remove: List[str]
    ) -> str:
        if not filenames_to_remove:
            return rag_content

        modified = rag_content
        for filename in filenames_to_remove:

            pattern = re.compile(
                rf'<source[^>]*name="{re.escape(filename)}"[^>]*>.*?</source>\s*',
                re.DOTALL,
            )
            modified = pattern.sub("", modified)

        if PATTERN_EMPTY_CONTEXT.search(modified) or not PATTERN_SOURCE_TAGS.search(
            modified
        ):

            logger.debug(f"📋 RAG: All sources removed, clearing entire RAG message")
            return ""

        logger.debug(
            f"📋 RAG: Removed {len(filenames_to_remove)} source(s) from RAG content"
        )
        return modified

    def _remove_specific_sources_from_rag_message(
        self,
        processed_messages: List[Dict[str, Any]],
        filenames_to_remove: List[str],
    ) -> None:
        if not filenames_to_remove:
            return

        for i in range(len(processed_messages) - 1, -1, -1):
            msg = processed_messages[i]
            if msg.get("role") != "user":
                continue

            content = msg.get("content")
            if not isinstance(content, list):
                continue

            modified = False
            new_content: List[Dict[str, Any]] = []

            for block in content:
                if block.get("type") != "text":
                    new_content.append(block)
                    continue

                text = block.get("text", "")
                match = PATTERN_RAG_MESSAGE.search(text)

                if not match:
                    new_content.append(block)
                    continue

                rag_content = match.group(0)
                modified_rag = self._remove_sources_from_rag(
                    rag_content, filenames_to_remove
                )

                start, end = match.span()
                if not modified_rag:

                    new_text = text[:start] + text[end:]
                    logger.debug(
                        f"📋 RAG: Removed entire RAG block (all sources matched)"
                    )
                else:

                    new_text = text[:start] + modified_rag + text[end:]
                    logger.debug(
                        f"📋 RAG: Kept partial RAG content (some sources remain)"
                    )

                new_text = new_text.strip()
                if new_text:
                    new_block = dict(block)
                    new_block["text"] = new_text
                    new_content.append(new_block)

                modified = True

            if modified:
                processed_messages[i]["content"] = new_content
                return

    def _extract_and_remove_memories(self, text: str) -> tuple[str, Optional[str]]:

        if "<memory_context>" not in text and "User Context:" not in text:
            return text.strip(), None

        extracted_parts: list[str] = []

        def _take_memory_context(match) -> str:
            content = match.group(1).strip()
            if content:
                extracted_parts.append(content)
            return ""

        cleaned_text = PATTERN_MEMORY_CONTEXT.sub(_take_memory_context, text)

        match = PATTERN_USER_CONTEXT.search(cleaned_text)
        if match:
            context_content = match.group(1).strip()
            if context_content:
                extracted_parts.append(f"User Context:\n{context_content}")

            cleaned_text = cleaned_text[: match.start()]

        extracted_context = "\n\n".join(extracted_parts) if extracted_parts else None
        return cleaned_text.strip(), extracted_context

    def _create_metadata_marker(self, id: str, value: str, messagenum: int = 0) -> str:

        encoded_value = quote(value, safe="")
        return f" [](anthropic:{messagenum}:{id}:{encoded_value}) "

    def _extract_metadata_marker_from_message(self, message) -> List[str]:
        metadata: List[str] = []
        if not isinstance(message, dict):
            return metadata
        if message.get("role") == "assistant":
            text = None
            content = message.get("content")
            if isinstance(content, list):

                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        block_text = block.get("text", "")
                        matches = self.METADATA_PATTERN.findall(block_text)
                        for match in matches:
                            metadata.append(match)

                        cleaned_text = self.METADATA_PATTERN.sub("", block_text)
                        block["text"] = cleaned_text
            elif isinstance(content, str):
                matches = self.METADATA_PATTERN.findall(content)
                for match in matches:
                    metadata.append(match)

                message["content"] = self.METADATA_PATTERN.sub("", content)
        return metadata

    @staticmethod
    def _encode_block_payload(payload: Any) -> str:
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return base64.b64encode(raw.encode("utf-8")).decode("ascii")

    @staticmethod
    def _decode_block_payload(payload_b64: str) -> Optional[Any]:
        try:
            return json.loads(base64.b64decode(payload_b64).decode("utf-8"))
        except Exception:
            return None

    @staticmethod
    def _block_visibility_key(name: str) -> str:
        key = name[: -len("_tool_result")] if name.endswith("_tool_result") else name
        if key.startswith("tool_search"):
            return "tool_search"

        if key.endswith("code_execution"):
            return "code_execution"
        return key

    def _is_block_hidden(self, name: str) -> bool:
        if SLIM_OUTPUT.get():
            return True
        hidden = HIDDEN_BLOCKS.get()
        if not hidden:
            return False
        return self._block_visibility_key(name) in hidden

    @staticmethod
    def _parse_hidden_blocks(raw: Any) -> frozenset:
        if isinstance(raw, str):
            raw = raw.split(",")
        if not raw:
            return frozenset()
        return frozenset(str(part).strip() for part in raw if str(part).strip())

    def _format_hidden_block(self, payloads: list, label_id: str = "") -> str:
        if SLIM_OUTPUT.get():

            return ""
        suffix = f"-{re.sub(r'[^A-Za-z0-9_]', '', label_id)}" if label_id else ""
        return f"\n\n[anthropic-hidden{suffix}]: #{self._encode_block_payload(payloads)}\n"

    @staticmethod
    def _stringify_terminal_result(result: Any) -> str:
        if isinstance(result, tuple) and result:
            result = result[0]
        if isinstance(result, str):
            return result
        try:
            return json.dumps(result, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            return str(result)

    async def _emit_terminal_event(
        self,
        emitter: Optional[Callable],
        event_type: str,
        path: str = "",
    ) -> None:
        if not emitter:
            return
        data = {"path": path} if path else {}
        try:
            await emitter({"type": f"terminal:{event_type}", "data": data})
        except Exception:
            logger.debug("terminal:%s event emit failed", event_type, exc_info=True)

    async def _dispatch_bash_tool(
        self,
        tool_input: dict,
        __tools__: dict,
        emitter: Optional[Callable] = None,
    ) -> str:
        try:
            run_cmd = __tools__.get("run_command", {}).get("callable")
            if not run_cmd:
                return "Error: run_command callable is not available."
            if tool_input.get("restart"):
                await run_cmd(command="cd ~")
                await self._emit_terminal_event(emitter, "run_command")
                return "Bash session reset (working dir → $HOME)."
            command = tool_input.get("command", "")
            if not command:
                return "Error: missing required parameter `command`."

            result = await self._run_terminal_command(__tools__, command)
            await self._emit_terminal_event(emitter, "run_command")
            return result
        except Exception as e:
            logger.exception("bash dispatch failed")
            return f"Error executing bash command: {e}"

    async def _run_terminal_command(self, __tools__: dict, command: str) -> str:
        run_cmd = __tools__.get("run_command", {}).get("callable")
        if not run_cmd:
            return "Error: run_command callable is not available."
        timeout_s = max(5, int(self.valves.BASH_TOOL_TIMEOUT))
        deadline = time.monotonic() + timeout_s
        try:
            raw = await run_cmd(command=command, wait=min(timeout_s, 300))
        except TypeError:
            raw = await run_cmd(command=command)
        data = self._parse_terminal_payload(raw)

        if not isinstance(data, dict) or "id" not in data:
            return self._stringify_terminal_result(raw)
        status = data.get("status")
        if status and status != "running":
            return self._format_bash_process_result(data)

        process_id = data["id"]
        poll_cb = __tools__.get("get_process_status", {}).get("callable")
        if not poll_cb:

            return self._stringify_terminal_result(raw)

        delay = 0.25
        offset = 0
        collected: list = list(data.get("output") or [])
        last_status: dict = data
        use_wait = True
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                last_status["status"] = last_status.get("status") or "timeout"
                last_status["timed_out_after_s"] = timeout_s
                break
            try:
                if use_wait:
                    poll_raw = await poll_cb(
                        process_id=process_id, offset=offset, wait=min(remaining, 25)
                    )
                else:
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 2.0)
                    poll_raw = await poll_cb(process_id=process_id, offset=offset)
            except TypeError:

                if use_wait:
                    use_wait = False
                    continue
                poll_raw = await poll_cb(process_id=process_id)
            poll_data = self._parse_terminal_payload(poll_raw)
            if not isinstance(poll_data, dict):
                last_status = {"id": process_id, "status": "unknown"}
                break
            if "status" not in poll_data and "output" not in poll_data:

                collected.append(json.dumps(poll_data))
                last_status = {"id": process_id, "status": "error"}
                break
            last_status = poll_data
            new_chunk = poll_data.get("output") or []
            if isinstance(new_chunk, list):
                collected.extend(new_chunk)
                offset = poll_data.get("next_offset", offset + len(new_chunk))
            if poll_data.get("status") and poll_data["status"] != "running":
                break

        last_status["output"] = collected
        return self._format_bash_process_result(last_status)

    async def _await_tool_approval(self, tool_call_data: dict) -> tuple[bool, Any]:
        mode, event_call = TOOL_APPROVAL.get()
        if mode != "ask" or event_call is None:
            return True, None

        name = tool_call_data.get("name", "tool")
        try:
            args = json.dumps(
                tool_call_data.get("input") or {}, ensure_ascii=False, indent=2
            )
        except (TypeError, ValueError):
            args = str(tool_call_data.get("input"))
        if len(args) > 2000:
            args = args[:2000] + "\n… (truncated)"

        try:
            answer = await event_call(
                {
                    "type": "confirmation",
                    "data": {
                        "title": f"Run tool: {name}?",
                        "message": f"The model wants to call `{name}` with:\n\n```json\n{args}\n```",
                    },
                }
            )
        except Exception as e:

            logger.warning("Tool approval prompt failed for '%s': %s", name, e)
            answer = False

        if answer:
            logger.info("Tool '%s' approved by user", name)
            return True, None

        logger.info("Tool '%s' denied by user", name)
        return False, json.dumps(
            {"error": f"The user denied permission to run '{name}'."},
            ensure_ascii=False,
        )

    async def _await_tool_task_result(
        self,
        tool_call_data: dict,
        awaitable: Awaitable[Any],
        timeout_s: Optional[float] = None,
    ) -> tuple[dict, Any, Optional[Exception]]:
        if timeout_s is None:
            timeout_s = getattr(self.valves, "TOOL_CALL_TIMEOUT", self.TOOL_CALL_TIMEOUT)

        approved, denial = await self._await_tool_approval(tool_call_data)
        if not approved:
            if hasattr(awaitable, "close"):
                awaitable.close()
            return tool_call_data, denial, None

        try:
            result = await asyncio.wait_for(awaitable, timeout=max(1, float(timeout_s)))
            return tool_call_data, result, None
        except asyncio.TimeoutError:
            return tool_call_data, None, TimeoutError(
                f"tool call timed out after {timeout_s}s"
            )
        except Exception as e:
            return tool_call_data, None, e

    @staticmethod
    def _parse_terminal_payload(raw: Any) -> Any:
        if isinstance(raw, tuple) and raw:
            raw = raw[0]
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except (TypeError, ValueError):
                return raw
        return raw

    @staticmethod
    def _format_bash_process_result(data: dict) -> str:
        chunks_out: list[str] = []
        chunks_err: list[str] = []
        for entry in data.get("output") or []:
            if isinstance(entry, dict):
                stream = entry.get("stream") or entry.get("type") or "stdout"
                text = entry.get("data") or entry.get("text") or ""
                (chunks_err if stream == "stderr" else chunks_out).append(str(text))
            else:
                chunks_out.append(str(entry))
        stdout = "".join(chunks_out).rstrip()
        stderr = "".join(chunks_err).rstrip()

        parts: list[str] = []
        if stdout:
            parts.append(stdout)
        if stderr:
            parts.append(f"[stderr]\n{stderr}")

        meta_bits: list[str] = []
        status = data.get("status")

        if status and status not in ("done", "completed"):
            meta_bits.append(f"status={status}")
        exit_code = data.get("exit_code")
        if exit_code not in (None, 0):
            meta_bits.append(f"exit_code={exit_code}")
        if data.get("truncated"):
            meta_bits.append("truncated=true")
        if "timed_out_after_s" in data:
            meta_bits.append(f"timed_out_after_s={data['timed_out_after_s']}")
        if meta_bits:
            parts.append("[" + " ".join(meta_bits) + "]")

        if not parts:
            return "(no output)"
        return "\n".join(parts)

    async def _dispatch_text_editor_tool(
        self,
        tool_input: dict,
        __tools__: dict,
        emitter: Optional[Callable] = None,
    ) -> str:
        try:
            command = tool_input.get("command", "")
            path = tool_input.get("path", "")
            run_cmd = __tools__.get("run_command", {}).get("callable")

            if command == "view":

                if not run_cmd:
                    return "Error: run_command callable required for `view`."
                view_range = tool_input.get("view_range")

                safe_path = path.replace("'", "'\\''")
                if view_range and isinstance(view_range, list) and len(view_range) == 2:
                    start, end = view_range
                    if end == -1:
                        shell = f"sed -n '{int(start)},$p' '{safe_path}' | nl -ba -s': ' -w1"
                    else:
                        shell = f"sed -n '{int(start)},{int(end)}p' '{safe_path}' | nl -ba -s': ' -v{int(start)} -w1"
                else:

                    shell = (
                        f"if [ -d '{safe_path}' ]; then ls -la '{safe_path}'; "
                        f"else cat -n '{safe_path}'; fi"
                    )
                text = await self._run_terminal_command(__tools__, shell)

                await self._emit_terminal_event(emitter, "display_file", path)
                max_chars = self.valves.TEXT_EDITOR_MAX_CHARACTERS
                if len(text) > max_chars:
                    text = text[:max_chars] + f"\n…[truncated to {max_chars} chars]"
                return text

            elif command == "str_replace":
                replace_cb = __tools__.get("replace_file_content", {}).get("callable")
                if not replace_cb:
                    return "Error: replace_file_content callable is not available."
                old_str = tool_input.get("old_str", "")
                new_str = tool_input.get("new_str", "")
                result = await replace_cb(path=path, old_str=old_str, new_str=new_str)
                await self._emit_terminal_event(emitter, "replace_file_content", path)
                return self._stringify_terminal_result(result)

            elif command == "create":
                write_cb = __tools__.get("write_file", {}).get("callable")
                if not write_cb:
                    return "Error: write_file callable is not available."
                file_text = tool_input.get("file_text", "")
                result = await write_cb(path=path, content=file_text)
                await self._emit_terminal_event(emitter, "write_file", path)
                return self._stringify_terminal_result(result)

            elif command == "insert":

                if not run_cmd:
                    return "Error: run_command callable required for `insert`."
                insert_line = int(tool_input.get("insert_line", 0))
                insert_text = tool_input.get("insert_text", "")
                payload = json.dumps({
                    "path": path,
                    "line": insert_line,
                    "text": insert_text,
                }, ensure_ascii=False)

                shell = (
                    "python3 <<'PYEOF'\n"
                    "import json\n"
                    f"d=json.loads({json.dumps(payload)})\n"
                    "p=d['path']; ln=d['line']; t=d['text']\n"
                    "with open(p,'r',encoding='utf-8') as f: lines=f.readlines()\n"
                    "ins=t if t.endswith('\\n') else t+'\\n'\n"
                    "lines.insert(ln, ins)\n"
                    "with open(p,'w',encoding='utf-8') as f: f.writelines(lines)\n"
                    "print(f'Inserted {len(ins.splitlines())} line(s) at position {ln} in {p}')\n"
                    "PYEOF"
                )
                result_text = await self._run_terminal_command(__tools__, shell)

                await self._emit_terminal_event(emitter, "replace_file_content", path)
                return result_text

            else:
                return f"Error: unsupported text_editor command '{command}'."
        except Exception as e:
            logger.exception("text_editor dispatch failed")
            return f"Error in text_editor.{tool_input.get('command', '?')}: {e}"

    def _format_server_tool_use_block(
        self,
        tool_name: str,
        tool_use_id: str,
        tool_input: Any,
        display_body: str = "",
        *,
        result_payload: Optional[Any] = None,
        result_block_type: str = "",
        result_summary: str = "",
        result_display_body: str = "",
    ) -> str:
        payload = {
            "type": "server_tool_use",
            "id": tool_use_id,
            "name": tool_name,
            "input": tool_input if isinstance(tool_input, (dict, list)) else {},
        }
        payload_b64 = self._encode_block_payload(payload)
        icon = {
            "web_search": "🔍",
            "web_fetch": "🌐",
            "tool_search_tool_regex": "🧰",
            "tool_search_tool_bm25": "🧰",
            "advisor": "🧑‍⚖️",
        }.get(tool_name, "🔧")
        hint = ""
        if isinstance(tool_input, dict):
            hint = tool_input.get("query") or tool_input.get("url") or ""
            if not hint:

                for list_key in ("patterns", "queries"):
                    val = tool_input.get(list_key)
                    if isinstance(val, list) and val:
                        hint = ", ".join(str(v) for v in val[:3])
                        break
        default_summary = f"{icon} {tool_name}"
        if hint:
            default_summary += f": {str(hint)[:120]}"

        result_attrs = ""
        result_payload_dict = (
            {
                "type": result_block_type,
                "tool_use_id": tool_use_id,
                "content": result_payload,
            }
            if result_payload is not None and result_block_type
            else None
        )

        if self._is_block_hidden(tool_name):

            blocks = [payload] + ([result_payload_dict] if result_payload_dict else [])
            return self._format_hidden_block(blocks, tool_use_id)

        if result_payload_dict is not None:
            result_payload_b64 = self._encode_block_payload(result_payload_dict)

            result_attrs = (
                f' data-result-kind="{html.escape(result_block_type)}"'
                f' data-result-payload-b64="{result_payload_b64}"'
            )
            summary_text = result_summary or default_summary
            body_src = result_display_body or display_body
        else:
            summary_text = default_summary
            body_src = display_body

        body_part = f"{body_src}\n" if body_src else ""
        return (
            f'<details type="tool_calls" done="true"'
            f' data-block-kind="server_tool_use"'
            f' data-tool-name="{html.escape(tool_name)}"'
            f' data-tool-use-id="{html.escape(tool_use_id)}"'
            f' data-payload-b64="{payload_b64}"'
            f'{result_attrs}>\n'
            f'<summary>{html.escape(summary_text)}</summary>\n'
            f"{body_part}"
            f"</details>\n"
        )

    def _format_server_tool_result_block(
        self,
        block_type: str,
        tool_use_id: str,
        content_payload: Any,
        display_body: str = "",
        summary_text: str = "",
    ) -> str:
        payload = {
            "type": block_type,
            "tool_use_id": tool_use_id,
            "content": content_payload,
        }
        if self._is_block_hidden(block_type):
            return self._format_hidden_block([payload], tool_use_id)
        payload_b64 = self._encode_block_payload(payload)
        summary = summary_text or block_type

        body_part = f"{display_body}\n" if display_body else ""
        return (
            f'<details type="tool_calls" done="true"'
            f' data-block-kind="server_tool_result"'
            f' data-block-type="{html.escape(block_type)}"'
            f' data-tool-use-id="{html.escape(tool_use_id)}"'
            f' data-payload-b64="{payload_b64}">\n'
            f"<summary>{html.escape(summary)}</summary>\n"
            f"{body_part}"
            f"</details>\n"
        )

    def _serialize_tool_result_content(self, result_block: Any) -> Optional[Any]:
        if result_block is None:
            return None
        if hasattr(result_block, "model_dump"):
            try:
                return result_block.model_dump(exclude_none=True, mode="json")
            except Exception:
                try:
                    return result_block.model_dump(exclude_none=True)
                except Exception:
                    return None
        if isinstance(result_block, (dict, list, str, int, float, bool)):
            return result_block
        return None

    async def _persist_server_tool_result(
        self,
        content_block: Any,
        block_type: str,
        emit_message_delta,
        summary_text: str = "",
    ) -> None:
        tool_use_id = getattr(content_block, "tool_use_id", "") or ""
        if not tool_use_id:
            return
        result_block = getattr(content_block, "content", None)
        serialized = self._serialize_tool_result_content(result_block)
        if serialized is None:
            serialized = {}
        persisted = self._format_server_tool_result_block(
            block_type=block_type,
            tool_use_id=tool_use_id,
            content_payload=serialized,
            display_body="",
            summary_text=summary_text or block_type,
        )
        await emit_message_delta(persisted)

    def _format_compaction_block(self, summary: str) -> str:
        if self._is_block_hidden("compaction"):
            return self._format_hidden_block([{"type": "compaction", "content": summary}])
        return (
            '<details type="compaction">\n'
            "<summary>📦 Context Summary</summary>\n\n"
            f"{summary}\n\n"
            "</details>\n\n"
        )

    @staticmethod
    def _append_block_to_text(text: str, block: str) -> str:
        if not text:
            return block
        if not block:
            return text
        if text.endswith(("\n", "\r")) or block.startswith(("\n", "\r")):
            return text + block
        return f"{text}\n{block}"

    def _format_thinking_block(
        self, content: str, duration: Optional[float] = None,
        signature: Optional[str] = None,
    ) -> str:
        if SLIM_OUTPUT.get():

            return ""

        escaped_lines = "\n".join(
            f"> {html.escape(line)}" if not line.startswith(">") else html.escape(line)
            for line in content.splitlines()
        )

        sig_attr = f' data-signature="{html.escape(signature)}"' if signature else ""

        if duration is not None:
            duration_int = int(duration)
            return (
                f'<details type="reasoning" done="true" duration="{duration_int}"{sig_attr}>\n'
                f"<summary>Thought for {duration_int} seconds</summary>\n"
                f"{escaped_lines}\n"
                f"</details>\n"
            )
        else:
            return (
                f'<details type="reasoning" done="false"{sig_attr}>\n'
                f"<summary>Thinking…</summary>\n"
                f"{escaped_lines}\n"
                f"</details>\n"
            )

    def _format_tool_result_block(
        self,
        tool_call_id: str,
        tool_name: str,
        tool_input: dict,
        tool_output: str,
        is_error: bool = False,
        done: bool = True,
        embeds: list = None,
        files: list = None,
    ) -> str:
        if SLIM_OUTPUT.get():

            return ""

        escaped_args = (
            html.escape(json.dumps(tool_input, ensure_ascii=False))
            if tool_input
            else ""
        )

        done_str = "true" if done else "false"
        summary = "Tool Executed" if done else "Executing..."
        error_attr = ' error="true"' if is_error and done else ""

        if done:

            try:
                if isinstance(tool_output, str):
                    try:
                        parsed = json.loads(tool_output)
                        escaped_result = html.escape(
                            json.dumps(parsed, ensure_ascii=False)
                        )
                    except (json.JSONDecodeError, ValueError):
                        escaped_result = html.escape(
                            json.dumps(tool_output, ensure_ascii=False)
                        )
                else:
                    escaped_result = html.escape(
                        json.dumps(tool_output, ensure_ascii=False)
                    )
            except Exception:
                escaped_result = html.escape(
                    json.dumps(str(tool_output), ensure_ascii=False)
                )

            escaped_embeds = (
                html.escape(json.dumps(embeds, ensure_ascii=False))
                if embeds
                else ""
            )

            return (
                f'<details type="tool_calls" done="{done_str}" id="{html.escape(tool_call_id)}" name="{html.escape(tool_name)}" '
                f'arguments="{escaped_args}" result="{escaped_result}" '
                f'files="{html.escape(json.dumps(files)) if files else ""}" '
                f'embeds="{escaped_embeds}"{error_attr}>\n'
                f"<summary>{summary}</summary>\n"
                f"</details>\n"
            )
        else:

            return (
                f'<details type="tool_calls" done="{done_str}" id="{html.escape(tool_call_id)}" name="{html.escape(tool_name)}" '
                f'arguments="{escaped_args}">\n'
                f"<summary>{summary}</summary>\n"
                f"</details>\n"
            )

    def _format_code_execution_block(
        self,
        code: str,
        language: str = "python",
        done: bool = False,
        duration: float = None,
        stdout: str = "",
        stderr: str = "",
        return_code: int = None,
        download_links: list = None,
        tool_calls_info: list = None,
    ) -> str:
        if self._is_block_hidden("code_execution"):

            return ""

        done_str = "true" if done else "false"
        summary = "Analyzed" if done else "Analyzing…"

        display = f"```{language}\n{code}\n```" if code else ""

        output_data = {}
        if stdout:
            output_data["stdout"] = stdout
        if stderr:
            output_data["stderr"] = stderr

        result_parts = []
        if return_code is not None and return_code != 0:
            result_parts.append(f"Exit code: {return_code}")
        if tool_calls_info:
            for tc in tool_calls_info:
                name = tc.get("name", "?")
                res = tc.get("result", "")[:200]
                error = " ❌" if tc.get("is_error") else ""
                result_parts.append(f"🔧 {name}: {res}{error}")
        if download_links:
            result_parts.append("Files: " + ", ".join(download_links))
        if result_parts:
            output_data["result"] = "\n".join(result_parts)

        attrs = f'type="code_interpreter" done="{done_str}"'
        if duration is not None and done:
            attrs += f' duration="{duration:.1f}"'
        if output_data:
            output_json = json.dumps(output_data, ensure_ascii=False)
            attrs += f' output="{html.escape(output_json)}"'

        return f"<details {attrs}>\n<summary>{summary}</summary>\n{display}\n</details>\n"

    async def _emit_code_execution_source(
        self,
        emit_event_local: Callable,
        code: str,
        language: str,
        stdout: str = "",
        stderr: str = "",
        return_code: int = None,
        download_links: list = None,
        tool_calls_info: list = None,
    ) -> None:
        output_parts = []
        if stdout:
            output_parts.append(f"stdout:\n{stdout}")
        if stderr:
            output_parts.append(f"stderr:\n{stderr}")
        if return_code is not None and return_code != 0:
            output_parts.append(f"Return code: {return_code}")
        if download_links:
            output_parts.append("Files:\n" + "\n".join(download_links))

        output_text = "\n\n".join(output_parts) if output_parts else "(no output)"

        code_preview = code[:80].replace("\n", " ").strip() + "..." if code and len(code) > 80 else (code or "").replace("\n", " ").strip()
        source_name = f"💻 {language}: {code_preview}" if code_preview else f"💻 Code Execution ({language})"

        source_data = {
            "source": {
                "name": source_name,
            },
            "document": [output_text],
            "metadata": [
                {
                    "source": f"code_execution_{language}_{id(code)}",
                    "name": source_name,
                }
            ],
        }

        await emit_event_local({"type": "source", "data": source_data})

    @staticmethod
    def _try_parse_partial_json(buffer: str):
        if not buffer or not buffer.strip():
            return None

        for suffix in ("", "}", '"}', '"}}', "]}"):
            try:
                return json.loads(buffer + suffix)
            except (json.JSONDecodeError, ValueError):
                continue
        return None

    @classmethod
    def _parse_api_capabilities(cls, model) -> dict:
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

            "supports_memory": True,

            "supports_dynamic_filtering": False,
            "supports_fast_mode": False,
            "thinking_on_by_default": False,
        }

        model_id = model.id if hasattr(model, "id") else ""
        overrides = cls.MODEL_CAPABILITY_OVERRIDES.get(model_id, {})
        info.update(overrides)

        return info

    @classmethod
    def get_model_info(cls, model_name: str) -> dict:
        if model_name in cls._api_capabilities_cache:
            return cls._api_capabilities_cache[model_name]

        normalized = re.sub(r"-\d{8}$", "", model_name)
        if normalized != model_name and normalized in cls._api_capabilities_cache:
            return cls._api_capabilities_cache[normalized]

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
        parts = [
            (self.valves.ANTHROPIC_API_KEY or "").strip(),
            (self.valves.ANTHROPIC_BASE_URL or "").strip(),
            (getattr(self.valves, "ANTHROPIC_WORKSPACE_ID", "") or "").strip(),
            (getattr(self.valves, "ENABLED_MODELS", "") or "").strip(),
        ]
        return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()

    async def get_anthropic_models(self) -> List[dict]:

        enabled_raw = getattr(self.valves, "ENABLED_MODELS", "") or ""
        if enabled_raw.strip():
            enabled_list = [m.strip() for m in enabled_raw.split(",") if m.strip()]
            return [
                self._build_openwebui_model_entry(name, self.get_model_info(name))
                for name in enabled_list
            ]

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

                info = self._parse_api_capabilities(m)
                info["_display_name"] = display_name
                new_cache[name] = info

                entry = self._build_openwebui_model_entry(name, info, display_name)
                models.append(entry)

            if not models:
                logger.warning("Model listing returned no models; using static fallback")
                return self._static_fallback_models()

            Pipe._api_capabilities_cache = new_cache
            Pipe._api_capabilities_cache_ts = time.time()
            Pipe._api_capabilities_cache_sig = cache_sig
            logger.info(f"Cached capabilities for {len(new_cache)} models from API")
            return models
        except Exception as e:
            logging.warning(
                f"Could not fetch models from SDK/API: {e}"
            )

            if (
                self._api_capabilities_cache
                and self._api_capabilities_cache_sig == cache_sig
            ):
                logging.info("Using stale capability cache as fallback")
                for name, info in self._api_capabilities_cache.items():
                    models.append(self._build_openwebui_model_entry(name, info))
                return models

            return models

    @staticmethod
    def _build_openwebui_model_entry(
        name: str, info: dict, display_name: str = ""
    ) -> dict:
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

        api_key = decrypt_valve_secret(api_key)
        base_url = self.valves.ANTHROPIC_BASE_URL.strip() or None

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
        return [
            self._build_openwebui_model_entry(name, self.get_model_info(name))
            for name in self.MODEL_CAPABILITY_OVERRIDES
        ]

    async def pipes(self) -> List[dict]:
        return await self.get_anthropic_models()

    MEMORY_REVIEW_TASK = "memory_review"

    TASK_MAX_TOKENS_CAP = 8192

    TASK_RESPONSE_SCHEMAS = {
        "title_generation": {
            "type": "object",
            "properties": {"title": {"type": "string"}},
            "required": ["title"],
            "additionalProperties": False,
        },
        "tags_generation": {
            "type": "object",
            "properties": {"tags": {"type": "array", "items": {"type": "string"}}},
            "required": ["tags"],
            "additionalProperties": False,
        },
        "follow_up_generation": {
            "type": "object",
            "properties": {"follow_ups": {"type": "array", "items": {"type": "string"}}},
            "required": ["follow_ups"],
            "additionalProperties": False,
        },
        "query_generation": {
            "type": "object",
            "properties": {"queries": {"type": "array", "items": {"type": "string"}}},
            "required": ["queries"],
            "additionalProperties": False,
        },
        "image_prompt_generation": {
            "type": "object",
            "properties": {"prompt": {"type": "string"}},
            "required": ["prompt"],
            "additionalProperties": False,
        },
        "autocomplete_generation": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
        MEMORY_REVIEW_TASK: {
            "type": "object",
            "properties": {
                "operations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["add", "replace", "move", "remove"],
                            },
                            "id": {"type": "string"},
                            "type": {"type": "string", "enum": ["user", "context"]},
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                        },

                        "required": ["action"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["operations"],
            "additionalProperties": False,
        },
    }

    async def _run_task_model_request(
        self,
        body: dict[str, Any],
        task: Optional[str] = None,
    ) -> str:
        try:

            actual_model_name = self._resolve_task_model(body, task)
            messages = body.get("messages", [])
            model_info = self.get_model_info(actual_model_name)

            task_payload = {
                "model": actual_model_name,

                "max_tokens": min(
                    body.get("max_tokens") or model_info.get("max_tokens", 4096),
                    self.TASK_MAX_TOKENS_CAP,
                ),
                "messages": self._process_messages_for_task(messages),
                "stream": False,
            }

            response_schema = (
                self.TASK_RESPONSE_SCHEMAS.get(task) if isinstance(task, str) else None
            )
            if response_schema and model_info.get("supports_structured_outputs"):
                task_payload["output_config"] = {
                    "format": {"type": "json_schema", "schema": response_schema}
                }
                logger.debug(f"Structured output enabled for task {task}")

            task_system = self._extract_task_system(messages)
            if task_system:
                task_payload["system"] = task_system

            logger.debug(f"Task payload: {json.dumps(task_payload, indent=2)}")
            try:
                logger.debug(
                    "[PAYLOAD] task %s",
                    json.dumps(
                        self._strip_payload(task_payload),
                        ensure_ascii=False,
                        separators=(",", ":"),
                        default=str,
                    ),
                )
            except Exception as _pl_err:
                logger.debug(f"[PAYLOAD] task strip/log failed: {_pl_err}")

            api_key = self.valves.ANTHROPIC_API_KEY
            client = self._build_anthropic_client(api_key)

            try:
                response = await client.messages.create(**task_payload)
            except Exception as struct_err:

                if "output_config" not in task_payload:
                    raise
                logger.warning(
                    f"Task {task} rejected with structured outputs, retrying "
                    f"without: {struct_err}"
                )
                task_payload.pop("output_config", None)
                response = await client.messages.create(**task_payload)

            text_parts = []
            for content_block in response.content:
                if content_block.type == "text":
                    text_parts.append(content_block.text)

            result = "".join(text_parts).strip()

            logger.debug(f"Task response: {result}")

            return result

        except Exception as e:

            logger.warning(f"Task model error ({task}): {e}")
            return ""

    def _process_messages_for_task(self, messages: List[dict]) -> List[dict]:
        processed = []
        for msg in messages:
            role = msg.get("role")
            if role == "system":
                continue

            content = msg.get("content", "")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):

                text = " ".join(
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                )
            else:
                continue

            text = self._sanitize_task_text(text)

            if not text:
                continue

            if processed and processed[-1]["role"] == role:
                processed[-1]["content"] = f"{processed[-1]['content']}\n\n{text}"
            else:
                processed.append({"role": role, "content": text})

        return processed

    def _resolve_task_model(self, body: dict, task: Optional[str]) -> str:
        requested = body["model"].split("/")[-1]
        if task != self.MEMORY_REVIEW_TASK:
            return requested

        override = getattr(self.valves, "MEMORY_REVIEW_MODEL", "same as chat model")
        if not override or override == "same as chat model":
            return requested

        logger.debug(f"Memory review routed to {override} instead of {requested}")
        return override

    @classmethod
    def _sanitize_task_text(cls, text: str) -> str:
        if not text or ("<" not in text and "[" not in text):
            return text

        cleaned = PATTERN_ANY_DETAILS.sub("\n", text)
        cleaned = PATTERN_HIDDEN_BLOCK.sub("", cleaned)
        cleaned = PATTERN_INLINE_METADATA_MARKER.sub(" ", cleaned)
        cleaned = PATTERN_TRAILING_SPACES.sub("", cleaned)
        return PATTERN_EXCESS_BLANK_LINES.sub("\n\n", cleaned).strip()

    @classmethod
    def _extract_task_system(cls, messages: List[dict]) -> str:
        parts = []
        for msg in messages:
            if msg.get("role") != "system":
                continue
            content = msg.get("content", "")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text = " ".join(
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                )
            else:
                continue
            if text.strip():
                parts.append(text.strip())

        return "\n\n".join(parts)

    def _handle_message_start_usage(
        self,
        event: Any,
        *,
        include_usage: bool,
        total_usage: Optional[dict[str, int]],
        stream_output_tokens: int,
    ) -> int:

        message = getattr(event, "message", None)
        if not message:
            return stream_output_tokens

        request_id = getattr(message, "id", None)
        logger.debug(f" Message started with ID: {request_id}")

        if not include_usage or total_usage is None:
            return stream_output_tokens

        usage = getattr(message, "usage", {})
        if not usage:
            return stream_output_tokens

        input_tokens = getattr(usage, "input_tokens", 0)
        current_output_tokens = getattr(usage, "output_tokens", 0)

        total_usage["input_tokens"] += input_tokens
        diff = current_output_tokens - stream_output_tokens
        total_usage["output_tokens"] += diff
        stream_output_tokens = current_output_tokens

        if self.valves.CACHE_CONTROL != "cache disabled":
            cache_creation_input_tokens = getattr(usage, "cache_creation_input_tokens", 0) or 0
            cache_read_input_tokens = getattr(usage, "cache_read_input_tokens", 0) or 0

            total_usage["cache_creation_input_tokens"] += cache_creation_input_tokens
            total_usage["cache_read_input_tokens"] += cache_read_input_tokens
            logger.debug(
                f" Usage stats: input={input_tokens}, output={current_output_tokens}, "
                f"cache_creation={cache_creation_input_tokens}, cache_read={cache_read_input_tokens}"
            )
        else:
            cache_creation_input_tokens = 0
            cache_read_input_tokens = 0
            logger.debug(f" Usage stats: input={input_tokens}, output={current_output_tokens}")

        total_usage["_calls"] = total_usage.get("_calls", 0) + 1

        total_usage["_ctx_input"] = (
            input_tokens + cache_creation_input_tokens + cache_read_input_tokens
        )
        total_usage["_ctx_output"] = current_output_tokens

        total_usage["total_tokens"] = (
            total_usage.get("input_tokens", 0) + total_usage.get("output_tokens", 0)
        )
        logger.debug(f" Accumulated usage: {total_usage}")

        return stream_output_tokens

    @staticmethod
    def _public_usage(total_usage: dict[str, int]) -> dict[str, int]:

        public = {k: v for k, v in total_usage.items() if not k.startswith("_")}
        public["prompt_tokens"] = total_usage.get("_ctx_input", 0)
        public["completion_tokens"] = total_usage.get("_ctx_output", 0)
        return public

    async def _handle_stream_exception(
        self,
        exc: Exception,
        *,
        retry_attempts: int,
        request_ctx: PipeRequestContext,
    ) -> tuple[bool, int, str]:

        max_retries = self.valves.MAX_RETRIES
        status = StatusEmitter(request_ctx.emit_event)

        non_retry_map: dict[type[Exception], str] = {
            RateLimitError: f"\n\n⚠️ Rate limit exceeded - maximum retries ({max_retries}) reached. Please try again later.",
            AuthenticationError: f"\n\nError: API key issues. Reason: {getattr(exc, 'message', str(exc))}",
            PermissionDeniedError: f"\n\nError: Permission denied. Reason: {getattr(exc, 'message', str(exc))}",
            NotFoundError: f"\n\nError: Resource not found. Reason: {getattr(exc, 'message', str(exc))}",
            BadRequestError: f"\n\nError: Invalid request format. Reason: {getattr(exc, 'message', str(exc))}",
            UnprocessableEntityError: f"\n\nError: Unprocessable entity. Reason: {getattr(exc, 'message', str(exc))}",
        }

        for error_type, suffix in non_retry_map.items():
            if isinstance(exc, error_type):
                await self.handle_errors(exc, request_ctx.event_emitter)
                return (False, retry_attempts, suffix)

        retryable_with_status: list[tuple[type[Exception], str, str]] = [
            (OverloadedError, "⏳ API overloaded, retrying...", "🔧 API overloaded"),
            (InternalServerError, "⏳ Server error, retrying...", "🔧 Server error"),
            (APIConnectionError, "🌐 Connection error, retrying...", "🌐 Network connection failed"),
        ]

        for error_type, status_label, fail_label in retryable_with_status:
            if isinstance(exc, error_type):
                retry_attempts += 1
                if retry_attempts <= max_retries:
                    await status.activity(f"{status_label} ({retry_attempts}/{max_retries})")
                    return (True, retry_attempts, "")

                await self.handle_errors(exc, request_ctx.event_emitter)
                if isinstance(exc, APIConnectionError):
                    return (
                        False,
                        retry_attempts,
                        f"\n\n{fail_label} after {max_retries} attempts. Please check your connection.",
                    )
                return (
                    False,
                    retry_attempts,
                    f"\n\n{fail_label} - maximum retries ({max_retries}) reached. Please try again later.",
                )

        if isinstance(exc, APIStatusError):
            error_body = getattr(exc, "body", None) or {}
            error_info = error_body.get("error", {}) if isinstance(error_body, dict) else {}
            is_overloaded = error_info.get("type") == "overloaded_error"

            if is_overloaded and retry_attempts < max_retries:
                retry_attempts += 1
                await status.activity(
                    f"⏳ API overloaded (streaming), retrying... ({retry_attempts}/{max_retries})"
                )
                return (True, retry_attempts, "")

            await self.handle_errors(exc, request_ctx.event_emitter)
            if is_overloaded:
                return (
                    False,
                    retry_attempts,
                    f"\n\n🔧 API overloaded (streaming) - maximum retries ({max_retries}) reached. Please try again later.",
                )
            return (
                False,
                retry_attempts,
                f"\n\nError: Anthropic API error. Reason: {getattr(exc, 'message', str(exc))}",
            )

        await self.handle_errors(exc, request_ctx.event_emitter)
        return (
            False,
            retry_attempts,
            f"\n\nError: {type(exc).__name__} occurred. Reason: {exc}",
        )

    async def _apply_sdk_stop_reason_fallback(
        self,
        *,
        sdk_final_message: Any,
        conversation_ended: bool,
        has_pending_tool_calls: bool,
        tool_calls: list[dict[str, Any]],
        tool_loop_iteration: int,
        payload_for_stream: dict[str, Any],
        stream_event_counts: dict[str, int],
        request_ctx: PipeRequestContext,
    ) -> tuple[bool, bool, list[dict[str, Any]]]:

        if not sdk_final_message or conversation_ended or has_pending_tool_calls:
            return conversation_ended, has_pending_tool_calls, tool_calls

        status = StatusEmitter(request_ctx.emit_event)

        sdk_stop = getattr(sdk_final_message, "stop_reason", None)
        sdk_content = getattr(sdk_final_message, "content", [])

        if sdk_stop:
            logger.info(f"📍 Fallback stop_reason from SDK message: {sdk_stop}")
            if sdk_stop == "end_turn":
                conversation_ended = True
            elif sdk_stop == "tool_use":
                has_pending_tool_calls = True
                if not tool_calls:
                    for block in sdk_content:
                        if getattr(block, "type", None) == "tool_use":
                            logger.warning(
                                f"📍 Rebuilding tool_call from SDK: {getattr(block, 'name', '?')}"
                            )
                            tool_calls.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": getattr(block, "id", ""),
                                    "content": "Error: tool call was not processed during streaming",
                                    "is_error": True,
                                }
                            )
            elif sdk_stop == "pause_turn":
                has_pending_tool_calls = True
                await status.activity("⏳ Long-running turn paused, continuing...")
            elif sdk_stop in (
                "max_tokens",
                "refusal",
                "stop_sequence",
                "model_context_window_exceeded",
            ):
                conversation_ended = True
                if sdk_stop == "max_tokens":
                    await request_ctx.emit_delta("\n\n⚠️ Maximum token limit reached.")
                elif sdk_stop == "model_context_window_exceeded":
                    await request_ctx.emit_delta("\n\n⚠️ Context window exceeded.")
                elif sdk_stop == "refusal":
                    _stop_details = getattr(sdk_final_message, "stop_details", None)
                    _category = getattr(_stop_details, "category", None) if _stop_details else None
                    _explanation = getattr(_stop_details, "explanation", None) if _stop_details else None
                    _REFUSAL_LABELS = {
                        "cyber": "cybersecurity policy",
                        "bio": "biological safety policy",
                        "reasoning_extraction": "reasoning extraction policy",
                    }
                    _cat_label = _REFUSAL_LABELS.get(_category, "content policy") if _category else "content policy"
                    _ref_msg = f"\u26a0\ufe0f Request declined by Claude ({_cat_label})."
                    if _explanation:
                        _ref_msg += f"\n\n_{_explanation}_"
                    await request_ctx.emit_delta(_ref_msg)
        elif not sdk_content:
            logger.warning(
                f"⚠️ Empty API response (no stop_reason, no content). "
                f"Container: {payload_for_stream.get('container', 'NONE')}. "
                f"Events: {stream_event_counts}. Treating as end_turn."
            )
            conversation_ended = True
            if tool_loop_iteration > 1:
                await request_ctx.emit_delta(
                    "\n\n⚠️ Code execution continuation returned empty response. "
                    "The container may have timed out."
                )
        else:

            block_types = [getattr(b, "type", "?") for b in sdk_content]
            has_text = any(
                getattr(b, "type", None) == "text"
                and len(getattr(b, "text", "") or "") > 0
                for b in sdk_content
            )
            logger.warning(
                f"⚠️ Truncated stream: no stop_reason but content present. "
                f"Blocks: {block_types}. has_text={has_text}. "
                f"Container: {payload_for_stream.get('container', 'NONE')}. "
                f"Events: {stream_event_counts}."
            )

        return conversation_ended, has_pending_tool_calls, tool_calls

    async def handle_errors(
        self,
        exception,
        __event_emitter__: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ):

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

        if isinstance(exception, APIStatusError) and hasattr(exception, "response"):
            try:
                request_id = exception.response.headers.get("request-id")
                if request_id:
                    logger.info(f"Request ID: %s", request_id)
            except Exception:
                pass

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

    async def handle_citation(self, event, __event_emitter__, citation_counter=None):
        try:
            logger.debug(
                f" Processing citation event type: {getattr(event, 'type', 'unknown')}"
            )

            delta = getattr(event, "delta", None)
            citation = None

            if delta and hasattr(delta, "citation"):
                citation = delta.citation
            elif hasattr(event, "citation"):

                citation = event.citation

            if not citation:
                logger.debug(f"No citation data found in event")
                return

            logger.debug(f" Citation data found: {citation}")

            citation_type = getattr(citation, "type", "")
            if citation_type != "web_search_result_location":
                logger.debug(f" Skipping non-web-search citation type: {citation_type}")
                return

            url = getattr(citation, "url", "")
            title = getattr(citation, "title", "Unknown Source")
            cited_text = getattr(citation, "cited_text", "")

            metadata = {
                "source": f"{url}#{citation_counter}",
                "date_accessed": datetime.now().isoformat(),
                "name": f"[{citation_counter}]",
            }

            source_data = {
                "source": {
                    "name": title,
                    "url": url,
                    "id": f"{citation_counter}",
                },
                "document": [cited_text],
                "metadata": [metadata],
            }

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
        if __event_emitter__ is None:
            return
        try:
            await __event_emitter__(event)
        except Exception as e:
            logger.warning(f"Event emitter failed: {e}")

    def _convert_sdk_message_to_api_blocks(self, message) -> list:
        blocks = []
        for block in message.content:
            block_dict = block.model_dump(exclude_none=True)
            block_type = block_dict.get("type", "")

            if block_type in self._SKIP_BLOCK_TYPES:
                continue

            if block_type == "compaction":
                content = block_dict.get("content", "")
                if content:
                    blocks.append({"type": "compaction", "content": content})
                continue

            sanitize_keys = self._SANITIZE_BLOCK_KEYS.get(block_type)
            if sanitize_keys is not None:
                blocks.append({k: v for k, v in block_dict.items() if k in sanitize_keys})
                continue

            if block_type == "text":
                block_dict.pop("citations", None)
                blocks.append(block_dict)
                continue

            if block_type == "tool_use":
                caller = block_dict.get("caller")
                if caller and caller.get("type") == "direct":
                    block_dict.pop("caller", None)
                blocks.append(block_dict)
                continue

            blocks.append(block_dict)

        return blocks

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
        __request__: Optional[Any] = None,
        __event_call__: Optional[Callable[[Dict[str, Any]], Awaitable[Any]]] = None,
    ):

        request_ctx = PipeRequestContext(pipe=self, event_emitter=__event_emitter__)
        final_message = request_ctx.final_message
        emit_event_local = request_ctx.emit_event
        emit_message_delta = request_ctx.emit_delta
        emit_message_replace = request_ctx.emit_replace
        update_content_block = request_ctx.update_content_block
        final_text = request_ctx.text
        status = StatusEmitter(emit_event_local)
        request_ctx.status = status
        request_ctx.metadata = __metadata__ or {}
        request_ctx.user = __user__ or {}
        request_ctx.tools = __tools__

        handler_registry = HandlerRegistry(default_handlers())

        is_internal = False

        run_id = request_ctx.run_id
        logger.info(
            "[RUN %s] pipe() start chat_id=%s message_id=%s session_id=%s",
            run_id,
            (__metadata__ or {}).get("chat_id"),
            (__metadata__ or {}).get("message_id"),
            (__metadata__ or {}).get("session_id"),
        )

        try:

            if logger.isEnabledFor(logging.DEBUG):

                logger.debug(f"OpenWebUI version: {OPENWEBUI_VERSION}")
                logger.debug(f"Valves: {self.valves.model_dump()}")
                user_valves = __user__.get("valves")
                if user_valves and hasattr(user_valves, "model_dump"):
                    logger.debug(f"UserValves: {user_valves.model_dump()}")
                elif user_valves:
                    logger.debug(f"UserValves: {user_valves}")

            user_valves = __user__.get("valves")
            user_api_key = getattr(user_valves, "ANTHROPIC_API_KEY", "") if user_valves else ""
            api_key = user_api_key.strip() if user_api_key and user_api_key.strip() else self.valves.ANTHROPIC_API_KEY

            resolved_api_key = decrypt_valve_secret(api_key).strip()
            if not resolved_api_key or resolved_api_key == "Your API Key Here":
                error_msg = "Error: No API key configured. Set it in admin Valves or your personal UserValves."
                logger.error(f"{error_msg}")
                await status.complete("No API Key Set!")
                return error_msg

            HIDDEN_BLOCKS.set(
                self._parse_hidden_blocks(getattr(user_valves, "HIDE_BLOCKS", None))
            )

            TOOL_APPROVAL.set(
                (
                    (__metadata__ or {}).get("params", {}).get("tool_approval_mode", "full"),
                    __event_call__,
                )
            )

            is_internal = bool(
                __request__ is not None
                and getattr(getattr(__request__, "state", None), "internal", False) is True
            )
            SLIM_OUTPUT.set(is_internal)
            if is_internal:
                logger.debug("Internal (sub-agent) run: emitting slim prose output")

            if __task__:
                return await self._run_task_model_request(body, task=__task__)

            if inspect.isawaitable(__tools__):
                __tools__ = await __tools__

            builtin_tools = {}
            if BUILTIN_TOOLS_AVAILABLE and __request__:
                try:

                    memory_enabled = (
                        __user__.get("settings", {}).get("ui", {}).get("memory", False)
                        if __user__
                        else False
                    )

                    skill_ids = []
                    try:
                        openwebui_model_id = __metadata__.get("model_id") or body.get("model", "")
                        if openwebui_model_id and MODELS_AVAILABLE:
                            owui_model = await Models.get_model_by_id(openwebui_model_id)
                            if owui_model:

                                meta = owui_model.meta
                                if meta:
                                    meta_dict = meta.model_dump() if hasattr(meta, "model_dump") else (meta if isinstance(meta, dict) else {})
                                    model_skill_ids = set(meta_dict.get("skillIds", []))
                                else:
                                    model_skill_ids = set()
                                logger.debug(f"Model {openwebui_model_id} skill IDs: {model_skill_ids}")
                                if model_skill_ids:
                                    from open_webui.models.skills import Skills as SkillsModel

                                    user_id = __user__.get("id", "") if __user__ else ""
                                    accessible_skills = await SkillsModel.get_skills_by_user_id(user_id, "read")
                                    accessible = {s.id for s in accessible_skills}
                                    logger.debug(f"Accessible skills for user: {accessible}")
                                    skill_ids = []
                                    for sid in model_skill_ids:
                                        if sid not in accessible:
                                            continue
                                        s = await SkillsModel.get_skill_by_id(sid)
                                        if s and s.is_active:
                                            skill_ids.append(sid)
                                    logger.debug(f"Resolved skill_ids: {skill_ids}")
                    except Exception as e:
                        logger.debug(f"Could not resolve skill IDs: {e}")

                    builtin_tools = get_builtin_tools(
                        __request__,
                        {
                            "__user__": __user__,
                            "__event_emitter__": __event_emitter__,
                            "__chat_id__": (
                                __metadata__.get("chat_id") if __metadata__ else None
                            ),
                            "__message_id__": (
                                __metadata__.get("message_id") if __metadata__ else None
                            ),
                            "__skill_ids__": skill_ids,
                        },
                        features={"memory": memory_enabled},
                        model={},
                    )
                    if inspect.isawaitable(builtin_tools):
                        builtin_tools = await builtin_tools
                    logger.debug(
                        f"Loaded {len(builtin_tools)} builtin tools: {list(builtin_tools.keys())}"
                    )
                except Exception as e:
                    logger.warning(f"Could not load builtin tools: {e}")
                    builtin_tools = {}

            metadata_tools = __metadata__.get("tools", {}) if __metadata__ else {}
            if metadata_tools:
                for t_name, t_data in metadata_tools.items():
                    if t_name not in builtin_tools and (not __tools__ or t_name not in __tools__):
                        if isinstance(t_data, dict) and t_data.get("callable"):
                            builtin_tools[t_name] = t_data
                if builtin_tools:
                    logger.debug(
                        f"After metadata merge, builtin_tools: {list(builtin_tools.keys())}"
                    )

            if __tools__ and MODELS_AVAILABLE:
                try:

                    openwebui_model_id = (
                        __metadata__.get("model_id") if __metadata__ else None
                    )
                    if not openwebui_model_id and body and "model" in body:
                        openwebui_model_id = body["model"]

                    if openwebui_model_id:
                        model = await Models.get_model_by_id(openwebui_model_id)
                        if model:
                            params = dict(model.params or {})
                            if params.get("function_calling") != "native":
                                logger.debug(
                                    f"Auto-enabling native function calling for model: {openwebui_model_id}"
                                )

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
                                await Models.update_model_by_id(
                                    openwebui_model_id, ModelForm(**form_data)
                                )
                except Exception as e:
                    logger.warning(
                        f"Could not auto-enable native function calling: {e}"
                    )

            if __metadata__ is not None:
                __metadata__.setdefault("params", {})["reasoning_tags"] = False

            payload, headers, new_marker_metadata, api_tool_names = await self._create_payload(
                body, __metadata__, __user__, __tools__, __event_emitter__, __files__
            )

            api_key = headers.get("x-api-key", self.valves.ANTHROPIC_API_KEY)

            if user_api_key and user_api_key.strip():
                api_key = user_api_key.strip()
                logger.debug("Using user-provided API key from UserValves")
            request_timeout = self.valves.REQUEST_TIMEOUT

            request_ctx.api_key = api_key
            request_ctx.builtin_tools = builtin_tools
            request_ctx.api_tool_names = api_tool_names
            client = self._build_anthropic_client(api_key, default_headers=headers, timeout=request_timeout)
            payload_for_stream = {k: v for k, v in payload.items() if k != "stream"}
            include_usage = (
                __user__["valves"].SHOW_TOKEN_COUNT != "Off"
                or body.get("stream_options", {}).get("include_usage", False)
            )
            total_usage: Optional[dict[str, int]] = None
            if include_usage:
                total_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "_ctx_input": 0, "_ctx_output": 0}
                if self.valves.CACHE_CONTROL != "cache disabled":
                    total_usage["cache_creation_input_tokens"] = 0
                    total_usage["cache_read_input_tokens"] = 0

            cache_diagnostics_records: list[dict[str, Any]] = []
            cache_diagnostics_chat_id: Optional[str] = (
                __metadata__.get("chat_id") if __metadata__ else None
            )

            token_buffer_size = getattr(self.valves, "TOKEN_BUFFER_SIZE", 1)
            max_function_calls = self.valves.MAX_TOOL_CALLS

            sdk_final_message = None

            tool_use_state = request_ctx.state.tool_use
            has_pending_tool_calls = False
            tool_calls = []

            server_tool_state = request_ctx.state.server_tool

            payload_tools = payload.get("tools", [])
            has_explicit_code_execution = any(
                t.get("name") == "code_execution" for t in payload_tools
            )
            server_tool_state.has_explicit_code_execution = has_explicit_code_execution

            text_state = request_ctx.state.text

            conversation_ended = False
            retry_attempts = 0
            current_function_calls = 0

            await status.waiting()

            tool_loop_iteration = 0
            while (
                current_function_calls < max_function_calls
                and not conversation_ended
                and retry_attempts <= self.valves.MAX_RETRIES
            ):
                tool_loop_iteration += 1

                stream_output_tokens = 0

                try:
                    stream_event_counts = {}

                    self._apply_cache_control(
                        payload_for_stream,
                        is_tool_loop=(tool_loop_iteration > 1),
                        iteration=tool_loop_iteration,
                    )

                    _diff_chat_id = __metadata__.get("chat_id") if __metadata__ else None
                    self._log_message_hash_diff(_diff_chat_id, payload_for_stream)

                    try:
                        logger.debug(
                            "[PAYLOAD run=%s] iter=%d retry=%d %s",
                            run_id,
                            tool_loop_iteration,
                            retry_attempts,
                            json.dumps(
                                self._strip_payload(payload_for_stream),
                                ensure_ascii=False,
                                separators=(",", ":"),
                                default=str,
                            ),
                        )
                    except Exception as _pl_err:
                        logger.debug(f"[PAYLOAD] strip/log failed: {_pl_err}")
                    async with client.beta.messages.stream(
                        **payload_for_stream
                    ) as stream:
                        async for event in stream:
                            event_type = getattr(event, "type", None)
                            stream_event_counts[event_type] = stream_event_counts.get(event_type, 0) + 1
                            logger.debug(f"Received stream event: {event_type} | counts: {stream_event_counts} | payload: {event}")
                            if event_type == "message_start":

                                stream_output_tokens = self._handle_message_start_usage(
                                    event,
                                    include_usage=include_usage,
                                    total_usage=total_usage if include_usage else None,
                                    stream_output_tokens=stream_output_tokens,
                                )
                                if getattr(self.valves, "ENABLE_CACHE_DIAGNOSTICS", False):
                                    msg = getattr(event, "message", None)
                                    msg_id = getattr(msg, "id", None) if msg else None

                                    http_request_id = None
                                    try:
                                        http_request_id = stream.response.headers.get("request-id")
                                    except Exception:
                                        pass

                                    diag_obj = getattr(msg, "diagnostics", None) if msg else None
                                    if diag_obj is None and isinstance(msg, dict):
                                        diag_obj = msg.get("diagnostics")
                                    diag_dump = self._dump_sdk_obj(diag_obj) if diag_obj else None

                                    usage_obj = getattr(msg, "usage", None) if msg else None
                                    usage_dump = self._dump_sdk_obj(usage_obj) if usage_obj else None
                                    if msg_id or diag_dump or http_request_id or usage_dump:
                                        cache_diagnostics_records.append(
                                            {"message_id": msg_id, "request_id": http_request_id, "usage": usage_dump, "diagnostics": diag_dump}
                                        )
                                        logger.info(
                                            f"[CACHE-DIAG run={run_id}] record #{len(cache_diagnostics_records)} "
                                            f"iter={tool_loop_iteration} retry={retry_attempts} "
                                            f"chat_id={cache_diagnostics_chat_id} "
                                            f"message_id={msg_id} request_id={http_request_id} "
                                            f"usage={usage_dump} diagnostics={diag_dump}"
                                        )

                            elif event_type == "content_block_start":
                                content_block = getattr(event, "content_block", None)
                                content_type = getattr(content_block, "type", None)
                                if not content_block:
                                    continue

                                await handler_registry.handle_start(event, request_ctx)

                            elif event_type == "content_block_delta":
                                await handler_registry.handle_delta(event, request_ctx)

                            elif event_type == "content_block_stop":
                                await handler_registry.handle_stop(event, request_ctx)

                            elif event_type == "message_delta":
                                if include_usage:
                                    usage = getattr(event, "usage", None)
                                    if usage:
                                        current_output_tokens = getattr(
                                            usage, "output_tokens", 0
                                        )
                                        diff = (
                                            current_output_tokens - stream_output_tokens
                                        )
                                        total_usage["output_tokens"] += diff
                                        stream_output_tokens = current_output_tokens

                                        total_usage["_ctx_output"] = current_output_tokens

                                        total_usage["total_tokens"] = (
                                            total_usage.get("input_tokens", 0)
                                            + total_usage.get("output_tokens", 0)
                                        )
                                delta = getattr(event, "delta", None)
                                code_execution_container_id = getattr(delta, "container", None)
                                if code_execution_container_id:
                                    delta_container_id = getattr(code_execution_container_id, "id", None) if hasattr(code_execution_container_id, "id") else (code_execution_container_id.get("id") if isinstance(code_execution_container_id, dict) else str(code_execution_container_id))
                                    if delta_container_id:
                                        current_container_id = payload_for_stream.get("container")
                                        if current_container_id != delta_container_id:
                                            text_state.chunk += self._create_metadata_marker(
                                                "container_id",
                                                delta_container_id,
                                                messagenum=len(
                                                    payload_for_stream.get("messages", [])
                                                ),
                                            )
                                            logger.debug(
                                                f"📦 Container ID from message_delta: {delta_container_id}"
                                            )
                                        payload_for_stream["container"] = delta_container_id

                                stop_reason = getattr(delta, "stop_reason", None)
                                if stop_reason:
                                    logger.debug(f"📍 stop_reason received: {stop_reason}")
                                if stop_reason == "tool_use":

                                    if text_state.chunk:
                                        if not text_state.chunk.endswith("\n"):
                                            text_state.chunk += "\n"
                                        await emit_message_delta(text_state.chunk)
                                        text_state.chunk = ""
                                        text_state.chunk_count = 0

                                    if tool_use_state.api_passthrough and not tool_use_state.running_tasks:
                                        logger.info(
                                            "🔄 API tool passthrough complete — skipping tool loop"
                                        )
                                        conversation_ended = True
                                        break

                                    if tool_use_state.running_tasks:
                                        logger.debug(
                                            f"⏳ Waiting for %d tool tasks to complete...",
                                            len(tool_use_state.running_tasks),
                                        )

                                        try:
                                            completed_results = 0

                                            for completed_task in asyncio.as_completed(
                                                tool_use_state.running_tasks
                                            ):
                                                (
                                                    tool_call_data,
                                                    tool_result,
                                                    task_error,
                                                ) = await completed_task
                                                completed_results += 1
                                                tool_use_id = tool_call_data.get(
                                                    "id", ""
                                                )
                                                tool_name = tool_call_data.get(
                                                    "name", ""
                                                )
                                                tool_input = tool_call_data.get(
                                                    "input", {}
                                                )

                                                if task_error is not None:
                                                    tool_result = f"Error executing tool '{tool_name}': {task_error}"

                                                tool_result_embeds = []
                                                tool_result_files = []
                                                if PROCESS_TOOL_RESULT_AVAILABLE and __request__:
                                                    try:
                                                        tool_result, tool_result_files, tool_result_embeds = (
                                                            await process_tool_result(
                                                                __request__,
                                                                tool_name,
                                                                tool_result,
                                                                "pipe",
                                                                metadata=__metadata__,
                                                                user=__user__,
                                                            )
                                                        )
                                                    except Exception as e:
                                                        logger.warning(f"process_tool_result failed for '{tool_name}': {e}")

                                                if tool_result_files and __event_emitter__:
                                                    await __event_emitter__(
                                                        {
                                                            "type": "files",
                                                            "data": {"files": tool_result_files},
                                                        }
                                                    )

                                                is_error = isinstance(
                                                    tool_result, str
                                                ) and (
                                                    tool_result.startswith("Error:")
                                                    or tool_result.startswith("Error executing tool")
                                                )

                                                if isinstance(tool_result, str):
                                                    result_str = tool_result
                                                else:
                                                    try:
                                                        result_str = json.dumps(tool_result, ensure_ascii=False)
                                                    except (TypeError, ValueError):
                                                        result_str = str(tool_result)

                                                result_block = {
                                                    "type": "tool_result",
                                                    "tool_use_id": tool_use_id,
                                                    "content": self._convert_tool_result_content(result_str, __user__),
                                                }
                                                if is_error:
                                                    result_block["is_error"] = True
                                                tool_calls.append(result_block)

                                                if server_tool_state.in_code_execution:

                                                    server_tool_state.tool_calls_info.append({
                                                        "name": tool_name,
                                                        "input": tool_input,
                                                        "result": result_str,
                                                        "is_error": is_error,
                                                    })
                                                else:

                                                    completed = self._format_tool_result_block(
                                                        tool_use_id, tool_name, tool_input,
                                                        str(tool_result), is_error=is_error, done=True,
                                                        files=tool_result_files,
                                                        embeds=tool_result_embeds,
                                                    )
                                                    old_block = tool_use_state.progress_blocks.pop(tool_use_id, None)
                                                    if old_block:
                                                        text = final_text()
                                                        text = text.replace(old_block, completed, 1)
                                                        final_message.clear()
                                                        final_message.append(text)
                                                        await request_ctx.emit_event({"type": "replace", "data": {"content": text}})
                                                    else:

                                                        text = self._append_block_to_text(final_text(), completed)
                                                        final_message.clear()
                                                        final_message.append(text)
                                                        await emit_message_replace(text)

                                            logger.debug(
                                                f"✅ All %d tool tasks completed",
                                                completed_results,
                                            )
                                        except Exception as ex:
                                            logger.error(
                                                f"❌ Tool execution failed: %s", ex
                                            )
                                            for task in tool_use_state.running_tasks:
                                                if not task.done():
                                                    task.cancel()

                                            for tool_use_id, old_block in list(tool_use_state.progress_blocks.items()):
                                                error_result = f"Error executing tool: {str(ex)}"
                                                tool_calls.append(
                                                    {
                                                        "type": "tool_result",
                                                        "tool_use_id": tool_use_id,
                                                        "content": error_result,
                                                        "is_error": True,
                                                    }
                                                )
                                                completed = self._format_tool_result_block(
                                                    tool_use_id,
                                                    "unknown",
                                                    {},
                                                    error_result,
                                                    is_error=True,
                                                    done=True,
                                                )
                                                if old_block:
                                                    text = final_text()
                                                    text = text.replace(old_block, completed, 1)
                                                    final_message.clear()
                                                    final_message.append(text)
                                                    await request_ctx.emit_event({"type": "replace", "data": {"content": text}})

                                            tool_use_state.progress_blocks = {}

                                    logger.debug(
                                        f" Tool use detected, collected {len(tool_calls)} tool results:\nTool_Call JSON: {tool_calls}"
                                    )

                                    tool_use_state.reset_for_iteration()
                                    has_pending_tool_calls = True
                                elif stop_reason == "max_tokens":
                                    text_state.chunk += "Claude has Reached the maximum token limit!"
                                elif stop_reason == "end_turn":
                                    conversation_ended = True
                                elif stop_reason == "pause_turn":

                                    has_pending_tool_calls = True

                                    await status.activity("⏳ Long-running turn paused, continuing...")
                                elif stop_reason == "refusal":

                                    _snap = getattr(stream, "current_message_snapshot", None)
                                    _stop_details = getattr(_snap, "stop_details", None) if _snap else None
                                    _category = getattr(_stop_details, "category", None) if _stop_details else None
                                    _explanation = getattr(_stop_details, "explanation", None) if _stop_details else None
                                    _REFUSAL_LABELS = {
                                        "cyber": "cybersecurity policy",
                                        "bio": "biological safety policy",
                                        "reasoning_extraction": "reasoning extraction policy",
                                    }
                                    _cat_label = _REFUSAL_LABELS.get(_category, "content policy") if _category else "content policy"
                                    _ref_msg = f"\u26a0\ufe0f Request declined by Claude ({_cat_label})."
                                    if _explanation:
                                        _ref_msg += f"\n\n_{_explanation}_"
                                    logger.info(f"\U0001f6ab Refusal: category={_category!r} explanation={(_explanation or '')[:120]!r}")
                                    text_state.chunk += _ref_msg
                                    conversation_ended = True
                                elif stop_reason == "stop_sequence":
                                    text_state.chunk += "Claude stopped generating based on stop sequence."
                                    conversation_ended = True
                                elif stop_reason == "model_context_window_exceeded":
                                    text_state.chunk += "Claude has reached the maximum context window for this model."
                                    conversation_ended = True
                                elif stop_reason == "compaction":

                                    has_pending_tool_calls = True
                                    logger.info("Compaction stop_reason — will auto-continue")

                            elif event_type == "message_stop":
                                pass

                            elif event_type == "message_error":
                                error = getattr(event, "error", None)
                                if error:

                                    error_details = f"Stream Error: {getattr(error, 'message', str(error))}"
                                    if hasattr(error, "type"):
                                        error_details = f"Stream Error ({error.type}): {getattr(error, 'message', str(error))}"

                                    stream_error = Exception(error_details)
                                    await self.handle_errors(
                                        stream_error, __event_emitter__
                                    )
                                    return (
                                        final_text()
                                        + f"\n\nAn error occurred: {error_details}"
                                    )

                            if text_state.chunk_count > token_buffer_size:
                                if text_state.chunk:
                                    await emit_message_delta(text_state.chunk)
                                    text_state.chunk = ""
                                    text_state.chunk_count = 0

                        sdk_final_message = stream.current_message_snapshot

                    logger.debug(f"📊 Stream events: {stream_event_counts}")

                    if (
                        getattr(self.valves, "ENABLE_CACHE_DIAGNOSTICS", False)
                        and cache_diagnostics_records
                    ):
                        try:
                            _fmsg = sdk_final_message
                            _final_diag = getattr(_fmsg, "diagnostics", None) if _fmsg else None
                            if _final_diag is None and isinstance(_fmsg, dict):
                                _final_diag = _fmsg.get("diagnostics")
                            _final_diag_dump = self._dump_sdk_obj(_final_diag) if _final_diag else None
                            _final_usage = getattr(_fmsg, "usage", None) if _fmsg else None
                            _final_usage_dump = self._dump_sdk_obj(_final_usage) if _final_usage else None
                            _rec = cache_diagnostics_records[-1]
                            if _final_diag_dump:
                                _rec["diagnostics"] = _final_diag_dump
                            if _final_usage_dump:
                                _rec["usage"] = _final_usage_dump
                            logger.info(
                                f"[CACHE-DIAG run={run_id}] final-message refresh "
                                f"chat_id={cache_diagnostics_chat_id} "
                                f"message_id={_rec.get('message_id')} "
                                f"diagnostics={_final_diag_dump}"
                            )
                        except Exception as _e:
                            logger.debug(f"[CACHE-DIAG] final-message refresh failed: {_e}")

                    conversation_ended, has_pending_tool_calls, tool_calls = await self._apply_sdk_stop_reason_fallback(
                        sdk_final_message=sdk_final_message,
                        conversation_ended=conversation_ended,
                        has_pending_tool_calls=has_pending_tool_calls,
                        tool_calls=tool_calls,
                        tool_loop_iteration=tool_loop_iteration,
                        payload_for_stream=payload_for_stream,
                        stream_event_counts=stream_event_counts,
                        request_ctx=request_ctx,
                    )

                    if text_state.chunk:
                        await emit_message_delta(text_state.chunk)
                        text_state.chunk = ""
                        text_state.chunk_count = 0

                    if has_pending_tool_calls and tool_calls:

                        tool_names = [tc.get("name", tc.get("tool_use_id", "?")) for tc in tool_calls]
                        sdk_block_types = [getattr(b, "type", "?") for b in sdk_final_message.content] if sdk_final_message else []
                        logger.info(
                            f"🔧 Tool loop iter {tool_loop_iteration} complete | "
                            f"{len(tool_calls)} tool results: {tool_names} | "
                            f"SDK blocks: {sdk_block_types}"
                        )

                        num_tool_results = sum(1 for tc in tool_calls if tc.get("type") == "tool_result")
                        current_function_calls += num_tool_results
                        if current_function_calls >= max_function_calls:
                            await status.complete(
                                f"⚠️ Maximum tool call limit ({max_function_calls}) reached. Stopping tool execution."
                            )
                            await emit_event_local(
                                {
                                    "type": "notification",
                                    "data": {
                                        "type": "warning",
                                        "content": f"Tool call limit ({max_function_calls}) reached. Increase MAX_TOOL_CALLS in valves if needed.",
                                    },
                                }
                            )
                            await emit_message_delta(
                                f"\n\n⚠️ **Tool call limit reached** ({current_function_calls}/{max_function_calls}). Some tool results may not have been processed. You can increase the limit in the model's valve settings."
                            )
                            break

                        if sdk_final_message:
                            assistant_content = self._convert_sdk_message_to_api_blocks(sdk_final_message)
                            logger.debug(
                                f"Built assistant_content from SDK message: "
                                f"{[b.get('type') for b in assistant_content]}"
                            )
                        else:

                            assistant_content = []
                            final_message_snapshot = final_text()
                            if final_message_snapshot.strip():
                                assistant_content.append({"type": "text", "text": final_message_snapshot})
                            logger.warning("No SDK message available, using text fallback")

                        if assistant_content:

                            for i, block in enumerate(assistant_content):
                                btype = block.get("type", "?")
                                if btype == "thinking":
                                    logger.debug(
                                        f"  assistant_content[{i}]: thinking "
                                        f"({len(block.get('thinking', ''))}c, "
                                        f"sig={len(block.get('signature', ''))}c)"
                                    )
                                elif btype == "redacted_thinking":
                                    logger.debug(
                                        f"  assistant_content[{i}]: redacted_thinking "
                                        f"(data={len(block.get('data', ''))}c)"
                                    )
                                elif btype == "tool_use":
                                    logger.debug(
                                        f"  assistant_content[{i}]: tool_use "
                                        f"name={block.get('name')}, id={block.get('id')}"
                                    )
                                elif btype == "text":
                                    logger.debug(
                                        f"  assistant_content[{i}]: text ({len(block.get('text', ''))}c)"
                                    )
                                else:
                                    logger.debug(f"  assistant_content[{i}]: {btype}")

                            payload_for_stream["messages"].append(
                                {"role": "assistant", "content": assistant_content}
                            )

                        tool_use_ids_in_assistant = {
                            b.get("id") for b in assistant_content
                            if b.get("type") == "tool_use"
                        }
                        tool_result_ids = {
                            b.get("tool_use_id") for b in tool_calls
                            if b.get("type") == "tool_result"
                        }
                        missing_ids = tool_use_ids_in_assistant - tool_result_ids
                        for missing_id in missing_ids:
                            logger.warning(f"⚠️ Missing tool_result for tool_use {missing_id}, adding error result")
                            tool_calls.append({
                                "type": "tool_result",
                                "tool_use_id": missing_id,
                                "content": "Error: tool execution failed - no result was produced",
                                "is_error": True,
                            })

                        user_content = tool_calls.copy()
                        if user_content:

                            payload_for_stream["messages"].append(
                                {"role": "user", "content": user_content}
                            )

                            if logger.isEnabledFor(logging.DEBUG):
                                for b in user_content:
                                    if b.get("type") == "tool_result":
                                        _content = b.get("content", "")
                                        _clen = len(_content) if isinstance(_content, str) else len(json.dumps(_content, default=str))
                                        logger.debug(
                                            f"📤 tool_result: id={b.get('tool_use_id', '?')[:25]} | "
                                            f"is_error={b.get('is_error', False)} | "
                                            f"content_size={_clen}c"
                                        )

                        if not assistant_content and not user_content:
                            logger.debug(
                                f"🔧 No valid content to add, ending conversation"
                            )
                            break

                        remaining = max_function_calls - current_function_calls
                        if remaining <= 0:

                            break
                        elif remaining == 1:

                            await status.activity(
                                f"⚠️ Final tool call available ({current_function_calls}/{max_function_calls} used)"
                            )
                            await asyncio.sleep(0.05)

                            if not self.valves.ENABLE_PROGRAMMATIC_TOOL_CALLING:
                                payload_for_stream["messages"].append(
                                    {
                                        "role": "user",
                                        "content": [
                                            {
                                                "type": "text",
                                                "text": f"⚠️ SYSTEM WARNING: Tool call limit nearly reached ({current_function_calls}/{max_function_calls} used). You have 1 tool call remaining. After the next tool use, the conversation will be automatically terminated. Please provide a comprehensive text response instead of calling more tools, and suggest the user continue manually if needed.",
                                            }
                                        ],
                                    }
                                )
                        elif remaining <= 5:

                            await status.activity(
                                f"⚠️ {remaining} tool call(s) remaining ({current_function_calls}/{max_function_calls} used)"
                            )
                            await asyncio.sleep(0.05)

                            if not self.valves.ENABLE_PROGRAMMATIC_TOOL_CALLING:
                                payload_for_stream["messages"].append(
                                    {
                                        "role": "user",
                                        "content": [
                                            {
                                                "type": "text",
                                                "text": f"[SYSTEM: {remaining} tool call(s) remaining out of {max_function_calls}. Plan your remaining tool calls carefully.]",
                                            }
                                        ],
                                    }
                                )

                        has_pending_tool_calls = False
                        tool_calls = []
                        sdk_final_message = None
                        current_tool_choice = payload_for_stream.get("tool_choice")
                        if (
                            isinstance(current_tool_choice, dict)
                            and current_tool_choice.get("type") in {"tool", "any"}
                        ):
                            payload_for_stream.pop("tool_choice", None)
                            logger.debug("Cleared forced tool_choice after tool loop iteration")
                        text_state.reset_for_iteration()
                        continue

                    elif has_pending_tool_calls and not tool_calls:
                        logger.info(
                            f"⏸️ pause_turn continuation (iter {tool_loop_iteration})"
                        )
                        if sdk_final_message:
                            assistant_content = self._convert_sdk_message_to_api_blocks(sdk_final_message)
                            if assistant_content:
                                payload_for_stream["messages"].append(
                                    {"role": "assistant", "content": assistant_content}
                                )
                        has_pending_tool_calls = False
                        sdk_final_message = None
                        text_state.reset_for_iteration()
                        continue

                    if not conversation_ended:
                        retry_attempts += 1
                        if retry_attempts <= self.valves.MAX_RETRIES:

                            sdk_block_types = (
                                [getattr(b, "type", "?") for b in getattr(sdk_final_message, "content", [])]
                                if sdk_final_message else []
                            )

                            logger.warning(
                                f"⚠️ [RUN {run_id}] Truncated stream (no stop_reason, no tool handling). "
                                f"SDK blocks: {sdk_block_types}. "
                                f"iter={tool_loop_iteration} "
                                f"diag_records={len(cache_diagnostics_records)} "
                                f"discarding {len(final_text())} char(s) of accumulated text. "
                                f"Auto-retrying ({retry_attempts}/{self.valves.MAX_RETRIES})..."
                            )
                            await status.activity(
                                f"⚠️ Stream abgebrochen, Retry ({retry_attempts}/{self.valves.MAX_RETRIES})..."
                            )

                            final_message.clear()
                            sdk_final_message = None
                            text_state.reset_for_retry()
                            request_ctx.state.thinking.reset_for_retry()
                            server_tool_state.reset_for_retry()
                            request_ctx.state.reset_current_block()

                            continue
                        else:
                            logger.error(
                                f"❌ Truncated stream: max retries ({self.valves.MAX_RETRIES}) exhausted. "
                                f"Returning error to user."
                            )
                            await request_ctx.emit_delta(
                                "\n\n⚠️ Die Anthropic API hat den Stream mehrfach abgebrochen "
                                f"({self.valves.MAX_RETRIES} Versuche). Bitte versuche es erneut."
                            )
                    break

                except Exception as e:

                    await _finalize_open_code_block(request_ctx)
                    server_tool_state.current_code = ""
                    should_retry, retry_attempts, response_suffix = await self._handle_stream_exception(
                        e,
                        retry_attempts=retry_attempts,
                        request_ctx=request_ctx,
                    )
                    if should_retry:
                        continue
                    if response_suffix:
                        return final_text() + response_suffix
                    return final_text()
        except asyncio.CancelledError:

            try:
                await status.emit("⏹️ Request Cancelled", done=True, hidden=False, force=True)
                consolidated = final_text()
                if consolidated:
                    await emit_event_local(
                        {"type": "replace", "data": {"content": consolidated}}
                    )
                await emit_event_local(
                    {
                        "type": "chat:completion",
                        "data": {
                            "choices": [
                                {"finish_reason": "stop", "delta": {"content": ""}}
                            ],
                            "done": True,
                        },
                    }
                )
            except Exception as _cancel_cleanup_err:
                logger.debug(f"Cancel cleanup emit failed: {_cancel_cleanup_err}")
            raise
        except Exception as e:
            await self.handle_errors(e, __event_emitter__)
            return final_text()

        final_status = "✅ Response Complete"

        show_token_setting = __user__["valves"].SHOW_TOKEN_COUNT
        if include_usage and show_token_setting != "Off" and total_usage and not is_internal:
            def format_num(n: int) -> str:
                if n >= 1_000_000:
                    return f"{n/1_000_000:.1f}M"
                if n >= 1_000:
                    return f"{n/1_000:.1f}K"
                return str(n)

            context_used = (
                total_usage.get("_ctx_input", 0) + total_usage.get("_ctx_output", 0)
            )
            model_info = self.get_model_info(body["model"].split("/")[-1])
            context_window = model_info.get("context_length", 200_000)
            context_label = f"{context_window // 1000}k" if context_window < 1_000_000 else f"{context_window / 1_000_000:.0f}M"
            percentage = min((context_used / context_window) * 100, 100)
            filled = int(percentage / 10)
            bar = "█" * filled + "░" * (10 - filled)

            final_status += (
                f" [{bar}] {format_num(context_used)}/{context_label} ({percentage:.1f}%)"
            )

            calls = total_usage.get("_calls", 1)
            if calls > 1:
                final_status += f" · {calls} calls"

            if (
                show_token_setting == "With Cache"
                and self.valves.CACHE_CONTROL != "cache disabled"
            ):
                ttl_label = "1hr" if self.valves.CACHE_TTL == "1 hour" else "5min"
                cache_write = total_usage.get("cache_creation_input_tokens", 0)
                cache_read = total_usage.get("cache_read_input_tokens", 0)
                fresh_input = total_usage.get("input_tokens", 0)
                billed_input = cache_write + cache_read + fresh_input
                final_status += (
                    f" | 📝 {format_num(cache_write)} ({ttl_label})"
                    f" | 📖 {format_num(cache_read)}"
                )

                if billed_input:
                    final_status += f" | ⚡ {cache_read / billed_input * 100:.0f}% cached"

        if (
            getattr(self.valves, "ENABLE_CACHE_DIAGNOSTICS", False)
            and cache_diagnostics_records
            and not is_internal
        ):
            try:
                last_id = next(
                    (rec.get("message_id") for rec in reversed(cache_diagnostics_records) if rec.get("message_id")),
                    None,
                )
                if cache_diagnostics_chat_id and last_id:
                    self._cache_diagnostics_state[cache_diagnostics_chat_id] = last_id

                if last_id:
                    try:
                        if not isinstance(new_marker_metadata, list):
                            new_marker_metadata = list(new_marker_metadata or [])
                        new_marker_metadata.append(
                            self._create_metadata_marker("cachediag", last_id)
                        )
                    except Exception as _e:
                        logger.debug(f"[CACHE-DIAG] could not persist id marker: {_e}")

                visible = next(
                    (rec for rec in cache_diagnostics_records if rec.get("diagnostics")),
                    cache_diagnostics_records[0] if cache_diagnostics_records else None,
                )
                if visible:
                    import json as _json

                    all_request_ids = [
                        rec["request_id"] for rec in cache_diagnostics_records if rec.get("request_id")
                    ]
                    all_message_ids = [
                        rec["message_id"] for rec in cache_diagnostics_records if rec.get("message_id")
                    ]
                    all_usages = [
                        rec["usage"] for rec in cache_diagnostics_records if rec.get("usage")
                    ]
                    display_obj = {}
                    if all_request_ids:
                        display_obj["request_ids"] = all_request_ids if len(all_request_ids) > 1 else all_request_ids[0]
                    if all_message_ids:
                        display_obj["message_ids"] = all_message_ids if len(all_message_ids) > 1 else all_message_ids[0]
                    if all_usages:
                        display_obj["usage"] = all_usages if len(all_usages) > 1 else all_usages[0]
                    if visible.get("diagnostics"):
                        display_obj["diagnostics"] = visible["diagnostics"]
                    body_json = _json.dumps(display_obj, indent=2, ensure_ascii=False, default=str)
                    reason = ""
                    try:
                        reason = (
                            (visible.get("diagnostics") or {})
                            .get("cache_miss_reason", {})
                            .get("type", "")
                        )
                    except Exception:
                        reason = ""
                    summary = f"Cache Diagnostics{(' — ' + reason) if reason else ''}"
                    diag_block = (
                        f'\n\n<details type="cache-diagnostics">\n'
                        f'<summary>{summary}</summary>\n\n'
                        f'```json\n{body_json}\n```\n'
                        f'</details>\n'
                    )

                    _already = final_text().count('<details type="cache-diagnostics">')
                    logger.info(
                        "[CACHE-DIAG run=%s] emit block: records=%d request_ids=%s "
                        "already_present=%d accumulated=%d char(s) fragments=%d",
                        run_id,
                        len(cache_diagnostics_records),
                        all_request_ids,
                        _already,
                        len(final_text()),
                        len(final_message),
                    )
                    if _already:
                        logger.warning(
                            "[CACHE-DIAG run=%s] DUPLICATE: %d block(s) already in the "
                            "accumulated text before emitting request_ids=%s — "
                            "finalisation ran more than once for this message",
                            run_id,
                            _already,
                            all_request_ids,
                        )
                    await request_ctx.emit_delta(diag_block)
            except Exception as e:
                logger.warning(f"[CACHE-DIAG] failed to emit diagnostics block: {e}")

        if new_marker_metadata and not is_internal:
            marker_text = "".join(new_marker_metadata) if isinstance(new_marker_metadata, list) else str(new_marker_metadata)
            if marker_text:
                final_message.append(marker_text)
                logger.debug("Persisted %d metadata marker char(s)", len(marker_text))

        consolidated = final_text()

        logger.info(
            "[RUN %s] final replace: %d char(s), %d diagnostics block(s), %d fragment(s)",
            run_id,
            len(consolidated),
            consolidated.count('<details type="cache-diagnostics">'),
            len(final_message),
        )
        if consolidated:
            await emit_event_local(
                {"type": "replace", "data": {"content": consolidated}}
            )

        await status.complete(final_status)

        done_data: dict = {"choices": [{"finish_reason": "stop", "delta": {"content": ""}}], "done": True}
        if include_usage and total_usage:
            done_data["usage"] = self._public_usage(total_usage)
        await emit_event_local({"type": "chat:completion", "data": done_data})

        if include_usage and total_usage and CHATS_AVAILABLE and __metadata__:
            chat_id = __metadata__.get("chat_id")
            message_id = __metadata__.get("message_id")
            if chat_id and message_id and not str(chat_id).startswith("local:"):
                try:
                    await Chats.upsert_message_to_chat_by_id_and_message_id(
                        chat_id, message_id, {"usage": self._public_usage(total_usage)}
                    )
                except Exception as e:
                    logger.warning(f"Failed to persist usage to chat_message: {e}")

        return final_text()

    async def _create_payload(
        self,
        body: Dict,
        __metadata__: dict[str, Any],
        __user__: Dict[str, Any],
        __tools__: Optional[Dict[str, Dict[str, Any]]],
        __event_emitter__: Callable[[Dict[str, Any]], Awaitable[None]],
        __files__: Optional[List[Dict[str, Any]]] = None,
    ) -> tuple[dict, dict, List[str]]:
        return await create_request_payload(
            self, body, __metadata__, __user__, __tools__, __event_emitter__, __files__
        )

    _SANITIZE_BLOCK_KEYS = {
        "thinking": {"type", "thinking", "signature"},
        "redacted_thinking": {"type", "data"},
    }

    _SKIP_BLOCK_TYPES = frozenset({"context_cleared"})

    METADATA_PATTERN = re.compile(r"\[\]\(anthropic:([^)]+)\)")
