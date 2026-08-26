"""
title: Anthropic API Integration
id: anthropic_new
author: Podden (https://github.com/Podden/)
github: https://github.com/Podden/openwebui_anthropic_api_manifold_pipe
original_author: Balaxxe (Updated by nbellochi)
version: 0.9.27
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
v0.9.27
- Fixed model display names being lost while the model list is served from cache: the cached entries were built without the stored `_display_name`, so the picker fell back to raw ids for the whole cache TTL (#47, reported by @clang13)
- Fixed a follow-up request 400 ("tool use found without a corresponding tool_result block") after a turn with several Anthropic-hosted code-execution calls: the stored carriers interleave, and replaying them in document order separated a server_tool_use from its result. Results are now pulled forward next to their tool_use (#40, by @JaWoDigiB)
- Fixed error notices and the File Content collapsible being swallowed into the preceding paragraph: code-execution / text-editor errors and safety refusals now go through the same own-line guarantee as every other rendered block (#46, by @Willian-Zhang)
- Fixed an empty SKILLS valve triggering the code_execution notification: OpenWebUI stores an empty array valve as "", which round-trips back as [""], and that is truthy. Blank entries are now dropped (#48, reported by @clang13)

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
- Added Claude Opus 5 (claude-opus-5): 1M context, 128k output, thinking on by default, full effort ladder incl. max, fast mode (#45, by @AliD101v)
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
    # anthropic SDK < 0.45 doesn't have OverloadedError
    # Create a placeholder that will never match (handled via APIStatusError instead)
    class OverloadedError(Exception):
        pass
from typing import Literal
from fastapi import Request

logger = logging.getLogger(__name__)

# =============================================================================
# COMPILED REGEX PATTERNS
# Pre-compiled patterns for performance - avoids re-compiling on every call
# =============================================================================

# NOTE: Thinking blocks must NEVER be removed from assistant messages!
# Per Anthropic API docs:
# - During tool use loops: thinking blocks MUST be preserved unmodified in assistant content
# - Multi-turn: thinking blocks from prior turns CAN be omitted (API filters them),
#   but preserving them is preferred
# - The entire sequence of consecutive thinking blocks must match the original model output
# - signature field is critical and must be preserved exactly
# - Interleaved thinking (Claude 4): thinking blocks can appear BETWEEN tool calls
# Previously PATTERN_THINKING_BLOCK was defined here but never used - removed as dead code.

# Patterns to extract memories injected by the OpenWebUI Memory System into the
# system prompt. Both forms are volatile: OpenWebUI re-retrieves and re-ranks the
# memories per request, so leaving them in `system` reports back from the API as
# cache_miss_reason=system_changed on every single turn. They are relocated to the
# last user message instead, which sits behind the cached prefix.
#
# Legacy form: everything after "\nUser Context:\n" to end of string.
PATTERN_USER_CONTEXT = re.compile(r"\nUser Context:\n(.*)$", flags=re.DOTALL)
# Current form (utils/memory.py): a <memory_context> element, appended or
# prepended to the system message depending on OpenWebUI version.
PATTERN_MEMORY_CONTEXT = re.compile(
    r"<memory_context>(.*?)</memory_context>", flags=re.DOTALL
)

# Header the relocated memories are prefixed with when they are appended to the
# last user message. Single source of truth: the injector writes it and
# _cache_last_stable_message recognises it to keep the breakpoint off a message
# carrying volatile content. If the two ever drift apart, the memories land
# inside the cached prefix and every turn pays a rewrite of the whole history.
MEMORY_CONTEXT_APPENDIX_HEADER = (
    "\n\n---\n**IMPORTANT:** The following is NOT part of the user's message, "
    "but context from a memory system to help answer the user's questions:\n\n"
)

# Patterns for RAG template cleanup when all sources are native PDFs
PATTERN_RAG_TEMPLATE_WITH_CONTEXT = re.compile(
    r"###\s*Task:.*?<context>.*?</context>", flags=re.DOTALL | re.MULTILINE
)
PATTERN_RAG_TEMPLATE_FALLBACK = re.compile(
    r"###\s*Task:.*?$", flags=re.DOTALL | re.MULTILINE
)
PATTERN_EMPTY_CONTEXT = re.compile(r"<context>\s*</context>", flags=re.DOTALL)

# Pattern to find remaining source tags (for checking if all were removed)
PATTERN_SOURCE_TAGS = re.compile(r"<source[^>]*>.*?</source>", flags=re.DOTALL)

# RAG message detection: matches "### Task:...<context>...</context>" blocks
PATTERN_RAG_MESSAGE = re.compile(r"### Task:.*?<context>.*?</context>", re.DOTALL)

# Individual <source> tag with name attribute extraction
PATTERN_SOURCE_TAG = re.compile(
    r'<source[^>]*name="([^"]+)"[^>]*>.*?</source>\s*', re.DOTALL
)

# Empty <attached_files> blocks after file tag removal
PATTERN_EMPTY_ATTACHED = re.compile(
    r"<attached_files>\s*</attached_files>\s*", re.DOTALL
)

# Pattern to strip OpenWebUI <details type="tool_calls"> blocks from conversation history.
# These are UI-rendering artifacts that cause Claude 4.6 models to pattern-match and
# generate fake tool call HTML instead of making actual API tool_use calls.
# NOTE: negative lookahead excludes our persisted server-tool carrier blocks
# (which also use type="tool_calls" so OpenWebUI's Svelte parser groups them
# with adjacent <details type="reasoning"> / <details type="code_interpreter">).
# Those carriers are identified by data-payload-b64 and processed separately.
PATTERN_TOOL_CALLS_DETAILS = re.compile(
    r'\n?<details type="tool_calls"(?![^>]*data-payload-b64=)[^>]*>.*?</details>\n?',
    flags=re.DOTALL,
)

# Pattern to MATCH (not strip) <details type="tool_calls"> blocks for structured
# reconstruction into tool_use/tool_result Claude API blocks on replay.
# Group 1 captures the attributes string (id, name, arguments, result, done, error).
# Attribute values are html.escape()'d JSON — no raw '"' inside — so a simple
# `(\w+)="([^"]*)"` attribute parser is safe.
# Negative lookahead mirrors PATTERN_TOOL_CALLS_DETAILS so server-tool carriers
# don't get pulled into the client-side tool_use reconstruction path.
PATTERN_TOOL_CALLS_BLOCK = re.compile(
    r'\n?<details type="tool_calls"(?![^>]*data-payload-b64=)([^>]*)>.*?</details>\n?',
    flags=re.DOTALL,
)
PATTERN_TOOL_CALLS_ATTRS = re.compile(r'(\w+)="([^"]*)"')

# Pattern to MATCH <details type="reasoning"> blocks for reconstruction into
# structured Claude API ``thinking`` blocks on replay. Group 1 captures the
# attribute string (for signature extraction), group 2 captures the body
# (between </summary> and </details>) where each line is prefixed with "> ".
# The signature is stored as ``data-signature="..."`` (html.escape'd) and
# must be html.unescape'd before being sent back to the API byte-exact.
PATTERN_REASONING_BLOCK = re.compile(
    r'\n?<details type="reasoning"([^>]*)>\s*<summary>[^<]*</summary>\s*(.*?)\s*</details>\n?',
    flags=re.DOTALL,
)
# Matches a quoted-line body: strips the leading "> " prefix per line.
PATTERN_REASONING_QUOTED_LINE = re.compile(r'^>\s?', flags=re.MULTILINE)

# Patterns to MATCH persisted server-tool carrier blocks for round-trip
# reconstruction into structured Claude API blocks.
#
# CARRIER FORMAT: <details type="tool_calls" data-block-kind="server_tool_use|server_tool_result" data-payload-b64="...">
#
# type="tool_calls" is critical: OpenWebUI's Svelte parser
# (GROUPABLE_DETAIL_TYPES = {'tool_calls','reasoning','code_interpreter'})
# only merges consecutive <details> into the single "Exploring/Explored"
# bubble when all siblings use one of those three types. Using a custom type
# like "server_tool_use" placed BETWEEN reasoning and code_interpreter blocks
# breaks the group and renders as three separate collapsibles.
#
# data-block-kind disambiguates server-tool carriers from regular OpenWebUI
# tool_calls UI blocks (which we still want to strip via
# PATTERN_TOOL_CALLS_DETAILS above).
#
# The opaque block payload (id, name, input for server_tool_use;
# tool_use_id + content array for *_tool_result) is stored as a base64-encoded
# JSON blob in ``data-payload-b64`` for byte-exact round-trip — preserving
# thinking-block ordering (otherwise: 400 "thinking blocks cannot be modified")
# and prompt-cache prefix stability.
PATTERN_SERVER_TOOL_USE_BLOCK = re.compile(
    r'\n?<details type="tool_calls"([^>]*?data-block-kind="server_tool_use"[^>]*)>.*?</details>\n?',
    flags=re.DOTALL,
)
PATTERN_SERVER_TOOL_RESULT_BLOCK = re.compile(
    r'\n?<details type="tool_calls"([^>]*?data-block-kind="server_tool_result"[^>]*)>.*?</details>\n?',
    flags=re.DOTALL,
)
# Generic data-* attribute extractor for server-tool block attrs.
PATTERN_DATA_ATTR = re.compile(r'data-([\w-]+)="([^"]*)"')

# Invisible carrier for content blocks the user hid via HIDE_BLOCKS. A markdown
# link reference definition renders as nothing at all (the tokenizer folds it
# into the link table and emits no token), while still round-tripping the
# base64 API payload through OpenWebUI storage. Anchored to line starts because
# that is the only position where markdown treats it as a definition.
PATTERN_HIDDEN_BLOCK = re.compile(
    r"^[ ]{0,3}\[anthropic-hidden[^\]]*\]:[ ]*#([A-Za-z0-9+/=]+)[ ]*$\n?",
    flags=re.MULTILINE,
)

# Which block concepts the *current* request's user hid via UserValves.HIDE_BLOCKS.
# A ContextVar rather than an attribute on the Pipe instance: OpenWebUI keeps one
# Pipe object for all users, so an attribute would leak one user's preference into
# a concurrently streaming request. Formatters are reached through a long call
# chain that has no request context, and threading one through every block
# formatter for a display preference is not worth the churn.
HIDDEN_BLOCKS: contextvars.ContextVar[frozenset] = contextvars.ContextVar(
    "anthropic_pipe_hidden_blocks", default=frozenset()
)

# True while serving an OpenWebUI sub-agent run (request.state.internal). The
# response is then not read by a human but pasted verbatim into the PARENT
# agent's context, so every decoration is pure token cost there: collapsibles
# carry markup a human never sees, and the invisible base64 carriers exist only
# to rebuild API blocks on a later turn -- which cannot happen, because a
# sub-agent run is a single request (its iteration cap is the in-request tool
# loop, not a multi-turn conversation). Same ContextVar reasoning as
# HIDDEN_BLOCKS: one Pipe object serves concurrent requests.
SLIM_OUTPUT: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "anthropic_pipe_slim_output", default=False
)

# Human-in-the-loop tool approval (OpenWebUI 0.11.1+). OpenWebUI enforces its own
# approval gate inside `utils/middleware.py`, which only covers ITS tool loop --
# a manifold that runs its own loop bypasses the gate entirely. We re-implement
# it at the single point where a tool coroutine is actually awaited.
#
# Holds `(mode, event_call)` for the current request: `mode` is
# `__metadata__["params"]["tool_approval_mode"]` ("full" = run freely, "ask" =
# confirm each call), `event_call` is OpenWebUI's blocking `__event_call__`.
# Same ContextVar reasoning as HIDDEN_BLOCKS: one Pipe object serves concurrent
# requests, so this must not live on `self`.
TOOL_APPROVAL: contextvars.ContextVar[tuple] = contextvars.ContextVar(
    "anthropic_pipe_tool_approval", default=("full", None)
)

# Pattern to strip OpenWebUI <details type="code_interpreter"> blocks from conversation history.
PATTERN_CODE_INTERPRETER_DETAILS = re.compile(
    r'\n?<details type="code_interpreter"[^>]*>.*?</details>\n?',
    flags=re.DOTALL,
)

# Pattern to strip debug-only cache trace blocks from assistant replay.
# These blocks are written to OpenWebUI message content for post-mortem analysis,
# but they were never part of Anthropic's assistant response and must not be sent
# back on the next turn (otherwise the trace feature breaks the very cache it
# diagnoses).
PATTERN_CACHE_TRACE_DETAILS = re.compile(
    r'\n*<details type="cache-trace"[^>]*>.*?</details>\n*',
    flags=re.DOTALL,
)

# Pattern to extract compaction blocks from assistant messages for API reconstruction.
PATTERN_COMPACTION_DETAILS = re.compile(
    r'<details type="compaction"[^>]*>\s*<summary>[^<]*</summary>\s*(.*?)\s*</details>',
    flags=re.DOTALL,
)

# Pattern to detect base64 image data URIs embedded in a client tool's raw
# result string (e.g. a file-reading tool returning a PNG/JPEG). Used to
# convert them into real Anthropic image blocks instead of raw base64 TEXT.
PATTERN_TOOL_RESULT_DATA_IMAGE = re.compile(
    r"data:image/(?P<mime>jpeg|png|gif|webp);base64,(?P<data>[A-Za-z0-9+/]+=*)"
)

# Patterns used to reduce a task request to plain prose. Task requests
# (title/tag/follow-up generation, and OpenWebUI's memory background review)
# are one-shot: nothing is replayed, so every collapsible, carrier and inline
# marker in the transcript is pure noise that the task model has to pay for and
# reason around. The memory reviewer is the worst case — it truncates each
# message to 1600 characters, so a cache-diagnostics dump can crowd out the
# actual conversation it is supposed to review.
PATTERN_ANY_DETAILS = re.compile(r"\n?<details[^>]*>.*?</details>\n?", flags=re.DOTALL)
PATTERN_INLINE_METADATA_MARKER = re.compile(r"[ ]?\[\]\(anthropic:[^)]*\)[ ]?")
# Removing a marker or carrier leaves the line it sat on whitespace-only, which
# the blank-line collapse below would otherwise treat as content.
PATTERN_TRAILING_SPACES = re.compile(r"[ \t]+$", flags=re.MULTILINE)
PATTERN_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")

# Note: Some patterns are compiled dynamically at runtime because they depend
# on user-provided data (filenames). See:
#   - _remove_specific_sources_from_rag_message() - dynamic filename pattern

# =============================================================================
# IMPORTS
# =============================================================================

# Import OpenWebUI Models for auto-enabling native function calling
try:
    from open_webui.models.models import Models, ModelForm

    MODELS_AVAILABLE = True
except ImportError:
    Models = None
    ModelForm = None
    MODELS_AVAILABLE = False

# =============================================================================
# SECRET VALVE ENCRYPTION
# =============================================================================
# OpenWebUI can encrypt valves at rest itself since 0.10.0, but only when
# ENABLE_VALVE_ENCRYPTION is set -- it defaults to False (see
# open_webui/env.py and open_webui/utils/valves.py). On a default install of any
# version the API key therefore sits in the functions table in plaintext, which
# is what this covers.
#
# The key derivation below matches OpenWebUI's own (_fernet in utils/valves.py)
# on purpose, so both layers behave identically where they overlap. With their
# flag on, the value ends up encrypted twice, which is harmless. Every step here
# is a no-op for values that are not encrypted, so existing plaintext valves
# keep working and nothing has to be migrated.
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

# Whether OpenWebUI encrypts valves at rest itself. Checked instead of comparing
# version numbers: the constant only exists from 0.10.0, and it reflects the
# actual ENABLE_VALVE_ENCRYPTION setting rather than what the release could do.
# Missing (older releases) or False means the key would land in the DB in
# plaintext, so the pipe encrypts it itself.
try:
    from open_webui.env import ENABLE_VALVE_ENCRYPTION as OPENWEBUI_ENCRYPTS_VALVES
except Exception:
    OPENWEBUI_ENCRYPTS_VALVES = False


def _valve_encryption_key() -> Optional[bytes]:
    """Fernet key from WEBUI_SECRET_KEY, derived the same way OpenWebUI does it.

    Returns None when encryption is unavailable or no secret is configured; the
    callers then pass values through unchanged rather than failing.
    """
    if not VALVE_ENCRYPTION_AVAILABLE:
        return None
    secret = os.environ.get("WEBUI_SECRET_KEY", "").strip()
    if not secret:
        return None
    # A 44-char secret may already be a valid Fernet key; use it directly.
    if len(secret) == 44:
        try:
            Fernet(secret.encode())
            return secret.encode()
        except Exception:
            pass
    return base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())


def encrypt_valve_secret(value: str) -> str:
    """Encrypt a valve value. Idempotent, and a no-op without a secret key.

    Skipped when OpenWebUI encrypts valves itself -- doing it twice with the
    same cipher and the same key buys nothing and only adds a way to fail.

    Idempotency is load-bearing: OpenWebUI re-validates the whole Valves model
    every time an admin saves the valve page, so an already-encrypted value is
    handed back in. Encrypting it again each save would nest the ciphertext.
    """
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
    """Return the plaintext behind a valve value.

    Values without the marker prefix are returned unchanged, which covers
    plaintext valves from installs that predate this, defaults, and setups
    without WEBUI_SECRET_KEY.

    Deliberately not gated on OPENWEBUI_ENCRYPTS_VALVES: a key encrypted while
    that flag was off must stay readable after an admin turns it on.
    """
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
        """Valve field type that keeps its value encrypted at rest.

        OpenWebUI persists `Valves(**form_data).model_dump()`, so the value the
        validator returns is what reaches the database.
        """

        @classmethod
        def _validate(cls, value: Any) -> "EncryptedStr":
            return cls(encrypt_valve_secret(str(value or "")))

        @classmethod
        def __get_pydantic_core_schema__(cls, source_type, handler):
            return core_schema.no_info_after_validator_function(
                cls._validate, core_schema.str_schema()
            )

        def get_secret(self) -> str:
            """Plaintext value. Raises ValueError if the secret key changed."""
            return decrypt_valve_secret(self)

else:  # pragma: no cover - pydantic v2 always ships pydantic_core
    EncryptedStr = str


# Import OpenWebUI builtin tools helper
try:
    from open_webui.utils.tools import get_builtin_tools

    BUILTIN_TOOLS_AVAILABLE = True
except ImportError:
    get_builtin_tools = None
    BUILTIN_TOOLS_AVAILABLE = False

# Import process_tool_result for Rich UI (HTMLResponse, embeds, files)
try:
    from open_webui.utils.middleware import process_tool_result

    PROCESS_TOOL_RESULT_AVAILABLE = True
except ImportError:
    process_tool_result = None
    PROCESS_TOOL_RESULT_AVAILABLE = False

# Import OpenWebUI Files and Storage for PDF native upload
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

# Import OpenWebUI Chats for persisting usage to chat_message table (0.9.0+ analytics)
try:
    from open_webui.models.chats import Chats

    CHATS_AVAILABLE = True
except ImportError:
    Chats = None
    CHATS_AVAILABLE = False

# Import Pillow for downscaling images embedded in client tool results.
# Optional: degrade gracefully (send original image / skip resize) if absent.
try:
    from PIL import Image as PILImage

    PIL_AVAILABLE = True
except Exception:
    PILImage = None
    PIL_AVAILABLE = False

@dataclass
class PipeRenderStrategy:
    """Per-request rendering strategy toggles (no shared state across users)."""

    stream_reasoning_live: bool = True
    stream_code_execution_live: bool = False
    stream_tool_results_live: bool = False


# BEGIN GENERATED SECTION: anthropic_pipe.response.state
# END GENERATED SECTION: anthropic_pipe.response.state


@dataclass
class PipeRequestContext:
    """Request-scoped helpers and stream state — the single object handlers receive.

    Handlers take ``(event, ctx)`` and reach everything through here instead of
    accepting a pile of keyword arguments and returning dicts the caller has to
    unpack back into locals. Mutable per-block state lives on ``state``; the
    request-scoped dependencies below are populated by ``pipe()`` once auth and
    tool resolution are done.
    """

    pipe: Any
    event_emitter: Callable[[Dict[str, Any]], Awaitable[None]]
    render_strategy: PipeRenderStrategy = field(default_factory=PipeRenderStrategy)
    final_message: list[str] = field(default_factory=list)
    state: StreamState = field(default_factory=StreamState)
    # Correlation id for one `pipe()` invocation. Logged on every lifecycle line
    # so interleaved runs — retries, concurrent turns, two runs writing into the
    # same OpenWebUI message — can be told apart in the container log.
    run_id: str = field(default_factory=lambda: os.urandom(4).hex())

    # Populated by pipe() after auth/tool setup; handlers read them via ctx.
    # `status` is a StatusEmitter, typed loosely because its class is compiled
    # into a generated section further down this file.
    status: Any = None
    user: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tools: Optional[Dict[str, Any]] = None
    builtin_tools: Dict[str, Any] = field(default_factory=dict)
    api_tool_names: List[str] = field(default_factory=list)
    api_key: str = ""

    async def emit_event(self, event: dict) -> None:
        """Forward an event to the pipe's event emitter."""
        await self.pipe.emit_event(event, self.event_emitter)

    async def emit_delta(self, content: str) -> None:
        """Emit a streaming content delta and append it to the accumulated message."""
        await self.emit_event({"type": "message", "data": {"content": content}})
        self.final_message.append(content)

    async def emit_block(self, block: str) -> None:
        """Emit a rendered block, guaranteeing it starts on its own line.

        Separating a block from preceding prose is the block's job, not the text
        handler's. Text content_blocks are arbitrary fragments — Anthropic splits
        them mid-table, mid-list and mid-bold around citations — so a newline added
        when a text block *ends* lands inside markdown constructs and breaks them.
        Same rule as `_append_block_to_text`, applied on the streaming delta path.
        """
        if (
            block
            and self.final_message
            and not self.text().endswith(("\n", "\r"))
            and not block.startswith(("\n", "\r"))
        ):
            block = "\n" + block
        await self.emit_delta(block)

    async def emit_replace(self, content: str) -> None:
        """Emit a full-content replace event and reset the accumulated message to it."""
        await self.emit_event({"type": "replace", "data": {"content": content}})
        self.final_message.clear()
        self.final_message.append(content)

    async def update_content_block(self, old_block: str, new_block: str) -> None:
        """Replace old_block in accumulated content with new_block, preserving surrounding text."""
        if not old_block and not new_block:
            # Slim (sub-agent) output formats every collapsible to "". Without
            # this the fall-through below would append nothing and still emit a
            # full replace per block lifecycle event.
            return
        if old_block:
            text = self.text()
            idx = text.find(old_block)
            if idx != -1:
                text = text[:idx] + new_block + text[idx + len(old_block):]
                await self.emit_replace(text)
                return
        # First emit or old block not found — append and replace with full text
        text = self.pipe._append_block_to_text(self.text(), new_block)
        await self.emit_replace(text)

    def text(self) -> str:
        """Return the accumulated message content as a single string."""
        return "".join(self.final_message)


