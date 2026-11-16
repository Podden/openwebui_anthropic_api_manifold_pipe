# 🚀 Anthropic API Manifold Pipe for Open WebUI

> Near-complete Anthropic Messages API parity for OpenWebUI — model auto-discovery, native streaming, citations, web search/fetch, code execution, Files API, Agent Skills, prompt caching, context editing, compaction, and programmatic tool calling.

---

## 📌 Current status

- **Current pipe version:** `0.11.2`
- **Recommended OpenWebUI:** `0.12.2+` (answers stream as native output items; older versions from `0.9.0+` keep the text path)
- **Minimum practical OpenWebUI for good UX:** `0.8.11+`
- **Requirements:** `pydantic>=2.0.0`, `anthropic~=2.7`, `pillow-heif>=0.18.0`
- **Anthropic API version:** `2026-10-21`
- **Model list and capabilities are fetched dynamically** from Anthropic's Models API (`max_input_tokens`, `max_tokens`, thinking/effort support, compaction support, etc.)
- **Current Anthropic model docs focus on:** `Claude Fable 5.2`, `Claude Opus 5.5`, `Claude Sonnet 5.5`, `Claude Haiku 5.5`

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
| **OpenWebUI integration** | Notes, channels, task generation, built-in tools, MCP tools, sub-agents, tool approval, toggle filters; OpenWebUI's Web Search / Code Interpreter buttons switch on the Anthropic tools |

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
2. Paste the source of [`anthropic_pipe.py`](anthropic_pipe.py) from this repo — or [`anthropic_pipe.min.py`](anthropic_pipe.min.py), the same pipe with comments and docstrings stripped (~28% smaller, quicker to paste)
3. Repeat for the toggle filters you want to use (`anthropic_pipe_thinking_toggle.py`, `anthropic_pipe_web_search_toggle.py`, `anthropic_pipe_code_execution_toggle.py`, `anthropic_pipe_files_toggle.py`, `anthropic_pipe_fast_toggle.py`)
4. Set the admin valves described below (at least `ANTHROPIC_API_KEY`, or the `ANTHROPIC_API_KEY` environment variable)
5. The **Companion Filter** is only needed if a model runs with Function Calling **`Legacy`** (see below)

### Recommended OpenWebUI model configuration

For each Claude model in **Admin Settings → Models**:

1. Set **Function Calling** to **`Native`** (the default since OpenWebUI 0.10)
2. Attach the toggle filters you want available for that model
3. Use the model's **Builtin Tools** switches to decide what the model may use. **Web Search** off: no Anthropic web search and no web fetch for this model, whatever the valves say. **Code Interpreter** off: no code execution on request (Files API uploads and programmatic tool calling still turn it on, they need it)
4. OpenWebUI's **Web Search** and **Code Interpreter** buttons in the chat input work without any filter: with `WEB_SEARCH` / `CODE_EXECUTION` on, they switch on Anthropic's tools instead of OpenWebUI's
5. Attach the **Companion Filter** only to models with Function Calling **`Legacy`**: there OpenWebUI would run its own search and code-interpreter prompt before the pipe sees the request, and the filter switches those off
6. If you plan to use **Skills** or **Files API** workflows heavily, prefer models with strong tool and code-exec support (today that usually means **Opus 5.5** or **Sonnet 5.5**)

### Which tool runs when

OpenWebUI brings its own built-in tools (`search_web`, `fetch_url`, `execute_code`) and its own Tool Search. The pipe offers Claude only one of each pair:

| Feature | Anthropic tool when | Otherwise |
|---------|--------------------|-----------|
| Web search | `WEB_SEARCH` on (or the Web Search Toggle) **and** the model's Web Search switch on → `web_search`, OpenWebUI's `search_web` is dropped. The Web Search button forces a search for that message | OpenWebUI's `search_web`, if its Web Search button is on |
| Fetch a URL | `WEB_FETCH` on **and** the model's Web Search switch on → `web_fetch`, `fetch_url` is dropped | OpenWebUI's `fetch_url` |
| Code | Code Interpreter button (with `CODE_EXECUTION` on), Code Execution Toggle, Files API uploads or programmatic tool calling → `code_execution`, `execute_code` is dropped. Button and toggle need the model's Code Interpreter switch | OpenWebUI's `execute_code`, if its Code Interpreter button is on and `CODE_EXECUTION` is off |
| Tool Search | `ENABLE_TOOL_SEARCH` on → Claude's native tool search (off under programmatic tool calling on models that support it) | OpenWebUI's Tool Search if enabled in Admin → Interface, otherwise all tools loaded |

### Setup by OpenWebUI version

| OpenWebUI | Function Calling | Companion Filter | Worth setting up |
|-----------|------------------|------------------|------------------|
| `0.8.11` – `0.9.x` | **Native**. Unset meant the prompt-based mode there, which bypasses the pipe's tool loop; the pipe switches the model to Native on the first request with tools and asks you to re-run it | Not needed with Native. Before `0.8.2` OpenWebUI added its code-interpreter prompt even with Native: attach it there | Toggle filters, the model's Builtin Tools switches (since `0.8.0`). Answers use the text path |
| `0.10` – `0.12.1` | Native is the default | Only for models set to **Legacy** | `ENABLE_VALVE_ENCRYPTION=true` if you want OpenWebUI to encrypt valves itself (otherwise the pipe encrypts the API key). Tool approval from `0.11.1`, OpenWebUI's Context Compaction from `0.11.3` (the pipe's `ENABLE_COMPACTION` steps aside on chats it summarized) |
| `0.12.2` – `0.12.x` | Native | Only for Legacy | Answers stream as output items (recommended minimum). From `0.12.3` OpenWebUI has its own Tool Search: `ENABLE_TOOL_SEARCH` on uses Claude's instead, off uses OpenWebUI's |
| `0.13+` | Native | Only for Legacy | Tool Call Labels and the "Auto" tool permission mode work with the pipe's tool calls; `call_tool` batches from `0.13.1` |

