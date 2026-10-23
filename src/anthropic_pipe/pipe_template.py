"""
title: Anthropic API Integration
id: anthropic_new
author: Podden (https://github.com/Podden/)
github: https://github.com/Podden/openwebui_anthropic_api_manifold_pipe
original_author: Balaxxe (Updated by nbellochi)
version: 0.10.0
license: MIT
requirements: pydantic>=2.0.0, anthropic~=2.0, pillow-heif>=0.18.0
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
- Tool Search (BM25/Regex)
- Native PDF Upload (visual PDF analysis with charts/images)
- Agent Skills (pptx, xlsx, docx, pdf and custom skills)
- Fast Mode for Opus 5.5 / 5 / 4.8
- Programmatic Tool Calling (tools callable from code execution)
- Server-side fallback on safety refusals

Changelog (older versions: CHANGELOG.md in the repository):
v0.10.0
- API version 2026-10-21 and anthropic SDK 2.x (requirement `anthropic~=2.0`; OpenWebUI upgrades it when it loads the pipe).
- temperature / top_p / top_k from model params are no longer sent. 2026-10-21 rejects them on every model, and with SDK 1.9+ they already failed with a TypeError on Haiku 4.5, Sonnet 4.5 and Opus 4.5.
- SDK 2.x authenticates with `Authorization: Bearer`. A custom ANTHROPIC_BASE_URL (proxy, gateway) also gets the key as `x-api-key` so gateways that read only that header keep working.
- Fast mode on Opus 5.5 is GA and goes out without the beta header; Opus 5 and Opus 4.8 keep it.
- /v1/models: `server_tools` gates the web search and code execution tools per model, `thinking.types` picks how a thinking-on-by-default model is switched off (disabled or between_tools).
- Web fetch switched off for the organization in the Claude Console: the turn retries once without the tool and shows a warning instead of failing with a 400.

v0.9.39
- Prompt cache kept across tool calls: the tool loop now sends a tool result in the same form the next turn replays it (JSON compacted, plain text unquoted). Before, every turn after a tool call lost the cache from the first tool result on.
- Prompt cache kept for tool calls with two or more arguments (e.g. tool search's query + limit): replay no longer re-sorts the model's `input` keys, which the API renders into the prompt (cache diagnostics: messages_changed).
- A server tool the model calls right after a client tool in the same response (e.g. bash after view_knowledge_file) stays in that assistant message on replay instead of moving into the next one.
- Tool search: the system hint now names the deferred tools (sorted, changes only with the tool set). Without the names the model answered "use the weather tool" with web search instead of searching for the deferred tool.
- Open Terminal plus code execution in one request: a system hint tells the model that only the terminal tools reach the user's terminal. Asked to run a command in the terminal, it used Anthropic's isolated code execution sandbox instead.
- CACHE-DIFF debug log no longer reports block key-order differences as breaks; the API ignores them (measured), only tool `input` order counts. The [PAYLOAD] log line lists deferred tools.

v0.9.38
- Estimated USD cost per turn (new SHOW_COST user valve, contributed by Willian-Zhang in #49): `cost_usd` plus a per-component `cost_breakdown_usd` in the message usage (message info tooltip, persisted for analytics) and appended to the SHOW_TOKEN_COUNT status line. Prices come from a built-in list-price table (verified 2026-10-13); admins patch it via the MODEL_PRICING_OVERRIDES valve (JSON, USD per MTok)
- The estimate follows the bill: cache writes split 5m/1h, fast mode, Haiku 5.5's prompt-length tier and US data residency priced per API call from the response usage, web searches at $10 per 1,000

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
    OverloadedError,
    UnprocessableEntityError,
)

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

PATTERN_EMPTY_CONTEXT = re.compile(r"<context>\s*</context>", flags=re.DOTALL)

# Pattern to find remaining source tags (for checking if all were removed)
PATTERN_SOURCE_TAGS = re.compile(r"<source[^>]*>.*?</source>", flags=re.DOTALL)

# RAG message detection: matches "### Task:...<context>...</context>" blocks
PATTERN_RAG_MESSAGE = re.compile(r"### Task:.*?<context>.*?</context>", re.DOTALL)

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

# Tools that must never carry `defer_loading`, split by who owns them.
#
# Anthropic server tools are executed inside the API and are addressed by
# `type`, not by a schema we send; deferring them is meaningless. The two
# tool_search tools are worse than meaningless -- deferring the tool that
# resolves deferred tools is circular. OpenWebUI's own builtins are listed so a
# default install never pays a tool_search round trip for them.
#
# Kept as a module constant so the UserValves default and the multiselect
# options below cannot drift apart.
ANTHROPIC_SERVER_TOOL_NAMES = [
    "web_search",
    "web_fetch",
    "code_execution",
    "bash_code_execution",
    "text_editor_code_execution",
    "tool_search_tool_regex",
    "tool_search_tool_bm25",
    "advisor",
    "mcp_toolset",
    "memory",
    "bash",
    "str_replace_based_edit_tool",
    "computer",
]

OPENWEBUI_BUILTIN_TOOL_NAMES = [
    "add_memory", "ask_user", "calculate_timestamp", "create_automation",
    "create_calendar_event", "create_tasks", "delegate_task",
    "delete_automation", "delete_calendar_event", "delete_memory",
    "edit_image", "execute_code", "fetch_url", "generate_image",
    "get_current_timestamp", "grep_chat_files", "grep_knowledge_files",
    "list_automations", "list_chat_files", "list_knowledge",
    "list_knowledge_bases", "list_memories", "list_memory_paths",
    "notify", "query_chat_files", "query_knowledge_bases",
    "query_knowledge_files", "read_memory_path", "replace_memory_content",
    "replace_note_content", "search_calendar_events",
    "search_channel_messages", "search_channels", "search_chats",
    "search_knowledge_bases", "search_knowledge_files", "search_memories",
    "search_notes", "search_web", "timer", "toggle_automation",
    "update_automation", "update_calendar_event", "update_memory",
    "update_task", "view_channel_message", "view_channel_thread",
    "view_chat", "view_file", "view_knowledge_file", "view_note",
    "view_skill", "read_skill_file", "create_skill", "update_skill_files",
    "write_note",
    # Open Terminal / kb tools
    "kb_exec",
    "display_file", "get_process_status", "glob_search", "grep_search",
    "kill_process", "list_files", "list_processes", "read_file",
    "replace_file_content", "run_command", "send_process_input",
    "write_file",
]

DEFAULT_TOOL_SEARCH_EXCLUDE_TOOLS = (
    ANTHROPIC_SERVER_TOOL_NAMES + OPENWEBUI_BUILTIN_TOOL_NAMES
)

# OpenWebUI >= 0.12 Tool Search (open_webui/utils/tool_search.py): its
# search tool and the `<available_tools>` manifest it appends to the system
# prompt. Replaced by Claude's native tool search, see request/tools.py.
OWUI_SEARCH_TOOL_NAME = "search_tools"
OWUI_TOOL_MANIFEST_RE = re.compile(r"\n?<available_tools>\n.*?</available_tools>", re.DOTALL)


def normalize_tool_name_list(value: Any) -> set[str]:
    """Flatten a tool-name valve into a set of bare names.

    Accepts what the valve actually contains rather than what its type says.
    OpenWebUI renders a `List[str]` without a multiselect hint as a single
    comma-joined text field, and versions of this pipe before 0.9.28 shipped the
    default as one multi-line blob string inside a one-element list -- so stored
    values in the wild are any of: a proper list, a comma-separated string, or a
    list holding one comma-separated string. Membership tests against the raw
    value silently fail on the last two, which is how every excluded tool ended
    up deferred anyway.
    """
    if value is None:
        return set()
    items = value if isinstance(value, (list, tuple, set)) else [value]
    return {
        name.strip()
        for item in items
        for name in str(item).split(",")
        if name.strip()
    }

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

from pydantic_core import core_schema

ENCRYPTED_VALVE_PREFIX = "encrypted:"

try:
    from open_webui.env import VERSION as OPENWEBUI_VERSION
except Exception:
    OPENWEBUI_VERSION = "unknown"


def _owui_version_below(target: tuple) -> bool:
    """True when the running OpenWebUI is older than `target`; False if unknown."""
    try:
        parts = tuple(int(p) for p in str(OPENWEBUI_VERSION).split("-")[0].split(".")[:3])
    except ValueError:
        return False
    return parts < target


# OpenWebUI < 0.10 defaults function_calling to the prompt-based mode, which
# bypasses the pipe's own tool loop. Since 0.10 an unset value means native.
try:
    from open_webui.models.models import Models, ModelForm

    MODELS_AVAILABLE = True
except ImportError:
    Models = None
    ModelForm = None
    MODELS_AVAILABLE = False

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

# BEGIN GENERATED SECTION: anthropic_pipe.shared.pricing
# END GENERATED SECTION: anthropic_pipe.shared.pricing






class Pipe:
    API_VERSION = "2026-10-21"  # also the default of anthropic SDK 2.x
    _DEFAULT_API_BASE = "https://api.anthropic.com"

    # Capability overrides for fields NOT available from the /v1/models API.
    # The API now provides: max_tokens, max_input_tokens, capabilities (thinking, effort, vision, etc.)
    # These overrides only contain flags that must be derived from model identity.
    # Static max-output-token fallbacks, used ONLY when the /v1/models API does not
    # report max_tokens (custom/Azure endpoints, ENABLED_MODELS manual ids). The
    # live API value always wins for direct Anthropic. Keyed by base (suffix-stripped) id.
    MODEL_MAX_TOKENS_FALLBACK = {
        "claude-opus-5-5": 128000,
        "claude-sonnet-5-5": 128000,
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
        "claude-fable-5-1": 128000,
        "claude-mythos-5-1": 128000,
        "claude-haiku-5-5": 128000,
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
        "claude-opus-5-5": 1000000,
        "claude-sonnet-5-5": 1000000,
        "claude-opus-5": 1000000,
        "claude-sonnet-5": 1000000,
        "claude-fable-5": 1000000,
        "claude-mythos-5": 1000000,
        "claude-fable-5-1": 1000000,
        "claude-mythos-5-1": 1000000,
        "claude-opus-4-8": 1000000,
        "claude-opus-4-7": 1000000,
        "claude-opus-4-6": 1000000,
        "claude-sonnet-4-6": 1000000,
        "claude-sonnet-4-5": 1000000,
        "claude-haiku-5-5": 1000000,
    }

    # Identity-keyed capability fixups, applied on top of whatever /v1/models
    # reports (and on top of the static defaults when it reports nothing).
    #
    # `supports_adaptive_thinking` is listed here even though the API does
    # advertise it: get_model_info's static fallback has to default it to False,
    # and endpoints that serve no capability metadata (Azure and other proxies,
    # or ids named manually via ENABLED_MODELS) never overwrite that. The pipe
    # then sends explicit `budget_tokens` thinking to a model that wants
    # `thinking:{"type":"adaptive"}` -- which the API rejects. Pinning it per identity makes those endpoints
    # behave like the direct one.
    MODEL_CAPABILITY_OVERRIDES = {
        # Fable 5.1 / Mythos 5.1 reject tool_choice "tool" and "any" with a 400
        # (auto/none unchanged). /v1/models does not report that, so it is
        # pinned by identity; Mythos mirrors Fable (see the parity note below).
        "claude-fable-5-1": {
            "supports_dynamic_filtering": True,
            "supports_compaction": True,
            "supports_adaptive_thinking": True,
            "supports_structured_outputs": True,
            "supports_forced_tool_choice": False,
        },
        "claude-mythos-5-1": {
            "supports_dynamic_filtering": True,
            "supports_compaction": True,
            "supports_adaptive_thinking": True,
            "supports_structured_outputs": True,
            "supports_forced_tool_choice": False,
        },
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
        # capability cache is still empty, and Haiku 4.5 is a selectable
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
        "claude-opus-5-5": {
            "supports_dynamic_filtering": True,
            "supports_fast_mode": True,
            "supports_compaction": True,
            "supports_thinking": True,
            "supports_adaptive_thinking": True,
            "supports_effort": True,
            "supports_effort_xhigh": True,
            "supports_effort_max": True,
            "supports_structured_outputs": True,
            # Adaptive thinking is always on: thinking:{"type":"disabled"} and
            # {"type":"enabled"} both 400. Effort is the only control.
            "thinking_always_on": True,
            # tool_choice "tool" / "any" 400 on this model; only auto / none.
            "supports_forced_tool_choice": False,
        },
        "claude-opus-5": {
            "supports_dynamic_filtering": True,
            "supports_fast_mode": True,
            # Fast mode still a research preview here (GA only on Opus 5.5).
            "fast_mode_beta": True,
            "supports_compaction": True,
            "supports_adaptive_thinking": True,
            "supports_structured_outputs": True,
            # Opus 5 runs with thinking ON unless thinking:{"type":"disabled"}
            # is sent explicitly. Disabling is rejected at effort xhigh/max.
            "thinking_on_by_default": True,
        },
        "claude-sonnet-5-5": {
            "supports_dynamic_filtering": True,
            "supports_compaction": True,
            "supports_thinking": True,
            "supports_adaptive_thinking": True,
            "supports_effort": True,
            "supports_effort_xhigh": True,
            "supports_effort_max": True,
            "supports_structured_outputs": True,
            "thinking_on_by_default": True,
            # thinking:{"type":"disabled"} 400s; the lowest setting is
            # between_tools (no up-front thinking, effort low..high only).
            "thinking_off_type": "between_tools",
            # tool_choice "tool" / "any" 400 on this model; only auto / none.
            "supports_forced_tool_choice": False,
        },
        "claude-sonnet-5": {
            "supports_dynamic_filtering": True,
            "supports_compaction": True,
            "supports_adaptive_thinking": True,
            "supports_structured_outputs": True,
            "thinking_on_by_default": True,
        },
        "claude-haiku-5-5": {
            "supports_dynamic_filtering": True,
            "supports_compaction": True,
            "supports_thinking": True,
            "supports_adaptive_thinking": True,
            "supports_effort": True,
            "supports_effort_xhigh": True,
            "supports_effort_max": True,
            "supports_structured_outputs": True,
            # Thinks unless thinking:{"type":"disabled"} is sent; disabling is
            # rejected at effort xhigh/max (same rule as Opus 5).
            "thinking_on_by_default": True,
            # No server-side fallback: "default" stays declined and a pinned
            # fallback model 400s.
            "supports_refusal_fallback": False,
        },
        "claude-opus-4-8": {
            "supports_dynamic_filtering": True,
            "supports_fast_mode": True,
            "fast_mode_beta": True,
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
    # Fingerprint of the connection settings the cached model list was fetched
    # with. A changed key, base URL, workspace or allow-list must invalidate the
    # cache immediately -- otherwise pointing the pipe at a different endpoint
    # keeps serving the previous endpoint's models until the TTL expires.
    _api_capabilities_cache_sig: str = ""

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
            description="Enable Fast Mode for Opus Models (Opus 5.5 / 5 / 4.8). Up to 2.5x faster output at higher costs",
        )
        REFUSAL_FALLBACK: Literal[
            "off",
            "default",
            "claude-opus-5-5",
            "claude-opus-5",
            "claude-opus-4-8",
            "claude-sonnet-5-5",
            "claude-sonnet-5",
            "claude-haiku-4-5",
        ] = Field(
            default="off",
            description=(
                "Retry server-side on another model when the safety classifier refuses a "
                "request, instead of returning the refusal. 'default' lets Anthropic pick the "
                "recommended model per refusal category; picking a model pins that one. "
                "Claude API only — ignored on Bedrock / Vertex / Foundry endpoints and "
                "for Haiku 5.5, which has no server-side fallback."
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
            "claude-haiku-5-5",
            "claude-sonnet-5",
            "claude-sonnet-5-5",
            "claude-opus-4-8",
            "claude-opus-5",
            "claude-opus-5-5",
            "same as chat model",
        ] = Field(
            default="claude-haiku-5-5",
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
            "standard multipliers (1.25x / 2x / 0.1x). Prompt-length pricing (Haiku 5.5): "
            "long_context_threshold plus long_input / long_output (long_cache_* optional), applied to every "
            "API call whose prompt exceeds the threshold. Example: "
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
        THINKING_DISPLAY: Literal["summarized", "omitted", "updates"] = Field(
            default="omitted",
            description="'summarized' returns summarized thinking, 'omitted' hides thinking in favor of faster time-to-first-text, 'updates' (beta) hides reasoning but shows the short progress updates Fable 5 / 5.1, Opus 5.5 and Sonnet 5.5 write before each tool call.",
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
            default=list(DEFAULT_TOOL_SEARCH_EXCLUDE_TOOLS),
            json_schema_extra={
                "input": {
                    "type": "multiselect",
                    "options": list(DEFAULT_TOOL_SEARCH_EXCLUDE_TOOLS),
                }
            },
            description="Excluded Tools are always loaded. Anthropic tools and OpenWebUI-native tools (builtin + Open Terminal) are excluded by default.",
        )
        # Advisor tool (advisor-tool-2026-03-01) — per-user
        ENABLE_ADVISOR_TOOL: bool = Field(
            default=False,
            description="Enable the Advisor tool. A faster executor model consults a stronger advisor model mid-generation for strategic guidance.",
        )
        ADVISOR_MODEL: Literal["claude-opus-4-7", "claude-opus-4-8", "claude-opus-5", "claude-opus-5-5", "claude-fable-5", "claude-mythos-5", "claude-fable-5-1", "claude-mythos-5-1"] = Field(
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
            description="Enable automatic context compaction. When input tokens exceed the trigger threshold, the API summarizes older conversation context to save tokens. If OpenWebUI's own Context Compaction (Admin > Interface) is enabled, it runs first and wins: the pipe detects its summary and does not compact a second time. Turn one of the two off; both at once is wasted work.",
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