# Generated sections are filled in place by helpers/build_anthropic_pipe.py.
# Their ORDER here is the order in the compiled artifact, and it is load-bearing:
# the build strips `from __future__ import annotations`, so a name must already
# exist when a later section annotates against it. Handlers and registry sit
# below PipeRequestContext because they annotate `ctx: PipeRequestContext`.

# BEGIN GENERATED SECTION: anthropic_pipe.request_payload
# END GENERATED SECTION: anthropic_pipe.request_payload

# BEGIN GENERATED SECTION: anthropic_pipe.response.handlers
# END GENERATED SECTION: anthropic_pipe.response.handlers

# BEGIN GENERATED SECTION: anthropic_pipe.response.registry
# END GENERATED SECTION: anthropic_pipe.response.registry

# BEGIN GENERATED SECTION: anthropic_pipe.response.status_events
# END GENERATED SECTION: anthropic_pipe.response.status_events

# BEGIN GENERATED SECTION: anthropic_pipe.response.text_block
# END GENERATED SECTION: anthropic_pipe.response.text_block

# BEGIN GENERATED SECTION: anthropic_pipe.response.thinking_block
# END GENERATED SECTION: anthropic_pipe.response.thinking_block

# BEGIN GENERATED SECTION: anthropic_pipe.response.compaction_block
# END GENERATED SECTION: anthropic_pipe.response.compaction_block

