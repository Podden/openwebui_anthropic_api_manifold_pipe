# Anthropic API Manifold Pipe — agent notes

## Scope

This repo holds one OpenWebUI manifold pipe for the Anthropic Messages API plus its companion/toggle filters. Tasks usually touch model discovery, request payload assembly, the tool loop, content-block streaming, prompt caching, Files API / code execution / skills, or the toggle filters.

## Golden rule

`anthropic_pipe.py` and `anthropic_pipe.min.py` are **generated**. Edit `src/anthropic_pipe/**`, then rebuild. Hand-edits to the generated sections are lost on the next build.

## Build

| Need | Command (from repo root) |
|---|---|
| Compile the single-file artifact | `python helpers/build_anthropic_pipe.py` |
| Minify it for upload | `python helpers/minify_pipe.py anthropic_pipe.py -o anthropic_pipe.min.py --check` |
| Pull the current artifact back into the template | `python helpers/build_anthropic_pipe.py --refresh-template` |
| Check model-list caching and invalidation | `python helpers/test_model_cache.py` (fakes the Anthropic client, no network) |

`--refresh-template` overwrites `src/anthropic_pipe/pipe_template.py` with the current artifact minus its generated sections. Use it only when the template drifted, never as a normal step.

The build works by marker pairs (`# BEGIN/END GENERATED SECTION: anthropic_pipe.<section>`) inside the template. Marker **order in the template pins section order in the artifact** — a module must appear above any code that annotates against it, because the build strips `from __future__ import annotations`.

## File map

| Path | Role |
|---|---|
| `src/anthropic_pipe/pipe_template.py` | Template for the pipe module: docstring/frontmatter (title, version, requirements), `class Pipe`, valves, generated-section markers. Version bumps and changelog live here. |
| `src/anthropic_pipe/request/payload.py` | Payload assembly source of truth: messages, tools, betas, thinking, Files API, context management, cache-control inputs. Compiled into a module-level `create_request_payload()`. |
| `src/anthropic_pipe/request/{cache_control,messages,tools,files,rag}.py` | `Pipe` method groups for the request half of a turn. |
| `src/anthropic_pipe/response/*.py` | Response half: one module per Anthropic content-block family (`text_block`, `thinking_block`, `client_tool`, `server_tool`, `code_execution_results`, `web_tool_results`, `internal_tool_results`, `compaction_block`, `status_events`) plus `state`, `handlers`, `registry`, `runtime`, `formatting`. |
| `src/anthropic_pipe/shared/{models,tasks}.py` | Model discovery/capabilities and OpenWebUI task handling (title, tags, follow-ups, memory review). |
| `src/anthropic_pipe/pipe_orchestrator.py` | `Pipe.pipe()` request orchestration and the high-level tool loop. |
| `helpers/build_anthropic_pipe.py` | Compiles `src/` into `anthropic_pipe.py`. |
| `helpers/minify_pipe.py` | Strips comments/docstrings (keeps the module docstring OpenWebUI parses) for the upload artifact. |
| `anthropic_pipe.py` | Generated single-file OpenWebUI artifact (committed; this is what users install). |
| `anthropic_pipe.min.py` | Generated minified artifact (git-ignored). |
| `anthropic_manifold_companion_filter.py` | Routes OpenWebUI's built-in web_search / code_interpreter buttons to Anthropic-native tools. |
| `anthropic_pipe_{thinking,web_search,code_execution,files}_toggle.py` | One-shot toggle filters. |
| `README.md` | User-facing docs: install, valves, changelog. Keep the changelog in sync with the template docstring. |

Two module lists in `helpers/build_anthropic_pipe.py` are load-bearing:

- `STREAM_SOURCES` — module-level sections, compiled in list order.
- `METHOD_GROUP_SOURCES` — spliced into one `class Pipe` body. A duplicate method name in a later module **silently overrides** the earlier one.

## Architecture anchors

| Concern | Start with |
|---|---|
| Model list and capabilities | `shared/models.py` → `_parse_api_capabilities`, `get_model_info`, `get_anthropic_models`, `pipes` |
| Payload assembly | `request/payload.py` → `create_request_payload`, then `request/messages.py`, `request/tools.py` |
| File handling | `request/files.py` → `_get_pdf_base64_from_file_id`, `_process_files_api_data`, `_generate_file_download_link` |
| RAG cleanup | `request/rag.py` → `_extract_rag_from_system_message`, `_remove_rag_*` |
| Prompt caching | `request/cache_control.py` (breakpoint placement, TTL, cache diagnostics) |
| Main execution loop | `pipe_orchestrator.py` → `pipe`, `_process_tool_calls`, `_process_tool_results`, `_run_tool_callable` |
| Content-block streaming | `response/` — handlers are grouped by content type, not by Anthropic event type; `registry.py` wires them up |
| Skills / tasks | `shared/tasks.py`, `request/files.py` → `_validate_and_get_skills` |
| Formatting and persistence | `response/formatting.py`, `response/runtime.py` → `_format_thinking_block`, `_format_tool_result_block`, `_format_code_execution_block`, `_create_metadata_marker` |

## Invariants to preserve

- OpenWebUI persists the last emitted `chat:message`; full-message replacement matters more than the return value once streaming has started.
- Streamed text must have exactly one source of truth; duplicate bookkeeping causes doubled output.
- File flow priority is `Files API > native PDF upload > RAG fallback`.
- Metadata markers must accumulate forward — only the last assistant message survives into the next request.
- Cache breakpoints must stay stable across turns: anything appended per-request (memory, RAG, tool order) above a breakpoint invalidates the whole prefix. Tools are appended name-sorted for exactly this reason.
- Be careful with cache control around thinking blocks and programmatic tool-calling flows.
- Do not send empty location values for Anthropic web-search configuration.
- The model-list cache is class-level and must stay fingerprinted against the connection settings (`_model_cache_signature`). Adding a valve that changes which models an endpoint returns means adding it to that signature.
- Task requests and sub-agent runs must return plain prose: no collapsibles, no replay carriers, no token footer, no metadata markers.

## Common failure patterns

| Symptom | First checks |
|---|---|
| Doubled text | text accumulation and message rebuild logic |
| Lost code-exec state | container marker persistence and resend |
| Tool loop stalls or repeats | assistant block conversion, tool results |
| Anthropic 400 errors | payload shape; sampling params on adaptive-thinking models; beta headers |
| Files disappear on later turns | metadata markers, dedupe logic, file-id restoration |
| Cache hit rate collapses | breakpoint placement, tool ordering, per-request appendices (`ENABLE_CACHE_DIAGNOSTICS`) |
| Web search rejects request | empty or invalid location fields |
| Skills do not activate | `SKILLS` valve, skill validation, Files API / code-execution prerequisites |

## Release checklist

1. Change `src/anthropic_pipe/**`.
2. Bump `version:` and add a changelog entry in `src/anthropic_pipe/pipe_template.py`.
3. `python helpers/build_anthropic_pipe.py`
4. `python helpers/minify_pipe.py anthropic_pipe.py -o anthropic_pipe.min.py --check`
5. Mirror the changelog entry into `README.md` and update the "Current pipe version" line.
6. Commit `src/` **and** the regenerated `anthropic_pipe.py`.
