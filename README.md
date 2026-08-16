# 🚀 Anthropic API Manifold Pipe for Open WebUI

> Near-complete Anthropic Messages API parity for OpenWebUI — model auto-discovery, native streaming, citations, web search/fetch, code execution, Files API, Agent Skills, prompt caching, context editing, compaction, and programmatic tool calling.

---

## 📌 Current status

- **Current pipe version:** `0.9.25`
- **Recommended OpenWebUI:** `0.11+` (works from `0.9.0+`)
- **Minimum practical OpenWebUI for good UX:** `0.8.11+`
- **Requirements:** `pydantic>=2.0.0`, `anthropic>=0.121.0`, `pillow-heif>=0.18.0`
- **Model list and capabilities are fetched dynamically** from Anthropic's Models API (`max_input_tokens`, `max_tokens`, thinking/effort support, compaction support, etc.)
- **Current Anthropic model docs focus on:** `Claude Opus 5`, `Claude Sonnet 5`, `Claude Fable 5`, `Claude Opus 4.8`, `Claude Haiku 4.5`

This pipe targets the **Anthropic Messages API** directly through the official **Anthropic Python SDK** and keeps the OpenWebUI experience close to Anthropic-native behavior while still playing nicely with OpenWebUI models, tools, filters, files, notes, channels, and task generation.

---

## ✨ Highlights

| Area | What you get |
|------|---------------|
| **Models & capabilities** | Auto-discovered Claude models, capability parsing from Anthropic's Models API, no hardcoded model tables to babysit |
| **Streaming UX** | SDK-based streaming, grouped reasoning/tool/code blocks, rich tool result rendering via OpenWebUI's `process_tool_result()` |
| **Reasoning controls** | Extended thinking, adaptive thinking where supported, interleaved thinking, `thinking.display="omitted"`, effort levels including `xhigh` |
| **Web tooling** | Native `web_search` + `web_fetch`, citations, location-aware searches, optional dynamic filtering on supported models |
| **Execution** | Anthropic code execution, persistent container reuse across turns, unified code/tool/output display, programmatic tool calling |
| **Files** | Native PDF upload, Anthropic Files API upload/download, file persistence markers, code-exec file roundtrips |
| **Skills** | Prebuilt and custom Agent Skills, skill validation, API-side skill support via Files API + code execution |
| **Context efficiency** | Prompt caching, optional 1-hour cache TTL, token/cache stats, context editing, compaction, tool search, Advisor sub-inference |
| **OpenWebUI integration** | Notes, channels, task generation, built-in tools, MCP tools, toggle filters, companion filter for native Anthropic buttons |

---

## 📦 Installation

### Option 1: Install from OpenWebUI Community

