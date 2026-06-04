# 🚀 Anthropic API Manifold Pipe for Open WebUI

> Near-complete Anthropic Messages API parity for OpenWebUI — model auto-discovery, native streaming, citations, web search/fetch, code execution, Files API, Agent Skills, prompt caching, context editing, compaction, and programmatic tool calling.

---

## 📌 Current status

- **Current pipe version:** `0.9.10`
- **Recommended OpenWebUI:** `0.9.0+`
- **Minimum practical OpenWebUI for good UX:** `0.8.11+`
- **Model list and capabilities are fetched dynamically** from Anthropic's Models API (`max_input_tokens`, `max_tokens`, thinking/effort support, compaction support, etc.)
- **Current Anthropic model docs focus on:** `Claude Opus 4.7`, `Claude Sonnet 4.6`, `Claude Haiku 4.5`
- **Anthropic deprecation note:** `Claude Sonnet 4` and `Claude Opus 4` are deprecated and retire on **2026-06-15**

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

## 🧠 Anthropic / Claude notes reflected in this pipe

- The Anthropic docs now treat **Opus 4.7** as the flagship generally available model for the hardest agentic and coding workloads.
- **Opus 4.7** and **Sonnet 4.6** expose a **1M token** context window; **Haiku 4.5** uses **200k**.
- Modern Claude models expose capabilities through the **Models API**, which this pipe reads directly.
- `thinking.display: "omitted"` suppresses streamed `thinking_delta` events; only the thinking block shell and signature are emitted.
- Anthropic's **Files API** remains **beta** and is especially useful together with code execution and skills.
- Anthropic's **Skills API** relies on **code execution + files + skills beta headers**; this pipe handles that plumbing for you.
- Anthropic's **effort** parameter is now the recommended control for adaptive-thinking models; `xhigh` is **Opus 4.7 only**.

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
2. Paste the source for `anthropic_pipe.py`
3. Repeat for the toggle filters you want to use
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
| `ANTHROPIC_API_KEY` | required | Anthropic API key used by the pipe unless overridden by a per-user key |
| `ANTHROPIC_BASE_URL` | `https://api.anthropic.com` | Custom base URL / proxy for Anthropic API requests. For Claude Platform on AWS, set to `https://aws-external-anthropic.<region>.api.aws` |
| `ANTHROPIC_WORKSPACE_ID` | `""` | Claude Platform on AWS workspace ID. When set, sent as the `anthropic-workspace-id` header on every request. Required when `ANTHROPIC_BASE_URL` points at an `aws-external-anthropic` endpoint |
| `ENABLE_FAST_MODE` | `false` | Sends Anthropic's `speed: "fast"` research-preview speed tier on models this pipe marks as fast-mode capable |
| `ENABLE_INTERLEAVED_THINKING` | `true` | Allows thinking blocks between tool calls where supported |
| `WEB_SEARCH` | `true` | Enables Anthropic native web search |
| `WEB_FETCH` | `true` | Enables Anthropic native URL fetch |
| `MAX_TOOL_CALLS` | `15` | Maximum Claude → tool → Claude loop count per request |
| `MAX_RETRIES` | `3` | Retries for overload, rate limits, and transient transport/provider errors |
| `CACHE_CONTROL` | `cache tools array, system prompt and messages` | Prompt caching scope |
| `CACHE_TTL` | `5 minutes` | Anthropic cache TTL (`1 hour` is also supported) |
| `WEB_SEARCH_USER_CITY / REGION / COUNTRY / TIMEZONE` | `""` | Default search-location hints for Anthropic web search |
| `ENABLE_PROGRAMMATIC_TOOL_CALLING` | `false` | Allows Claude to call OpenWebUI tools from inside code execution |
| `ENABLE_BASH_TOOL` | `false` | Enable Claude's native `bash_20250124` tool, bridged to Open Terminal's `run_command`. Only activates when `run_command` is present in tools. |
| `ENABLE_TEXT_EDITOR_TOOL` | `false` | Enable Claude's native `text_editor_20250728` (`str_replace_based_edit_tool`), bridged to `write_file` + `replace_file_content` (+ `run_command` fallback for `view`/`insert`). Only activates when both callables are present. |
| `TEXT_EDITOR_MAX_CHARACTERS` | `10000` | Anthropic-side truncation limit for text_editor `view` results |
| `DATA_RESIDENCY` | `global` | Anthropic `inference_geo` routing: `global` or `us` |
| `REQUEST_TIMEOUT` | `300` | Anthropic API timeout in seconds |
| `TOOL_CALL_TIMEOUT` | `30` | Per-tool execution timeout in seconds |