Toggle filters, by need:

| Toggle | Use it when |
|--------|-------------|
| **Thinking**, **Fast Mode**, **Files API** | Any version: per-message switches for things OpenWebUI has no button for |
| **Web Search** | Only if `WEB_SEARCH` is off and you want Anthropic search for single messages. With the valve on, OpenWebUI's own Web Search button does the same |
| **Code Execution** | Only if `CODE_EXECUTION` is off and you want Anthropic code execution for single messages. With the valve on, OpenWebUI's Code Interpreter button does the same |

Both the Web Search and the Code Execution toggle respect the model's Builtin Tools switches: with the switch off they do nothing.

A chat that started with another model can carry that model's calls to `search_web` or OpenWebUI's `call_tool`. If Claude repeats such a call, the pipe answers with the tool to use instead (for example "Use the 'web_search' tool instead") rather than a dead-end error.

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
- **0.11**
   - sub-agents (`delegate_task`) and the built-in tools `notify`, `timer`, `list_chat_files`, `grep_chat_files`, `query_chat_files`
   - auto-compaction reads the context gauge the pipe reports
- **0.11.1**
   - human-in-the-loop tool approval, and the `ask_user` built-in tool
   - multiselect valve inputs
- **0.11.3**
   - OpenWebUI's own Context Compaction (Admin → Interface). When it has summarized a chat, the pipe's API-side compaction steps aside for that request
- **0.12.3**
   - OpenWebUI's own Tool Search (Admin → Interface) holds large tools back behind `search_tools` / `call_tool`. With `ENABLE_TOOL_SEARCH` on, Claude's native tool search replaces it; with it off, OpenWebUI's Tool Search runs and the pipe resolves `call_tool` in its tool loop

- **0.12.2**
   - pipes can stream OpenWebUI output items with provider data (`provider_function`, `reasoning_details`) that come back on the next turn. From pipe 0.11.0 on, answers stream this way: thinking, tool calls and server tools render natively and the prompt cache holds across them
- **0.13**
   - skill list, memories and attached knowledge arrive as hidden tool results after the user's message; Tool Call Labels and the "Auto" tool permission mode, both honoured by the pipe (0.11.1+)
   - **0.13.1:** `call_tool` takes a batch of calls; the pipe runs each and shows it as its own tool

If you fork this pipe or copy code into your own plugin, note that OpenWebUI `0.9.0+` moved DB/model helpers to async. The pipe is already migrated, but custom additions must also follow the async model/helper rules. See the official migration guide: https://docs.openwebui.com/features/extensibility/plugin/migration/to-0.9.0

---

## 🔧 Configuration

### Global Valves (admin-wide)