# BEGIN GENERATED SECTION: anthropic_pipe.response.client_tool
# END GENERATED SECTION: anthropic_pipe.response.client_tool

# BEGIN GENERATED SECTION: anthropic_pipe.response.server_tool
# END GENERATED SECTION: anthropic_pipe.response.server_tool

# BEGIN GENERATED SECTION: anthropic_pipe.response.code_execution_results
# END GENERATED SECTION: anthropic_pipe.response.code_execution_results

# BEGIN GENERATED SECTION: anthropic_pipe.response.web_tool_results
# END GENERATED SECTION: anthropic_pipe.response.web_tool_results

# BEGIN GENERATED SECTION: anthropic_pipe.response.internal_tool_results
# END GENERATED SECTION: anthropic_pipe.response.internal_tool_results






class Pipe:
    API_VERSION = "2023-06-01"  # Current API version as of May 2025
    _DEFAULT_API_BASE = "https://api.anthropic.com"

    # Capability overrides for fields NOT available from the /v1/models API.
    # The API now provides: max_tokens, max_input_tokens, capabilities (thinking, effort, vision, etc.)
    # These overrides only contain flags that must be derived from model identity.
    # Static max-output-token fallbacks, used ONLY when the /v1/models API does not
    # report max_tokens (custom/Azure endpoints, ENABLED_MODELS manual ids). The
    # live API value always wins for direct Anthropic. Keyed by base (suffix-stripped) id.
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

    # Static context-window fallbacks for the 1M-context models, used ONLY when
    # /v1/models does not report max_input_tokens (custom/Azure endpoints,
    # ENABLED_MODELS manual ids). The live API value always wins; the generic
    # default stays 200k.
    # The 1M window is generally available on the current models and billed at
    # the 200k rate, so no beta header gates it any more. Values mirror
    # max_input_tokens as reported by /v1/models (verified 2026-08-10); Haiku 4.5
    # and Opus 4.5 are the 200k exceptions and stay on the generic default.
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

    # Identity-keyed capability fixups, applied on top of whatever /v1/models
    # reports (and on top of the static defaults when it reports nothing).
    #
    # `supports_adaptive_thinking` is listed here even though the API does
    # advertise it: get_model_info's static fallback has to default it to False,
    # and endpoints that serve no capability metadata (Azure and other proxies,
    # or ids named manually via ENABLED_MODELS) never overwrite that. The pipe
    # then sends explicit `budget_tokens` thinking plus temperature/top_p to a
    # model that wants `thinking:{"type":"adaptive"}` and no sampling params --
    # which the API rejects. Pinning it per identity makes those endpoints
    # behave like the direct one.
    MODEL_CAPABILITY_OVERRIDES = {
         "claude-fable-5": {
            "supports_dynamic_filtering": True,
            "supports_compaction": True,
            "supports_adaptive_thinking": True,
            "supports_structured_outputs": True,
        },
         # Deliberately identical to claude-fable-5, its sibling: no account we
         # can query is entitled to Mythos, so its capabilities cannot be read
         # off /v1/models. Keep the two in lockstep rather than guessing
         # separately (locked in by a parity test).
         "claude-mythos-5": {
            "supports_dynamic_filtering": True,
            "supports_compaction": True,
            "supports_adaptive_thinking": True,
            "supports_structured_outputs": True,
        },
        # No capability fixups of their own, but they still need the structured
        # outputs pin: task requests fire on a freshly loaded Pipe whose API
        # capability cache is still empty, and Haiku 4.5 is the default
        # MEMORY_REVIEW_MODEL. All three report structured_outputs support and
        # no adaptive thinking (verified 2026-08-10).
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
            # Opus 5 runs with thinking ON unless thinking:{"type":"disabled"}
            # is sent explicitly. Disabling is rejected at effort xhigh/max.
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
            # Fast mode removed for Opus 4.7 (2026-07-24): speed:"fast" now
            # returns an error instead of falling back to standard speed.
            # Use Opus 5 or Opus 4.8 for fast mode.
            "supports_compaction": True,
            "supports_adaptive_thinking": True,
            "supports_structured_outputs": True,
        },
        "claude-opus-4-6": {
            "supports_dynamic_filtering": True,
            # Fast mode removed for Opus 4.6 (2026-06-29): speed:"fast" is now a
            # silent no-op billed at standard rate. Don't send it. Use Opus 4.8.
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

    # Cached model capabilities from API (populated by get_anthropic_models)
    _api_capabilities_cache: Dict[str, dict] = {}
    _api_capabilities_cache_ts: float = 0.0
    _API_CACHE_TTL = 86400  # 24 hours; overridden by MODEL_CACHE_TTL_MINUTES
    # Fingerprint of the connection settings the cached model list was fetched
    # with. A changed key, base URL, workspace or allow-list must invalidate the
    # cache immediately -- otherwise pointing the pipe at a different endpoint
    # keeps serving the previous endpoint's models until the TTL expires.
    _api_capabilities_cache_sig: str = ""

    REQUEST_TIMEOUT = (
        300  # Default; overridden by valve REQUEST_TIMEOUT
    )
    THINKING_BUDGET_TOKENS = 4096  # Default thinking budget tokens (max 16K)
    TOOL_CALL_TIMEOUT = 120  # Default; overridden by valve TOOL_CALL_TIMEOUT

    # =========================================================================
    # MODEL INFO & INITIALIZATION
    # =========================================================================



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
            """Accept the pre-v0.9.25 comma-separated string form.

            HIDE_BLOCKS used to be a `str`. Existing users have one stored, and
            OpenWebUI validates the whole UserValves model on every save — so
            without this, a saved `""` makes *every* valve update fail with a
            400 until the user manually clears the field.
            """
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
        # Advisor tool (advisor-tool-2026-03-01) — per-user
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
        # Files API and Skills Settings
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
        """Initialize pipe identity, valves, and per-instance caches."""
        self.type = "manifold"
        self.id = "anthropic"
        self.valves = self.Valves()
        self.logger = logger
        self._validated_skills_cache: Dict[str, Dict[str, Optional[Dict[str, Any]]]] = (
            {}
        )
        # Per-chat_id cache of last request's messages[] signature list,
        # used by _log_message_hash_diff to identify byte-drift between turns
        # that invalidates the Anthropic prompt cache.
        self._cache_diff_state: Dict[str, List[Tuple[str, str, str]]] = {}
        # Per-chat_id cache of the last Anthropic response id. Used by the cache
        # diagnostics beta (`cache-diagnosis-2026-04-07`) to pass
        # `diagnostics.previous_message_id` on the next turn so the API can
        # report where the prompt-cache prefix diverged.
        self._cache_diagnostics_state: Dict[str, str] = {}

    # COMPILED PIPE METHOD GROUPS INSERTION POINT




    # =========================================================================
    # PDF & FILE HANDLING
    # =========================================================================



    # =========================================================================
    # RAG (RETRIEVAL-AUGMENTED GENERATION) HANDLING
    # =========================================================================




    # =========================================================================
    # FILES API (UPLOAD, DOWNLOAD, DEDUPLICATION)
    # =========================================================================



    # =========================================================================
    # CACHE CONTROL
    # =========================================================================














    # =========================================================================
    # PAYLOAD BUILDING & MESSAGE/TOOL CONVERSION
    # =========================================================================

    async def _create_payload(
        self,
        body: Dict,
        __metadata__: dict[str, Any],
        __user__: Dict[str, Any],
        __tools__: Optional[Dict[str, Dict[str, Any]]],
        __event_emitter__: Callable[[Dict[str, Any]], Awaitable[None]],
        __files__: Optional[List[Dict[str, Any]]] = None,
    ) -> tuple[dict, dict, List[str]]:
        """Build the Anthropic request payload and headers from the incoming request."""
        return await create_request_payload(
            self, body, __metadata__, __user__, __tools__, __event_emitter__, __files__
        )










    # =========================================================================
    # MAIN ENTRY POINT
    # =========================================================================


    # =========================================================================
    # TASK MODEL (TITLE, TAGS, FOLLOW-UPS)
    # =========================================================================



    # =========================================================================
    # ERROR HANDLING
    # =========================================================================


    # =========================================================================
    # TEXT PROCESSING & MEMORY EXTRACTION
    # =========================================================================


    # =========================================================================
    # CITATIONS & EVENT EMISSION
    # =========================================================================



    # =========================================================================
    # SDK MESSAGE CONVERSION HELPER
    # Converts SDK BetaMessage content blocks to API-compatible dicts
    # =========================================================================
    # CRITICAL: All blocks must be preserved to maintain thinking block positions.
    # The SDK (and Anthropic's tool runner) keeps ALL blocks as-is when sending
    # assistant content back during tool loops. Stripping server_tool_use or
    # *_tool_result shifts thinking block indices, causing:
    #   "thinking blocks cannot be modified"
    # Only strip truly structural meta-events (context_cleared).
    # Compaction blocks MUST be preserved — the API uses them to drop prior context.
    #
    # Thinking + redacted_thinking get strict key sanitization to prevent
    # cache_control or other extra fields from causing API errors.

    # Block types that must be strictly sanitized (extra keys cause API errors)
    _SANITIZE_BLOCK_KEYS = {
        "thinking": {"type", "thinking", "signature"},  # signature MUST be preserved exactly
        "redacted_thinking": {"type", "data"},           # opaque data, pass through unchanged
    }

    # Block types to skip entirely (structural meta-events)
    _SKIP_BLOCK_TYPES = frozenset({"context_cleared"})


    # =========================================================================
    # IMMEDIATE BLOCK FORMATTING HELPERS
    # These format individual blocks immediately when they finish streaming
    # =========================================================================



    # =========================================================================
    # SKILLS VALIDATION AND CONTAINER BUILDING
    # =========================================================================


    # =========================================================================
    # METADATA PERSISTENCE SYSTEM
    # Stores metadata in empty markdown links that OpenWebUI doesn't render
    #
    # NEW COMPACT FORMAT for message-level file tracking:
    # [](anthropic:m=1:fid1,fid2|3:fid3;p=1:pid1|2:pid2;c=container_xyz;u=file.csv:aid1,doc.pdf:aid2)
    #
    # Keys:
    #   m = Files API: msg_idx:file_id,file_id|msg_idx:file_id
    #   p = Native PDFs: msg_idx:openwebui_id,openwebui_id|msg_idx:openwebui_id
    #   c = Container ID (single, reused across conversation)
    #   u = Uploaded file mapping: filename:anthropic_id,filename:anthropic_id
    #
    # CRITICAL: Only the LAST assistant message persists between requests.
    # We must accumulate ALL state in EVERY response.
    # =========================================================================

    METADATA_PATTERN = re.compile(r"\[\]\(anthropic:([^)]+)\)")