#### `CACHE_CONTROL` options

| Value | Meaning |
|-------|---------|
| `cache disabled` | Disable Anthropic prompt caching |
| `cache tools array only` | Cache tool definitions only |
| `cache tools array and system prompt` | Cache tools + system prompt |
| `cache tools array, system prompt and messages` | Cache tools + system + growing message history |

#### Using Claude on AWS (Claude Platform on AWS)

This pipe can target [Claude Platform on AWS](https://docs.aws.amazon.com/claude-platform/latest/userguide/making-requests.html#_using_the_base_anthropic_client)
via the base Anthropic client (no `boto3`/SigV4 dependency). Set three things in the Global Valves:

- `ANTHROPIC_API_KEY` — your Anthropic API key
- `ANTHROPIC_BASE_URL` — `https://aws-external-anthropic.<region>.api.aws` (e.g. `https://aws-external-anthropic.us-west-2.api.aws`)
- `ANTHROPIC_WORKSPACE_ID` — your workspace ID (sent as the required `anthropic-workspace-id` header)

If the AWS endpoint does not expose `/v1/models`, the pipe falls back to a built-in model list so the picker stays populated.

### UserValves (per-user)

#### Reasoning and output

| Valve | Default | Description |
|-------|---------|-------------|
| `ANTHROPIC_API_KEY` | `""` | Personal key override for the admin key |
| `ENABLE_THINKING` | `false` | Enables extended thinking |
| `THINKING_BUDGET_TOKENS` | `8192` | Manual thinking budget for models that still use `budget_tokens` |
| `THINKING_DISPLAY` | `summarized` | `summarized` or `omitted` |
| `EFFORT` | `high` | `low`, `medium`, `high`, `xhigh`, `max` (clamped by model support) |
| `SHOW_TOKEN_COUNT` | `Off` | `Off`, `On`, or `With Cache` |
| `DEBUG_MODE` | `false` | Extra logging and status output |

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
| `TOOL_SEARCH_EXCLUDE_TOOLS` | `[web_search, web_fetch, code_execution_20250825, code_execution_20260120]` | Always keep these tools loaded |
| `ENABLE_ADVISOR_TOOL` | `false` | Enables the Advisor tool (beta `advisor-tool-2026-03-01`). Executor model consults a stronger advisor (Opus 4.7) mid-generation for strategic guidance. Billed at the advisor's rate. |
| `ADVISOR_MODEL` | `claude-opus-4-7` | Advisor model (only `claude-opus-4-7` is currently supported) |
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

- On **Opus 4.7 / Opus 4.6 / Sonnet 4.6**, the pipe automatically prefers **adaptive thinking** when the model advertises it.
- Anthropic now recommends **`effort`** as the main control for adaptive-thinking models. `xhigh` is **Opus 4.7 only**. `max` is available on **Opus 4.7 / Opus 4.6 / Sonnet 4.6**.
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

### `v0.9.15`
- Added support for **Claude Platform on AWS** via the base Anthropic client (`ANTHROPIC_BASE_URL` + new `ANTHROPIC_WORKSPACE_ID` valve)
- Centralized Anthropic client creation and added a static model-list fallback for endpoints without `/v1/models`
- @Willian-Zhang

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