| Valve | Default | Description |
|-------|---------|-------------|
| `ANTHROPIC_API_KEY` | `$ANTHROPIC_API_KEY` | Anthropic API key, unless overridden by a per-user key. Falls back to the `ANTHROPIC_API_KEY` environment variable. Stored encrypted, see [below](#-api-key-storage) |
| `ANTHROPIC_BASE_URL` | `https://api.anthropic.com` | Custom base URL / proxy (Azure, `aws-external-anthropic`, gateways) |
| `ENABLED_MODELS` | `""` | Comma-separated model IDs to expose. Bypasses `/v1/models` auto-discovery — needed for endpoints without a models API |
| `ANTHROPIC_WORKSPACE_ID` | `""` | Experimental: "Claude on AWS" workspace ID, sent as the `anthropic-workspace-id` header |
| `LEGACY_CHAT_MIGRATION` | `dry-run` | One-time upgrade of chats written before pipe 0.11 to output items. `dry-run` counts and writes `anthropic_pipe_legacy_migration_*.dryrun.json` to OpenWebUI's data directory, `on` converts (one write per chat), `off` skips. Each mode runs once; delete its file to run it again. Turns that carried the cache-diagnostics block or adjacent text blocks miss the prompt cache once |
| `ENABLE_MESSAGE_THREADS` | `false` | Message threads (beta): inside a tool loop only the new tool results are sent instead of the whole conversation on every request. Anthropic holds the conversation in memory for up to 1 hour (not ZDR-eligible). Not faster at ~25k tokens of context, and after a web search the next request re-writes the search result to the cache (API-side). Not used together with compaction; any thread error falls back to full requests |
| `ENABLE_FAST_MODE` | `false` | Sends Anthropic's `speed: "fast"` tier on models that support it (Fable 5.2, Opus 5.5 / 5; up to ~2.5x faster, higher cost). Per message: Fast Mode Toggle |
| `REFUSAL_FALLBACK` | `off` | Retry a safety-refused request server-side: `off`, `default` (Anthropic's per-category recommendation), or a pinned model. Claude API only; skipped for Haiku 5.5, which has no server-side fallback |
| `ENABLE_INTERLEAVED_THINKING` | `true` | Allows thinking blocks between tool calls where supported |
| `WEB_SEARCH` | `true` | Anthropic web search replaces OpenWebUI's `search_web` / `fetch_url`. A model whose Web Search builtin tool is switched off cannot search, even with this on. The Web Search button forces a search for that message |
| `WEB_FETCH` | `true` | Anthropic native URL fetch (replaces `fetch_url`; follows the model's Web Search switch) |
| `CODE_EXECUTION` | `true` | The Code Interpreter button turns on Anthropic code execution instead of OpenWebUI's `execute_code` (and removes the pyodide note OpenWebUI adds to the system prompt). A model whose Code Interpreter builtin tool is switched off gets neither |
| `MAX_TOOL_CALLS` | `15` | Maximum Claude → tool → Claude loop count per request |
| `MAX_RETRIES` | `3` | Retries for overload, rate limits, and transient transport/provider errors |
| `CACHE_CONTROL` | `cache tools array, system prompt and messages` | Prompt caching scope (see below) |
| `CACHE_TTL` | `5 minutes` | Anthropic cache TTL (`1 hour` is also supported, at higher write cost) |
| `CACHE_TTL_FOR_TOOLS_AND_SYSTEM_PROMT` | `same as CACHE_TTL` | Separate TTL for tools array + system prompt, independent of messages. Useful for big multi-user setups |
| `MEMORY_REVIEW_MODEL` | `claude-haiku-5-5` | Model used for OpenWebUI's background memory review (`same as chat model` to disable the override) |
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
| `ENABLE_THINKING` | `false` | Enables extended thinking. On models with thinking on by default turning it **off** sends their lowest setting: `disabled` on Opus 5 / Sonnet 5 / Haiku 5.5, `between_tools` on Sonnet 5.5, effort `low` on Opus 5.5 (thinking cannot be turned off there) |
| `THINKING_BUDGET_TOKENS` | `8192` | Manual thinking budget for models that still use `budget_tokens` |
| `THINKING_DISPLAY` | `omitted` | `summarized` streams summarized thinking, `omitted` hides it for faster time-to-first-text, `updates` (beta) hides reasoning but shows the short progress updates Fable 5 / 5.1, Opus 5.5 and Sonnet 5.5 write before a tool call |
| `EFFORT` | `high` | `low`, `medium`, `high`, `xhigh`, `max` (clamped by model support; also settable via OpenWebUI's `reasoning_effort`) |
| `HIDE_BLOCKS` | `[]` | Multiselect: block types to hide from the chat display while still replaying them to the API — `web_search`, `web_fetch`, `tool_search`, `advisor`, `code_execution`, `compaction` |
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
| `ENABLE_TOOL_SEARCH` | `true` | Claude's native deferred tool loading with search for large tool sets. Wins over OpenWebUI's own Tool Search; off: OpenWebUI's Tool Search runs if enabled, otherwise no tool search |
| `TOOL_SEARCH_TYPE` | `bm25` | Tool search mode: `bm25` or `regex` |
| `TOOL_SEARCH_MAX_DESCRIPTION_LENGTH` | `100` | Tools with longer JSON definitions are deferred for lazy loading |
| `TOOL_SEARCH_EXCLUDE_TOOLS` | Anthropic server tools + OpenWebUI built-ins + Open Terminal tools | Multiselect: always keep these tools loaded. Tools passed in the request body are never deferred |
| `ENABLE_ADVISOR_TOOL` | `false` | Enables the Advisor tool (beta `advisor-tool-2026-03-01`). Executor model consults a stronger advisor mid-generation for strategic guidance. Billed at the advisor's rate. |
| `ADVISOR_MODEL` | `claude-opus-5` | Advisor model, at least as capable as the chat model (Opus 4.6 to 5.5, Sonnet 4.6 / 5 / 5.5, Haiku 5.5, Fable / Mythos 5 to 5.2). `claude-fable-5-2` can advise every model; an invalid pair falls back to the strongest valid advisor |
| `ADVISOR_MAX_USES` | `0` | Max advisor calls per request (`0` = unlimited). Beyond this, further calls return `advisor_tool_result_error` with `max_uses_exceeded`. |
| `ADVISOR_CACHING` | `off` | Ephemeral prompt caching for the advisor transcript: `off`, `5m`, or `1h` |

#### Compaction and context editing

| Valve | Default | Description |
|-------|---------|-------------|
| `ENABLE_COMPACTION` | `false` | Enables Anthropic API compaction where the model supports it. Steps aside on chats OpenWebUI's own Context Compaction has already summarized |
| `COMPACTION_TRIGGER_TOKENS` | `50000` | Token threshold that triggers compaction |
| `COMPACTION_INSTRUCTIONS` | `""` | Optional custom compaction prompt |
| `CONTEXT_EDITING_STRATEGY` | `none` | `none`, `clear_tool_results`, `clear_thinking`, `clear_both` |
| `CONTEXT_EDITING_THINKING_KEEP` | `0` | Recent assistant thinking turns to preserve; `0` means keep all |
| `CONTEXT_EDITING_TOOL_TRIGGER` | `50000` | Token threshold for clearing tool results |
| `CONTEXT_EDITING_TOOL_KEEP` | `5` | Number of recent tool results to keep |
| `CONTEXT_EDITING_TOOL_CLEAR_AT_LEAST` | `10000` | Minimum tokens to clear when triggered |
| `CONTEXT_EDITING_TOOL_CLEAR_TOOL_INPUT` | `false` | Also clear tool input payloads |

### Important behavior notes

- The pipe automatically prefers **adaptive thinking** whenever the model advertises it (Fable 5.1, Opus 5.5, Sonnet 5.5, Haiku 5.5, Opus 5, Sonnet 5, Opus 4.8/4.7/4.6, Sonnet 4.6).
- Anthropic recommends **`effort`** as the main control for adaptive-thinking models. Effort levels are clamped per model from the Models API, so unsupported values (`xhigh`, `max`) degrade instead of erroring.
- On **Opus 5 / Sonnet 5 / Haiku 5.5**, thinking is **on by default**. Switching `ENABLE_THINKING` off sends `thinking: {"type": "disabled"}` and clamps effort to `high`, because disabled thinking is rejected at `xhigh`/`max`. **Sonnet 5.5** rejects `disabled`; it gets `thinking: {"type": "between_tools"}` (no up-front thinking) with the same clamp. **Opus 5.5** always thinks, so "off" lowers effort to `low`.
- **Opus 5.5, Sonnet 5.5, Fable 5.1 and Mythos 5.1** reject forced `tool_choice` (`tool` / `any`). The pipe degrades it to `auto` on those models instead of failing the request.
- `THINKING_DISPLAY="omitted"` suppresses streamed `thinking_delta` events, matching Anthropic's streaming behavior.
- `USE_FILES_API` **overrides** native PDF upload. If enabled, the pipe uploads files to Anthropic and injects `container_upload` blocks at the correct message positions.
- Anthropic's **Files API** supports create-once / use-many flows, but remains **beta**.
- Anthropic **citations** work well with prompt caching, but Anthropic docs note they are incompatible with strict structured outputs.
- `CACHE_TTL="1 hour"` maps to Anthropic's extended cache TTL (`{"type": "ephemeral", "ttl": "1h"}`).
- `CONTEXT_EDITING_THINKING_KEEP=0` is the safest cache-friendly default. Sliding windows (`>0`) can reduce cache efficiency on long thinking-heavy chats.
- `ENABLE_DYNAMIC_FILTERING` improves quality for supported web-search / web-fetch models but is **substantially slower** than the normal flow.
- **Tool approval** (OpenWebUI `0.11.1`) is honored by the pipe itself. OpenWebUI enforces its own gate inside its native tool loop, which a manifold never enters — so without this the setting silently did nothing. Enable it with `ENABLE_TOOL_PERMISSIONS=true` **and** the matching admin toggle (Admin Settings → Chat → tool permissions); the env var only seeds the persisted config on a fresh database. With approval set to `ask`, every client, built-in and Open Terminal tool call waits for an explicit allow/deny, one prompt per call. A denial is returned to the model as an ordinary tool result, so the conversation continues instead of erroring.
- There is **no dedicated Claude memory tool** documented here anymore. This README intentionally reflects the current pipe surface only.

### 🔐 API key storage

The API key valve — admin-wide and the per-user override — is encrypted before it reaches the database: Fernet, with the key derived from `WEBUI_SECRET_KEY` the same way OpenWebUI derives it.

| Situation | What happens |
|-----------|--------------|
| **Default OpenWebUI install, any version** | The pipe encrypts the key. OpenWebUI's own valve encryption is **off unless you set `ENABLE_VALVE_ENCRYPTION=true`** — without it, valves land in the `functions` table in plaintext |
| `ENABLE_VALVE_ENCRYPTION=true` (0.10.0+) | The pipe steps aside and lets OpenWebUI handle it — no double encryption. Keys encrypted before you flipped the flag stay readable |
| No `WEBUI_SECRET_KEY`, or `cryptography` unavailable | Values pass through in plaintext. Nothing breaks |
| Upgrading with a key already configured | Keeps working as-is. Plaintext values are read unchanged; no migration step |
| `WEBUI_SECRET_KEY` changed after the key was stored | The pipe reports that the key could not be decrypted and asks you to re-enter it, instead of failing with a confusing `401` |

### Toggle filters & companion filter

| Component | Purpose |
|-----------|---------|
| **Thinking Toggle** | One-shot thinking enable for the next message |
| **Web Search Toggle** | One-shot web-search forcing for the next message. Only needed with `WEB_SEARCH` off, see [Setup by OpenWebUI version](#setup-by-openwebui-version) |
| **Code Execution Toggle** | One-shot code-execution enable for the next message. Only needed with `CODE_EXECUTION` off |
| **Files API Toggle** | One-shot Files API mode for file-heavy / skill-heavy flows |
| **Fast Mode Toggle** | One-shot fast mode for the next message (Fable 5.2, Opus 5.5 / 5; ignored on other models) |
| **Companion Filter** | Only for Function Calling `Legacy`: switches off OpenWebUI's own web search / code interpreter so the Anthropic tools run instead. With `Native` the pipe handles the buttons itself |

---

## 📝 Recent pipe changes
### `v0.11.2`
_Tested on OpenWebUI 0.13.3._
- WEB_SEARCH now means: Anthropic web search replaces OpenWebUI's search_web / fetch_url. While web_search / web_fetch go out, OpenWebUI's two tools are dropped from the request. New valve CODE_EXECUTION (on by default) does the same for the Code Interpreter button: it turns on Anthropic code execution instead of OpenWebUI's execute_code, and the pyodide note OpenWebUI appends to the system prompt for its tool is removed.
- The Web Search and Code Interpreter buttons work without the Companion Filter: the pipe reads them itself. The filter is only needed with function calling set to "legacy".
- The model's Builtin Tools switches apply: with Web Search off the model gets neither web_search nor web_fetch (even with WEB_SEARCH on or the web search toggle), with Code Interpreter off no code execution on request. Files API uploads and programmatic tool calling still turn code execution on, they need it.
- A chat started with another model can carry its calls to search_web or OpenWebUI's call_tool. Claude copied them, got "not available ... not configured" and answered without searching. A call to a replaced tool now gets "Use the 'web_search' tool instead" (only when that tool is in the request), a call_tool the request does not offer says to call tools by name.

### `v0.11.1`
_Tested on OpenWebUI 0.12.3 and 0.13.3. Needs `anthropic~=2.7`; OpenWebUI installs it when it loads the pipe._
- Claude Fable 5.2 and Mythos 5.2: model data, prices ($8 / $40 per MTok, fast mode $16 / $80) and fast mode, which needs no beta header there. Thinking cannot be switched off on them; with the thinking toggle off the pipe sends effort `low`, as on Opus 5.5.
- Advisor pairs follow Anthropic's current table: Fable 5.2 can advise every model, a Fable 5.2 chat model takes only Fable / Mythos 5.2, Opus 5.5 gets an advisor (the tool was skipped there before), and Sonnet 4.6 / 5 / 5.5, Haiku 5.5 and Opus 4.6 are selectable advisors. An invalid pair still falls back to the strongest valid advisor.
- New valve ENABLE_MESSAGE_THREADS (beta, off by default): inside a tool loop the pipe sends only the new tool results instead of the whole conversation on every request, so requests get smaller. Measured with about 25k tokens of context it is not faster, and after a web search the next request writes the search result to the cache again (an API-side miss, reported to Anthropic), so it stays off unless your loops are long and search-free. Anthropic holds the conversation in memory for up to an hour (not eligible for zero data retention). Not used together with compaction; any thread error falls back to full requests.
- OpenWebUI 0.13 puts the skill list, memories and attached knowledge after the user's message as hidden tool results. The pipe took that tool result for the user's message: retrieved file context (RAG) ended up inside the cached prefix, so every follow-up in a chat with files re-wrote the conversation instead of reading it from the prompt cache, and a newly attached full-context file was placed on the tool result. Both now go by the message the user wrote. OpenWebUI 0.12 behaves as before.
- OpenWebUI 0.13: Tool Call Labels show on the pipe's tool calls, and the label and approval fields OpenWebUI adds to tool schemas no longer reach the tool. Tool permission mode "Auto" is honoured: a tool runs unasked only when the model marks the call as needing no approval, otherwise the pipe asks.
- The chat migration from 0.11.0 (LEGACY_CHAT_MIGRATION) stopped with an error on OpenWebUI 0.12.4 and newer, which renamed a database call; neither the dry run nor `on` did anything there. It runs again; chatting was not affected.
- OpenWebUI 0.13.1 Tool Search: `call_tool` now takes a batch (`calls`: list of tool_name + params). The pipe only knew the single-call form, so every deferred tool failed with "call_tool requires tool_name and params". The calls run in order; each shows as its own tool with its own result and card, as in OpenWebUI's own loop, while the API gets one call with one combined result, so the replay and the prompt cache are unchanged. OpenWebUI 0.13.0 and older keep the single-call form.
- Tool Rich UI (HTML cards such as a weather widget) shows again in chats with output items: the embeds and files a tool returns now sit on its result item, as OpenWebUI's own connections store them. Since 0.11.0 they were dropped there.
- OpenWebUI Tool Search: the call shows as the tool it ran (e.g. get_weather) instead of a hidden call_tool, like OpenWebUI's own loop; the replay still sends the API's call_tool.
- Tool calls carry started_at / ended_at / duration. OpenWebUI's Stop handling uses them to tell "outcome unknown" from "not executed", its analytics show the time.
- Without the token display (SHOW_TOKEN_COUNT `Off`) a turn ends without the "✅ Response Complete" line, like OpenWebUI's own connections. OpenWebUI's own finished statuses (e.g. retrieved sources), notices and a web search's source list stay visible.
- Number valves show as sliders on OpenWebUI 0.12.5+ (thinking budget, max uses, retries).
- Cache diagnostics goes out without its beta header (generally available). Requirement raised to `anthropic~=2.7`; OpenWebUI installs it when it loads the pipe.

### `v0.11.0`
_Streaming as output items needs OpenWebUI 0.12.2; older versions keep the text path._
- Answers stream as OpenWebUI output items, the way OpenWebUI's own OpenAI and Ollama connections do: thinking as reasoning, text as a message, every tool call (local tools, web search, web fetch, code execution, tool search, advisor) as a function call with its result. OpenWebUI renders them natively, writes the chat once at the end and serves reloads and reconnects from its own copy. The exact Anthropic blocks (thinking signatures, encrypted search results) ride in `reasoning_details` and `provider_function`, so the next turn sends the API byte for byte what it saw and the prompt cache holds across thinking, tools and server tools.
- The tool loop builds its next request from the same items the next turn replays, so the two cannot drift apart (the cause of #58 and of the `caller` cache break fixed in 0.10.3).
- Every tool call has an output before the stream ends, an error if the run failed, so OpenWebUI never runs one of the pipe's calls itself. When the user stops an answer, OpenWebUI marks open calls incomplete and the next turn leaves them out.
- Chats written before 0.11 convert once to output items: valve LEGACY_CHAT_MIGRATION, default `dry-run` (counts and writes a report to OpenWebUI's data directory), `on` converts. A turn is converted only if the API gets the same messages afterwards; turns that still carried the cache-diagnostics block or two adjacent text blocks miss the prompt cache once. The `<details>` parser moved to its own module and goes away in a later release.
- In item mode the 5-second `replace` throttle and the 2-second resync from 0.10.3 are gone: OpenWebUI stores and resyncs items itself.
- A response that is retried (stream cut off, overloaded API) replaces what the failed attempt had shown instead of being appended to it.

### `v0.10.3`
- Streaming no longer rewrites the chat in the database on every delta. OpenWebUI stores each `replace` and `message` event by rewriting the whole chat row, so a long answer wrote a long chat hundreds of times per turn and Postgres grew until it ran out of space. Text deltas now go out as `chat:message:delta` and thinking, tool-input, code-preview and compaction re-renders as `chat:message` (both shown, not stored); the stored copy follows at most every 5 seconds and at every block end. A thinking answer went from 111 stored events to 8 (#59, reported by @icsy7867).
- Reloading the page, reopening the tab, a dropped connection or a phone that put the browser in the background mid-stream: the answer is whole again within 2 seconds and keeps streaming. OpenWebUI's frontend only appends deltas, so a reloaded or reconnected page missed everything in between; every 2 s a delta now goes out as the full content instead. Tested in the browser for reload, tab close, offline, 10 s / 60 s freeze, stop, and reload during thinking.
- Follow-ups no longer fail with "tool_use ids were found without tool_result blocks immediately after" when a local tool round was followed by thinking or a server tool such as web search. Replay used to end a tool round only at text and folded two rounds into one assistant message; it now ends the round at any content. A server tool the model called in the same response as a client tool stays with it (marked since v0.9.39). Chats replayed with the old structure get one prompt-cache miss (#58, reported by @yinccc999).
- A web search in the same turn as a local tool no longer breaks the prompt cache on the next message: the tool loop sent the result's `caller: direct` field, replay rebuilt the block without it. `direct` callers are now dropped from every block, as they already were on tool_use.
- Fast mode is no longer offered on Opus 4.8: Anthropic removes it on 2026-11-30, after which speed "fast" on claude-opus-4-8 returns an error. Opus 5.5 and Opus 5 keep it. The fast toggle filter's description now names those two.
- Native PDF upload takes PDFs up to 64 MB on the Claude API (was 25 MB), following the request limit raised from 32 to 128 MB. A custom ANTHROPIC_BASE_URL keeps 25 MB. The size is checked before the file is read.

### `v0.10.2`
- Logs carry no chat content or personal data at any level, DEBUG included. The `[PAYLOAD]` line replaces every string in `messages`, `system` and `metadata` with its length and a salted hash (`‹33c#8cf3e5f8›`); type, role, ids, tool names and `cache_control` stay readable, so prompt-cache drift is still traceable. Before, the system prompt (memories, user name, location) went out in full and message text clipped to 20 characters
- Also gone from the logs: stream event bodies, tool arguments and results, web/tool search queries, bash commands, code execution / web search / advisor results, citations, file names (now file ids), extracted memories, refusal explanations, task responses (titles, tags), the CACHE-DIFF message dumps, and the API key in the DEBUG Valves dump
- The `anthropic` SDK logger is capped at INFO: under `GLOBAL_LOG_LEVEL=DEBUG` it logged every request body in full. OpenWebUI's own DEBUG logs still contain chat content; keep `GLOBAL_LOG_LEVEL` at INFO or above in production

### `v0.10.1`
- OpenWebUI Tool Search with `ENABLE_TOOL_SEARCH` on: Claude's native tool search wins, and the `call_tool` dispatcher OpenWebUI 0.12.3 added is dropped along with `search_tools`. Before, `call_tool` reached the model pointing at a missing `search_tools`, and calling it ended the turn with its arguments shown as message text
- `ENABLE_TOOL_SEARCH` off: OpenWebUI's Tool Search now runs as OpenWebUI designed it (manifest, `search_tools`, `call_tool`, which the pipe resolves in its own tool loop) instead of being replaced by Claude's tool search anyway. Both off: no tool search

### `v0.10.0`
- API version `2026-10-21` and anthropic SDK 2.x (requirement `anthropic~=2.0`; OpenWebUI upgrades it when it loads the pipe)
- `temperature` / `top_p` / `top_k` from model params are no longer sent. `2026-10-21` rejects them on every model, and with SDK 1.9+ they already failed with a `TypeError` on Haiku 4.5, Sonnet 4.5 and Opus 4.5
- SDK 2.x authenticates with `Authorization: Bearer`. A custom `ANTHROPIC_BASE_URL` (proxy, gateway) also gets the key as `x-api-key`, so gateways that read only that header keep working
- Fast mode on Opus 5.5 is GA and goes out without the beta header; Opus 5 and Opus 4.8 keep it
- `/v1/models`: `server_tools` gates the web search and code execution tools per model, `thinking.types` picks how a thinking-on-by-default model is switched off (`disabled` or `between_tools`)
- Web fetch switched off for the organization in the Claude Console: the turn retries once without the tool and shows a warning instead of failing with a 400

### `v0.9.39`
- Prompt cache kept across tool calls: the tool loop now sends a tool result in the same form the next turn replays it (JSON compacted, plain text unquoted). Before, every turn after a tool call lost the cache from the first tool result on
- Prompt cache kept for tool calls with two or more arguments (e.g. tool search's `query` + `limit`): replay no longer re-sorts the model's `input` keys, which the API renders into the prompt (cache diagnostics: `messages_changed`)
- A server tool the model calls right after a client tool in the same response (e.g. `bash` after `view_knowledge_file`) stays in that assistant message on replay instead of moving into the next one
- Tool search: the system hint now names the deferred tools (sorted, changes only with the tool set). Without the names the model answered "use the weather tool" with web search instead of searching for the deferred tool
- Open Terminal plus code execution in one request: a system hint tells the model that only the terminal tools reach the user's terminal. Asked to run a command in the terminal, it used Anthropic's isolated code execution sandbox instead
- `CACHE-DIFF` debug log no longer reports block key-order differences as breaks (the API ignores them; only tool `input` order counts). The `[PAYLOAD]` log line lists deferred tools

### `v0.9.38`
- Estimated USD cost per turn (new `SHOW_COST` user valve, contributed by Willian-Zhang in #49): `cost_usd` plus a per-component `cost_breakdown_usd` in the message usage (message info tooltip, persisted for analytics) and appended to the `SHOW_TOKEN_COUNT` status line. Prices come from a built-in list-price table (verified 2026-10-13); admins patch it via the `MODEL_PRICING_OVERRIDES` valve (JSON, USD per MTok)
- The estimate follows the bill: cache writes split 5m/1h, fast mode, Haiku 5.5's prompt-length tier and US data residency priced per API call from the response usage, web searches at $10 per 1,000

### `v0.9.37`
- Removed the beta headers of features Anthropic made generally available (effort, code execution 20250825, web fetch 20250910, tool search / programmatic tool calling, prompt caching); verified live without them
- Removed context editing (`CONTEXT_EDITING_*` user valves): off by default, and it invalidated the prompt cache whenever it cleared. Compaction stays

### `v0.9.36`
- OpenWebUI < 0.10 only: the auto-switch to native function calling is back, gated on the running version. From 0.10 on an unset `function_calling` already means native, so the pipe no longer rewrites model rows there or overrides an explicit "legacy"

### `v0.9.35`
- Removed the native-function-calling auto-switch for OpenWebUI 0.12, where it rewrote every model row without the param, showed a "re-run your query" toast and overrode "legacy" (restored for < 0.10 in v0.9.36)
- `web_search` enforcement (`tool_choice`) no longer depends on any beta header being sent; with caching and all betas off it was silently skipped
- Dead code removed (unused helpers, SDK < 0.121 shims, fallback emitters); payload/task JSON dumps only serialize at DEBUG; per-tool log lines moved to DEBUG

### `v0.9.34`
- OpenWebUI 0.12 Tool Search: tools OpenWebUI holds back are sent with native `defer_loading` (Claude's tool search); OpenWebUI's `search_tools` and its `<available_tools>` manifest are dropped
- Tool approval uses OpenWebUI 0.12's native Tool Permissions dialog (`tool_call` in the confirmation event). Only an explicit allow approves; a timed-out or closed dialog no longer counts as approval
- Private tool helpers (names starting with `_`) stored in a tool's specs are no longer sent to the model
- Removed the dead skill-id resolution; skill tools come from OpenWebUI, gated by the model's Builtin Tools > Skills switch

### `v0.9.33`
- Fast mode falls back to standard speed on a `429`. Fast requests are sent without SDK retries; when fast mode is rate-limited (or not enabled for your organization: fast mode is a research preview, limit `0`), the turn is retried at standard speed and a warning notification says so, instead of failing with "Rate limit exceeded" after several backoffs. The fallback costs one prompt-cache miss, since fast and standard requests share no cached prefix

### `v0.9.32`
- Fixed the per-message **Fast Mode Toggle** not sending the `fast-mode-2026-02-01` beta header when the admin valve `ENABLE_FAST_MODE` is off (#52)
- Fixed the Opus-5.5 advisor skip and the executor→advisor fallback lookup missing dated model ids. Endpoints that serve dated aliases (e.g. `claude-opus-5-5-20260215` from Azure/custom proxies) slipped past the literal `claude-opus-5-5` check, which re-enabled the advisor tool on an executor that has no valid pair and 400'd the request. Both paths now normalize the id (strip the `-YYYYMMDD` suffix) through the same helper `get_model_info` uses

### `v0.9.31`
- Added **Claude Sonnet 5.5** (`claude-sonnet-5-5`): 1M context, 128k output, adaptive thinking on by default, full effort ladder including `max`
- Sonnet 5.5 rejects `thinking: {"type": "disabled"}`. The Thinking Toggle / `ENABLE_THINKING=off` now sends its lowest setting there, `thinking: {"type": "between_tools"}`: no up-front thinking, while the notes between tool calls still arrive as thinking blocks. Like the Opus 5 disable, it is capped at effort `high`
- Sonnet 5.5 rejects forced `tool_choice` (`tool` / `any`); it is degraded to `auto`, as on Opus 5.5 / Fable 5.1
- Added **Claude Haiku 5.5** (`claude-haiku-5-5`): 1M context, 128k output, adaptive thinking on by default, full effort ladder including `max`. Thinking off sends `thinking: {"type": "disabled"}` (capped at effort `high`); forced `tool_choice` keeps working
- Haiku 5.5 has no server-side refusal fallback, and a pinned fallback model returns a 400, so `REFUSAL_FALLBACK` is skipped for it
- Advisor pairs for Sonnet 5.5 and Haiku 5.5 executors; Opus 5.5 is now selectable as `ADVISOR_MODEL`
- `MEMORY_REVIEW_MODEL` now defaults to Haiku 5.5, at about a tenth of Haiku 4.5's price. Sonnet 5.5 is selectable there as well, and as a `REFUSAL_FALLBACK` target
- The `drop_block` retry for changed prompt prefixes is skipped for `between_tools` requests, which accept no other thinking field

### `v0.9.30`
- Added **Claude Opus 5.5** (`claude-opus-5-5`): 1M context, 128k output, always-on adaptive thinking, full effort ladder including `max`, fast mode
- Opus 5.5 rejects `thinking: {"type": "disabled"}`: the Thinking Toggle / `ENABLE_THINKING=off` lowers effort to `low` there instead of disabling thinking
- Opus 5.5 rejects forced `tool_choice` (`tool` / `any`); it is degraded to `auto`, as on Fable 5.1
- `thinking.block_binding` `"drop_block"` is no longer sent up front. On accounts created before 2026-08-31 it opted every request in to the prefix check and dropped thinking blocks the model could otherwise still read. Newer accounts get a 400 for a changed prefix instead; the pipe retries that request once with `drop_block`, so the turn still goes through
- `THINKING_DISPLAY="updates"` also covers Opus 5.5, where the notes between tool calls arrive as thinking blocks and stay empty at `omitted`. Its beta header is sent whenever `updates` is used
- Opus 5.5 is not a valid advisor executor yet: the advisor tool is skipped on that model instead of failing the request

### `v0.9.29`
- Added **Claude Fable 5.1 / Mythos 5.1**: 128k output, 1M context, adaptive thinking, compaction, structured outputs, and selectable as advisor models
- Forced `tool_choice` (`tool` / `any`) is no longer sent to models that reject it: Fable 5.1 and Mythos 5.1 return a 400 for forced tool use, so web-search enforcement and a forced `tool_choice` from the request body degrade to `auto` on them (logged)
- Thinking blocks replayed to Fable 5.1 are bound to the request prefix (system, tools, earlier messages). OpenWebUI changes that prefix between turns (memory/RAG appendix, tool toggles, context compaction summary); the pipe now handles a prefix mismatch instead of surfacing a 400
- `THINKING_DISPLAY` accepts `updates` (beta): reasoning stays hidden, the one-line progress updates Fable 5 / 5.1 write before a tool call are shown as thinking text
- `ENABLE_COMPACTION` steps aside when OpenWebUI's own Context Compaction (`0.11.3+`) has already summarized the chat, so the two never run on the same conversation

### `v0.9.28`
- Fixed every tool being deferred for tool search regardless of the exclude list: the `TOOL_SEARCH_EXCLUDE_TOOLS` default shipped as one comma-separated blob inside a one-element list, so nothing ever matched. Server tools and even `tool_search` itself were deferred, which proxies without deferred loading (litellm, Bedrock) answered with a 400 (#44, reported by @icsy7867)
- `TOOL_SEARCH_EXCLUDE_TOOLS` is now a multiselect with a real list default; comma-separated and legacy blob values still load
- Raised the `max_tokens` fallback for unrecognised model ids from 4096 to 64000. Proxies that rename models (`us.anthropic.claude-sonnet-5-v1:0`) missed the lookup table and truncated long answers (#43, reported by @icsy7867)
- The truncation notice now names the actual output limit instead of suggesting a full context window
- Fixed a truncated answer being retried up to `MAX_RETRIES` times: `stop_reason: "max_tokens"` fell through to the truncated-stream retry, and each attempt was billed
- Non-streaming requests that carry their own `tools` now return a real OpenAI `tool_calls` array with `finish_reason: "tool_calls"` instead of the arguments serialized into `message.content` (#35, reported by @kdo-jl)
- Tools passed in `body.tools` are no longer deferred for tool search; the caller runs them itself (#35)
- Added a **Fast Mode Toggle** filter (`anthropic_pipe_fast_toggle.py`) for per-message fast requests, next to the admin valve. It is ignored on models without fast mode (#50, requested by @Willian-Zhang)

### `v0.9.27`
- Fixed a follow-up request failing with `tool use found without a corresponding tool_result block` after a turn with several Anthropic-hosted code-execution calls. The stored carriers interleave once server tools run in quick succession, and replaying them in document order separated a `server_tool_use` from its result. Results are now pulled forward so the pair stays adjacent (#40, by @JaWoDigiB)
- Fixed error notices and the File Content collapsible being swallowed into the preceding paragraph: code-execution / text-editor errors and safety refusals now go through the same own-line guarantee as every other rendered block (#46, by @Willian-Zhang)
- Fixed model display names being lost while the model list is served from cache — the cached entries were built without the stored display name, so the picker fell back to raw ids (`claude-opus-5` instead of `Claude Opus 5`) for the whole cache TTL (#47, reported by @clang13)
- Fixed an empty `SKILLS` valve triggering the code-execution notification: OpenWebUI stores an empty array valve as `""`, which round-trips back as `[""]`, and that is truthy. Blank entries are now dropped (#48, reported by @clang13)

### `v0.9.26`
- Added **human-in-the-loop tool approval** (OpenWebUI `0.11.1`). OpenWebUI enforces its gate inside its own tool loop, which a manifold never enters — so the setting silently did nothing here. Now, with approval set to `ask`, every client, built-in and Open Terminal tool call waits for an explicit allow/deny, and a denial goes back to the model as a normal tool result so the turn continues instead of erroring
- Fixed a client tool failing outright when the model sends an argument its schema does not declare (observed: `{"params": "{}"}` for a parameterless tool, streamed by the API itself). Undeclared keys are dropped before the call, matching what OpenWebUI does in its own tool loop
- `HIDE_BLOCKS` is now a **multiselect** instead of a comma-separated string; existing string values still load
- Fixed `HIDE_BLOCKS` never hiding code execution: the collapsible ignored the valve entirely, and the bash / text editor variants were not recognised as the same block
- Fixed `total_tokens` double-counting cache traffic — now `input + output`, matching OpenWebUI's own usage contract. Cache reads and writes stay in their own two fields
- Added `ask_user` (OpenWebUI `0.11.1`) to the tool-search exclude list

### `v0.9.25`
- The Anthropic API key (admin valve and per-user override) is stored **encrypted** — Fernet, key derived from `WEBUI_SECRET_KEY`. OpenWebUI's own valve encryption is opt-in (`ENABLE_VALVE_ENCRYPTION`, default off), so on a default install this is what keeps the key out of the database in plaintext. Where that flag is on, the pipe defers to OpenWebUI instead of encrypting twice. Existing plaintext keys keep working, no migration needed
- Debug logs start with the detected OpenWebUI version and no longer contain the API key in plaintext
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
- Added **Claude Opus 5** (`claude-opus-5`): 1M context, 128k output, thinking on by default, full effort ladder incl. `max`, fast mode (#45, by @AliD101v)
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
| `helpers/test_valve_encryption.py` | Self-check for API key encryption at rest (`python helpers/test_valve_encryption.py`) |
| `anthropic_pipe.py` | **Generated** single-file pipe (this is what you install) |
| `anthropic_pipe.min.py` | **Generated** minified pipe (also committed, written by the same build) |
| `anthropic_pipe_*_toggle.py`, `anthropic_manifold_companion_filter.py` | Standalone filters, edited directly |

Inside `src/anthropic_pipe/`, `request/` holds everything that converges on the request payload, `response/` has one module per Anthropic `content_block` family plus rendering helpers, `shared/` holds model discovery and OpenWebUI task handling, and `pipe_template.py` carries the pipe frontmatter (title, version, requirements) and the class skeleton.

### Build

```bash
# compiles src/ into anthropic_pipe.py and anthropic_pipe.min.py
python helpers/build_anthropic_pipe.py
```

Both artifacts are committed and both are offered as an install source, so the build writes them together — the minified one can never lag behind. It is also compile-checked before it is written.

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