| Component | Link |
|-----------|------|
| **Main Pipe** | [anthropic_pipe](https://openwebui.com/f/podden/anthropic_pipe) |
| **Thinking Toggle** | [anthropic_pipe_thinking_toggle](https://openwebui.com/f/podden/anthropic_pipe_thinking_toggle) |
| **Web Search Toggle** | [anthropic_web_search_toggle](https://openwebui.com/f/podden/anthropic_web_search_toggle) |
| **Code Execution Toggle** | [anthropic_pipe_code_execution_toggle](https://openwebui.com/f/podden/anthropic_pipe_code_execution_toggle) |
| **Files API Toggle** | [anthropic_pipe_files_toggle](https://openwebui.com/f/podden/anthropic_pipe_files_toggle) |
| **Companion Filter** | [anthropic_manifold_companion](https://openwebui.com/f/podden/anthropic_manifold_companion) |

### Option 2: Manual installation

1. Open **Admin Settings** → **Functions** → **+ New Function**
2. Paste the source of [`anthropic_pipe.py`](anthropic_pipe.py) from this repo
3. Repeat for the toggle filters you want to use (`anthropic_pipe_thinking_toggle.py`, `anthropic_pipe_web_search_toggle.py`, `anthropic_pipe_code_execution_toggle.py`, `anthropic_pipe_files_toggle.py`)
4. Optionally install the **Companion Filter**
5. Set the admin valves described below

### Recommended OpenWebUI model configuration

For each Claude model in **Admin Settings → Models**:

1. Attach the toggle filters you want available for that model
2. Set **Function Calling** to **`Native`**
3. Optionally attach the **Companion Filter** if you want OpenWebUI's built-in `web_search` / `code_interpreter` buttons to route to Anthropic-native tools
4. If you plan to use **Skills** or **Files API** workflows heavily, prefer models with strong tool and code-exec support (today that usually means **Opus 4.7** or **Sonnet 4.6**)

---

## 🔌 OpenWebUI compatibility notes

Recent OpenWebUI releases matter for this pipe:

- **0.8.11**
   - grouped consecutive reasoning/tool blocks into single collapsible summaries
   - improved tool-call streaming persistence and reasoning spinner behavior
   - added upstream `WEB_FETCH_MAX_CONTENT_LENGTH` support
- **0.8.12**
   - rich embeds from tool calls remain visible outside collapsed groups
- **0.9.0**
   - async plugin/backend migration for Tools, Functions, Pipes, Filters, and Actions
   - built-in and MCP tools reach pipes more reliably
   - richer Anthropic-compatible tool result content and citation rendering
   - active filter badges can expose valve configuration shortcuts directly in chat
- **0.9.2**
   - persisted skill mentions inject into system prompts reliably on stored chats

If you fork this pipe or copy code into your own plugin, note that OpenWebUI `0.9.0+` moved DB/model helpers to async. The pipe is already migrated, but custom additions must also follow the async model/helper rules. See the official migration guide: https://docs.openwebui.com/features/extensibility/plugin/migration/to-0.9.0

---

## 🔧 Configuration

### Global Valves (admin-wide)

| Valve | Default | Description |
|-------|---------|-------------|
| `ANTHROPIC_API_KEY` | `$ANTHROPIC_API_KEY` | Anthropic API key, unless overridden by a per-user key. Falls back to the `ANTHROPIC_API_KEY` environment variable |
| `ANTHROPIC_BASE_URL` | `https://api.anthropic.com` | Custom base URL / proxy (Azure, `aws-external-anthropic`, gateways) |
| `ENABLED_MODELS` | `""` | Comma-separated model IDs to expose. Bypasses `/v1/models` auto-discovery — needed for endpoints without a models API |
| `ANTHROPIC_WORKSPACE_ID` | `""` | Experimental: "Claude on AWS" workspace ID, sent as the `anthropic-workspace-id` header |
| `ENABLE_FAST_MODE` | `false` | Sends Anthropic's `speed: "fast"` tier on Opus models that support it (up to ~2.5x faster, higher cost) |
| `REFUSAL_FALLBACK` | `off` | Retry a safety-refused request server-side: `off`, `default` (Anthropic's per-category recommendation), or a pinned model. Claude API only |
| `ENABLE_INTERLEAVED_THINKING` | `true` | Allows thinking blocks between tool calls where supported |
| `WEB_SEARCH` | `true` | Enables Anthropic native web search |
| `WEB_FETCH` | `true` | Enables Anthropic native URL fetch |
| `MAX_TOOL_CALLS` | `15` | Maximum Claude → tool → Claude loop count per request |
| `MAX_RETRIES` | `3` | Retries for overload, rate limits, and transient transport/provider errors |
| `CACHE_CONTROL` | `cache tools array, system prompt and messages` | Prompt caching scope (see below) |
| `CACHE_TTL` | `5 minutes` | Anthropic cache TTL (`1 hour` is also supported, at higher write cost) |
| `CACHE_TTL_FOR_TOOLS_AND_SYSTEM_PROMT` | `same as CACHE_TTL` | Separate TTL for tools array + system prompt, independent of messages. Useful for big multi-user setups |
| `MEMORY_REVIEW_MODEL` | `claude-haiku-4-5` | Model used for OpenWebUI's background memory review (`same as chat model` to disable the override) |
| `WEB_SEARCH_USER_CITY / REGION / COUNTRY / TIMEZONE` | `""` | Default search-location hints for Anthropic web search |
| `ENABLE_PROGRAMMATIC_TOOL_CALLING` | `false` | Allows Claude to call OpenWebUI tools from inside code execution |
| `ENABLE_BASH_TOOL` | `false` | Experimental: Claude's native `bash_20250124` tool, bridged to Open Terminal's `run_command`. Only activates when `run_command` is present in tools |
| `BASH_TOOL_TIMEOUT` | `120` | Seconds to wait for an Open Terminal bash command before returning partial output |
| `ENABLE_TEXT_EDITOR_TOOL` | `false` | Experimental: Claude's native `text_editor_20250728` (`str_replace_based_edit_tool`), bridged to `write_file` + `replace_file_content` (+ `run_command` fallback for `view`/`insert`). Only activates when both callables are present |
| `TEXT_EDITOR_MAX_CHARACTERS` | `10000` | Anthropic-side truncation limit for text_editor `view` results |
| `DATA_RESIDENCY` | `global` | Anthropic `inference_geo` routing: `global` or `us` (`us` costs 1.1x tokens) |
| `REQUEST_TIMEOUT` | `300` | Anthropic API timeout in seconds |
| `TOOL_CALL_TIMEOUT` | `30` | Per-tool execution timeout in seconds |
| `ENABLE_CACHE_DIAGNOSTICS` | `false` | Logs cache-prefix diffs between turns. Debugging only |
| `MODEL_CACHE_TTL_MINUTES` | `1440` | How long the discovered model list is cached (`0` = re-fetch on every model list render). Changing API key, base URL, workspace or `ENABLED_MODELS` refreshes immediately regardless |

#### `CACHE_CONTROL` options

| Value | Meaning |
|-------|---------|
| `cache disabled` | Disable Anthropic prompt caching |
| `cache tools array only` | Cache tool definitions only |
| `cache tools array and system prompt` | Cache tools + system prompt |
| `cache tools array, system prompt and messages` | Cache tools + system + growing message history |

### UserValves (per-user)

#### Reasoning and output

| Valve | Default | Description |
|-------|---------|-------------|
| `ANTHROPIC_API_KEY` | `""` | Personal key override for the admin key |
| `ENABLE_THINKING` | `false` | Enables extended thinking. On models with thinking on by default (Opus 5 / Sonnet 5) turning it **off** actively disables thinking |
| `THINKING_BUDGET_TOKENS` | `8192` | Manual thinking budget for models that still use `budget_tokens` |
| `THINKING_DISPLAY` | `omitted` | `summarized` streams summarized thinking, `omitted` hides it for faster time-to-first-text |
| `EFFORT` | `high` | `low`, `medium`, `high`, `xhigh`, `max` (clamped by model support; also settable via OpenWebUI's `reasoning_effort`) |
| `HIDE_BLOCKS` | `""` | Comma-separated block types to hide from the chat display (still replayed to the API): `web_search`, `web_fetch`, `tool_search`, `advisor`, `code_execution`, `compaction` |
| `SHOW_TOKEN_COUNT` | `Off` | `Off`, `On`, or `With Cache` (adds cache read/write tokens and call count) |
| `TOOL_RESULT_MAX_TOKENS` | `50000` | Backstop truncation for oversized text tool results (`0` disables). Image blocks are exempt |

#### Search, files, and skills

| Valve | Default | Description |
|-------|---------|-------------|
| `USE_PDF_NATIVE_UPLOAD` | `true` | Use native Anthropic PDF documents instead of RAG text extraction |
| `WEB_SEARCH_MAX_USES` | `5` | Maximum native web searches per turn |
| `WEB_FETCH_MAX_USES` | `5` | Maximum native web fetch calls per turn |
| `WEB_SEARCH_USER_CITY / REGION / COUNTRY / TIMEZONE` | `""` | Per-user search-location overrides |
| `ENABLE_DYNAMIC_FILTERING` | `false` | Enables Anthropic dynamic filtering flow for web search/fetch on supported models |
| `USE_FILES_API` | `false` | Upload chat files to Anthropic Files API for code execution / skills |
| `SKILLS` | `[]` | Skill IDs such as `pptx`, `xlsx`, `docx`, `pdf`, or custom uploaded skill IDs |

#### Tool Search and Advisor

| Valve | Default | Description |
|-------|---------|-------------|
| `ENABLE_TOOL_SEARCH` | `true` | Deferred tool loading with search for large tool sets (beta `advanced-tool-use-2025-11-20`) |
| `TOOL_SEARCH_TYPE` | `bm25` | Tool search mode: `bm25` or `regex` |
| `TOOL_SEARCH_MAX_DESCRIPTION_LENGTH` | `100` | Tools with longer JSON definitions are deferred for lazy loading |
| `TOOL_SEARCH_EXCLUDE_TOOLS` | Anthropic server tools + OpenWebUI built-ins + Open Terminal tools | Always keep these tools loaded |
| `ENABLE_ADVISOR_TOOL` | `false` | Enables the Advisor tool (beta `advisor-tool-2026-03-01`). Executor model consults a stronger advisor mid-generation for strategic guidance. Billed at the advisor's rate. |
| `ADVISOR_MODEL` | `claude-opus-5` | Advisor model: `claude-opus-5`, `claude-opus-4-8`, `claude-opus-4-7`, `claude-fable-5`, `claude-mythos-5` (auto-adjusted if incompatible) |
| `ADVISOR_MAX_USES` | `0` | Max advisor calls per request (`0` = unlimited). Beyond this, further calls return `advisor_tool_result_error` with `max_uses_exceeded`. |
| `ADVISOR_CACHING` | `off` | Ephemeral prompt caching for the advisor transcript: `off`, `5m`, or `1h` |

#### Compaction and context editing

| Valve | Default | Description |
|-------|---------|-------------|
| `ENABLE_COMPACTION` | `false` | Enables Anthropic API compaction where the model supports it |
| `COMPACTION_TRIGGER_TOKENS` | `50000` | Token threshold that triggers compaction |
| `COMPACTION_INSTRUCTIONS` | `""` | Optional custom compaction prompt |
| `CONTEXT_EDITING_STRATEGY` | `none` | `none`, `clear_tool_results`, `clear_thinking`, `clear_both` |
| `CONTEXT_EDITING_THINKING_KEEP` | `0` | Recent assistant thinking turns to preserve; `0` means keep all |
| `CONTEXT_EDITING_TOOL_TRIGGER` | `50000` | Token threshold for clearing tool results |
| `CONTEXT_EDITING_TOOL_KEEP` | `5` | Number of recent tool results to keep |
| `CONTEXT_EDITING_TOOL_CLEAR_AT_LEAST` | `10000` | Minimum tokens to clear when triggered |
| `CONTEXT_EDITING_TOOL_CLEAR_TOOL_INPUT` | `false` | Also clear tool input payloads |

### Important behavior notes

- The pipe automatically prefers **adaptive thinking** whenever the model advertises it (Opus 5, Sonnet 5, Opus 4.8/4.7/4.6, Sonnet 4.6).
- Anthropic recommends **`effort`** as the main control for adaptive-thinking models. Effort levels are clamped per model from the Models API, so unsupported values (`xhigh`, `max`) degrade instead of erroring.
- On **Opus 5 / Sonnet 5**, thinking is **on by default**. Switching `ENABLE_THINKING` off sends `thinking: {"type": "disabled"}` and clamps effort to `high`, because Opus 5 rejects disabled thinking at `xhigh`/`max`.
- `THINKING_DISPLAY="omitted"` suppresses streamed `thinking_delta` events, matching Anthropic's streaming behavior.
- `USE_FILES_API` **overrides** native PDF upload. If enabled, the pipe uploads files to Anthropic and injects `container_upload` blocks at the correct message positions.
- Anthropic's **Files API** supports create-once / use-many flows, but remains **beta**.
- Anthropic **citations** work well with prompt caching, but Anthropic docs note they are incompatible with strict structured outputs.
- `CACHE_TTL="1 hour"` maps to Anthropic's extended cache TTL (`{"type": "ephemeral", "ttl": "1h"}`).
- `CONTEXT_EDITING_THINKING_KEEP=0` is the safest cache-friendly default. Sliding windows (`>0`) can reduce cache efficiency on long thinking-heavy chats.
- `ENABLE_DYNAMIC_FILTERING` improves quality for supported web-search / web-fetch models but is **substantially slower** than the normal flow.
- There is **no dedicated Claude memory tool** documented here anymore. This README intentionally reflects the current pipe surface only.

### Toggle filters & companion filter

| Component | Purpose |
|-----------|---------|
| **Thinking Toggle** | One-shot thinking enable for the next message |
| **Web Search Toggle** | One-shot web-search forcing for the next message |
| **Code Execution Toggle** | One-shot code-execution enable for the next message |
| **Files API Toggle** | One-shot Files API mode for file-heavy / skill-heavy flows |
| **Companion Filter** | Routes OpenWebUI's built-in `web_search` / `code_interpreter` UI actions to Anthropic-native tools |

---

## 📝 Recent pipe changes
### `v0.9.25`
- Added `MODEL_CACHE_TTL_MINUTES` (default `1440`, `0` disables caching): controls how long the discovered model list is cached. The 24h TTL used to be hardcoded, so a newly released Claude model could not be picked up without restarting OpenWebUI
- Fixed the model cache surviving a connection change — the cached list is fingerprinted against API key, base URL, workspace ID and `ENABLED_MODELS`. Repointing the pipe at a different endpoint used to keep serving the old endpoint's models for up to 24 hours
- A failed model refresh no longer falls back to a cache fetched with different connection settings

### `v0.9.24`
- Fixed the context-window reading OpenWebUI uses for auto-compaction: `prompt_tokens` / `completion_tokens` now carry the last call's full input (uncached + cache writes + cache reads). `input_tokens` / `output_tokens` stay cumulative and uncached-only, so cost and the analytics page are unchanged. Under caching the old numbers understated occupancy badly and compaction fired far too late or never
- Sub-agent runs (OpenWebUI 0.11) return plain prose: no collapsibles, replay carriers, token footer, or metadata markers — their text is pasted into the parent agent's context, where all of that is pure token cost
- Task models (title, tags, follow-ups, queries, image prompts, autocomplete, memory review) pin their response shape with structured outputs
- Added the OpenWebUI 0.11 builtin tools to the tool-search exclude list: `notify`, `timer`, `delegate_task`, `list_chat_files`, `grep_chat_files`, `query_chat_files`
- Fixed sampling params being sent to adaptive-thinking models on endpoints without capability metadata (Azure/proxies, manual `ENABLED_MODELS`), which the API answered with a 400 (#36, reported by @attilaolah)
- Corrected stale static model limits: Opus 4.6/4.7/4.8 and Sonnet 4.6 serve 128k output, Sonnet 4.5 serves a 1M window, and the 1M window no longer needs a beta header
- Requires `anthropic>=0.121.0`

### `v0.9.23`
- Added **Claude Opus 5** (`claude-opus-5`): 1M context, 128k output, thinking on by default, full effort ladder incl. `max`, fast mode
- Thinking Toggle now works on thinking-on-by-default models: turning it off sends `thinking: {"type": "disabled"}` and clamps effort to `high`
- Added `REFUSAL_FALLBACK` valve: retry a safety-refused request server-side, on Anthropic's per-category recommendation or a pinned model
- Removed Fast Mode for Opus 4.7 (2026-07-24): `speed: "fast"` now errors there
- Fixed a prompt-cache killer: user tools are appended name-sorted, so OpenWebUI's shifting tool order no longer rebuilds the whole cache

### `v0.9.22`
- Compatibility with OpenWebUI's `ENABLE_MEMORY_BACKGROUND_REVIEW`: task requests forward their system prompt again
- Added `MEMORY_REVIEW_MODEL` valve to run background memory review on a cheap model (default Haiku)
- Task requests are stripped to plain prose: no collapsibles, cache diagnostics, replay carriers, or inline markers
- `HIDE_BLOCKS` moved from admin Valves to UserValves

### `v0.9.21`
- Added `HIDE_BLOCKS` valve to hide individual collapsibles: `web_search`, `web_fetch`, `tool_search`, `advisor`, `code_execution`, `compaction`
- Added `CACHE_TTL_FOR_TOOLS_AND_SYSTEM_PROMT` valve to cache system prompt and tools array for an hour separately
- Compatibility with the new OpenWebUI memory format so the cache stays stable
- Added cached-% and multi-call count to the token display
- Fixed markdown breaking at text `content_block` boundaries

### `v0.9.20`
- Fixed an "API key is invalid" error when using the `ANTHROPIC_API_KEY` valve

### `v0.9.19`
- Removed static `ANTHROPIC_BUILTIN_TOOL_NAMES` in favor of a default `TOOL_SEARCH_EXCLUDE_TOOLS` covering all OpenWebUI internal tools
- Fixed Open Terminal tool calls and `read_file` bugs; experimental bash and text_editor support now works
- Fixed token explosion on requests containing images and binary files from older `read_file` calls

### `v0.9.18`
- Client tool results with base64 image data are converted into Anthropic image blocks instead of raw base64 text
- Uses OpenWebUI's native image compression user settings
- Added **Claude Sonnet 5** (`claude-sonnet-5`): 1M context, 128k output, adaptive thinking on by default
- Experimental Claude on AWS support via `ANTHROPIC_WORKSPACE_ID`
- Added `ENABLED_MODELS` valve + date-suffix normalization + static model fallback for endpoints without `/v1/models`
- Reads the `ANTHROPIC_API_KEY` environment variable
- Fixed file downloads from the code execution container via the Files API

### `v0.9.17`
- Added Fable and Mythos as advisor models
- Advisor model is dynamically adjusted to the next best model if incompatible

### `v0.9.16`
- Added Claude Fable and Mythos 5 alongside new stop_reasons and refusals

### `v0.9.15`
- Fixed Newline after Citations
- Fixed Tool calling error when tools payload changes while old tool results are still present in previous answers
- Fixed Stop Handling
- Fixed Status Emitting for Tool Search and Advisor

### `v0.9.14`
- Added Claude Opus 4.8
- Promt caching bugfixes when using native PDF Upload and Images

### `v0.9.13`
- Token counting is now Claude-Code-style: `total_tokens` only counts NEW tokens (uncached input + cache_creation + output) instead of all tokens
- Added `ENABLE_CACHE_DIAGNOSTICS` valve for debug purposes

### `v0.9.12`
- Refactored the pipe into modular source files under `src/anthropic_pipe/`.
- Extracted request payload creation into `request_payload.py` for cache/debug work.
- Split streaming content-block handling into per-content modules and added a build step that compiles/minifies the OpenWebUI single-file artifact before deploy.
- Fixed Anthropic API Skills container payload shape and added clearer Files API / code execution guidance.

### `v0.9.11`
- Added async handling for Open Terminal `run_command` ↔ Anthropic `bash` tool bridging
- Added all Anthropic server tools to the hardcoded tool-search excludes so they never get deferred

### `v0.9.10`
- Added an experimental path for Anthropic's native `bash_20250124` tool via Open Terminal (`ENABLE_BASH_TOOL`)
- Added an experimental path for Anthropic's native `text_editor_20250728` / `str_replace_based_edit_tool` via Open Terminal (`ENABLE_TEXT_EDITOR_TOOL`)

### `v0.9.9`
- Fixed tool-search block reconstruction so results render as a collapsible instead of a status message
- Added experimental Advisor tool support (beta `advisor-tool-2026-03-01`) with `ENABLE_ADVISOR_TOOL`, `ADVISOR_MODEL`, `ADVISOR_MAX_USES`, and `ADVISOR_CACHING`

### `v0.9.8`
- Complete overhaul of how message blocks are recreated for a new turn to align with Anthropic cache restrictions
- Cache should now stay intact on new turns even when using **RAG**, **image/PDF upload**, **memory**, **tools**, and similar flows
- Group tool / thinking output into **one** collapsible UI block

### `v0.9.7`
- Preserve thinking signatures across turns for better replay continuity and cache behavior

### `v0.9.6`
- Updated for Open WebUI `0.9.0+` async APIs

### `v0.9.5`
- Added **Claude Opus 4.7** and the new **`xhigh`** effort level

### `v0.9.4`
- Add cache statistics to token-count output

### `v0.9.3`
- Moved **Compaction** and **Context Editing** into **UserValves**
- Upgraded token display to **`Off / On / With Cache`**

### `v0.9.2`
- Add compaction and client-side pre-trim before request submission

### `v0.9.1`
- Return the full final message and persist stream content through `message` delta behavior to avoid empty saved messages

### `v0.9.0`
- Fetch model capabilities directly from Anthropic's Models API
- Add support for `thinking.display: "omitted"`
- Fix usage handling when analytics/token capabilities differ between models

<details>
<summary><b>Older 0.8.x milestones</b></summary>

### `v0.8.12`
- API tool passthrough for external function calling
- Add `ANTHROPIC_BASE_URL`
- Fix OpenTerminal tools and tool-result grouping

### `v0.8.11`
- Add `CACHE_TTL`
- Add proper stream completion event in final phase
- Fix programmatic tool calling and OpenWebUI 0.8.11 grouping behavior

### `v0.8.10`
- Rich UI tool results (`HTMLResponse`, embeds, files)
- OpenWebUI Skills support

### `v0.8.9`
- Request / tool timeouts
- Optional per-user API key override
- Remove separate 1M-context valve now that extended context is model/capability driven

### `v0.8.8`
- Interleaved thinking + tool-call fixes
- Stream code/tool input into live collapsible blocks
- Surface tool-call errors correctly instead of spinning forever

### `v0.8.7`
- Native OpenWebUI `code_interpreter` details format for code execution
- Removed redundant code-exec status events

### `v0.8.0`
- Major streaming refactor to Anthropic SDK message accumulation
- Web fetch
- programmatic tool calling
- unified code execution display
- `web_search_20260209` support

</details>

---

## 🛠️ Development

You only need Python 3.11+ to build — the build and minify scripts use the standard library only. The Anthropic SDK is a runtime dependency of the pipe inside OpenWebUI, not of the build.

### Repo layout

| Path | Role |
|------|------|
| `src/anthropic_pipe/` | Maintainable sources — **edit here** |
| `helpers/build_anthropic_pipe.py` | Compiles the sources into the single-file artifact |
| `helpers/minify_pipe.py` | Strips comments/docstrings for a smaller upload artifact |
| `helpers/test_model_cache.py` | Self-check for model-list caching and invalidation (`python helpers/test_model_cache.py`) |
| `anthropic_pipe.py` | **Generated** single-file pipe (this is what you install) |
| `anthropic_pipe.min.py` | **Generated** minified pipe (git-ignored) |
| `anthropic_pipe_*_toggle.py`, `anthropic_manifold_companion_filter.py` | Standalone filters, edited directly |

Inside `src/anthropic_pipe/`, `request/` holds everything that converges on the request payload, `response/` has one module per Anthropic `content_block` family plus rendering helpers, `shared/` holds model discovery and OpenWebUI task handling, and `pipe_template.py` carries the pipe frontmatter (title, version, requirements) and the class skeleton.

### Build

```bash
# 1. compile src/ into anthropic_pipe.py
python helpers/build_anthropic_pipe.py

# 2. optional: minified upload artifact, verified with py_compile
python helpers/minify_pipe.py anthropic_pipe.py -o anthropic_pipe.min.py --check
```

Do **not** hand-edit the `# BEGIN/END GENERATED SECTION` blocks in `anthropic_pipe.py` — the next build overwrites them. If the artifact and the template ever drift apart, pull the artifact back in with `python helpers/build_anthropic_pipe.py --refresh-template`.

Version bumps and changelog entries go into the module docstring of `src/anthropic_pipe/pipe_template.py`, then get mirrored into this README.

See [`AGENTS.md`](AGENTS.md) for architecture anchors, invariants, and common failure patterns.

---

## 🤝 Contributing

Bug reports and feature requests are welcome. If something breaks, opens twice, or starts philosophizing in HTML, please [open an issue](https://github.com/Podden/openwebui_anthropic_api_manifold_pipe/issues).

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built for [Open WebUI](https://github.com/open-webui/open-webui)
- Powered by [Anthropic Claude](https://www.anthropic.com/)
- Based on earlier work by Balaxxe and nbellochi
