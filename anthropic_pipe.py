"""
title: Anthropic API Integration
id: anthropic_new
author: Podden (https://github.com/Podden/)
github: https://github.com/Podden/openwebui_anthropic_api_manifold_pipe
original_author: Balaxxe (Updated by nbellochi)
version: 0.9.28
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
v0.9.28
- Added an estimated USD cost per turn (new SHOW_COST user valve): reported as `cost_usd` plus a per-component `cost_breakdown_usd` in the message usage, so it shows in the message info tooltip and is persisted for analytics, and appended to the SHOW_TOKEN_COUNT status line. Anthropic exposes no pricing via the API, so prices come from a built-in list-price table; admins can patch it without a release via the new MODEL_PRICING_OVERRIDES valve (JSON, USD per MTok)
- The estimate follows the bill: cache writes are split 5m/1h from usage.cache_creation, fast mode and US data residency are detected from the response usage, and web searches are added at $10 per 1,000

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

    ## General payload creation
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
    # Opus 4.7 / 4.8 and the 4.6+ adaptive-thinking family reject sampling params
    # (temperature / top_p / top_k) — API returns 400. Strip them there.
    # Heuristic: models that support adaptive thinking (Opus 4.6, Sonnet 4.6,
    # Opus 4.7, Opus 4.8) do not accept these fields when adaptive is enabled.
    # On Opus 4.7 / 4.8 they are rejected unconditionally. Safe to skip for the set.
    _strip_sampling = bool(model_info.get("supports_adaptive_thinking"))
    if not _strip_sampling and body.get("temperature") is not None:
        payload["temperature"] = float(body.get("temperature", 0))
    if not _strip_sampling and body.get("top_k") is not None:
        payload["top_k"] = float(body.get("top_k", 0))
    if not _strip_sampling and body.get("top_p") is not None:
        payload["top_p"] = float(body.get("top_p", 0))

    # Add data residency if set to US (1.1x token cost)
    if pipe.valves.DATA_RESIDENCY == "us":
        payload["inference_geo"] = "us"

    # Add Fast Mode if enabled and model supports it (Opus 4.8 / Opus 5)
    if pipe.valves.ENABLE_FAST_MODE and model_info.get("supports_fast_mode", False):
        payload["speed"] = "fast"
        logger.debug("Fast Mode enabled for this request")
        
    # Handle "Effort" parameter (maps from OpenWebUI's reasoning_effort or user valves)
    # Effort works differently based on model capabilities
    effort_config = None
    effective_effort = None

    if model_info["supports_effort"]:
        # Clamp an effort value to what the current model supports.
        #   xhigh -> high if the model doesn't advertise xhigh (Opus 4.7 only)
        #   max   -> high if the model doesn't advertise max   (Opus 4.7/4.6, Sonnet 4.6)
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

    # Handle Thinking
    enable_thinking = __user__["valves"].ENABLE_THINKING or __metadata__.get(
        "anthropic_thinking", False
    )
    if enable_thinking and model_info["supports_thinking"]:
        # Opus 4.6 (supports adaptive thinking) uses effort as the control
        if model_info["supports_adaptive_thinking"]:
            thinking_config = {"type": "adaptive"}
        else:
            user_budget = __user__["valves"].THINKING_BUDGET_TOKENS
            max_tokens = min(
                body.get("max_tokens", model_info["max_tokens"]),
                model_info["max_tokens"],
            )
            context_limit = model_info.get("context_length", 200000)

            # For Claude 4 models with interleaved thinking+tools, allow up to context window
            if model_info.get("supports_thinking") and model_info.get(
                "supports_programmatic_calling"
            ):
                thinking_budget = min(user_budget, context_limit)
            else:
                # budget_tokens must be < max_tokens
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
        # Opus 5 / Sonnet 5 think unless told otherwise, so simply omitting the
        # `thinking` field no longer honours the toggle — send the explicit
        # disable. Opus 5 rejects `thinking:{"type":"disabled"}` at effort
        # xhigh/max with a 400, so the toggle also caps effort at high.
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

    # Extract container_id from previous metadata markers for multi-turn container reuse
    previous_container_id = None
    for metadata_entry in previous_marker_metadata:
        # Format: "N:container_id:ENCODED_VALUE"
        parts = metadata_entry.split(":", 2)
        if len(parts) >= 3 and parts[1] == "container_id":
            previous_container_id = unquote(parts[2])
            logger.debug(f"📦 Restored container_id from marker: {previous_container_id}")

    # Track if Files API uploaded any files (for auto-enabling code execution)
    has_files_api_uploads = False
    user_valves_for_features = __user__["valves"]
    requested_skills = [
        s.strip()
        for s in (getattr(user_valves_for_features, "SKILLS", []) or [])
        if s and s.strip()
    ]
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

    # Native-PDF anchors persisted on earlier turns. OpenWebUI drops full-context
    # files from __files__ on follow-up turns (it only sends a file in __files__
    # the turn it was attached). Without restoring the document block from these
    # markers, the native PDF vanishes from the cache prefix on every later turn,
    # which both hides the PDF from the model and forces a full cache rebuild.
    has_prior_pdf_markers = any(
        len(e.split(":", 2)) >= 3 and e.split(":", 2)[1] == "pdf"
        for e in (previous_marker_metadata or [])
    )

    if __files__ and use_files_api and FILES_AVAILABLE:
        # Files API overrules native PDF upload — all files go as container_upload
        blocks_by_user_msg, uploaded_filenames = await pipe._process_files_api_data(
            __files__, __event_emitter__, processed_messages
        )
        if blocks_by_user_msg:
            has_files_api_uploads = True
            # Insert container_upload blocks at the correct user messages
            user_msg_num = 0
            for i, msg in enumerate(processed_messages):
                if msg["role"] == "user" and user_msg_num in blocks_by_user_msg:
                    # Ensure content is a list
                    if isinstance(msg["content"], str):
                        msg["content"] = [{"type": "text", "text": msg["content"]}]
                    msg["content"] = blocks_by_user_msg[user_msg_num] + msg["content"]
                if msg["role"] == "user":
                    user_msg_num += 1

            # Remove RAG sources for uploaded files
            if uploaded_filenames:
                logger.debug(f"📋 RAG: Removing {len(uploaded_filenames)} file source(s) from RAG")
                pipe._remove_specific_sources_from_rag_message(processed_messages, uploaded_filenames)

    elif __user__["valves"].USE_PDF_NATIVE_UPLOAD and (__files__ or has_prior_pdf_markers):
        # Native PDF upload (base64 document blocks) — only PDFs.
        # Each PDF is anchored to the user-message it was first attached
        # to (tracked via metadata markers); never to msg[0]. This keeps
        # the byte-prefix of the conversation cache-stable across turns.
        # This branch also runs on follow-up turns with an empty __files__
        # as long as a prior PDF marker exists, so the document block is
        # restored at its original anchor instead of disappearing.
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

        # Remove RAG sources for native-PDF files on every turn, even
        # when the PDF block itself was restored from prior metadata.
        # Otherwise OpenWebUI can re-inject the same PDF as <context>
        # on the latest user message after the PDF is already attached
        # natively.
        if native_pdf_filenames:
            logger.debug(
                f"📋 RAG: Removing {len(native_pdf_filenames)} native PDF source(s) from RAG"
            )
            pipe._remove_specific_sources_from_rag_message(
                processed_messages, native_pdf_filenames
            )

    # Full-context uploads that neither the Files API nor native PDF upload
    # claimed (EPUB, DOCX, TXT, MD — and PDFs too when native upload is off).
    # OpenWebUI merges them into its <context> RAG template on the last user
    # message, where the cache-control pass must treat them as volatile and the
    # breakpoint lands in front of them: the whole file is re-sent uncached on
    # every turn. Anchor them like PDFs instead and cut them out of the
    # template, so the existing breakpoint covers them.
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

    ## Tools Handling
    # Correct Order for Caching: Tools, System, Messages
    tools_list, api_tool_names = pipe._convert_tools_to_claude_format(
        __tools__, body, actual_model_name, __user__, __metadata__
    )

    activate_code_execution = __metadata__.get(
        "activate_code_execution_tool", False
    )

    # Auto-enable code execution when Files API uploaded files (container_upload needs it)
    if has_files_api_uploads:
        activate_code_execution = True

    # Auto-enable code execution when programmatic tool calling is active
    # (programmatic calling requires code execution to orchestrate tool calls)
    if (
        pipe.valves.ENABLE_PROGRAMMATIC_TOOL_CALLING
        and model_info.get("supports_programmatic_calling", False)
        and tools_list  # Only when there are tools to call programmatically
    ):
        activate_code_execution = True

    # Check if any dynamic filtering web tools (20260209) are in tools_list.
    # These tools cause the API to AUTO-INJECT code_execution internally.
    # We must NOT add code_execution_20250825 manually when these are present —
    # doing so triggers: "Auto-injecting tools would conflict with existing tool names"
    # However, code_execution_20260120 (programmatic) CAN coexist because we provide
    # it explicitly and the API won't auto-inject a second code_execution.
    has_dynamic_filtering_tools = any(
        t.get("type", "").endswith("_20260209") for t in tools_list
    )
    has_code_execution = any(
        t.get("name") == "code_execution" for t in tools_list
    )

    # Open Terminal bridge is mutually exclusive with the code_execution sandbox:
    # when Claude's native bash / text_editor tools are wired to the real
    # terminal session, don't also hand it Anthropic's ephemeral server sandbox
    # for the same operations. No terminal → these tools are absent and
    # code_execution is injected as usual.
    has_native_terminal_tools = any(
        t.get("name") in ("bash", "str_replace_based_edit_tool") for t in tools_list
    )

    # Determine which code_execution version to add
    use_programmatic_code_exec = (
        pipe.valves.ENABLE_PROGRAMMATIC_TOOL_CALLING
        and model_info.get("supports_programmatic_calling", False)
    )

    if activate_code_execution and not has_code_execution and not has_native_terminal_tools:
        if use_programmatic_code_exec:
            # Always add code_execution_20260120 for programmatic calling,
            # even alongside dynamic filtering tools (it supersedes the auto-injected one)
            code_exec_type = "code_execution_20260120"
            tools_list.insert(0, {"type": code_exec_type, "name": "code_execution"})
            has_code_execution = True
        elif not has_dynamic_filtering_tools:
            # Only add code_execution_20250825 if no dynamic filtering
            # (dynamic filtering auto-injects its own code_execution)
            code_exec_type = "code_execution_20250825"
            tools_list.insert(0, {"type": code_exec_type, "name": "code_execution"})
            has_code_execution = True
        # else: dynamic filtering tools present, no programmatic → let API auto-inject

    if requested_skills and not has_code_execution:
        await status.activity("Skills require Anthropic code_execution")
        await status.notification(
            "Anthropic API Skills require Anthropic code_execution. Enable the Code Execution Toggle, "
            "or attach the Companion Filter so OpenWebUI code_interpreter requests set activate_code_execution_tool."
        )

    # Create Headers - check UserValves API key first
    user_valves = __user__.get("valves") if __user__ else None
    user_api_key = getattr(user_valves, "ANTHROPIC_API_KEY", "") if user_valves else ""
    api_key = user_api_key.strip() if user_api_key and user_api_key.strip() else pipe.valves.ANTHROPIC_API_KEY

    headers = {
        "x-api-key": api_key,
        "anthropic-version": pipe.API_VERSION,
        "content-type": "application/json",
    }

    beta_headers: list[str] = []

    # Enable prompt caching if not disabled
    if pipe.valves.CACHE_CONTROL != "cache disabled":
        beta_headers.append("prompt-caching-2024-07-31")

    # Add code-execution beta header ONLY when we explicitly added code_execution to tools.
    # Do NOT add when using dynamic filtering v20260209 web tools — those auto-inject
    # code_execution internally and the beta header would cause a second injection → duplicate error.
    if has_code_execution:
        # code_execution_20260120 doesn't need the old beta header
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

    # Add web_fetch beta header when using the older version (20250910)
    # The newer 20260209 version doesn't need a beta header
    uses_old_web_fetch = any(
        t.get("type") == "web_fetch_20250910" for t in tools_list
    )
    if pipe.valves.WEB_FETCH and uses_old_web_fetch:
        beta_headers.append("web-fetch-2025-09-10")

    # Add Files API beta header when files were uploaded but code_execution
    # wasn't otherwise activated (standalone file upload scenario)
    if has_files_api_uploads and "files-api-2025-04-14" not in beta_headers:
        beta_headers.append("files-api-2025-04-14")

    # Skills Integration. Anthropic expects an object container:
    # {"skills": [...]}, optionally with {"id": previous_container_id} for reuse.
    if requested_skills and has_code_execution:
        if "skills-2025-10-02" not in beta_headers:
            beta_headers.append("skills-2025-10-02")
        if "files-api-2025-04-14" not in beta_headers:
            beta_headers.append("files-api-2025-04-14")

        # Validate skills (cached to avoid API calls on every turn)
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
        # Reuse container from previous turn for code execution state continuity
        payload["container"] = previous_container_id
        logger.info(f"📦 Reusing container from previous turn: {previous_container_id}")

    # Add advanced tool use beta (for programmatic calling and tool search)
    if __user__["valves"].ENABLE_TOOL_SEARCH or pipe.valves.ENABLE_PROGRAMMATIC_TOOL_CALLING:
        beta_headers.append("advanced-tool-use-2025-11-20")

    # Add advisor tool beta
    if __user__["valves"].ENABLE_ADVISOR_TOOL:
        beta_headers.append("advisor-tool-2026-03-01")

    # Add context editing strategies if enabled
    context_editing_strategy = __user__["valves"].CONTEXT_EDITING_STRATEGY
    if context_editing_strategy != "none":
        if "context-management-2025-06-27" not in beta_headers:
            beta_headers.append("context-management-2025-06-27")

        # Build context_management array for payload
        # IMPORTANT: clear_thinking must be FIRST if present (API requirement)
        context_management = []

        # Add clear_thinking FIRST if needed
        if (
            context_editing_strategy in ["clear_thinking", "clear_both"]
            and enable_thinking
            and model_info["supports_thinking"]
        ):
            _keep_val = __user__["valves"].CONTEXT_EDITING_THINKING_KEEP
            clear_thinking = {
                "type": "clear_thinking_20251015",
                # keep=0 → "all" (preserve all thinking → stable prompt cache).
                # keep>0 → sliding window (breaks cache every turn past threshold).
                "keep": "all" if _keep_val <= 0 else {
                    "type": "thinking_turns",
                    "value": _keep_val,
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

    # Add compaction if enabled and model supports it. New beta support may need
    # MODEL_CAPABILITY_OVERRIDES because API capability metadata can lag.
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

    # Add effort beta header and output_config if effort is configured
    if model_info["supports_effort"] and effort_config:
        beta_headers.append("effort-2025-11-24")
        payload["output_config"] = effort_config

    # Add Fast Mode beta header if enabled and model supports it
    if pipe.valves.ENABLE_FAST_MODE and model_info.get("supports_fast_mode", False):
        beta_headers.append("fast-mode-2026-02-01")

    # Server-side fallback on safety refusals. Claude API only — not supported on
    # Bedrock / Vertex / Foundry or the Batches API, so it stays off whenever the
    # base URL is not Anthropic's.
    fallback_mode = getattr(pipe.valves, "REFUSAL_FALLBACK", "off")
    if fallback_mode != "off" and pipe.valves.ANTHROPIC_BASE_URL.rstrip("/") == pipe._DEFAULT_API_BASE:
        beta_headers.append("server-side-fallback-2026-07-01")
        # `fallbacks` is not a named SDK parameter yet, so pass it through
        # extra_body (same route as `diagnostics`) instead of as a kwarg the
        # installed SDK version may reject.
        _fallbacks = (
            "default" if fallback_mode == "default" else [{"model": fallback_mode}]
        )
        payload.setdefault("extra_body", {})["fallbacks"] = _fallbacks
        logger.debug(f"Server-side refusal fallback: {_fallbacks}")

    # Cache diagnostics beta — only meaningful with prompt caching active. Always
    # send `diagnostics.previous_message_id` (null on first turn) so the API can
    # report `cache_miss_reason` whenever the cache prefix diverged from last turn.
    if (
        getattr(pipe.valves, "ENABLE_CACHE_DIAGNOSTICS", False)
        and pipe.valves.CACHE_CONTROL != "cache disabled"
    ):
        beta_headers.append("cache-diagnosis-2026-04-07")
        chat_id_for_diag = __metadata__.get("chat_id") if __metadata__ else None
        # Prefer the response id persisted as a `cachediag` marker on the prior
        # assistant message (survives pipe restarts / multiple workers). Fall
        # back to the in-memory state dict only if no marker is present.
        previous_message_id = None
        for _entry in previous_marker_metadata:
            _parts = _entry.split(":", 2)
            if len(_parts) >= 3 and _parts[1] == "cachediag":
                previous_message_id = unquote(_parts[2])
        if previous_message_id is None and chat_id_for_diag:
            previous_message_id = pipe._cache_diagnostics_state.get(chat_id_for_diag)
        # `diagnostics` is not a native SDK parameter — pass it via extra_body
        # so the SDK forwards it as-is in the JSON request body.
        payload.setdefault("extra_body", {})["diagnostics"] = {
            "previous_message_id": previous_message_id
        }
        logger.debug(
            f"[CACHE-DIAG] previous_message_id={previous_message_id} chat_id={chat_id_for_diag}"
        )

    # A compaction block replayed from history requires the compaction beta even
    # when API-side compaction isn't enabled for this turn — otherwise Anthropic
    # 400s with "Input tag 'compaction' does not match any of the expected tags".
    # This keeps previously-compacted chats replayable regardless of valve state.
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
        # Add betas list to payload for beta.messages.stream
        payload["betas"] = beta_headers

        ## Tool Choice Handling
        if __metadata__.get("web_search_enforced"):
            # Check if web_search is actually in the tools list
            has_web_search = any(t.get("name") == "web_search" for t in tools_list)
            if has_web_search:
                if "thinking" not in payload:
                    # No thinking active - enforce web_search
                    payload["tool_choice"] = {"type": "tool", "name": "web_search"}
                    logger.debug("Enforcing web_search via tool_choice")
                else:
                    # Thinking is active - cannot enforce web_search, but it's still available
                    payload["tool_choice"] = {"type": "auto"}
                    logger.debug(
                        "Thinking active - web_search added but not enforced (tool_choice=auto)"
                    )
            else:
                # No enforcement - use auto tool choice
                payload["tool_choice"] = {"type": "auto"}

    # API tool_choice passthrough (outside beta_headers block)
    # If no tool_choice was set by web_search enforcement, pass through from body
    if "tool_choice" not in payload and body.get("tool_choice"):
        api_tc = body["tool_choice"]
        if isinstance(api_tc, dict) and "function" in api_tc:
            # OpenAI format: {"type": "function", "function": {"name": "X"}}
            payload["tool_choice"] = {
                "type": "tool",
                "name": api_tc["function"]["name"],
            }
        elif isinstance(api_tc, str):
            # OpenAI string format: "auto", "none", "required"
            mapping = {"auto": "auto", "none": "none", "required": "any"}
            payload["tool_choice"] = {"type": mapping.get(api_tc, api_tc)}
        else:
            # Already in Anthropic format or other dict format
            payload["tool_choice"] = api_tc
        logger.debug(f"API tool_choice passthrough: {payload['tool_choice']}")

    # Filter stale tool_search references for tools toggled OFF.
    # History `tool_search_tool_result` blocks list `tool_references` for tools
    # the search surfaced on an earlier turn.  If such a user tool is no longer
    # enabled it is absent from `tools`, and replaying the reference makes the
    # API reject the request with 400 "Tool reference 'X' not found in available
    # tools".  Drop the missing references entirely rather than re-advertising a
    # disabled tool: a stub definition would let the model call a non-functional
    # tool again.  The cache is already invalidated by the tool-set change
    # (`tools_changed`), so editing history here costs nothing extra.
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

    # Tool search nudge: deferred tools are stripped from the prompt prefix, so the
    # model can't see them and tends to claim it lacks the capability. Tell it to
    # search first. Static text → does not churn the cache across turns.
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

    # Processing Messages and Caching
    if system_messages and len(system_messages) > 0:
        payload["system"] = system_messages

    payload["messages"] = processed_messages

    # Last step before the payload leaves: give every content block one
    # deterministic key order. Live blocks come from SDK objects and replayed
    # blocks from literal dicts, so the same content otherwise serializes to
    # different bytes -- and the prefix cache compares bytes. Done here rather
    # than at each construction site so it cannot be forgotten, and after
    # cache_control placement so those markers are ordered too.
    payload["messages"] = pipe._canonicalize_block(payload["messages"])
    if payload.get("system") is not None:
        payload["system"] = pipe._canonicalize_block(payload["system"])

    return payload, headers, new_marker_metadata, api_tool_names
# END GENERATED SECTION: anthropic_pipe.request_payload

# BEGIN GENERATED SECTION: anthropic_pipe.response.handlers
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
# END GENERATED SECTION: anthropic_pipe.response.handlers

# BEGIN GENERATED SECTION: anthropic_pipe.response.registry
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
# END GENERATED SECTION: anthropic_pipe.response.registry

# BEGIN GENERATED SECTION: anthropic_pipe.response.status_events
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

    # -- phases ------------------------------------------------------------
    # One method per thing that can actually be happening, so call sites read as
    # intent and the wording stays consistent across handlers.

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
# END GENERATED SECTION: anthropic_pipe.response.status_events

# BEGIN GENERATED SECTION: anthropic_pipe.response.text_block
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
        # Flushed verbatim. A text content_block is NOT a paragraph boundary: on a
        # cited answer Anthropic splits the prose around every citation, and those
        # splits land mid-table-row ("| "), mid-bullet ("- ") and mid-bold ("**").
        # Appending a separator newline here therefore breaks the markdown it was
        # meant to protect. Blocks that need their own line prepend it themselves
        # (ctx.emit_block / _append_block_to_text).
        await ctx.emit_delta(text.chunk)
        text.chunk = ""
        text.chunk_count = 0
# END GENERATED SECTION: anthropic_pipe.response.text_block

# BEGIN GENERATED SECTION: anthropic_pipe.response.thinking_block
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
# END GENERATED SECTION: anthropic_pipe.response.thinking_block

# BEGIN GENERATED SECTION: anthropic_pipe.response.compaction_block
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
# END GENERATED SECTION: anthropic_pipe.response.compaction_block

# BEGIN GENERATED SECTION: anthropic_pipe.response.client_tool
def _filter_tool_args(tool_entry: Any, args: dict) -> dict:
    if not isinstance(args, dict) or not args:
        return args if isinstance(args, dict) else {}
    spec = (tool_entry or {}).get("spec") if isinstance(tool_entry, dict) else None
    if not isinstance(spec, dict):
        return args
    params = spec.get("parameters")
    if not isinstance(params, dict) or not isinstance(params.get("properties"), dict):
        # No usable schema — passing the args through unchanged is the safer
        # guess than dropping everything.
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

    # A client tool firing inside code execution means the model is calling our
    # tools programmatically, not doing the dynamic web filtering pass.
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
        # Inside code execution the call is the model's own plumbing and already
        # shown in the code block; announcing it would just churn the status line.
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
# END GENERATED SECTION: anthropic_pipe.response.client_tool

# BEGIN GENERATED SECTION: anthropic_pipe.response.server_tool
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
        # Deliberately silent here: the query/url arrives a few deltas later, and the
        # status history keeps every line, so announcing a generic "Searching the
        # web..." now would leave a placeholder line stranded above the real one.
        if server_tool.in_code_execution:
            server_tool.had_web_tools = True

    elif tool_name == "code_execution":
        await ctx.status.running_code()
        await _finalize_open_code_block(ctx)

        server_tool.in_code_execution = True
        # Assume the dynamic web-filtering pass until a client tool_use proves the
        # model is calling our tools programmatically instead.
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

    # The buffer is only parseable once the JSON is complete; every earlier delta
    # raises and is skipped.
    try:
        parsed = json.loads(server_tool.input_buffer)
    except (json.JSONDecodeError, ValueError):
        return

    if tool_name == "web_search":
        query = parsed.get("query")
        if query:
            # Announced here rather than at block start: this is the first moment the
            # status can say what is actually being searched for. emit()'s dedup
            # absorbs the repeats as the remaining deltas re-parse the same JSON.
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
                # Plain-text files render as prose further down, not as a code block.
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
        # The sentinel makes the result renderer show prose rather than a code block.
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
        # The matching *_tool_result block pops this to merge its output into the
        # same collapsible instead of emitting a second one next to it.
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
# END GENERATED SECTION: anthropic_pipe.response.server_tool

# BEGIN GENERATED SECTION: anthropic_pipe.response.code_execution_results
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
        await ctx.emit_block(f"⚠️ Code execution error: {error_code}")
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
        await ctx.emit_block(f"⚠️ Text editor error: {error_code}")
        server_tool.last_code_content = ""
        return

    if _suppressed_as_web_filtering(server_tool):
        logger.debug("Suppressed text editor block (web filtering)")
        server_tool.last_code_content = ""
    elif result_type == "text_editor_code_execution_create_result":
        if server_tool.last_code_content and server_tool.last_code_language == "__inline_text__":
            # Plain-text files read better as prose than inside a code block.
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
            await ctx.emit_block(f"⚠️ Code execution error: {error_code}")
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
# END GENERATED SECTION: anthropic_pipe.response.code_execution_results

# BEGIN GENERATED SECTION: anthropic_pipe.response.web_tool_results
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
                # Hand the result urls to OpenWebUI's native web_search renderer so
                # the status line becomes a clickable source list instead of prose.
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
# END GENERATED SECTION: anthropic_pipe.response.web_tool_results

# BEGIN GENERATED SECTION: anthropic_pipe.response.internal_tool_results
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

    # activity, not complete: context editing happens mid-turn, and a done=True
    # status would close the line while the model keeps generating.
    await ctx.status.activity(status_desc)
    logger.debug("Context cleared: type=%s, tokens=%s", cleared_type, cleared_tokens)
# END GENERATED SECTION: anthropic_pipe.response.internal_tool_results

# BEGIN GENERATED SECTION: anthropic_pipe.shared.pricing
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
        if not usage:
            return
        if getattr(usage, "speed", None) == "fast":
            total_usage["_speed_fast"] = 1
        if getattr(usage, "inference_geo", None) == "us":
            total_usage["_geo_us"] = 1

    def breakdown(self, model_name: str, total_usage: dict) -> Optional[dict]:
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
        components = self.breakdown(model_name, total_usage)
        if components is None:
            return None
        return round(sum(components.values()), 6)

    @staticmethod
    def format_usd(cost: float) -> str:
        if cost >= 1:
            return f"${cost:.2f}"
        if cost >= 0.01:
            return f"${cost:.3f}"
        return f"${cost:.4f}"
# END GENERATED SECTION: anthropic_pipe.shared.pricing

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
        MODEL_PRICING_OVERRIDES: str = Field(
            default="",
            description="JSON patch for the built-in price table used by the SHOW_COST estimate, in USD per "
            "million tokens, keyed by model id. Keys: input, output, cache_write_5m, cache_write_1h, "
            "cache_read, fast_input, fast_output; omitted cache rates derive from `input` at Anthropic's "
            "standard multipliers (1.25x / 2x / 0.1x). Example: "
            '{"claude-sonnet-5": {"input": 3, "output": 15}, "my-proxy-model": {"input": 1, "output": 5}}. '
            "Anthropic does not publish prices through the API, so this is how to track price changes "
            "or a negotiated rate without waiting for a pipe release.",
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
        SHOW_COST: bool = Field(
            default=True,
            description="Report the estimated USD cost of the turn as `cost_usd` plus a per-component "
            "`cost_breakdown_usd` (input, output, cache writes/reads, web search) in the message usage "
            "(visible in the message info tooltip and persisted for analytics) and, when SHOW_TOKEN_COUNT "
            "is on, in the status line. Based on Anthropic list prices for the model, including cache "
            "writes/reads, fast mode, US data residency and web searches; negotiated or third-party-proxy "
            "rates are not known to the pipe unless the admin sets MODEL_PRICING_OVERRIDES.",
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
    # BEGIN GENERATED SECTION: anthropic_pipe.pipe_method_groups
    def _cache_control_marker(self, scope: str = "messages") -> dict:
        """Return the cache_control dict for one breakpoint scope.

        `tools_system` may run a longer TTL than `messages`: the tools array and
        system prompt are stable across turns, so a 1h entry pays for its doubled
        write cost, while messages change every turn and would just re-pay it.

        The API requires longer TTLs to sit *before* shorter ones in the prompt
        (render order is tools -> system -> messages), so tools/system may be
        longer than messages but never shorter. A configuration that inverts that
        is clamped to the messages TTL rather than sent and silently mis-billed.
        """
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
        """Recursively convert an Anthropic SDK object (or plain dict/list) to a
        plain Python structure suitable for JSON serialisation."""
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
        """Rewrite a content block with a deterministic key order.

        Anthropic hashes the serialized bytes of the prompt prefix, so two dicts
        with identical content but different key order are two different
        prefixes. That is exactly what happened: live blocks are dumped from SDK
        objects in the SDK's field order (``citations, text, type``), while
        replayed blocks are literal dicts written in reading order
        (``type, text, citations``). Same content, different bytes, guaranteed
        cache miss on the first turn after any tool use -- and invisible to any
        content-level comparison, which is why the pipe's own diff logger keeps
        a separate insertion-order hash to catch it.

        Normalising at one choke point beats matching orders at every
        construction site: whatever built the block, the wire format is the same.
        ``type`` leads because it is the discriminator and makes payload dumps
        readable; the rest is alphabetical. Key ORDER is all that changes, never
        keys or values, so the request itself is unaffected -- JSON objects are
        order-insensitive to the API's parser.
        """
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
        """Return a copy of the outgoing Anthropic payload with *minimal*
        structural changes, safe for debug logging.

        Only two things change:
          1. ``tools`` is replaced with a small summary (count + names +
             indices carrying cache_control).
          2. Every string value reachable inside ``messages`` is truncated to
             ``max_str`` chars + ``…[Nc]`` length marker.

        Everything else — key order, whitespace inside non-messages strings,
        `system`, `cache_control`, booleans, numbers, None values, extra
        top-level fields — is left **byte-for-byte** untouched so that two
        consecutive dumps can be diffed to locate cache-invalidating drift
        (double newlines, missing spaces, re-ordered keys, etc).
        """
        def _clip(s):
            """Truncate a string to max_str chars, appending a length+hash marker."""
            if isinstance(s, str) and len(s) > max_str:
                import hashlib as _hl
                _h = _hl.sha1(s.encode("utf-8", "replace")).hexdigest()[:8]
                return f"{s[:max_str]}…[{len(s)}c#{_h}]"
            return s

        def _walk(node):
            """Recursively clip every string value found within a dict/list structure."""
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
                # Serialize each tool the way it goes over the wire so two dumps
                # reveal both size (which segment owns the cache_creation tokens)
                # and byte drift (a schema that re-orders or re-renders per turn).
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
        """Compare the current outgoing payload.messages[] against the previous
        request for the same chat_id. Log first divergence index + per-message
        hash table so we can pinpoint which assistant/user message mutated
        between turns and broke the Anthropic prompt cache prefix.

        Uses hashlib.sha1 on ``json.dumps(sort_keys=True, separators=(",", ":"))``
        of each message (minus cache_control markers, which legitimately move).
        """
        if not chat_id:
            return
        try:
            msgs = payload.get("messages", []) or []

            def _strip_cache_control(obj):
                """Recursively remove all ``cache_control`` keys from a dict/list structure."""
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
                """Return canon as-is if short, else a truncated preview with a trailing sha1 digest."""
                if len(canon) <= limit:
                    return canon
                import hashlib
                digest = hashlib.sha1(canon.encode("utf-8", "replace")).hexdigest()[:10]
                return f"{canon[:limit]}...(truncated {len(canon)}c sha1={digest})"

            def _hash_msg(m: dict) -> tuple[str, str, str]:
                """Return (insertion_order_hash, sorted_hash, preview). The SDK sends
                dicts in Python insertion order, so insertion_order_hash is
                what the API actually sees for cache purposes. sorted_hash
                tells us whether the *content* matches regardless of order.

                ``cache_control`` markers are stripped from both hashes because
                they are placement hints that legitimately move between turns;
                treating them as message drift creates false positives.
                """
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
                """Build a short human-readable summary of a message's role and content blocks."""
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
                """Where the messages cache_control marker sits: (msg, block).

                Everything up to and including that BLOCK forms the prefix the
                next turn tries to read back. The block half matters: volatile
                context is normalised into trailing blocks, so the breakpoint now
                usually sits inside the very message whose tail is expected to
                differ. Judging at message granularity would report every single
                healthy turn as a break.
                """
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
                """Hash of the breakpoint message truncated at the breakpoint block.

                Lets the next turn tell "the tail of this message changed"
                (harmless, expected) from "the cached part changed" (a real break)
                without needing a per-block hash table.
                """
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
                # Check insertion-order (what the API actually sees)
                ins_first_diff = None
                for i in range(overlap):
                    if prev_ins[i] != ins_hashes[i]:
                        ins_first_diff = i
                        break
                # Check sorted/content (what we'd naively consider "the same")
                sort_first_diff = None
                for i in range(overlap):
                    if prev_sort[i] != sort_hashes[i]:
                        sort_first_diff = i
                        break

                # Only divergence at or before the *previous* breakpoint can cost
                # a cache read -- that is the prefix this turn tries to reuse.
                # Anything after it is replay noise (the memory/RAG appendix on
                # the last message is expected to differ) and must not be logged
                # as a break, or the real breaks drown in false positives.
                first_diff = ins_first_diff if ins_first_diff is not None else sort_first_diff
                if first_diff is None or prev_bp is None:
                    harmful = False
                elif first_diff < prev_bp:
                    # Divergence strictly before the breakpoint message: the
                    # cached prefix definitely changed.
                    harmful = True
                elif first_diff > prev_bp:
                    harmful = False
                else:
                    # Same message as the breakpoint. Only the part up to the
                    # breakpoint BLOCK was cached, and its tail is expected to
                    # differ -- that is where the memory/RAG appendix lives.
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
                    # CRITICAL: content equal but KEY ORDER diverged → API cache miss!
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
                    # Dump FULL JSON (insertion order) for diffing
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
            # Bound memory: keep only last ~20 chats
            if len(self._cache_diff_state) > 20:
                # drop oldest inserted (FIFO)
                oldest = next(iter(self._cache_diff_state))
                if oldest != chat_id:
                    self._cache_diff_state.pop(oldest, None)
        except Exception as e:
            logger.debug(f"_log_message_hash_diff failed: {e}")

    # From which tool-loop iteration on the in-turn breakpoint is worth its write.
    #
    # That breakpoint sits on the newest message, i.e. BEHIND the volatile
    # blocks, so its entry covers them. Within a turn that is fine and useful --
    # the payload is built once and only extended, so the appendix does not move
    # and the next iteration reads it. Across turns the entry is dead, because
    # the appendix vanishes from that message.
    #
    # So it pays off only while more iterations follow, and the write of the
    # LAST iteration is always wasted. Measured on a real conversation, the
    # wasted writes were 551, 571 and 8721 tokens -- the last one being a turn
    # with thinking plus three tool calls. Since most loops stop after one tool
    # round, waiting until the loop has proven itself deep avoids the common
    # waste and keeps the benefit where loops actually get long.
    TOOL_LOOP_VOLATILE_CACHE_MIN_ITERATION = 4

    def _apply_cache_control(
        self, payload: dict, is_tool_loop: bool = False, iteration: int = 1
    ) -> None:
        """Apply cache_control breakpoints to the payload right before sending to the API.

        Called once before the initial request and once before each tool loop iteration.
        Strips all existing cache_control markers first, then applies fresh ones
        based on the current payload state and valve configuration.

        ``iteration`` is the 1-based tool-loop iteration. It gates the in-turn
        breakpoint (see TOOL_LOOP_VOLATILE_CACHE_MIN_ITERATION); a caller that
        omits it gets the conservative behaviour of never placing one.

        Anthropic rules:
        - Max 4 breakpoints, hierarchy: tools → system → messages
        - Cache prefixes are cumulative (hash depends on all prior blocks)
        - Never add cache_control to thinking/redacted_thinking blocks (API rejects extra fields)
        - 20-block lookback window from each explicit breakpoint
        - Minimum cacheable: 1024-4096 tokens depending on model
        - Tool_result blocks CAN have cache_control (unless programmatic calling)
        """
        cache_level = self.valves.CACHE_CONTROL
        if cache_level == "cache disabled":
            return

        # --- Step 1: Strip all existing cache_control from entire payload ---
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

        # --- Step 2: Cache tools (breakpoint 1) ---
        # Always cache tools at every non-disabled level — tools rarely change
        # and having a separate breakpoint ensures cache hits even when system/messages change.
        # Tools and system share one marker; messages get their own further down,
        # so the two can run different TTLs.
        cache_marker = self._cache_control_marker("tools_system")

        tools = payload.get("tools", [])
        if tools:
            # Find last non-deferred tool for the breakpoint
            placed = False
            for i in range(len(tools) - 1, -1, -1):
                if not tools[i].get("defer_loading", False):
                    tools[i]["cache_control"] = cache_marker
                    placed = True
                    break
            if not placed:
                # All deferred — cache the last one anyway
                tools[-1]["cache_control"] = cache_marker

        if cache_level == "cache tools array only":
            return

        # --- Step 3: Cache system prompt (breakpoint 2) ---
        system = payload.get("system", [])
        if system:
            # Find last text block with content
            for i in range(len(system) - 1, -1, -1):
                block = system[i]
                if block.get("type") == "text" and block.get("text", "").strip():
                    block["cache_control"] = cache_marker
                    break

        if cache_level == "cache tools array and system prompt":
            return

        # --- Step 4: Cache messages (breakpoint 3) ---
        # "cache tools array, system prompt and messages"
        messages = payload.get("messages", [])
        if not messages:
            return

        if is_tool_loop:
            # Two different jobs during a tool loop, and conflating them is what
            # made a whole history get rewritten every turn.
            volatile_msg, volatile_at = None, None
            for msg in reversed(messages):
                idx = self._first_volatile_block_index(msg)
                if idx is not None:
                    volatile_msg, volatile_at = msg, idx
                    break

            if volatile_msg is None:
                # Nothing volatile in this conversation (no memories, no RAG), so
                # the newest message replays byte-identically next turn. One
                # breakpoint serves both jobs.
                place_in_turn = True
            else:
                # Job 1, always: anchor a breakpoint that ends right BEFORE the
                # volatile blocks. That is the furthest point still reproducible
                # once the appendix is gone, so it is the only entry the next
                # turn can read.
                if volatile_at > 0:
                    self._place_cache_on_last_cacheable_block(
                        volatile_msg.get("content", [])[:volatile_at]
                    )
                # Job 2, conditionally: the in-turn breakpoint below sits on the
                # newest message, so its entry also covers the volatile blocks
                # and the tool results. Inside the turn that is correct and
                # useful -- the payload is only extended, so the appendix does
                # not move and the next iteration reads it. It is worthless
                # across turns though, so it is only worth its 1.25x write while
                # further iterations are still coming.
                #
                # Budget note: tools and system claim one breakpoint each of
                # Anthropic's four, so messages may spend two. Overshooting is a
                # 400, not a degraded cache.
                place_in_turn = (
                    iteration >= self.TOOL_LOOP_VOLATILE_CACHE_MIN_ITERATION
                    and self._count_message_breakpoints(messages) < 2
                )

            # EXCEPTION: Programmatic tool calling — API rejects cache_control on
            # tool_result blocks routed through code_execution.
            if not place_in_turn:
                pass
            elif self.valves.ENABLE_PROGRAMMATIC_TOOL_CALLING:
                # With programmatic calling, cache the last assistant message block instead
                # (thinking blocks excluded — find last text or tool_use block)
                for msg in reversed(messages):
                    if msg.get("role") == "assistant":
                        self._place_cache_on_last_cacheable_block(msg.get("content", []))
                        break
            else:
                # Standard tool loop: cache the last user message block (tool_result)
                for msg in reversed(messages):
                    if msg.get("role") == "user":
                        content = msg.get("content", [])
                        if content:
                            # tool_result blocks are cacheable
                            content[-1]["cache_control"] = self._cache_control_marker()
                        break
        else:
            # Initial request: cache the last stable user message
            self._cache_last_stable_message(messages)

    def _place_cache_on_last_cacheable_block(self, content_blocks: list) -> None:
        """Add cache_control to the last block that isn't thinking/redacted_thinking
        or a tool_use called by code execution (API rejects cache_control on those)."""
        if not content_blocks:
            return
        for i in range(len(content_blocks) - 1, -1, -1):
            block = content_blocks[i]
            if isinstance(block, dict):
                btype = block.get("type")
                if btype in ("thinking", "redacted_thinking"):
                    continue
                # tool_use blocks called by code_execution cannot have cache_control
                if btype == "tool_use" and block.get("caller"):
                    continue
                block["cache_control"] = self._cache_control_marker()
                return

    @staticmethod
    def _message_carries_volatile_context(msg: dict) -> bool:
        """True when a message carries per-request context that never repeats.

        Two sources, same problem. OpenWebUI re-retrieves both on every request
        against the current question:
          * RAG chunks, injected into the last user message as <context> or as a
            "### Task:" template wrapping <source> elements.
          * Memories, which this pipe relocates out of the system prompt onto the
            last user message (see MEMORY_CONTEXT_APPENDIX_HEADER).

        Only the *last* message ever receives them, so on the next turn the very
        same message is replayed without them and the prefix diverges right there.
        Caching such a message poisons the whole history: the API then reports
        messages_changed and re-writes everything from that index onward, turn
        after turn. Cache the message before it instead.
        """
        return Pipe._first_volatile_block_index(msg) is not None

    @staticmethod
    def _count_message_breakpoints(messages: list) -> int:
        """How many cache_control markers the messages array already carries."""
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
        """Index of the first block carrying per-request context, or None.

        Both sources are normalised into trailing blocks of their own before this
        runs (see _split_rag_into_trailing_block and the memory appendix), so the
        returned index marks where the stable part of the message ends.
        """
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
        """Place the messages breakpoint on the newest message that will replay
        byte-identically next turn, skipping volatile per-request context and
        thinking/redacted_thinking blocks.
        """
        if not messages:
            return

        last = messages[-1]
        volatile_at = self._first_volatile_block_index(last)

        if volatile_at is None:
            self._place_cache_on_last_cacheable_block(last.get("content", []))
            return

        if volatile_at > 0:
            # The stable head of this very message can still be cached: volatile
            # context is normalised into trailing blocks, so a breakpoint on the
            # last block before them ends the prefix exactly where the message
            # stops being reproducible. This is what lets the FIRST request of a
            # conversation cache at all -- it used to fall through to the
            # len < 2 guard below and cache nothing but the tools.
            content = last.get("content", [])
            self._place_cache_on_last_cacheable_block(content[:volatile_at])
            return

        if len(messages) < 2:
            # The whole message is volatile and there is nothing before it.
            # Placing the breakpoint anyway would write an entry that cannot be
            # read back next turn; tools and system keep their own breakpoints.
            return

        self._place_cache_on_last_cacheable_block(messages[-2].get("content", []))

    def _convert_messages_to_claude_format(
        self, raw_messages
    ) -> tuple[list[dict], list[dict], list[str]]:
        """Convert a raw OpenWebUI message list into Claude system/processed messages plus extracted marker metadata."""
        processed_messages: list[Dict[str, Any]] = []
        extracted_memories = None
        previous_marker_metadata: list[str] = []
        system_messages = []
        if raw_messages is None or len(raw_messages) == 0:
            return system_messages, processed_messages, previous_marker_metadata

        for i, msg in enumerate(raw_messages):
            role = msg.get("role")
            raw_content = msg.get("content")

            # OpenAI-style tool result messages (role: "tool") are not valid for
            # Anthropic's API.  Convert them to role: "user" + type: "tool_result"
            # blocks.  Batch consecutive tool messages into a single user message
            # so the API always sees alternating user/assistant turns.
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
                # Merge into the preceding user message if it already holds
                # tool_result blocks (i.e. a previous role: "tool" message was
                # already converted), otherwise open a new user message.
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

            # Historical assistant turns may carry tool calls serialized as
            # <details type="tool_calls"> HTML (OpenWebUI stores flat strings
            # only). Parse them back into structured tool_use/tool_result
            # blocks so Claude sees its own prior tool usage and doesn't
            # re-execute tools on follow-up turns.
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

                    # Driven by what actually arrived, not by the user's memory
                    # toggle: OpenWebUI injects based on the request's
                    # `features.memory` and an admin ConfigVar, so the toggle can
                    # read "off" while memories are in the prompt. Missing that
                    # case costs a full prefix rewrite every turn. The helper
                    # short-circuits on a substring scan when nothing is there.
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

                    # Update block with cleaned text
                    block["text"] = cleaned_text

                    # Only add non-empty blocks to system (cache_control will be added later to last block only)
                    if block["text"].strip():
                        system_messages.append(block)
            else:
                # Wrap as dict so _extract_metadata_marker_from_message can check role
                # and modify content blocks in-place to strip markers
                wrapped_msg = {"role": role, "content": claude_message}
                extracted_metadata = self._extract_metadata_marker_from_message(
                    wrapped_msg
                )
                if extracted_metadata:
                    previous_marker_metadata.extend(extracted_metadata)

                processed_messages.append(wrapped_msg)

                if i == len(raw_messages) - 1 and role == "user":
                    # Volatile context has to end up in trailing blocks of its
                    # own, so the cache breakpoint can sit right before it. RAG
                    # first, then memories -- RAG arrives merged into the prose
                    # by OpenWebUI, memories are appended by us.
                    self._split_rag_into_trailing_block(processed_messages[-1])

                    if extracted_memories:
                        processed_messages[-1]["content"].append(
                            {
                                "type": "text",
                                "text": f"{MEMORY_CONTEXT_APPENDIX_HEADER}{extracted_memories}",
                            }
                        )

        # Client-side compaction trim: drop messages before the last compaction
        # block. The API would ignore them anyway but this saves bandwidth and
        # avoids sending stale context over the wire.
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
        """
        Process content from OpenWebUI format to Claude API format.
        Handles text, images, PDFs, tool_calls, and tool_results according to
        Anthropic API documentation.
        Filters out empty text blocks to prevent API errors.
        """
        if content is None:
            return []

        if isinstance(content, str):
            # NOTE: Do NOT remove thinking blocks from assistant messages!
            # Per Anthropic docs: thinking blocks MUST be preserved unmodified during tool use loops.
            # The entire sequence of consecutive thinking blocks must match the original model output.
            # For multi-turn: prior turn thinking CAN be omitted (API auto-filters), but preserving is preferred.
            # With interleaved thinking (Claude 4), thinking blocks can appear BETWEEN tool calls too.
            # Thinking blocks come back as serialized text (with <details type="reasoning">...) from OpenWebUI,
            # and the API requires them to remain unchanged.

            # Strip OpenWebUI UI-rendering artifacts from conversation history.
            # <details type="tool_calls"> and <details type="code_interpreter"> are display-only
            # HTML that OpenWebUI stores in message content. If sent to Claude 4.6 models,
            # they pattern-match these and generate fake tool call HTML as text output
            # instead of making actual API tool_use calls.
            if role == "assistant":
                content = PATTERN_TOOL_CALLS_DETAILS.sub("", content)
                content = PATTERN_CODE_INTERPRETER_DETAILS.sub("", content)
                content = PATTERN_CACHE_TRACE_DETAILS.sub("", content)

                # Reconstruct ALL replayable <details> blocks (reasoning,
                # server_tool_use, *_tool_result, compaction) into their
                # API-native forms, in original document order. Positional
                # fidelity is critical: the Anthropic API requires the exact
                # sequence of thinking + server_tool_use + tool_result blocks
                # to match the original assistant turn byte-exact, otherwise
                # subsequent requests 400 with "thinking blocks cannot be
                # modified" and the prompt cache prefix is invalidated.
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
                    # Pre-scan the standalone *_tool_result carriers, keyed by
                    # tool_use_id. The API requires a server_tool_use to be
                    # followed directly by its result; the stored HTML does not
                    # guarantee that order once several server tools run in
                    # quick succession (their carriers interleave with text and
                    # with each other), and replaying document order then 400s
                    # the next request with "tool use found without a
                    # corresponding tool_result block".
                    standalone_results: dict[str, dict] = {}
                    for _, kind, match in all_matches:
                        if kind != "server_tool_result":
                            continue
                        attrs = dict(PATTERN_DATA_ATTR.findall(match.group(1)))
                        payload_b64 = attrs.get("payload-b64", "")
                        decoded = (
                            self._decode_block_payload(payload_b64) if payload_b64 else None
                        )
                        if (
                            isinstance(decoded, dict)
                            and decoded.get("type", "").endswith("_tool_result")
                            and decoded.get("tool_use_id")
                        ):
                            standalone_results[decoded["tool_use_id"]] = decoded
                    consumed_results: set[str] = set()
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
                            # else: unsignatured reasoning → drop
                        elif kind == "server_tool_use":
                            attrs_str = match.group(1)
                            attrs = dict(PATTERN_DATA_ATTR.findall(attrs_str))
                            payload_b64 = attrs.get("payload-b64", "")
                            decoded = self._decode_block_payload(payload_b64) if payload_b64 else None
                            if isinstance(decoded, dict) and decoded.get("type") == "server_tool_use":
                                blocks.append(decoded)
                                # If this carrier also embeds the matching
                                # *_tool_result payload (merged display mode),
                                # emit it right after so the API sees the
                                # full tool_use + tool_result pair at the
                                # original position.
                                # data-result-kind carries the block type (e.g. "web_search_tool_result")
                                # and data-result-payload-b64 carries the encoded payload. The decoded
                                # payload already has "type": "...", so result_kind is just sanity-check.
                                result_b64 = attrs.get("result-payload-b64", "")
                                result_decoded = (
                                    self._decode_block_payload(result_b64) if result_b64 else None
                                )
                                if (
                                    isinstance(result_decoded, dict)
                                    and result_decoded.get("type", "").endswith("_tool_result")
                                ):
                                    blocks.append(result_decoded)
                                    if result_decoded.get("tool_use_id"):
                                        consumed_results.add(result_decoded["tool_use_id"])
                                else:
                                    # No embedded result — pull the standalone
                                    # carrier forward so the pair stays adjacent.
                                    tool_use_id = decoded.get("id", "")
                                    if tool_use_id in standalone_results:
                                        blocks.append(standalone_results[tool_use_id])
                                        consumed_results.add(tool_use_id)
                                    else:
                                        logger.warning(
                                            "server_tool_use id=%r has no result carrier; "
                                            "replaying it unpaired will 400 the request",
                                            tool_use_id,
                                        )
                            # else: legacy/missing payload → drop
                        elif kind == "server_tool_result":
                            attrs_str = match.group(1)
                            attrs = dict(PATTERN_DATA_ATTR.findall(attrs_str))
                            payload_b64 = attrs.get("payload-b64", "")
                            decoded = self._decode_block_payload(payload_b64) if payload_b64 else None
                            if isinstance(decoded, dict) and decoded.get("type", "").endswith("_tool_result"):
                                # Skip what was already pulled forward next to
                                # its server_tool_use above.
                                if decoded.get("tool_use_id") not in consumed_results:
                                    blocks.append(decoded)
                            # else: legacy/missing payload → drop
                        elif kind == "hidden":
                            # One carrier may hold several blocks (a merged
                            # server_tool_use + its *_tool_result), replayed in
                            # the order they were emitted.
                            decoded = self._decode_block_payload(match.group(1))
                            if isinstance(decoded, list):
                                blocks.extend(
                                    b for b in decoded if isinstance(b, dict) and b.get("type")
                                )
                            # else: corrupt payload → drop
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

                        # Resolve the real format from the bytes and transcode if
                        # needed. OpenWebUI's mime label is not trustworthy --
                        # see _resolve_image_for_anthropic.
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

                        # Check image size - API has 32MB request limit, but be conservative
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
        """Convert OpenWebUI tool_calls format to Claude tool_use format."""
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
        """Convert OpenWebUI tool_results format to Claude tool_result format."""
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

    # What the Anthropic API accepts as an image block.
    ANTHROPIC_IMAGE_TYPES = ("image/jpeg", "image/png", "image/gif", "image/webp")

    # ISO-BMFF brands identifying a HEIF-family still image. iPhone photos use
    # heic/heix; mif1/msf1 appear on images written by other encoders.
    _HEIF_BRANDS = frozenset({
        b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"hevm", b"hevs",
        b"mif1", b"msf1",
    })
    _AVIF_BRANDS = frozenset({b"avif", b"avis"})

    @classmethod
    def _sniff_image_media_type(cls, raw: bytes) -> Optional[str]:
        """Identify an image from its leading bytes, ignoring any declared type.

        Necessary because OpenWebUI's label is wrong in two different ways
        (both in MessageInput.svelte):

          * Its HEIC branch tests `file.type === 'image/heic'` exactly, so
            `image/heif`, the `*-sequence` variants, and the very common case of
            an empty `file.type` skip conversion entirely.
          * When conversion DOES run, the resulting JPEG is re-wrapped with
            `new File([blob], name, { type: file.type })` -- the ORIGINAL type.
            So a successfully converted image still arrives labelled HEIC.

        The bytes are the only reliable source.
        """
        if raw.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if raw.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if raw[:6] in (b"GIF87a", b"GIF89a"):
            return "image/gif"
        if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
            return "image/webp"
        # ISO-BMFF: size, then "ftyp", then the brand.
        if raw[4:8] == b"ftyp":
            brand = raw[8:12]
            if brand in cls._AVIF_BRANDS:
                return "image/avif"
            if brand in cls._HEIF_BRANDS:
                return "image/heic"
        return None

    @staticmethod
    def _transcode_image_to_jpeg(raw: bytes, media_type: str) -> Optional[bytes]:
        """Re-encode an image the API rejects into JPEG, or None if impossible.

        AVIF needs nothing extra (Pillow 11.3+ decodes it). HEIF does: Pillow
        ships no HEIF decoder for licensing reasons, so it needs pillow-heif,
        declared in the pipe's requirements header.
        """
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
            # JPEG has no alpha channel, and a palette or 16-bit source has to be
            # reduced before saving.
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
        """Return (media_type, base64_data, error_text).

        ``error_text`` is None on success; otherwise it is the placeholder to
        show in place of the image.
        """
        sniffed = cls._sniff_image_media_type(raw)

        # Trust the bytes. This alone repairs the mislabelled-JPEG case, which
        # needs no transcoding at all.
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
        """Move OpenWebUI's RAG template out of the prose into its own trailing
        text block. Returns True when something was moved.

        OpenWebUI merges the retrieved context straight INTO the existing text
        block and PREPENDS it (`utils/misc.py::update_message_content` with
        append=False), so prose and volatile context share one block. That makes
        the volatile part unexcludable: a cache breakpoint marks the end of a
        prefix, so there is no way to cache the question without also caching
        chunks that will be different -- or gone -- next turn. The pipe could
        only retreat a whole message, giving up the current question and the
        preceding assistant answer as well.

        Splitting it out makes the rule uniform with relocated memories: every
        volatile block trails the stable content, and the breakpoint goes on the
        last stable block.

        The text is moved VERBATIM, so what the model reads is unchanged except
        for its position: the context now follows the question instead of
        preceding it. That is the deliberate trade -- Anthropic's "documents
        early" advice is a soft quality heuristic aimed at stable documents,
        while a re-retrieved chunk set inside the cached prefix costs a full
        prefix rewrite on every single turn. Stable documents (native PDF
        upload) are untouched by this and keep their leading position.
        """
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
            # Strip, so a leftover newline cannot itself become cache drift.
            block["text"] = (text[: match.start()] + text[match.end():]).strip()

        if not extracted:
            return False

        # A message that was nothing but RAG would leave an empty text block,
        # which the API rejects.
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
        """Reconstruct structured Claude messages from an OpenWebUI assistant
        string that contains ``<details type="tool_calls">`` HTML blocks.

        OpenWebUI stores the entire assistant turn (including tool calls and
        results) as a single flat text string. To replay the conversation via
        the Claude API we must parse that HTML back into structured
        ``tool_use`` / ``tool_result`` blocks and emit the correct
        assistant→user→assistant sequence.

        Returns a list of ``{"role": ..., "content": [...]}`` dicts. Each
        consecutive run of ``tool_calls`` becomes one assistant message with
        multiple ``tool_use`` blocks followed by a single user message carrying
        all matching ``tool_result`` blocks. Text between tool-call runs
        terminates the current turn and starts a new assistant message.
        """
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
            """Emit the accumulated assistant/tool_result messages and reset the buffers."""
            if current_assistant:
                messages.append({"role": "assistant", "content": list(current_assistant)})
                current_assistant.clear()
            if pending_results:
                messages.append({"role": "user", "content": list(pending_results)})
                pending_results.clear()

        for kind, data in segments:
            if kind == "text":
                # Emptiness is checked BEFORE the flush, not after. Consecutive
                # tool-call blocks are separated by an empty segment (the pattern
                # eats the newline on both sides), and flushing on that split a
                # single multi-tool assistant turn into one message per tool --
                # a valid but different structure than the live turn, so the
                # prefix diverged there.
                if not data.strip():
                    continue
                # Reuse the existing converter for text (handles compaction
                # extraction and code_interpreter stripping). It will also no-op
                # on the already-extracted tool_calls HTML.
                blocks = self._convert_content_to_claude_format(data, role="assistant")
                if not blocks:
                    continue
                # Only real prose terminates the prior turn. A segment holding
                # nothing but server-tool carriers (web_search and friends are
                # rendered as <details type="tool_calls"> too, but carry
                # data-payload-b64 and are therefore skipped by
                # PATTERN_TOOL_CALLS_BLOCK) belongs to the SAME assistant
                # message it was emitted in. Flushing there produced
                # assistant[text, tool_use] / user[tool_result] /
                # assistant[server_tool_use] -- three messages where the live
                # turn had two.
                if pending_results and any(
                    isinstance(b, dict) and b.get("type") == "text" for b in blocks
                ):
                    flush()
                current_assistant.extend(blocks)
            else:  # tool_call
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
                    # Route through the same converter as live tool results:
                    # embedded data:image URIs become real image blocks instead
                    # of raw base64 text (~1.5k vs ~170k tokens per image), and
                    # the TOOL_RESULT_MAX_TOKENS backstop applies on replay too.
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
                    # Interrupted / aborted tool call — synthesize an error
                    # result so the assistant/user chain stays valid.
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
        """
        Convert a raw client-tool result string into Anthropic tool_result content.

        Detects `data:image/<fmt>;base64,...` data URIs (as produced by e.g. a
        file-reading tool returning a PNG/JPEG) and converts them into real
        Anthropic image blocks instead of sending the raw base64 as TEXT - the
        same image costs ~1.5k tokens as an image block vs. ~170k tokens as
        text, and Claude can actually see it. Mixed text+image output is split
        into ordered text/image blocks; non-image output is returned unchanged
        (as a plain string) except for a token-count backstop
        (UserValves.TOOL_RESULT_MAX_TOKENS) that truncates runaway tool text.

        Returns either a plain string (old behavior: no image, no truncation)
        or a list of Anthropic content blocks (text/image).
        """
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
        """
        Backstop against a runaway non-image tool result blowing the context
        window. Truncates to UserValves.TOOL_RESULT_MAX_TOKENS (estimated as
        len//4 chars). 0 disables the guard. Image blocks are exempt - they
        are already cheap after conversion.
        """
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
        """
        Read the user's OpenWebUI image-compression max dimensions from
        __user__["settings"]["ui"] (keys "imageCompression" bool and
        "imageCompressionSize" {"width":.., "height":..}). Falls back to a
        1568px long-edge cap (Anthropic's own recommended max before it
        downscales anyway) when compression is off or dims aren't set.
        """
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
        """
        Decode a base64 image payload extracted from a tool result into an
        Anthropic image content block, downscaling it per
        _get_tool_result_image_max_dims() to keep token cost low. Falls back
        to the original image (if under the 25MB cap) or a text placeholder
        on any decode/resize failure - mirrors the size-cap approach used for
        image_url content blocks above.
        """
        media_type = f"image/{mime_type}"
        MAX_IMAGE_SIZE = 25 * 1024 * 1024  # 25 MB (conservative, matches the image_url path)

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
        """
        Convert OpenWebUI tools format to Claude API format.

        Extracts tool specs from TWO sources:
        1. body.tools - Built-in tools (OpenAI format specs only, no callables)
        2. __tools__ - User tools (specs + callables for execution)

        Args:
            __tools__: Dict of user tools with callables from OpenWebUI
            body: Request body containing body.tools (built-in tool specs)
            actual_model_name: Model name for capability checking
            __user__: User dict for valve overrides
            __metadata__: Metadata dict for checking enforcement flags
        Returns:
            tuple: (Tools in Claude API format, set of API-provided tool names without callables)
        """
        claude_tools = []
        tool_names_seen = set()  # Track unique tool names
        api_tool_names = set()  # Track tools from body.tools (no callable, API passthrough)
        forced_tool_name = None
        requested_tool_choice = body.get("tool_choice")
        if isinstance(requested_tool_choice, dict):
            if requested_tool_choice.get("type") == "function":
                forced_tool_name = (requested_tool_choice.get("function") or {}).get("name")
            elif requested_tool_choice.get("type") == "tool":
                forced_tool_name = requested_tool_choice.get("name")

        # Names reserved for Anthropic server-side tools (skip if found in body.tools)
        anthropic_server_tool_names = {"web_search", "web_fetch"}

        # Open Terminal bridge activation: if native bash / text_editor tools
        # are enabled AND the required Open Terminal callables are present,
        # route Claude's native tool calls through them and hide the raw
        # callables from the regular tool list (Claude only sees the native
        # bash / str_replace_based_edit_tool definitions).
        has_run_command = bool(__tools__ and "run_command" in __tools__ and __tools__["run_command"].get("callable"))
        has_write_file = bool(__tools__ and "write_file" in __tools__ and __tools__["write_file"].get("callable"))
        has_replace_file = bool(__tools__ and "replace_file_content" in __tools__ and __tools__["replace_file_content"].get("callable"))
        # Only bridge when Open Terminal is actually active for this request.
        # `terminal_id` is OpenWebUI's canonical signal (set from the request
        # body when a terminal session is attached); the callables can linger
        # in __tools__ without an active terminal, so gating on presence alone
        # is unreliable. No terminal_id → native tools are not injected and the
        # request falls back to code_execution (see request_payload.py).
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

        # Extract built-in tools from body.tools (OpenAI format)
        # User tools are collected separately and appended name-sorted. OpenWebUI
        # builds both `body["tools"]` and `__tools__` from a dict whose insertion
        # order follows `tool_ids` — and that order shifts on its own (toggling a
        # tool appends it to the end of `selectedToolIds`, a page reload resets it
        # to the model's own order, MCP servers return whatever order they like).
        # Same tool set, different order, whole prompt cache gone. Sorting makes
        # the tools array depend on the set, not on how the user got there.
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

                    # Skip tools that will be handled by Anthropic server-side tools
                    if name in anthropic_server_tool_names:
                        logger.info(f"Skipping body tool '{name}' — handled by Anthropic server tool")
                        continue

                    # Skip Open Terminal callables that are being bridged to
                    # native bash / text_editor tools.
                    if name in terminal_hidden_names:
                        logger.info(f"Skipping body tool '{name}' — bridged to native Claude tool")
                        continue

                    # Convert OpenAI format to Claude format
                    claude_tool = {
                        "name": name,
                        "description": func.get("description", f"Tool: {name}"),
                        "input_schema": func.get(
                            "parameters", {"type": "object", "properties": {}}
                        ),
                    }
                    body_user_tools.append(claude_tool)
                    tool_names_seen.add(name)
                    # Track as API-provided tool (no callable — for passthrough)
                    if not (__tools__ and name in __tools__ and __tools__[name].get("callable")):
                        api_tool_names.add(name)

            claude_tools.extend(sorted(body_user_tools, key=lambda t: t["name"]))

        # Log user tools from __tools__
        if __tools__ and logger.isEnabledFor(logging.DEBUG):
            # Only attempt serialization if DEBUG is enabled
            try:
                logger.debug(
                    f"Converting {len(__tools__)} user tools: {json.dumps(__tools__, indent=2)}"
                )
            except (TypeError, ValueError):
                # Log tool names only if full serialization fails
                tool_names = list(__tools__.keys())[:10]
                logger.debug(
                    f"Converting {len(__tools__)} user tools (names): {tool_names}{'...' if len(__tools__) > 10 else ''}"
                )
        elif not __tools__:
            logger.debug("No user tools to convert")

        # Add web search tool if enabled OR if metadata enforces it (even if valve is disabled)
        web_search_enabled = self.valves.WEB_SEARCH or __metadata__.get(
            "web_search_enforced", False
        )
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
            # web_search_20260209 has dynamic filtering (code execution post-processes results)
            # web_search_20250305 works on all models without dynamic filtering
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
            # max_uses is only supported on web_search_20250305 (non-dynamic filtering)
            # Dynamic filtering versions (20260209) don't document max_uses support
            if web_search_type == "web_search_20250305":
                web_search_tool["max_uses"] = __user__["valves"].WEB_SEARCH_MAX_USES

            # Only add user_location if at least one field has a value.
            # Only include non-empty fields to avoid Anthropic API validation errors
            # (e.g. country must be ISO 3166-1 alpha-2, can't be empty string)
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

        # Add web_fetch tool if enabled
        # web_fetch_20260209 has dynamic filtering (requires code execution)
        # web_fetch_20250910 works on all models without dynamic filtering
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
            # max_uses is only supported on web_fetch_20250910 (non-dynamic filtering)
            # Dynamic filtering versions (20260209) don't document max_uses support
            if web_fetch_type == "web_fetch_20250910":
                web_fetch_tool["max_uses"] = __user__["valves"].WEB_FETCH_MAX_USES
            claude_tools.append(web_fetch_tool)
            tool_names_seen.add("web_fetch")
            logger.debug(f"Added web_fetch tool: {web_fetch_type}")

        # Add advisor tool if enabled (beta). Executor↔advisor pair validation
        # The advisor must be at least as capable as the executor.
        # If the pair is invalid, downgrade the advisor to the next compatible model.
        if __user__["valves"].ENABLE_ADVISOR_TOOL:
            executor_model = actual_model_name
            advisor_model = __user__["valves"].ADVISOR_MODEL

            # Valid advisor models per executor (advisor must be ≥ executor in capability),
            # strongest first so allowed[0] is the best fallback. These lists already only
            # contain API-supported advisors, so a single membership check covers both
            # "unsupported" and "incompatible" cases.
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

        # Inject native bash tool (bridged to Open Terminal's run_command)
        if bash_active:
            claude_tools.append({"type": "bash_20250124", "name": "bash"})
            tool_names_seen.add("bash")
            logger.debug("Added native bash tool (bridged to run_command)")

        # Inject native text editor tool (bridged to write_file + replace_file_content)
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

        # Process user tools from __tools__ (these have callables for execution)
        if __tools__ and len(__tools__) > 0:
            for tool_name, tool_data in __tools__.items():
                if not isinstance(tool_data, dict) or "spec" not in tool_data:
                    logger.debug(f"Skipping invalid tool: {tool_name} - missing spec")
                    continue

                spec = tool_data["spec"]

                # Extract basic tool info
                name = spec.get("name", tool_name)

                # Skip if tool name already exists
                if name in tool_names_seen:
                    continue

                # Skip if toolname starts with _ or __
                if name.startswith("_"):
                    logger.debug(f"Skipping private tool: {name}")
                    continue

                # Skip Open Terminal callables that are bridged to native
                # Claude bash / text_editor tools — they must not appear as
                # regular user tools or Claude will see duplicates.
                if name in terminal_hidden_names:
                    logger.debug(f"Skipping bridged Open Terminal tool: {name}")
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

                user_tools.append(claude_tool)
                tool_names_seen.add(name)

            claude_tools.extend(sorted(user_tools, key=lambda t: t["name"]))

        # Check if programmatic tool calling is active for this model
        # When active, tools must NOT be deferred (defer_loading) because
        # deferred tools loaded via tool_search may bypass allowed_callers enforcement
        is_programmatic_active = False
        if self.valves.ENABLE_PROGRAMMATIC_TOOL_CALLING:
            model_info_ptc = self.get_model_info(actual_model_name)
            is_programmatic_active = model_info_ptc.get("supports_programmatic_calling", False)

        _defer_active = __user__["valves"].ENABLE_TOOL_SEARCH and not is_programmatic_active

        for claude_tool in claude_tools:
            # Check if tool should be deferred for tool search
            # IMPORTANT: Skip deferring when programmatic tool calling is active.
            if _defer_active:
                # Skip deferring if tool is in exclusion list
                name = claude_tool["name"]
                user_excludes = __user__["valves"].TOOL_SEARCH_EXCLUDE_TOOLS
                if (
                    name != forced_tool_name
                    and name not in user_excludes
                ):
                    # Calculate tool definition size (JSON representation)
                    tool_json = json.dumps(claude_tool)
                    tool_len = len(tool_json)
                    if len(tool_json) > __user__["valves"].TOOL_SEARCH_MAX_DESCRIPTION_LENGTH:
                        claude_tool["defer_loading"] = True
                    else:
                        logger.debug(f"Tool '{name}' will be loaded normally")

            # Add allowed_callers for programmatic tool calling (only if model supports it)
            # When enabled, tools can be called from code execution
            # With code_execution_20260120 explicitly in the tools list, we can safely
            # add allowed_callers even alongside dynamic filtering tools (20260209) —
            # the explicit code_execution_20260120 supersedes auto-injection.
            if self.valves.ENABLE_PROGRAMMATIC_TOOL_CALLING:
                model_info = self.get_model_info(actual_model_name)
                if model_info.get("supports_programmatic_calling", False):
                    # Only add to user-defined tools (not server tools like web_search, web_fetch, memory)
                    if "type" not in claude_tool:  # Server tools have a "type" field
                        claude_tool["allowed_callers"] = ["code_execution_20260120"]

            # Enable fine-grained tool streaming for user-defined tools
            # Streams tool input JSON without buffering, reducing latency for large inputs
            # GA on all models, no beta header required
            if "type" not in claude_tool:  # Only user-defined tools (not server tools)
                claude_tool["eager_input_streaming"] = True

        if any(tool.get("defer_loading", False) for tool in claude_tools):
            if __user__["valves"].TOOL_SEARCH_TYPE == "regex":
                tool_search_tool = {
                    "type": "tool_search_tool_regex_20251119",
                    "name": "tool_search_tool_regex",
                }
            else:  # bm25 (default)
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
        """
        Read a PDF file from storage and return base64 encoded data.

        Args:
            file_id: The OpenWebUI file ID

        Returns:
            tuple[str, str]: (base64_data, filename) or None if not available
        """
        if not FILES_AVAILABLE:
            logger.warning("Files/Storage modules not available for PDF native upload")
            return None

        try:
            file = await Files.get_file_by_id(file_id)
            if not file:
                logger.warning(f"File not found: {file_id}")
                return None

            # Check if it's a PDF
            content_type = file.meta.get("content_type", "")
            filename = file.meta.get("name", file.filename)

            if content_type != "application/pdf" and not filename.lower().endswith(
                ".pdf"
            ):
                logger.debug(f"File {file_id} is not a PDF: {content_type}")
                return None

            # Get file path from storage
            file_path = Storage.get_file(file.path)
            file_path = Path(file_path)

            if not file_path.is_file():
                logger.warning(f"PDF file not found on disk: {file_path}")
                return None

            # Read and encode the PDF
            with open(file_path, "rb") as pdf_file:
                pdf_data = pdf_file.read()
                encoded_data = base64.b64encode(pdf_data).decode("utf-8")

            # Check size limits (Anthropic has 32MB request limit, be conservative)
            MAX_PDF_SIZE = 25 * 1024 * 1024  # 25 MB
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
        """Recursively collect file/id-like identifiers from a nested dict/list structure."""
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
        """Decide which user message each full-context file belongs to.

        Shared by the native-PDF path and the plain-text path: both must pin a
        file to the message it was attached to, because a block that moves to
        the newest message every turn rewrites the cache prefix every turn.

        Anchor priority per file:
          1) a marker persisted by an earlier pipe turn,
          2) ownership in OpenWebUI's raw ``message.files``,
          3) the latest user message, for genuinely new uploads.

        Files known only from prior markers are re-included, because OpenWebUI
        does not reliably re-send full-context files in ``__files__`` on
        follow-up turns; dropping them would make the block vanish mid-history.

        ``accept`` filters by filename (PDF vs. everything else). Returns
        ``(file_id -> anchor_msg_idx, file_id -> filename)``, both ordered by
        (anchor, file_id) so the rendered block order cannot drift between turns
        just because the underlying dicts were populated from different sources.
        """
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
        """Return the plain text OpenWebUI extracted for a file, or None.

        This is the same content OpenWebUI itself injects into its ``<context>``
        template for a full-context file, so reading it here changes what the
        model sees only in position, not in substance -- and it keeps working on
        later turns, when the file is gone from ``__files__``.
        """
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
        """Turn non-native full-context uploads into anchored, cacheable text blocks.

        A file uploaded with Full Context arrives inside OpenWebUI's
        ``### Task: ... <context><source>...`` template, merged into the last
        user message. The cache-control pass has to treat that template as
        volatile -- for retrieved RAG chunks it genuinely is, they are re-ranked
        against every new question -- so the breakpoint lands *before* it and the
        file is re-sent uncached on every single turn. For a 2 MB EPUB that is
        the whole book, every turn.

        A full-context file is not volatile, though: it is the entire file, the
        same bytes each turn. So it gets the same treatment PDFs already get --
        anchored to the user message it was attached to, placed ahead of the
        prose, and cut out of the RAG template by the caller. From there the
        existing breakpoint covers it and the book is written to cache once.

        Returns ``(anchor_msg_idx -> blocks, markers, filenames)``; the filenames
        are what the caller must strip from the RAG template.
        """
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
        """
        Extract PDFs from __files__ that should be uploaded as native documents.

        Each PDF is anchored to the user-message it was first attached to so that
        the byte-prefix of the conversation stays cache-stable across turns. New
        PDFs are anchored to the most recent user message; PDFs that were already
        anchored on previous turns are restored at the same anchor index by
        re-loading the base64 from disk.

        Args:
            __files__: List of file objects from OpenWebUI (current turn).
            previous_marker_metadata: Marker entries extracted from the prior
                assistant message. Each entry is "msg_idx:id:url_encoded_value".
            processed_messages: Full message list — used to count user messages
                and decide where to anchor new PDFs.
            raw_messages: Original OpenWebUI messages. Historical user messages
                can carry a `files` list, which is the most reliable source for
                restoring the original PDF attachment turn when OpenWebUI keeps
                passing old full-context files in `__files__`.

        Returns:
            tuple:
              - dict[int, list[dict]] mapping user_msg_index → list of document
                blocks to prepend to that message's content.
              - list of metadata markers (already formatted strings) that should
                be appended to the next assistant text response.
        """
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
            # Re-load base64 every turn (Anthropic native PDF blocks have no
            # file-id reuse; the bytes must be present for the cache prefix to
            # remain stable)
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
        """Download file from Anthropic Files API, save to OpenWebUI, return markdown link."""
        try:
            from anthropic import AsyncAnthropic
            import hashlib
            import io
            import uuid

            client = self._build_anthropic_client(api_key)

            # Get file metadata first
            file_meta = await client.beta.files.retrieve_metadata(file_id=file_id)
            filename = getattr(file_meta, "filename", file_id) or file_id

            # Download file content (async binary response — .read() is a coroutine)
            response = await client.beta.files.download(file_id=file_id)
            content = await response.read()

            # Save to OpenWebUI storage. upload_file(file: BinaryIO, filename, tags)
            # returns a (contents, file_path) tuple; tags is required.
            owui_file_id = str(uuid.uuid4())
            storage_filename = f"code_exec_{owui_file_id}_{filename}"
            _, file_path = Storage.upload_file(io.BytesIO(content), storage_filename, {})

            # Create OpenWebUI file record
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

            # Return markdown download link
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
        """
        Process files for Anthropic Files API using container_upload.

        Uploads files to Anthropic and caches the file_id in OpenWebUI file metadata.
        Tracks which user message each file belongs to for correct positioning.

        Returns:
            tuple: (
                Dict mapping user_msg_number → list of container_upload blocks,
                List of filenames that were processed (for RAG source removal)
            )
        """
        blocks_by_user_msg: Dict[int, List[Dict[str, Any]]] = {}
        processed_filenames: List[str] = []
        status_cls = globals().get("StatusEmitter")
        status = status_cls(__event_emitter__) if status_cls else None

        async def emit_status(description: str, *, done: bool = False) -> None:
            """Emit a status update via StatusEmitter if available, else fall back to a raw status event."""
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
            """Emit a notification via StatusEmitter if available, else fall back to a raw notification event."""
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

        # Count user messages to determine "current" position for new files
        user_msg_count = sum(1 for m in processed_messages if m["role"] == "user")
        current_user_msg_num = max(0, user_msg_count - 1)  # 0-based

        client = None
        try:
            from anthropic import AsyncAnthropic
            client = self._build_anthropic_client(self.valves.ANTHROPIC_API_KEY)
        except ImportError:
            logger.warning("Anthropic SDK not available for file upload")
            return blocks_by_user_msg, processed_filenames

        for file in __files__:
            # Skip non-file entries (RAG chunks, knowledge base refs, etc.)
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

            # Skip images — they use Vision (base64/URL), not Files API
            content_type = file.get("content_type", "")
            if not content_type:
                # Fallback: check OpenWebUI file meta for content_type
                file_record_check = await Files.get_file_by_id(file_id_owui)
                if file_record_check and file_record_check.meta:
                    content_type = file_record_check.meta.get("content_type", "")
            if content_type and content_type.startswith("image/"):
                logger.debug(f"Skipping image file for Files API: {file_name} ({content_type})")
                continue

            # Look up OpenWebUI file record for cached anthropic_file_id
            file_record = await Files.get_file_by_id(file_id_owui)
            if not file_record:
                logger.warning(f"File not found in DB: {file_id_owui}")
                continue

            meta = file_record.meta or {}
            anthropic_file_id = meta.get("anthropic_file_id")
            msg_num = meta.get("anthropic_file_msg_idx")

            if anthropic_file_id:
                # Cached — reuse without re-uploading
                if msg_num is None:
                    msg_num = current_user_msg_num
                logger.debug(f"♻️ Reusing cached file {file_name} → {anthropic_file_id} (msg {msg_num})")
            else:
                # New file — upload to Anthropic
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

                    # Cache in OpenWebUI file metadata
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

            # Group container_upload block by user message number
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
        """
        Validate user-specified skill names against the Anthropic List Skills API.

        Skills can be specified as:
        - Anthropic skills: Short names like "pptx", "xlsx", "docx", "pdf"
        - Custom skills: Full IDs like "skill_01AbCdEfGhIjKlMnOpQrStUv"

        Validation results are cached per API key to avoid repeated API calls.

        Args:
            skill_names: List of skill names/IDs from user's SKILLS valve
            api_key: Anthropic API key
            __event_emitter__: Optional event emitter for status updates

        Returns:
            List of validated skill configurations for the container parameter
        """
        if not skill_names:
            return []

        status = None
        if __event_emitter__:
            status_cls = globals().get("StatusEmitter")
            status = status_cls(__event_emitter__) if status_cls else None

        async def emit_status(description: str, *, done: bool = False, hidden: bool | None = None) -> None:
            """Emit a status update via StatusEmitter if available, else fall back to a raw status event."""
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
            """Emit a notification via StatusEmitter if available, else fall back to a raw notification event."""
            if not __event_emitter__:
                return
            if status and hasattr(status, "notification"):
                await status.notification(content, type=type)
                return
            await self.emit_event(
                {"type": "notification", "data": {"type": type, "content": content}},
                __event_emitter__,
            )

        # Initialize cache for this API key if needed
        if api_key not in self._validated_skills_cache:
            self._validated_skills_cache[api_key] = {}

        cache = self._validated_skills_cache[api_key]

        # Check which skills need validation
        skills_to_validate = [s for s in skill_names if s not in cache]

        # If we have skills to validate, fetch from API
        if skills_to_validate:
            logger.debug(
                f"🔧 Validating {len(skills_to_validate)} skills via API: {skills_to_validate}"
            )

            await emit_status("🔧 Validating Skills...", hidden=True)

            try:
                from anthropic import AsyncAnthropic

                client = self._build_anthropic_client(api_key)

                # Fetch all available skills
                available_skills = {}

                def index_skill(info: dict[str, Any]) -> None:
                    """Index a skill under its id/display_title and common format aliases (xlsx/pptx/docx/pdf)."""
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

                # Fetch Anthropic skills
                try:
                    anthropic_skills = await client.beta.skills.list(
                        source="anthropic", betas=["skills-2025-10-02"]
                    )
                    for skill in anthropic_skills.data:
                        # Store by both id and display_title for flexible matching
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

                # Fetch custom skills
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

                # Validate each skill
                for skill_name in skills_to_validate:
                    skill_lower = skill_name.lower().strip()

                    # Try exact match first
                    if skill_name in available_skills:
                        cache[skill_name] = available_skills[skill_name]
                        logger.debug(f"✓ Validated skill '{skill_name}' (exact match)")
                    # Try lowercase match
                    elif skill_lower in available_skills:
                        cache[skill_name] = available_skills[skill_lower]
                        logger.debug(
                            f"✓ Validated skill '{skill_name}' (case-insensitive match)"
                        )
                    else:
                        # Mark as invalid
                        cache[skill_name] = None
                        logger.warning(
                            f"✗ Invalid skill '{skill_name}' - not found in available skills"
                        )

            except Exception as e:
                logger.error(f"Failed to validate skills: {e}")
                # Mark all as failed validation
                for skill_name in skills_to_validate:
                    cache[skill_name] = None

        # Build the validated skills list
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
        """
        Remove specific <source> tags from RAG content by filename.

        Args:
            rag_content: RAG message with <context> and <source> tags
            filenames_to_remove: List of filenames to remove from RAG sources

        Returns:
            str: RAG content with specified sources removed, or empty string if all sources removed
        """
        if not filenames_to_remove:
            return rag_content

        # Remove each source tag that matches the filenames
        modified = rag_content
        for filename in filenames_to_remove:
            # Match source tags with this filename in the name attribute
            # Need to escape the filename for regex but match it exactly
            pattern = re.compile(
                rf'<source[^>]*name="{re.escape(filename)}"[^>]*>.*?</source>\s*',
                re.DOTALL,
            )
            modified = pattern.sub("", modified)

        # Check if all sources were removed (only <context></context> or empty context remains)
        if PATTERN_EMPTY_CONTEXT.search(modified) or not PATTERN_SOURCE_TAGS.search(
            modified
        ):
            # All sources removed - remove entire RAG template
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
        """
        Remove specific sources from RAG messages by filename.
        Only removes the sources matching the given filenames, keeps other sources.
        If all sources are removed, the entire RAG template is removed.

        Args:
            processed_messages: List of messages to process
            filenames_to_remove: List of filenames whose sources should be removed from RAG
        """
        if not filenames_to_remove:
            return

        # Find the last user message with RAG content
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

                # Found RAG content - extract and modify it
                rag_content = match.group(0)
                modified_rag = self._remove_sources_from_rag(
                    rag_content, filenames_to_remove
                )

                start, end = match.span()
                if not modified_rag:
                    # All sources removed - remove entire RAG block
                    new_text = text[:start] + text[end:]
                    logger.debug(
                        f"📋 RAG: Removed entire RAG block (all sources matched)"
                    )
                else:
                    # Some sources remain - update with modified RAG
                    new_text = text[:start] + modified_rag + text[end:]
                    logger.debug(
                        f"📋 RAG: Kept partial RAG content (some sources remain)"
                    )

                # Strip whitespace to prevent cache invalidation from leftover newlines
                new_text = new_text.strip()
                if new_text:
                    new_block = dict(block)
                    new_block["text"] = new_text
                    new_content.append(new_block)

                modified = True

            if modified:
                processed_messages[i]["content"] = new_content
                return  # Only process the first matching user message

    def _extract_and_remove_memories(self, text: str) -> tuple[str, Optional[str]]:
        """
        Extract memories injected by the OpenWebUI Memory System out of the system
        prompt and remove them from it.

        Two injection formats are recognised, because OpenWebUI changed shape:
          * ``<memory_context>...</memory_context>`` (current, utils/memory.py) —
            can sit anywhere in the system message.
          * ``\nUser Context:\n...`` (legacy) — runs to the end of the string.

        Both are re-retrieved and re-ranked per request, so they are never stable
        across turns. Leaving them in ``system`` costs a full prefix rewrite every
        turn (the API reports it as cache_miss_reason=system_changed); the caller
        relocates the return value to the last user message instead.

        Returns:
            tuple[str, Optional[str]]: (cleaned_text, extracted_context)
            - cleaned_text: Original text with all memory blocks removed (stripped)
            - extracted_context: The extracted memories with label, or None if none found
        """
        # Fast path: two substring scans are far cheaper than two regex scans,
        # and presence of the marker is the ground truth. Deliberately *not*
        # gated on a config flag — OpenWebUI decides to inject based on the
        # request's `features.memory` plus an admin-level ConfigVar, neither of
        # which the pipe can observe reliably. A gate that disagrees with what
        # actually arrived is what broke the cache in the first place.
        if "<memory_context>" not in text and "User Context:" not in text:
            return text.strip(), None

        extracted_parts: list[str] = []

        # <memory_context> may appear anywhere; strip every occurrence.
        def _take_memory_context(match) -> str:
            content = match.group(1).strip()
            if content:
                extracted_parts.append(content)
            return ""

        cleaned_text = PATTERN_MEMORY_CONTEXT.sub(_take_memory_context, text)

        # Legacy tail form.
        match = PATTERN_USER_CONTEXT.search(cleaned_text)
        if match:
            context_content = match.group(1).strip()
            if context_content:
                extracted_parts.append(f"User Context:\n{context_content}")
            # Remove "\nUser Context:\n" and everything after it
            cleaned_text = cleaned_text[: match.start()]

        extracted_context = "\n\n".join(extracted_parts) if extracted_parts else None
        return cleaned_text.strip(), extracted_context

    def _create_metadata_marker(self, id: str, value: str, messagenum: int = 0) -> str:
        """Build a URL-encoded inline metadata marker string for embedding in assistant text."""
        # URL-encode to handle special characters
        encoded_value = quote(value, safe="")
        return f" [](anthropic:{messagenum}:{id}:{encoded_value}) "

    def _extract_metadata_marker_from_message(self, message) -> List[str]:
        """
        Extract Anthropic metadata from the LAST assistant message in conversation.
        """
        metadata: List[str] = []
        if not isinstance(message, dict):
            return metadata
        if message.get("role") == "assistant":
            text = None
            content = message.get("content")
            if isinstance(content, list):
                # Join all text blocks for searching, but also update blocks in-place
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        block_text = block.get("text", "")
                        matches = self.METADATA_PATTERN.findall(block_text)
                        for match in matches:
                            metadata.append(match)
                        # Remove all metadata markers from this block
                        cleaned_text = self.METADATA_PATTERN.sub("", block_text)
                        block["text"] = cleaned_text
            elif isinstance(content, str):
                matches = self.METADATA_PATTERN.findall(content)
                for match in matches:
                    metadata.append(match)
                # Remove all metadata markers from the string
                message["content"] = self.METADATA_PATTERN.sub("", content)
        return metadata

    @staticmethod
    def _encode_block_payload(payload: Any) -> str:
        """Base64-encode a server-tool block payload (JSON) for byte-exact
        round-trip through OpenWebUI storage."""
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return base64.b64encode(raw.encode("utf-8")).decode("ascii")

    @staticmethod
    def _decode_block_payload(payload_b64: str) -> Optional[Any]:
        """Decode a base64-encoded JSON payload. Returns None on failure."""
        try:
            return json.loads(base64.b64decode(payload_b64).decode("utf-8"))
        except Exception:
            return None

    @staticmethod
    def _block_visibility_key(name: str) -> str:
        """Map a tool name or *_tool_result block type onto its visibility key.

        A single logical block reaches the formatters under several names
        (`tool_search_tool_bm25` for the call, `tool_search_tool_result` for the
        result), but the user hides *one* concept. Normalising here keeps the
        HIDE_BLOCKS valve spelled in concepts rather than wire names.
        """
        key = name[: -len("_tool_result")] if name.endswith("_tool_result") else name
        if key.startswith("tool_search"):
            return "tool_search"
        # bash_code_execution / text_editor_code_execution are variants of the
        # same user-facing concept; hiding "code_execution" must cover all three.
        if key.endswith("code_execution"):
            return "code_execution"
        return key

    def _is_block_hidden(self, name: str) -> bool:
        """True when HIDE_BLOCKS opts this block concept out of visible rendering.

        Read from the request-scoped HIDDEN_BLOCKS ContextVar, which pipe() fills
        from the requesting user's UserValves — hiding a collapsible is a personal
        display preference, not an admin-wide one.
        """
        if SLIM_OUTPUT.get():
            return True
        hidden = HIDDEN_BLOCKS.get()
        if not hidden:
            return False
        return self._block_visibility_key(name) in hidden

    @staticmethod
    def _parse_hidden_blocks(raw: Any) -> frozenset:
        """Normalize the HIDE_BLOCKS valve into a set of block concept keys.

        The valve is a multiselect (``list[str]``) since v0.9.25. Values saved
        under the previous comma-separated ``str`` form are still accepted so an
        upgrade does not silently drop a user's preference.
        """
        if isinstance(raw, str):
            raw = raw.split(",")
        if not raw:
            return frozenset()
        return frozenset(str(part).strip() for part in raw if str(part).strip())

    def _format_hidden_block(self, payloads: list, label_id: str = "") -> str:
        """Render API blocks as an invisible, replay-stable markdown carrier.

        A markdown *link reference definition* is consumed by the tokenizer into
        the link table and produces no token at all, so OpenWebUI renders exactly
        nothing — unlike an HTML comment (shown as escaped text) or an empty
        `[](...)` link (an empty paragraph taking vertical space). The payload
        rides in the destination, which may not contain spaces; base64 satisfies
        that. Read back by ``PATTERN_HIDDEN_BLOCK`` on replay.

        The leading BLANK line is load-bearing, and a single newline is not
        enough: with only one, markdown absorbs the definition into the
        preceding paragraph as a lazy continuation line and renders the whole
        payload as visible text. Verified against marked 9.1.6 with OpenWebUI's
        `breaks: true` — "prose\\n[def]" leaks, "prose\\n\\n[def]" yields no token.
        """
        if SLIM_OUTPUT.get():
            # Nothing will ever replay this run, and the parent agent pays for
            # every byte of it. Drop the carrier entirely.
            return ""
        suffix = f"-{re.sub(r'[^A-Za-z0-9_]', '', label_id)}" if label_id else ""
        return f"\n\n[anthropic-hidden{suffix}]: #{self._encode_block_payload(payloads)}\n"

    @staticmethod
    def _stringify_terminal_result(result: Any) -> str:
        """Normalize Open Terminal callable results to a plain string.

        ``execute_tool_server`` returns a ``(data, headers)`` tuple where
        ``headers`` is a ``CIMultiDictProxy`` (not JSON-serializable). The
        OpenWebUI middleware unpacks ``[0]`` before dumping; we do the same
        here, then JSON-encode the data half.
        """
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
        """Emit a ``terminal:*`` UI event so Open Terminal refreshes the panel.

        Mirrors OpenWebUI's ``terminal_event_handler``: run_command → empty
        data, file ops → ``{"path": ...}``. Best-effort — event emission must
        never break tool execution, so failures are swallowed.
        """
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
        """Bridge native bash tool calls to Open Terminal's run_command callable.

        Open Terminal's `run_command` is *asynchronous*: it returns a process
        descriptor (``id``, ``status="running"``, empty ``output``) immediately
        and the actual stdout/stderr must be polled via ``get_process_status``.
        This wrapper hides that detail from the model — it polls until the
        process completes (or times out) and returns a single concatenated
        result string, so Claude's bash tool semantics ("send command, receive
        output") are preserved.

        - {command: "..."}  → run_command + poll until done.
        - {restart: true}   → no native restart endpoint exists; reset CWD via `cd ~`.
        """
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
        """Run a shell command via Open Terminal and wait for its result.

        Open Terminal's ``run_command`` is asynchronous by default, but both
        ``run_command`` and ``get_process_status`` accept a server-side
        long-poll ``wait`` (≤300s) that returns early when the process exits.
        Prefer that; fall back to sleep-polling for older terminal builds.
        Path/query parameter names must match the OpenAPI spec exactly
        (``process_id``, not ``id``) — OpenWebUI's tool wrapper silently drops
        unknown parameters, which turns into 404 "Process not found"."""
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

        # Synchronous path: server returned a final status (no id, or already done).
        if not isinstance(data, dict) or "id" not in data:
            return self._stringify_terminal_result(raw)
        status = data.get("status")
        if status and status != "running":
            return self._format_bash_process_result(data)

        process_id = data["id"]
        poll_cb = __tools__.get("get_process_status", {}).get("callable")
        if not poll_cb:
            # No polling tool available — surface the async descriptor as-is.
            return self._stringify_terminal_result(raw)

        delay = 0.25  # exponential backoff: 0.25 → 0.5 → 1 → 2 (cap)
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
                # Older terminal builds may not accept `wait` / `offset`
                if use_wait:
                    use_wait = False
                    continue
                poll_raw = await poll_cb(process_id=process_id)
            poll_data = self._parse_terminal_payload(poll_raw)
            if not isinstance(poll_data, dict):
                last_status = {"id": process_id, "status": "unknown"}
                break
            if "status" not in poll_data and "output" not in poll_data:
                # Error payload (e.g. {"detail": "Process not found"}) — stop
                # instead of hammering the endpoint until the deadline.
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
        """Ask the user to allow this tool call when approval mode is 'ask'.

        OpenWebUI 0.11.1 added human-in-the-loop tool approval, but it is enforced
        inside `utils/middleware.py` — i.e. only around OpenWebUI's OWN tool loop.
        A manifold that runs its own loop (this one) would execute tools
        unchallenged while the UI claims approval is on, so the gate is
        reproduced here at the single point where a tool coroutine is awaited.

        Returns ``(approved, denial_payload)``. The denial payload is fed back to
        Claude as this call's tool result, so a refusal reads as a normal
        (negative) result and the tool loop continues instead of stalling.
        """
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
            # A broken approval channel must not silently turn into free
            # execution — that is the exact failure the gate exists to prevent.
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
        """Await a tool coroutine and keep its tool_use metadata attached.

        ``timeout_s`` overrides the generic TOOL_CALL_TIMEOUT valve — the Open
        Terminal bash/text_editor bridges poll internally up to
        BASH_TOOL_TIMEOUT and must not be killed early by the generic limit."""
        if timeout_s is None:
            timeout_s = getattr(self.valves, "TOOL_CALL_TIMEOUT", self.TOOL_CALL_TIMEOUT)

        approved, denial = await self._await_tool_approval(tool_call_data)
        if not approved:
            if hasattr(awaitable, "close"):
                awaitable.close()  # never started; release it without a warning
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
        """Normalize an Open Terminal callable result into a Python object.

        ``execute_tool_server`` returns ``(data, headers)``. ``data`` is usually
        already a dict, but some callables stringify their JSON. Handle both."""
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
        """Render a completed Open Terminal process descriptor as a readable
        text payload for Claude. Concatenates ``output`` lines (which may be
        ``{stream: stdout|stderr, data: "..."}`` objects or plain strings) and
        appends exit metadata."""
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
        # Open Terminal reports success as "done"; older builds may use "completed".
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
        """Bridge native text_editor (str_replace_based_edit_tool) calls to
        Open Terminal's write_file / replace_file_content + run_command fallback
        for view/insert operations.
        """
        try:
            command = tool_input.get("command", "")
            path = tool_input.get("path", "")
            run_cmd = __tools__.get("run_command", {}).get("callable")

            if command == "view":
                # Prefer run_command with sed/cat -n; directory listings use ls.
                if not run_cmd:
                    return "Error: run_command callable required for `view`."
                view_range = tool_input.get("view_range")
                # Escape path minimally for shell
                safe_path = path.replace("'", "'\\''")
                if view_range and isinstance(view_range, list) and len(view_range) == 2:
                    start, end = view_range
                    if end == -1:
                        shell = f"sed -n '{int(start)},$p' '{safe_path}' | nl -ba -s': ' -w1"
                    else:
                        shell = f"sed -n '{int(start)},{int(end)}p' '{safe_path}' | nl -ba -s': ' -v{int(start)} -w1"
                else:
                    # Detect directory vs file, fall back to ls for dirs
                    shell = (
                        f"if [ -d '{safe_path}' ]; then ls -la '{safe_path}'; "
                        f"else cat -n '{safe_path}'; fi"
                    )
                text = await self._run_terminal_command(__tools__, shell)
                # view is read-only → open the file preview in the panel.
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
                # Implement via run_command: read → splice → write back.
                if not run_cmd:
                    return "Error: run_command callable required for `insert`."
                insert_line = int(tool_input.get("insert_line", 0))
                insert_text = tool_input.get("insert_text", "")
                payload = json.dumps({
                    "path": path,
                    "line": insert_line,
                    "text": insert_text,
                }, ensure_ascii=False)
                # Embed the JSON inside a python3 heredoc; parse with json.loads
                # so newlines/quotes in payload are safe.
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
                # insert mutates the file → treat as a content replacement refresh.
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
        """Persist a server_tool_use block (web_search, web_fetch, code_execution…)
        as collapsible <details> HTML carrying the opaque payload in a
        ``data-payload-b64`` attribute. Needed so the block can be
        reconstructed byte-exact on the next turn's API replay — otherwise
        thinking-block positions shift and the API rejects the assistant
        message with "thinking blocks cannot be modified".

        If ``result_payload`` + ``result_block_type`` are provided, the carrier
        ALSO embeds the matching *_tool_result payload via ``data-result-payload-b64``
        and ``data-result-block-type``. This lets a single visible collapsible
        represent BOTH the tool call and its result (API replay still emits
        two separate blocks in their original order).
        """
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
                # tool_search_tool_regex uses "patterns" (list),
                # tool_search_tool_bm25 uses "queries" (list).
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
            # Hidden: the whole <details> goes, not just its body. The status
            # emitter carries the user-facing information for this turn; the
            # carrier below only has to survive replay.
            blocks = [payload] + ([result_payload_dict] if result_payload_dict else [])
            return self._format_hidden_block(blocks, tool_use_id)

        if result_payload_dict is not None:
            result_payload_b64 = self._encode_block_payload(result_payload_dict)
            # NOTE: attribute key MUST NOT contain "type=" as a substring.
            # marked's attribute tokenizer `(\w+)="(.*?)"` greedily picks up
            # `type="..."` anywhere in the tag and overwrites the primary
            # `type="tool_calls"`. Using `data-result-kind` instead of
            # `data-result-block-type` avoids that collision.
            result_attrs = (
                f' data-result-kind="{html.escape(result_block_type)}"'
                f' data-result-payload-b64="{result_payload_b64}"'
            )
            summary_text = result_summary or default_summary
            body_src = result_display_body or display_body
        else:
            summary_text = default_summary
            body_src = display_body

        # NOTE: type="tool_calls" (not "server_tool_use") is intentional —
        # OpenWebUI's Svelte parser only groups consecutive <details> into a
        # single "Exploring/Explored" bubble when each one carries
        # type ∈ {tool_calls, reasoning, code_interpreter}. A custom type
        # between reasoning and code_interpreter would break the group.
        # data-block-kind disambiguates our carriers from regular OpenWebUI
        # tool_calls UI artifacts (which we still strip on replay).
        #
        # CRITICAL: empty body MUST NOT produce a blank line between
        # <summary> and </details>. Markdown tokenizer treats `\n\n` as
        # block break and splits the adjacent <details> out of the group.
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
        """Persist a *_tool_result block (web_search/web_fetch/code_execution
        results) as collapsible <details> HTML with opaque payload in
        ``data-payload-b64``. See _format_server_tool_use_block for rationale.
        """
        payload = {
            "type": block_type,
            "tool_use_id": tool_use_id,
            "content": content_payload,
        }
        if self._is_block_hidden(block_type):
            return self._format_hidden_block([payload], tool_use_id)
        payload_b64 = self._encode_block_payload(payload)
        summary = summary_text or block_type
        # NOTE: type="tool_calls" — see _format_server_tool_use_block.
        # Empty body avoids `\n\n` which breaks markdown grouping.
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
        """Best-effort serialization of a Claude server-tool result payload
        into a JSON-serializable form. Returns None if nothing to persist."""
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
        """Emit a hidden <details type="server_tool_result"> carrying the full
        API payload, so the next turn can reconstruct the exact assistant
        block sequence. Required alongside the visible display block
        (<details type="code_interpreter">) which is stripped on replay."""
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
        """Format a compaction block as a collapsible <details> for display/storage."""
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
        """Append a rendered block with a safe markdown/html separator."""
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
        """Format a thinking block with OpenWebUI native <details type='reasoning'> format.

        This produces the same format that OpenWebUI's built-in pipes use,
        enabling proper spinner, localized text, and collapsible behavior.

        ``signature`` (when provided) is persisted as an HTML attribute so the
        block can be reconstructed as a valid Claude API ``thinking`` block on
        subsequent turns. The signature is an opaque server-issued token that
        must be sent back byte-exact; without it, the API rejects replayed
        thinking blocks with a 400 error.
        """
        if SLIM_OUTPUT.get():
            # A sub-agent's reasoning is not part of its answer. The parent only
            # needs the conclusion, and the signature is worthless here because
            # the block is never replayed.
            return ""

        # Escape content and add > prefix per line (OpenWebUI quota block style)
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
        """Format a tool result block with OpenWebUI native <details type='tool_calls'> format.

        This produces the same format that OpenWebUI's built-in pipes use,
        enabling proper spinner, localized text, and collapsible behavior.

        Args:
            done: If True, shows "Tool Executed". If False, shows "Executing..." with spinner.
            embeds: List of embed content (HTML strings, URLs) from process_tool_result.
            files: List of file dicts from process_tool_result.
        """
        if SLIM_OUTPUT.get():
            # The tool ran; only its effect on the answer matters to the parent
            # agent. Arguments, raw result, embeds and file chips are markup a
            # human would expand -- nobody will.
            return ""

        # Escape arguments for HTML attribute
        escaped_args = (
            html.escape(json.dumps(tool_input, ensure_ascii=False))
            if tool_input
            else ""
        )

        done_str = "true" if done else "false"
        summary = "Tool Executed" if done else "Executing..."
        error_attr = ' error="true"' if is_error and done else ""

        if done:
            # Escape result for HTML attribute
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
            # In-progress tool call - no result yet
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
        """Format code execution as <details type="code_interpreter"> matching OpenWebUI native format.

        Uses the same HTML structure as OpenWebUI's built-in code_interpreter,
        giving us spinner, Analyzing.../Analyzed transitions, and output display for free.
        """
        if self._is_block_hidden("code_execution"):
            # Reached directly by the code-execution handlers rather than through
            # the server-tool formatters, so it needs its own guard. Covers both
            # SLIM_OUTPUT (sub-agent runs) and an explicit HIDE_BLOCKS opt-out —
            # without this, hiding "code_execution" silently did nothing.
            return ""

        done_str = "true" if done else "false"
        summary = "Analyzed" if done else "Analyzing…"

        # Build display content (code block inside details body)
        display = f"```{language}\n{code}\n```" if code else ""

        # Build output JSON for the output attribute
        # CodeBlock.svelte expects {stdout, stderr, result} keys
        output_data = {}
        if stdout:
            output_data["stdout"] = stdout
        if stderr:
            output_data["stderr"] = stderr
        # Build a result summary for tool calls and other info
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

        # Build attributes
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
        """Emit code execution output as a source/citation event for the citation panel."""
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

        # Build a concise code summary for the source name
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
        """Try to parse partial JSON by attempting various closing strategies.

        During input_json_delta streaming, the input JSON arrives incrementally.
        This attempts to close the partial JSON to extract a parseable value
        for live UI updates. Returns parsed dict/list/value on success, None on failure.
        """
        if not buffer or not buffer.strip():
            return None
        # Try as-is first (might already be complete)
        for suffix in ("", "}", '"}', '"}}', "]}"):
            try:
                return json.loads(buffer + suffix)
            except (json.JSONDecodeError, ValueError):
                continue
        return None

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

    def _model_pricing(self) -> "ModelPricing":
        """Rate card for this pipe, with the admin's MODEL_PRICING_OVERRIDES applied."""
        return ModelPricing(getattr(self.valves, "MODEL_PRICING_OVERRIDES", "") or "")

    def _model_cache_signature(self) -> str:
        """Fingerprint of the settings the model list depends on.

        The API key is hashed rather than stored so the signature can be logged
        safely. Any change here means the cached list came from a different
        endpoint or allow-list and must not be reused.

        Uses the stored (possibly encrypted) key rather than decrypting it: the
        stored value is stable between saves, and a spurious change would only
        cost one extra model fetch -- decrypting here could raise on a rotated
        WEBUI_SECRET_KEY and take the model list down with it.
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
                models.append(self._build_openwebui_model_entry(
                        name, info, info.get("_display_name", "")
                    ))
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
                    models.append(self._build_openwebui_model_entry(
                        name, info, info.get("_display_name", "")
                    ))
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
        # Single decryption point: every request path (model listing, tasks,
        # file downloads, the main loop) builds its client here, and the key may
        # arrive either from a valve or via the x-api-key header built in
        # create_request_payload. Plaintext keys pass through untouched.
        api_key = decrypt_valve_secret(api_key)
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

    # OpenWebUI's background memory review arrives as a task whose name is not in
    # the TASKS enum — functions.py forwards metadata.task verbatim.
    MEMORY_REVIEW_TASK = "memory_review"

    # Upper bound on max_tokens for the non-streaming task request.
    #
    # The SDK refuses a non-streaming call outright -- before any network I/O --
    # when max_tokens implies a response that could take over 10 minutes:
    # `3600 * max_tokens / 128000 > 600`, i.e. anything above ~21.3k. It also
    # keeps a stricter per-model table (8192 for the Opus 4 generation).
    # Handing it the model's full output limit therefore raised ValueError for
    # every current model -- 64k on Haiku 4.5, 128k on the rest -- and the
    # blanket except returned "", so EVERY task silently produced nothing.
    #
    # 8192 clears both thresholds and is still far more than a title, a tag
    # list or a memory-operations array will ever need.
    TASK_MAX_TOKENS_CAP = 8192

    # Response schemas for the task requests whose prompt asks for raw JSON.
    #
    # OpenWebUI parses these answers with json.loads and drops the whole task
    # when it fails, so every one of its prompts spends several lines begging
    # for "no markdown fences, no preamble". Structured outputs make that a
    # guarantee instead of a plea: the model cannot emit anything but a
    # conforming object.
    #
    # Keys are the task names OpenWebUI passes in metadata.task. Deliberately
    # absent: emoji_generation and moa_response_generation (their prompts ask
    # for prose, not JSON) and function_calling (the pipe uses native tools).
    #
    # `additionalProperties: false` everywhere -- OpenWebUI reads exactly one
    # key out of each of these and extra keys are pure token cost.
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
                        # One flat object rather than a per-action union: the
                        # required field set differs per action, and structured
                        # outputs does not accept anyOf/oneOf. OpenWebUI
                        # validates the per-action requirements itself
                        # (validate_memory_operations), so pinning the action
                        # vocabulary and the field names is the useful part --
                        # it is what stops the model from inventing the
                        # "score"/"importance"/"stability" keys the prompt
                        # explicitly warns against.
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
        """
        Handle task model requests (title generation, tags, follow-ups etc.) by making a
        non-streaming request to Anthropic API and returning only the text response.

        Task models should return plain text without any JSON formatting or status updates
        mixed into the response.
        """
        try:
            # Extract model and messages from body
            actual_model_name = self._resolve_task_model(body, task)
            messages = body.get("messages", [])
            model_info = self.get_model_info(actual_model_name)

            # Build simple payload for task request (non-streaming)
            task_payload = {
                "model": actual_model_name,
                # The model's real output limit, but capped: a non-streaming
                # request may not ask for more than TASK_MAX_TOKENS_CAP.
                "max_tokens": min(
                    body.get("max_tokens") or model_info.get("max_tokens", 4096),
                    self.TASK_MAX_TOKENS_CAP,
                ),
                "messages": self._process_messages_for_task(messages),
                "stream": False,
            }

            # Pin the response shape for the JSON-answering tasks, so a stray
            # markdown fence or a polite preamble can no longer cost OpenWebUI
            # the entire task.
            response_schema = (
                self.TASK_RESPONSE_SCHEMAS.get(task) if isinstance(task, str) else None
            )
            if response_schema and model_info.get("supports_structured_outputs"):
                task_payload["output_config"] = {
                    "format": {"type": "json_schema", "schema": response_schema}
                }
                logger.debug(f"Structured output enabled for task {task}")

            # Some task callers rely on their system prompt: OpenWebUI's memory
            # background review (metadata.task == "memory_review") instructs the
            # model to answer with valid JSON only, and drops the whole turn when
            # the answer is prose. Forward it instead of silently discarding it.
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

            # Make synchronous request to Anthropic API
            # For task requests, we don't have __user__ context, so use default key
            api_key = self.valves.ANTHROPIC_API_KEY
            client = self._build_anthropic_client(api_key)

            try:
                response = await client.messages.create(**task_payload)
            except Exception as struct_err:
                # Self-healing fallback. `supports_structured_outputs` can be
                # wrong in the optimistic direction on a proxy endpoint that
                # serves an Anthropic model id without implementing
                # output_config. Losing the schema costs a markdown fence;
                # losing the request costs the whole task, so retry plain
                # rather than let the outer handler swallow it.
                if "output_config" not in task_payload:
                    raise
                logger.warning(
                    f"Task {task} rejected with structured outputs, retrying "
                    f"without: {struct_err}"
                )
                task_payload.pop("output_config", None)
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
            # Warning, not debug: returning "" makes OpenWebUI drop the task
            # silently, so at debug level a total task outage left no trace at
            # default log settings. That is how the max_tokens ValueError above
            # went unnoticed.
            logger.warning(f"Task model error ({task}): {e}")
            return ""

    def _process_messages_for_task(self, messages: List[dict]) -> List[dict]:
        """
        Process messages for task requests - convert to simple Anthropic format.
        Task requests don't need complex content processing, but they do need the
        UI artefacts stripped (see _sanitize_task_text).
        """
        processed = []
        for msg in messages:
            role = msg.get("role")
            if role == "system":
                continue  # Hoisted into the payload's top-level `system` field

            content = msg.get("content", "")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                # Extract text from content blocks
                text = " ".join(
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                )
            else:
                continue

            text = self._sanitize_task_text(text)
            # A message whose entire content was a collapsible sanitises to "".
            # The API rejects empty text blocks, so drop it rather than send it.
            if not text:
                continue

            # Dropping a message can leave two same-role messages adjacent, which
            # the API rejects. Merge instead of emitting an invalid sequence.
            if processed and processed[-1]["role"] == role:
                processed[-1]["content"] = f"{processed[-1]['content']}\n\n{text}"
            else:
                processed.append({"role": role, "content": text})

        return processed

    def _resolve_task_model(self, body: dict, task: Optional[str]) -> str:
        """Pick the model for a task request, honouring MEMORY_REVIEW_MODEL.

        OpenWebUI runs the background memory review on whatever model the chat
        uses, so an Opus conversation pays Opus rates to maintain its own memory
        bookkeeping. Every other task keeps the requested model.
        """
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
        """Reduce persisted chat content to the prose a task model actually needs.

        OpenWebUI hands task requests the stored message content, which carries
        every collapsible this pipe ever wrote — tool calls, reasoning, cache
        diagnostics, code interpreter output — plus the invisible carriers and
        inline metadata markers used for replay. None of it round-trips: task
        requests are one-shot. Stripping it cuts the bill and stops the task model
        from reasoning about its own UI artefacts. It matters most for the memory
        review, which truncates each message to 1600 characters and would
        otherwise spend that budget on a token-usage dump.
        """
        if not text or ("<" not in text and "[" not in text):
            return text

        cleaned = PATTERN_ANY_DETAILS.sub("\n", text)
        cleaned = PATTERN_HIDDEN_BLOCK.sub("", cleaned)
        cleaned = PATTERN_INLINE_METADATA_MARKER.sub(" ", cleaned)
        cleaned = PATTERN_TRAILING_SPACES.sub("", cleaned)
        return PATTERN_EXCESS_BLANK_LINES.sub("\n\n", cleaned).strip()

    @classmethod
    def _extract_task_system(cls, messages: List[dict]) -> str:
        """Collect the system messages of a task request into a single string.

        Returned as plain text rather than a block list: task requests are
        one-shot and never cached, so there is nothing to attach cache_control to.
        """
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
        """Handle message_start usage accounting and return updated stream output tokens."""

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
            # Accumulated, because every call is billed for its own cache traffic:
            # a write costs 1.25x (5m) or 2x (1h) and a read 0.1x, each time it
            # happens. Reporting only the last call's numbers hid the writes
            # entirely on any multi-call turn -- exactly the turns that cost the
            # most. Multi-call happens on client tool loops, `pause_turn`
            # continuations (server tools such as web_search) and retries.
            total_usage["cache_creation_input_tokens"] += cache_creation_input_tokens
            total_usage["cache_read_input_tokens"] += cache_read_input_tokens
            # 5m and 1h writes are billed at 1.25x and 2x respectively, so the
            # cost estimate needs the split. The API reports it in
            # `cache_creation`; without it, attribute the whole write to the
            # configured TTL (loses precision only when the tools/system TTL
            # differs from the messages TTL).
            breakdown = getattr(usage, "cache_creation", None)
            write_5m = getattr(breakdown, "ephemeral_5m_input_tokens", None) if breakdown else None
            write_1h = getattr(breakdown, "ephemeral_1h_input_tokens", None) if breakdown else None
            if write_5m is None and write_1h is None:
                if self.valves.CACHE_TTL == "1 hour":
                    write_1h = cache_creation_input_tokens
                else:
                    write_5m = cache_creation_input_tokens
            total_usage["_cache_write_5m"] = total_usage.get("_cache_write_5m", 0) + (write_5m or 0)
            total_usage["_cache_write_1h"] = total_usage.get("_cache_write_1h", 0) + (write_1h or 0)
            logger.debug(
                f" Usage stats: input={input_tokens}, output={current_output_tokens}, "
                f"cache_creation={cache_creation_input_tokens}, cache_read={cache_read_input_tokens}"
            )
        else:
            cache_creation_input_tokens = 0
            cache_read_input_tokens = 0
            logger.debug(f" Usage stats: input={input_tokens}, output={current_output_tokens}")

        total_usage["_calls"] = total_usage.get("_calls", 0) + 1
        ModelPricing.record_billing_modifiers(usage, total_usage)

        # Two different questions, deliberately kept apart:
        #
        # "What did this turn cost?" -> cumulative. Every call is billed
        #   separately, so the usage dict sums input, output and cache traffic.
        # "How full is the context window?" -> point in time. Never a sum: call
        #   N's input already CONTAINS calls 1..N-1's outputs, so adding the
        #   running output total on top counts every intermediate answer twice
        #   and the error grows with each tool iteration.
        #
        # `_ctx_*` are private (stripped before the usage dict is handed to
        # OpenWebUI) and describe the last call only.
        total_usage["_ctx_input"] = (
            input_tokens + cache_creation_input_tokens + cache_read_input_tokens
        )
        total_usage["_ctx_output"] = current_output_tokens
        # OpenWebUI's contract (utils/response.py normalize_usage):
        # total_tokens == input_tokens + output_tokens, with cache traffic kept
        # in its own two fields. Adding the cache counters here double-counted
        # them against every other provider on the analytics page.
        total_usage["total_tokens"] = (
            total_usage.get("input_tokens", 0) + total_usage.get("output_tokens", 0)
        )
        logger.debug(f" Accumulated usage: {total_usage}")

        return stream_output_tokens

    @staticmethod
    def _public_usage(total_usage: dict[str, int]) -> dict[str, int]:
        """Project the internal usage tally onto OpenWebUI's usage schema.

        OpenWebUI reads token counts through two different field pairs, and it
        asks a different question with each. Filling both lets one usage dict
        answer both correctly instead of forcing a compromise:

        `input_tokens`/`output_tokens`/`total_tokens` -- cumulative over the
            whole turn, input counted UNCACHED-ONLY. This is OpenWebUI's own
            convention (`utils/anthropic.py` derives `input_tokens` as
            `prompt_tokens - cache_creation - cache_read`) and matches how the
            Anthropic API reports `input_tokens` natively. Cost and the
            analytics page read these, and cache traffic stays in its own two
            fields so nothing is counted twice.
        `prompt_tokens`/`completion_tokens` -- the LAST call only, with input
            counted in FULL (uncached + cache writes + cache reads). This is
            the real occupancy of the context window, which is what the
            auto-compaction reader needs. Cumulative sums would understate it
            badly under caching (most input arrives as cache reads), so
            compaction would fire far too late or never.

        `cache_n` is deliberately NOT set: the compaction reader adds it on top
        of `prompt_tokens`, which already includes the cached tokens here.
        """

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
        """Central stream exception policy.

        Returns: (should_retry, updated_retry_attempts, response_suffix)
        """

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
        """Apply fallback stop-reason logic when message_delta was missing."""

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
                    await request_ctx.emit_block(_ref_msg)
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
            # stop_reason is None but content exists (e.g. thinking + server_tool blocks
            # without any text). This typically happens when the API is overloaded and
            # returns a truncated stream after 200 OK. Anthropic warns:
            # "When receiving a streaming response via SSE, it's possible that an error
            # can occur after returning a 200 response."
            # We leave conversation_ended=False here so the main loop's safety-break
            # section can detect this and trigger an auto-retry.
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
            # Don't set conversation_ended — let the safety-break handle retry logic

        return conversation_ended, has_pending_tool_calls, tool_calls

    async def handle_errors(
        self,
        exception,
        __event_emitter__: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ):
        """Map an exception to a user-facing message and emit error/status events."""
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

    def _convert_sdk_message_to_api_blocks(self, message) -> list:
        """Convert SDK accumulated BetaMessage content to API-compatible block dicts.

        Mirrors the SDK's own tool runner behavior: keeps ALL content blocks
        (including server_tool_use, *_tool_result, compaction) to preserve
        thinking block positions and compaction boundaries. Skips structural
        meta-events (context_cleared).

        Strict key sanitization is applied ONLY to thinking/redacted_thinking
        blocks (to prevent cache_control from being sent). All other blocks
        are passed through with minimal processing.
        """
        blocks = []
        for block in message.content:
            block_dict = block.model_dump(exclude_none=True)
            block_type = block_dict.get("type", "")

            # Skip structural meta-events (not real content blocks)
            if block_type in self._SKIP_BLOCK_TYPES:
                continue

            # Compaction: preserve as {type: "compaction"} so the API
            # recognises the boundary and drops all prior content blocks.
            if block_type == "compaction":
                content = block_dict.get("content", "")
                if content:
                    blocks.append({"type": "compaction", "content": content})
                continue

            # Thinking/redacted_thinking: strict key sanitization
            sanitize_keys = self._SANITIZE_BLOCK_KEYS.get(block_type)
            if sanitize_keys is not None:
                blocks.append({k: v for k, v in block_dict.items() if k in sanitize_keys})
                continue

            # Text blocks: strip citations (response-only presentation data)
            if block_type == "text":
                block_dict.pop("citations", None)
                blocks.append(block_dict)
                continue

            # tool_use blocks: strip "direct" caller (API rejects it),
            # but preserve programmatic caller (needed for code_execution routing)
            if block_type == "tool_use":
                caller = block_dict.get("caller")
                if caller and caller.get("type") == "direct":
                    block_dict.pop("caller", None)
                blocks.append(block_dict)
                continue

            # All other blocks (server_tool_use, *_tool_result, etc.):
            # pass through as-is to preserve thinking block positions
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
        """
        OpenWebUI Claude streaming pipe with integrated streaming logic.
        """
        # =========================================================================
        # PHASE 1: RESPONSE ACCUMULATION STATE
        # =========================================================================
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
        # Content-block dispatch. Handlers own one block family each and read
        # everything off request_ctx; families not migrated yet return False and
        # fall through to the inline chain below.
        handler_registry = HandlerRegistry(default_handlers())
        # Bound here, not only inside the try below: the finalisation phase reads
        # it from outside the try block.
        is_internal = False

        # Run marker. Every later lifecycle line carries the same `run=`, so a log
        # window can be split into invocations without guessing from timestamps —
        # the thing that made the doubled cache-diagnostics block hard to pin down.
        run_id = request_ctx.run_id
        logger.info(
            "[RUN %s] pipe() start chat_id=%s message_id=%s session_id=%s",
            run_id,
            (__metadata__ or {}).get("chat_id"),
            (__metadata__ or {}).get("message_id"),
            (__metadata__ or {}).get("session_id"),
        )


        try:
            # =========================================================================
            # PHASE 2: VALIDATION & SETUP
            # =========================================================================

            # Debug: Log all Valves and UserValves settings
            if logger.isEnabledFor(logging.DEBUG):
                # Environment first: most bug reports come down to an OpenWebUI
                # version whose behaviour differs from the one under test.
                logger.debug(f"OpenWebUI version: {OPENWEBUI_VERSION}")
                logger.debug(f"Valves: {self.valves.model_dump()}")
                user_valves = __user__.get("valves")
                if user_valves and hasattr(user_valves, "model_dump"):
                    logger.debug(f"UserValves: {user_valves.model_dump()}")
                elif user_valves:
                    logger.debug(f"UserValves: {user_valves}")

            # Get API key - check UserValves first, then fall back to admin valve
            user_valves = __user__.get("valves")
            user_api_key = getattr(user_valves, "ANTHROPIC_API_KEY", "") if user_valves else ""
            api_key = user_api_key.strip() if user_api_key and user_api_key.strip() else self.valves.ANTHROPIC_API_KEY
            # Compare against the plaintext: an encrypted valve never equals the
            # placeholder, so an unconfigured pipe would otherwise sail past this
            # check and fail later with a 401.
            resolved_api_key = decrypt_valve_secret(api_key).strip()
            if not resolved_api_key or resolved_api_key == "Your API Key Here":
                error_msg = "Error: No API key configured. Set it in admin Valves or your personal UserValves."
                logger.error(f"{error_msg}")
                await status.complete("No API Key Set!")
                return error_msg

            # Publish this user's block visibility preference for the formatters,
            # which are too deep in the call chain to be handed a request context.
            HIDDEN_BLOCKS.set(
                self._parse_hidden_blocks(getattr(user_valves, "HIDE_BLOCKS", None))
            )

            # Human-in-the-loop tool approval (OpenWebUI 0.11.1+). The mode is a
            # per-conversation chat param; automations, channel replies and
            # temporary chats never carry "ask". Without an __event_call__ there
            # is no channel to ask on, so the gate stays open — matching
            # OpenWebUI, which also only prompts in a saved conversation.
            TOOL_APPROVAL.set(
                (
                    (__metadata__ or {}).get("params", {}).get("tool_approval_mode", "full"),
                    __event_call__,
                )
            )

            # OpenWebUI marks sub-agent runs with request.state.internal; it is
            # the same flag OpenWebUI itself uses to skip chat persistence and to
            # refuse nested delegation. Such a run has no human reader -- its
            # text is handed straight to the parent agent -- so strip the whole
            # presentation layer and emit plain prose.
            is_internal = bool(
                __request__ is not None
                and getattr(getattr(__request__, "state", None), "internal", False) is True
            )
            SLIM_OUTPUT.set(is_internal)
            if is_internal:
                logger.debug("Internal (sub-agent) run: emitting slim prose output")

            # STEP 1: Detect if task model (generate title, tags, follow-ups etc.), handle it separately
            if __task__:
                return await self._run_task_model_request(body, task=__task__)

            # STEP 2: Await tools if needed
            if inspect.isawaitable(__tools__):
                __tools__ = await __tools__

            # STEP 2.5: Get builtin tools from OpenWebUI (for tools from body.tools)
            builtin_tools = {}
            if BUILTIN_TOOLS_AVAILABLE and __request__:
                try:
                    # Determine if memory feature is enabled
                    memory_enabled = (
                        __user__.get("settings", {}).get("ui", {}).get("memory", False)
                        if __user__
                        else False
                    )
                    # Resolve skill IDs for view_skill builtin tool
                    skill_ids = []
                    try:
                        openwebui_model_id = __metadata__.get("model_id") or body.get("model", "")
                        if openwebui_model_id and MODELS_AVAILABLE:
                            owui_model = await Models.get_model_by_id(openwebui_model_id)
                            if owui_model:
                                # ModelModel has .meta (ModelMeta pydantic model), not .info
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

            # Merge external tools from metadata (Open Terminal, external tool servers)
            # These have callables for execution but are not in __tools__ or builtin_tools
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
                        model = await Models.get_model_by_id(openwebui_model_id)
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
                                await Models.update_model_by_id(
                                    openwebui_model_id, ModelForm(**form_data)
                                )
                except Exception as e:
                    logger.warning(
                        f"Could not auto-enable native function calling: {e}"
                    )

            # Tell middleware to skip reasoning tag detection — the pipe renders
            # its own <details type="reasoning"> blocks which must not be re-parsed.
            if __metadata__ is not None:
                __metadata__.setdefault("params", {})["reasoning_tags"] = False

            payload, headers, new_marker_metadata, api_tool_names = await self._create_payload(
                body, __metadata__, __user__, __tools__, __event_emitter__, __files__
            )

            # =========================================================================
            # PHASE 3: STREAMING STATE INITIALIZATION
            # =========================================================================
            api_key = headers.get("x-api-key", self.valves.ANTHROPIC_API_KEY)
            # Use UserValves API key if available (override header-level key too)
            if user_api_key and user_api_key.strip():
                api_key = user_api_key.strip()
                logger.debug("Using user-provided API key from UserValves")
            request_timeout = self.valves.REQUEST_TIMEOUT
            # Tool resolution and auth are settled — hand them to the handlers.
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
            # Per-turn capture of Anthropic cache diagnostics (beta cache-diagnosis-2026-04-07).
            # First entry that has a non-null cache_miss_reason wins for display.
            cache_diagnostics_records: list[dict[str, Any]] = []
            cache_diagnostics_chat_id: Optional[str] = (
                __metadata__.get("chat_id") if __metadata__ else None
            )

            # Stream configuration from valves
            token_buffer_size = getattr(self.valves, "TOKEN_BUFFER_SIZE", 1)
            max_function_calls = self.valves.MAX_TOOL_CALLS

            # Thinking state lives on request_ctx.state.thinking, owned by
            # ThinkingBlockHandler. Compaction likewise on .state.compaction.

            # SDK-accumulated message: captured after each stream completes
            # Replaces manual api_assistant_blocks/thinking_blocks accumulation
            sdk_final_message = None

            # Tool execution state is owned by ClientToolUseBlockHandler and lives on
            # request_ctx.state.tool_use. The alias keeps the still-inline tool-result
            # processing below on the same object the handler mutates.
            # Note: tool_use_blocks and current_tool_caller removed - SDK preserves these in accumulated message
            tool_use_state = request_ctx.state.tool_use
            has_pending_tool_calls = False
            tool_calls = []

            # Server-tool state (web_search, code_execution, text_editor) is owned by
            # ServerToolUseBlockHandler and the code-execution result handlers, and
            # lives on request_ctx.state.server_tool. The alias keeps the still-inline
            # sites below (programmatic tool-call capture, final flush) on the same
            # object those handlers mutate.
            server_tool_state = request_ctx.state.server_tool

            # Dynamic filtering detection:
            # If code_execution was NOT explicitly added to tools (no code_execution_20250825 or
            # code_execution_20260120 in payload), then any code_execution in the stream is from
            # dynamic filtering auto-injection → suppress UI.
            # If code_execution WAS explicitly added, code_exec blocks could be real code → show UI.
            payload_tools = payload.get("tools", [])
            has_explicit_code_execution = any(
                t.get("name") == "code_execution" for t in payload_tools
            )
            server_tool_state.has_explicit_code_execution = has_explicit_code_execution

            # Text/citation state is owned by TextBlockHandler and lives on
            # request_ctx.state.text. The alias keeps the still-inline call sites below
            # (metadata markers, tool-result flush, stop-reason messages) on the very
            # same object the handler mutates.
            text_state = request_ctx.state.text

            # Loop control state
            conversation_ended = False
            retry_attempts = 0
            current_function_calls = 0

            await status.waiting()

            # =========================================================================
            # PHASE 4: MAIN STREAMING LOOP
            # Continues until conversation ends or max tool calls reached
            # =========================================================================
            tool_loop_iteration = 0
            while (
                current_function_calls < max_function_calls
                and not conversation_ended
                and retry_attempts <= self.valves.MAX_RETRIES
            ):
                tool_loop_iteration += 1
                # Reset per-iteration state
                stream_output_tokens = 0
                stream_web_search_requests = 0

                try:
                    stream_event_counts = {}  # Track event types for diagnostics#
                    # Apply cache breakpoints right before sending to API
                    self._apply_cache_control(
                        payload_for_stream,
                        is_tool_loop=(tool_loop_iteration > 1),
                        iteration=tool_loop_iteration,
                    )
                    # Log message-hash diff vs previous request on same chat_id
                    # to pinpoint byte-drift that breaks the prompt cache prefix.
                    _diff_chat_id = __metadata__.get("chat_id") if __metadata__ else None
                    self._log_message_hash_diff(_diff_chat_id, payload_for_stream)
                    # Dump the full (stripped) outgoing payload so we can audit
                    # cache_control placement, tool list, message order and byte
                    # drift across turns without logging megabytes of base64.
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
                                # Note: Container ID is not in message_start for streaming;
                                # it arrives in message_delta.
                                stream_output_tokens = self._handle_message_start_usage(
                                    event,
                                    include_usage=include_usage,
                                    total_usage=total_usage if include_usage else None,
                                    stream_output_tokens=stream_output_tokens,
                                )
                                if getattr(self.valves, "ENABLE_CACHE_DIAGNOSTICS", False):
                                    msg = getattr(event, "message", None)
                                    msg_id = getattr(msg, "id", None) if msg else None
                                    # Capture HTTP request-id from response headers for
                                    # matching against the Anthropic Console / dashboard.
                                    http_request_id = None
                                    try:
                                        http_request_id = stream.response.headers.get("request-id")
                                    except Exception:
                                        pass
                                    # `diagnostics` is attached to the response Message when
                                    # the cache-diagnosis beta is active. SDK exposes it as
                                    # an attribute; fall back to dict-style for resilience.
                                    diag_obj = getattr(msg, "diagnostics", None) if msg else None
                                    if diag_obj is None and isinstance(msg, dict):
                                        diag_obj = msg.get("diagnostics")
                                    diag_dump = self._dump_sdk_obj(diag_obj) if diag_obj else None
                                    # Capture per-call usage (input/output/cache tokens).
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

                            # ---------------------------------------------------------
                            # EVENT: content_block_start
                            # Routed to the handler owning this block type; see
                            # stream/handlers.py for the block-type -> handler map.
                            # ---------------------------------------------------------
                            elif event_type == "content_block_start":
                                content_block = getattr(event, "content_block", None)
                                content_type = getattr(content_block, "type", None)
                                if not content_block:
                                    continue
                                # No status is emitted here: each handler announces
                                # its own phase on start. Emitting a generic one for
                                # every block put a meaningless "Responding..." into
                                # the (persistent, user-visible) status history after
                                # every single tool result.
                                await handler_registry.handle_start(event, request_ctx)

                            # ---------------------------------------------------------
                            # EVENT: content_block_delta
                            # Routed by the block type recorded at content_block_start.
                            # ---------------------------------------------------------
                            elif event_type == "content_block_delta":
                                await handler_registry.handle_delta(event, request_ctx)

                            # ---------------------------------------------------------
                            # EVENT: content_block_stop
                            # Routed by the block's own type, falling back to the type
                            # recorded at start for raw SDK events that omit it.
                            # ---------------------------------------------------------
                            elif event_type == "content_block_stop":
                                await handler_registry.handle_stop(event, request_ctx)

                            # ---------------------------------------------------------
                            # EVENT: message_delta
                            # Updates output token counts, handles stop_reason
                            # Flushes buffered chunks
                            # ---------------------------------------------------------
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
                                        # Cost total, and this call's own output for
                                        # the context gauge — see
                                        # _handle_message_start_usage for why the two
                                        # must not be mixed.
                                        total_usage["_ctx_output"] = current_output_tokens
                                        # OpenWebUI contract: input + output only,
                                        # cache traffic stays in its own fields.
                                        total_usage["total_tokens"] = (
                                            total_usage.get("input_tokens", 0)
                                            + total_usage.get("output_tokens", 0)
                                        )
                                        # Web searches are billed per request
                                        # ($10/1k). Like output_tokens, the
                                        # count is cumulative within one API
                                        # call, so accumulate the delta.
                                        server_tool_use = getattr(usage, "server_tool_use", None)
                                        current_searches = (
                                            getattr(server_tool_use, "web_search_requests", 0) or 0
                                        ) if server_tool_use else 0
                                        total_usage["_web_search_requests"] = (
                                            total_usage.get("_web_search_requests", 0)
                                            + (current_searches - stream_web_search_requests)
                                        )
                                        stream_web_search_requests = current_searches
                                        ModelPricing.record_billing_modifiers(usage, total_usage)
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
                                    # Emit any remaining text chunk before tool results
                                    if text_state.chunk:
                                        if not text_state.chunk.endswith("\n"):
                                            text_state.chunk += "\n"
                                        await emit_message_delta(text_state.chunk)
                                        text_state.chunk = ""
                                        text_state.chunk_count = 0

                                    # API tool passthrough — skip tool loop, return directly
                                    if tool_use_state.api_passthrough and not tool_use_state.running_tasks:
                                        logger.info(
                                            "🔄 API tool passthrough complete — skipping tool loop"
                                        )
                                        conversation_ended = True
                                        break

                                    # Wait for all running tool tasks to complete
                                    if tool_use_state.running_tasks:
                                        logger.debug(
                                            f"⏳ Waiting for %d tool tasks to complete...",
                                            len(tool_use_state.running_tasks),
                                        )

                                        try:
                                            completed_results = 0

                                            # Build tool_result messages and emit to UI as each task completes.
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

                                                # Process tool result through OpenWebUI's handler
                                                # for Rich UI (HTMLResponse, embeds, files)
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

                                                # Emit files event if tool produced files
                                                if tool_result_files and __event_emitter__:
                                                    await __event_emitter__(
                                                        {
                                                            "type": "files",
                                                            "data": {"files": tool_result_files},
                                                        }
                                                    )

                                                # OpenWebUI renders Tool Rich UI inline only when
                                                # embeds are attached to the matching tool_calls
                                                # details block. Message-level `embeds` events render
                                                # above the response text, so we deliberately avoid
                                                # emitting them here and persist the embed with the
                                                # completed tool block below.

                                                # Determine if error
                                                is_error = isinstance(
                                                    tool_result, str
                                                ) and (
                                                    tool_result.startswith("Error:")
                                                    or tool_result.startswith("Error executing tool")
                                                )

                                                # Build result block for API
                                                # Ensure result is valid JSON string (not Python repr with single quotes)
                                                if isinstance(tool_result, str):
                                                    result_str = tool_result
                                                else:
                                                    try:
                                                        result_str = json.dumps(tool_result, ensure_ascii=False)
                                                    except (TypeError, ValueError):
                                                        result_str = str(tool_result)
                                                # Convert any embedded data:image;base64 URI (e.g. a
                                                # read_file tool returning a PNG) into a real Anthropic
                                                # image block instead of raw base64 TEXT, and apply the
                                                # TOOL_RESULT_MAX_TOKENS backstop to non-image output.
                                                result_block = {
                                                    "type": "tool_result",
                                                    "tool_use_id": tool_use_id,
                                                    "content": self._convert_tool_result_content(result_str, __user__),
                                                }
                                                if is_error:
                                                    result_block["is_error"] = True
                                                tool_calls.append(result_block)

                                                if server_tool_state.in_code_execution:
                                                    # Accumulate for unified code execution display
                                                    server_tool_state.tool_calls_info.append({
                                                        "name": tool_name,
                                                        "input": tool_input,
                                                        "result": result_str,
                                                        "is_error": is_error,
                                                    })
                                                else:
                                                    # Replace the in-progress block with completed version.
                                                    # Tool Rich UI HTML belongs to the tool_calls block:
                                                    # OpenWebUI renders message.embeds above the text, but
                                                    # tool-call embeds inline at the tool call indicator.
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
                                                        # Fallback: append if placeholder not found
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

                                            # Create error results and update in-progress blocks
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

                                    # Reset for next iteration
                                    tool_use_state.reset_for_iteration()
                                    has_pending_tool_calls = True
                                elif stop_reason == "max_tokens":
                                    text_state.chunk += "Claude has Reached the maximum token limit!"
                                elif stop_reason == "end_turn":
                                    conversation_ended = True
                                elif stop_reason == "pause_turn":
                                    # API paused a long-running turn — auto-continue
                                    has_pending_tool_calls = True  # reuses tool loop mechanism
                                    # tool_calls stays empty → PHASE 5 detects pause_turn
                                    await status.activity("⏳ Long-running turn paused, continuing...")
                                elif stop_reason == "refusal":
                                    # Extract stop_details from the live SDK snapshot.
                                    # Available after the message_delta event updates it.
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
                                    # Compaction triggered — response contains only the compaction block.
                                    # We need to continue the conversation with the compacted context.
                                    # Reuse tool loop mechanism to auto-continue.
                                    has_pending_tool_calls = True
                                    logger.info("Compaction stop_reason — will auto-continue")

                            # ---------------------------------------------------------
                            # EVENT: message_stop
                            # Stream complete for this turn
                            # ---------------------------------------------------------
                            elif event_type == "message_stop":
                                pass  # No deferred blocks to flush

                            # ---------------------------------------------------------
                            # EVENT: message_error
                            # Handle stream-level errors
                            # ---------------------------------------------------------
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

                            if text_state.chunk_count > token_buffer_size:
                                if text_state.chunk:
                                    await emit_message_delta(text_state.chunk)
                                    text_state.chunk = ""
                                    text_state.chunk_count = 0

                        # Capture SDK accumulated message after stream is fully consumed
                        # This replaces manual api_assistant_blocks/thinking_blocks accumulation
                        sdk_final_message = stream.current_message_snapshot
                    # Log stream event diagnostics
                    logger.debug(f"📊 Stream events: {stream_event_counts}")

                    # Cache diagnostics: the `cache_miss_reason` inside `diagnostics`
                    # is pending/null on the `message_start` event during streaming and
                    # is only fully populated on the final accumulated message. Refresh
                    # the record captured at message_start so the rendered details block
                    # and logs show the authoritative miss reason and final usage.
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

                    # ---------------------------------------------------------
                    # PHASE 5: TOOL EXECUTION LOOP
                    # After stream ends, if tools were called:
                    # 1. Check max tool call limit
                    # 2. Build assistant message with thinking + text + tool_use blocks
                    # 3. Execute tools and collect results
                    # 4. Add tool_result blocks as user message
                    # 5. Loop back to API for continuation
                    # ---------------------------------------------------------
                    if has_pending_tool_calls and tool_calls:
                        # Log tool call details
                        tool_names = [tc.get("name", tc.get("tool_use_id", "?")) for tc in tool_calls]
                        sdk_block_types = [getattr(b, "type", "?") for b in sdk_final_message.content] if sdk_final_message else []
                        logger.info(
                            f"🔧 Tool loop iter {tool_loop_iteration} complete | "
                            f"{len(tool_calls)} tool results: {tool_names} | "
                            f"SDK blocks: {sdk_block_types}"
                        )
                        # Check if we've reached the max tool call limit
                        # Count actual tool results (not loop iterations) for accurate tracking
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

                        # Tools were already executed during stream (in message_delta)
                        # tool_calls now contains tool_result blocks ready for API
                        # UI output was already emitted during message_delta

                        # Build assistant message from SDK accumulated message
                        # SDK correctly handles: signature accumulation, block ordering,
                        # caller field preservation, input JSON assembly
                        if sdk_final_message:
                            assistant_content = self._convert_sdk_message_to_api_blocks(sdk_final_message)
                            logger.debug(
                                f"Built assistant_content from SDK message: "
                                f"{[b.get('type') for b in assistant_content]}"
                            )
                        else:
                            # Fallback: build from final_message text
                            assistant_content = []
                            final_message_snapshot = final_text()
                            if final_message_snapshot.strip():
                                assistant_content.append({"type": "text", "text": final_message_snapshot})
                            logger.warning("No SDK message available, using text fallback")

                        if assistant_content:
                            # Log detailed block analysis for debugging
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

                        # Safety: ensure every tool_use in assistant has a tool_result
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

                        # Add user message with tool results (tool_calls already contains tool_result blocks)
                        user_content = tool_calls.copy()
                        if user_content:
                            # Optimization: Move cache_control to the end for multi-step tool loops
                            # This ensures we cache the tool results for the next iteration
                            # IMPORTANT: Skip when programmatic tool calling is active - Anthropic rejects
                            payload_for_stream["messages"].append(
                                {"role": "user", "content": user_content}
                            )
                            # Debug log tool results with content sizes
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

                        # Ensure we added at least one message, otherwise break the loop
                        if not assistant_content and not user_content:
                            logger.debug(
                                f"🔧 No valid content to add, ending conversation"
                            )
                            break

                        # Check if we're approaching the limit BEFORE next iteration
                        # (current_function_calls already updated above with actual tool result count)
                        remaining = max_function_calls - current_function_calls
                        if remaining <= 0:
                            # Hard limit reached - this shouldn't happen as we check above, but safety first
                            break
                        elif remaining == 1:
                            # Only 1 call left - warn Claude this is the final chance
                            await status.activity(
                                f"⚠️ Final tool call available ({current_function_calls}/{max_function_calls} used)"
                            )
                            await asyncio.sleep(0.05)

                            # Add system message to warn Claude
                            # Skip when programmatic tool calling is active - only tool_result blocks allowed
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
                            # Approaching limit - inform both user and Claude
                            await status.activity(
                                f"⚠️ {remaining} tool call(s) remaining ({current_function_calls}/{max_function_calls} used)"
                            )
                            await asyncio.sleep(0.05)

                            # Notify Claude about remaining calls so it can plan accordingly
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
                        sdk_final_message = None  # Reset for next iteration
                        current_tool_choice = payload_for_stream.get("tool_choice")
                        if (
                            isinstance(current_tool_choice, dict)
                            and current_tool_choice.get("type") in {"tool", "any"}
                        ):
                            payload_for_stream.pop("tool_choice", None)
                            logger.debug("Cleared forced tool_choice after tool loop iteration")
                        text_state.reset_for_iteration()
                        continue

                    # pause_turn continuation: API paused a long-running turn,
                    # send the response back as-is to let Claude continue
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

                    # SAFETY / TRUNCATED STREAM RETRY:
                    # If we reach here, the stream completed but no tool loop
                    # continuation was triggered and conversation_ended is False.
                    # This typically means a truncated stream (200 OK but no stop_reason).
                    # Auto-retry with the same payload instead of silently breaking.
                    if not conversation_ended:
                        retry_attempts += 1
                        if retry_attempts <= self.valves.MAX_RETRIES:
                            # Determine what happened for logging
                            sdk_block_types = (
                                [getattr(b, "type", "?") for b in getattr(sdk_final_message, "content", [])]
                                if sdk_final_message else []
                            )
                            # `final_message` is cleared below but the diagnostics
                            # records are not — the retried call adds a second
                            # record for the same turn. Log both counts so a
                            # doubled diagnostics block can be attributed to the
                            # retry rather than guessed at.
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
                            # Reset streaming state for retry — clear any partial content
                            # from this truncated iteration so we get a clean response
                            final_message.clear()
                            sdk_final_message = None
                            text_state.reset_for_retry()
                            request_ctx.state.thinking.reset_for_retry()
                            server_tool_state.reset_for_retry()
                            request_ctx.state.reset_current_block()
                            # payload_for_stream stays unchanged → same messages, same tools
                            # Cache from previous messages is preserved server-side
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

                # ---------------------------------------------------------
                # PHASE 6: ERROR HANDLING
                # Catches and handles Anthropic API errors with retry logic:
                # - RateLimitError (429): Retryable, backoff
                # - AuthenticationError (401): API key issues
                # - InternalServerError (500, 529): Retryable
                # - APIConnectionError: Network issues, retryable
                # ---------------------------------------------------------
                except Exception as e:
                    # Finalize any open live code_exec block before handling error, so it
                    # does not stay stuck mid-render behind the error message.
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
            # OpenWebUI stop button cancels the pipe task (task.cancel() ->
            # CancelledError raised inside `async for event in stream`).
            # CancelledError is a BaseException, so the `except Exception` paths
            # never finalize the UI.  Mark the status done and emit the completion
            # event so the frontend stops showing the generating indicator and the
            # status does not stay stuck active, then re-raise so OpenWebUI emits
            # chat:tasks:cancel and tears the task down.  The cancellation has
            # already been delivered, so awaiting the emits here is safe.
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

        # ---------------------------------------------------------
        # PHASE 7: FINALIZATION
        # After successful completion:
        # - Build final status with token count display
        # - Emit completion status event
        # - Emit chat:completion event with usage stats
        # - Return final message text
        # ---------------------------------------------------------

        final_status = "✅ Response Complete"
        # ============ Cost Estimate ============
        # Stored as public keys so they travel with the usage dict: OpenWebUI
        # renders every key of `message.usage` in the message info tooltip and
        # persists the dict for the analytics page. Absent (not 0) for models
        # with no known rate card.
        if include_usage and total_usage and getattr(__user__["valves"], "SHOW_COST", True):
            cost_breakdown = self._model_pricing().breakdown(body["model"].split("/")[-1], total_usage)
            if cost_breakdown is not None:
                total_usage["cost_usd"] = round(sum(cost_breakdown.values()), 6)
                total_usage["cost_breakdown_usd"] = cost_breakdown

        # ============ Token Count Display ============
        show_token_setting = __user__["valves"].SHOW_TOKEN_COUNT
        if include_usage and show_token_setting != "Off" and total_usage and not is_internal:
            def format_num(n: int) -> str:
                """Format a token count as a short human-readable string (e.g. 1.2K, 3.4M)."""
                if n >= 1_000_000:
                    return f"{n/1_000_000:.1f}M"
                if n >= 1_000:
                    return f"{n/1_000:.1f}K"
                return str(n)

            # Context window gauge: a point-in-time reading of the LAST call
            # (its full input plus its own output). Summing across tool-loop
            # calls would double-count, since each call's input already carries
            # the previous calls' answers.
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
            # Only worth showing when it explains why the cost figures below are
            # larger than the context gauge.
            calls = total_usage.get("_calls", 1)
            if calls > 1:
                final_status += f" · {calls} calls"

            # Cache status display (only in "With Cache" mode). These are billed
            # totals for the whole turn, so they can exceed the context gauge.
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
                # The one number that answers "is caching actually working for
                # me": the share of billed input served from cache at 0.1x.
                if billed_input:
                    final_status += f" | ⚡ {cache_read / billed_input * 100:.0f}% cached"

            # Estimated list-price cost of the whole turn (all calls). Silently
            # absent for models with no known rate card rather than showing $0.
            if "cost_usd" in total_usage:
                final_status += f" | 💵 ≈{ModelPricing.format_usd(total_usage['cost_usd'])}"

        # Consolidate: emit a final replace with the complete message so OpenWebUI
        # has the authoritative content (replaces any partial delta/replace state).
        # Cache diagnostics: persist last response id for next turn and render a
        # collapsible details block if the API reported any miss reasons.
        # `not is_internal`: a sub-agent's text is pasted into the PARENT agent's
        # context, where a diagnostics collapsible is a kilobyte of markup no one
        # will ever expand. Measured on a real run: the injected sub-agent result
        # carried a full cache-diagnostics block into the parent.
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
                # Persist the response id as a metadata marker on the saved
                # assistant message so the next turn can re-inject it as
                # `diagnostics.previous_message_id`. This survives pipe restarts
                # and multi-worker setups where the in-memory
                # `_cache_diagnostics_state` dict is not shared. The marker is an
                # invisible markdown link, stripped from future prompts by
                # `_extract_metadata_marker_from_message`.
                if last_id:
                    try:
                        if not isinstance(new_marker_metadata, list):
                            new_marker_metadata = list(new_marker_metadata or [])
                        new_marker_metadata.append(
                            self._create_metadata_marker("cachediag", last_id)
                        )
                    except Exception as _e:
                        logger.debug(f"[CACHE-DIAG] could not persist id marker: {_e}")
                # Pick the first non-empty diagnostics record for display.
                # Also show per-call usage even when no diagnostics object is present.
                visible = next(
                    (rec for rec in cache_diagnostics_records if rec.get("diagnostics")),
                    cache_diagnostics_records[0] if cache_diagnostics_records else None,
                )
                if visible:
                    import json as _json
                    # Build display dict: IDs first (for easy copy-paste into Console), then
                    # per-call usage array (one entry per API call in this turn), then diagnostics.
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
                    # One block per message is the invariant. If the accumulated
                    # text already carries one, this run is finalising a second
                    # time (or a previous run's content survived into ours) —
                    # the exact situation that produced two blocks with different
                    # request ids in chat 8e36a4d0. Log it loudly instead of
                    # silently appending a duplicate.
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

        # Persist request-side metadata (e.g. native PDF attachment anchors) in
        # the saved assistant message. The marker is an empty markdown link and
        # is stripped from future prompts by _extract_metadata_marker_from_message.
        if new_marker_metadata and not is_internal:
            marker_text = "".join(new_marker_metadata) if isinstance(new_marker_metadata, list) else str(new_marker_metadata)
            if marker_text:
                final_message.append(marker_text)
                logger.debug("Persisted %d metadata marker char(s)", len(marker_text))

        consolidated = final_text()
        # The authoritative content this run hands to OpenWebUI. Comparing the
        # block count here against what ends up persisted in the DB separates a
        # pipe-side duplication from anything OpenWebUI does downstream
        # (normalizer, delta/replace ordering, frontend merge).
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
        
        # Emit chat:completion done event so frontend knows streaming finished
        # (triggers TTS finish, usage display, etc.)
        done_data: dict = {"choices": [{"finish_reason": "stop", "delta": {"content": ""}}], "done": True}
        if include_usage and total_usage:
            done_data["usage"] = self._public_usage(total_usage)
        await emit_event_local({"type": "chat:completion", "data": done_data})

        # Persist usage to chat_message.usage column for the 0.9.0+ analytics page.
        # chat:completion events are NOT persisted by the socket event emitter
        # (only status|message|replace|embeds|files|source are), so without this
        # direct DB write the analytics tab never sees our token counts.
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

    # END GENERATED SECTION: anthropic_pipe.pipe_method_groups




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
