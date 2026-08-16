"""Build the deployable single-file Anthropic pipe from maintainable sources.

OpenWebUI can upload only one pipe file.  The maintainable source lives under
``src/anthropic_pipe`` and this script injects the compiled sections into
``anthropic_pipe.py`` at the repository root.

Run with ``--extract-payload`` once to bootstrap ``request_payload.py`` from the
current monolith; subsequent runs keep the compiled single-file artifact in sync
with the payload and stream handler modules.
"""
from __future__ import annotations

import argparse
import re
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PIPE_DIR = REPO_ROOT
PIPE_FILE = PIPE_DIR / "anthropic_pipe.py"
SRC_DIR = PIPE_DIR / "src" / "anthropic_pipe"
TEMPLATE_SOURCE = SRC_DIR / "pipe_template.py"
PAYLOAD_SOURCE = SRC_DIR / "request" / "payload.py"

# Source tree mirrors the two halves of a turn: `request/` is everything that
# converges on create_request_payload, `response/` is one module per Anthropic
# content_block family plus the shared rendering helpers, `shared/` is what both
# sides need.
#
# Module-level modules compiled into the artifact, in the order their generated
# sections appear. `state` carries a marker placed *above* PipeRequestContext in
# the template, because that dataclass annotates `state: StreamState` and
# annotations are evaluated eagerly (the build strips `from __future__ import
# annotations`). Everything else lands after the payload section. Order matters:
# a name must be defined before it is annotated against.
STREAM_SOURCES = [
    ("response.state", SRC_DIR / "response" / "state.py"),
    ("response.handlers", SRC_DIR / "response" / "handlers.py"),
    ("response.registry", SRC_DIR / "response" / "registry.py"),
    ("response.status_events", SRC_DIR / "response" / "status_events.py"),
    ("response.text_block", SRC_DIR / "response" / "text_block.py"),
    ("response.thinking_block", SRC_DIR / "response" / "thinking_block.py"),
    ("response.compaction_block", SRC_DIR / "response" / "compaction_block.py"),
    ("response.client_tool", SRC_DIR / "response" / "client_tool.py"),
    ("response.server_tool", SRC_DIR / "response" / "server_tool.py"),
    ("response.code_execution_results", SRC_DIR / "response" / "code_execution_results.py"),
    ("response.web_tool_results", SRC_DIR / "response" / "web_tool_results.py"),
    ("response.internal_tool_results", SRC_DIR / "response" / "internal_tool_results.py"),
]


def _markers(section: str) -> tuple[str, str]:
    """Begin/end marker pair delimiting one generated section in the artifact."""
    return (
        f"# BEGIN GENERATED SECTION: anthropic_pipe.{section}",
        f"# END GENERATED SECTION: anthropic_pipe.{section}",
    )


# Mixin method groups spliced into `class Pipe`, in this order. Order is
# load-bearing: they share one class body, so a duplicate method name in a later
# module silently overrides the earlier one (this is exactly how a duplicated
# _format_code_execution_block once shadowed the real renderer).
METHOD_GROUP_SOURCES = [
    SRC_DIR / "request" / "cache_control.py",
    SRC_DIR / "request" / "messages.py",
    SRC_DIR / "request" / "tools.py",
    SRC_DIR / "request" / "files.py",
    SRC_DIR / "request" / "rag.py",
    SRC_DIR / "response" / "formatting.py",
    SRC_DIR / "shared" / "models.py",
    SRC_DIR / "shared" / "tasks.py",
    SRC_DIR / "response" / "runtime.py",
    SRC_DIR / "pipe_orchestrator.py",
]

BEGIN_PAYLOAD, END_PAYLOAD = _markers("request_payload")
METHOD_GROUP_INSERT_MARKER = "    # COMPILED PIPE METHOD GROUPS INSERTION POINT"
BEGIN_METHOD_GROUPS = "    # BEGIN GENERATED SECTION: anthropic_pipe.pipe_method_groups"
END_METHOD_GROUPS = "    # END GENERATED SECTION: anthropic_pipe.pipe_method_groups"

METHOD_START_RE = re.compile(r"^    async def _create_payload\(", re.M)
NEXT_METHOD_RE = re.compile(r"^    def _convert_messages_to_claude_format\(", re.M)
ANY_PIPE_METHOD_RE = re.compile(r"^    (?:async\s+)?def \w+\(", re.M)
CLASS_RE = re.compile(r"^class Pipe:\s*$", re.M)


def _find_span(pattern: re.Pattern[str], text: str, label: str) -> re.Match[str]:
    match = pattern.search(text)
    if not match:
        raise RuntimeError(f"Could not find {label} in {PIPE_FILE}")
    return match


def _extract_payload_method(text: str) -> str:
    start = _find_span(METHOD_START_RE, text, "_create_payload start").start()
    end = _find_span(NEXT_METHOD_RE, text, "_convert_messages_to_claude_format start").start()
    return text[start:end].rstrip() + "\n"


def _method_to_module(method_source: str) -> str:
    lines = method_source.splitlines()
    if not lines or not lines[0].startswith("    async def _create_payload("):
        raise RuntimeError("Unexpected _create_payload method shape")

    converted: list[str] = [
        '"""Request payload creation for the Anthropic OpenWebUI pipe.\n',
        'This module is compiled into ``anthropic_pipe.py`` for OpenWebUI upload.\n',
        'Keep request-shaping logic here so cache/debug work does not require\n',
        'reading the full streaming pipe.\n',
        '"""\n',
        "\n",
        "from __future__ import annotations\n",
        "\n",
        "import json\n",
        "import logging\n",
        "from typing import Any, Awaitable, Callable, Dict, List, Optional\n",
        "from urllib.parse import unquote\n",
        "\n",
        "logger = logging.getLogger(__name__)\n",
        "\n",
    ]

    for idx, line in enumerate(lines):
        if idx == 0:
            converted.append("async def create_request_payload(\n")
            converted.append("    pipe,\n")
            continue
        if line == "        self,":
            continue
        if line.startswith("    "):
            line = line[4:]
        converted.append(line.replace("self.", "pipe.") + "\n")

    return "".join(converted).rstrip() + "\n"


def _source_to_compiled(source: str, begin_marker: str, end_marker: str) -> str:
    lines = source.splitlines()
    keep: list[str] = []
    skip_prefixes = (
        "from __future__ import",
        "import ",
        "from typing import",
        "from urllib.parse import",
        "logger = logging.getLogger(__name__)",
    )
    in_docstring = False
    for line in lines:
        stripped = line.strip()
        if in_docstring:
            if stripped.endswith('"""'):
                in_docstring = False
            continue
        if stripped.startswith('"""'):
            in_docstring = not (stripped.endswith('"""') and len(stripped) > 3)
            continue
        if stripped.startswith(skip_prefixes):
            continue
        keep.append(line)
    body = "\n".join(keep).strip() + "\n"
    return f"{begin_marker}\n{body}{end_marker}\n\n"


GENERATED_SECTION_RE = re.compile(
    r"\n?[ \t]*# BEGIN GENERATED SECTION: anthropic_pipe\.(?P<section>[\w.]+)\n"
    r".*?[ \t]*# END GENERATED SECTION: anthropic_pipe\.(?P=section)\n*",
    re.S,
)


def _strip_generated_sections(text: str) -> str:
    """Empty every generated section but keep its marker pair.

    The surviving markers are what pin section ORDER to the template: sections
    are filled in place, so a module can be placed above the code that annotates
    against it. Dropping the markers entirely would send every section to the
    same auto-insert point after the payload, in reverse insertion order.
    """
    def _empty(match: re.Match[str]) -> str:
        section = match.group("section")
        begin, end = _markers(section)
        return f"\n{begin}\n{end}\n"

    return GENERATED_SECTION_RE.sub(_empty, text)


def _method_group_source_to_class_body(source: str) -> str:
    lines = source.splitlines()
    class_line = next(
        (idx for idx, line in enumerate(lines) if line.startswith("class ") and line.rstrip().endswith(":")),
        None,
    )
    if class_line is None:
        raise RuntimeError("Method group source does not contain a class")
    body_lines = lines[class_line + 1:]
    while body_lines and not body_lines[0].strip():
        body_lines.pop(0)
    return "\n".join(body_lines).rstrip() + "\n\n"


def _compile_method_groups() -> str:
    parts = [BEGIN_METHOD_GROUPS + "\n"]
    for source_path in METHOD_GROUP_SOURCES:
        if not source_path.exists():
            raise RuntimeError(f"Missing method group source module: {source_path}")
        parts.append(_method_group_source_to_class_body(source_path.read_text(encoding="utf-8")))
    parts.append(END_METHOD_GROUPS + "\n")
    return "".join(parts)


def _insert_method_groups(text: str) -> str:
    compiled = _compile_method_groups()
    if BEGIN_METHOD_GROUPS in text and END_METHOD_GROUPS in text:
        start = text.index(BEGIN_METHOD_GROUPS)
        end = text.index(END_METHOD_GROUPS, start) + len(END_METHOD_GROUPS)
        while end < len(text) and text[end] in "\r\n":
            end += 1
        return text[:start] + compiled + text[end:]
    marker_pos = text.find(METHOD_GROUP_INSERT_MARKER)
    if marker_pos == -1:
        class_match = _find_span(CLASS_RE, text, "Pipe class")
        marker_pos = text.find("\n", class_match.end()) + 1
        return text[:marker_pos] + METHOD_GROUP_INSERT_MARKER + "\n" + compiled + text[marker_pos:]
    insert_pos = text.find("\n", marker_pos)
    if insert_pos == -1:
        insert_pos = marker_pos + len(METHOD_GROUP_INSERT_MARKER)
    else:
        insert_pos += 1
    return text[:insert_pos] + compiled + text[insert_pos:]


def _delegate_method() -> str:
    return """    async def _create_payload(
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
"""


def _replace_or_insert_generated_section(text: str, compiled: str) -> str:
    if BEGIN_PAYLOAD in text and END_PAYLOAD in text:
        start = text.index(BEGIN_PAYLOAD)
        end = text.index(END_PAYLOAD, start) + len(END_PAYLOAD)
        while end < len(text) and text[end] in "\r\n":
            end += 1
        return text[:start] + compiled + text[end:]

    class_match = _find_span(CLASS_RE, text, "Pipe class")
    return text[: class_match.start()] + compiled + text[class_match.start() :]


def _replace_or_insert_section(text: str, compiled: str, begin_marker: str, end_marker: str) -> str:
    if begin_marker in text and end_marker in text:
        start = text.index(begin_marker)
        end = text.index(end_marker, start) + len(end_marker)
        while end < len(text) and text[end] in "\r\n":
            end += 1
        return text[:start] + compiled + text[end:]

    insert_after = END_PAYLOAD if END_PAYLOAD in text else None
    if insert_after:
        pos = text.index(insert_after) + len(insert_after)
        while pos < len(text) and text[pos] in "\r\n":
            pos += 1
        return text[:pos] + "\n\n" + compiled + text[pos:]

    class_match = _find_span(CLASS_RE, text, "Pipe class")
    return text[: class_match.start()] + compiled + text[class_match.start() :]


def _replace_payload_method_with_delegate(text: str) -> str:
    start_match = _find_span(METHOD_START_RE, text, "_create_payload start")
    start = start_match.start()
    if "return await create_request_payload(" in text[start : start + 800]:
        return text
    end_match = ANY_PIPE_METHOD_RE.search(text, start + len(start_match.group(0)))
    if not end_match:
        class_match = _find_span(CLASS_RE, text, "Pipe class")
        next_top_level = re.search(r"^\S", text[start:], re.M)
        end = start + next_top_level.start() if next_top_level else len(text)
    else:
        end = end_match.start()
    current = text[start:end]
    if "return await create_request_payload(" in current:
        return text
    return text[:start] + _delegate_method() + "\n" + text[end:]


def extract_payload() -> None:
    text = PIPE_FILE.read_text(encoding="utf-8")
    method = _extract_payload_method(text)
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    PAYLOAD_SOURCE.write_text(_method_to_module(method), encoding="utf-8")
    print(f"extracted {PAYLOAD_SOURCE.relative_to(REPO_ROOT)}")


def build() -> None:
    input_file = TEMPLATE_SOURCE if TEMPLATE_SOURCE.exists() else PIPE_FILE
    if not input_file.exists():
        raise RuntimeError(
            f"Missing pipe template: {TEMPLATE_SOURCE}. Restore {PIPE_FILE} or run --refresh-template first."
        )
    if not PAYLOAD_SOURCE.exists():
        raise RuntimeError(f"Missing source module: {PAYLOAD_SOURCE}")
    for _section, source_path in STREAM_SOURCES:
        if not source_path.exists():
            raise RuntimeError(f"Missing source module: {source_path}")
    for method_group in METHOD_GROUP_SOURCES:
        if not method_group.exists() and TEMPLATE_SOURCE.exists():
            raise RuntimeError(f"Missing method group source module: {method_group}")
    text = input_file.read_text(encoding="utf-8")
    if input_file == TEMPLATE_SOURCE:
        text = _strip_generated_sections(text)
    compiled = _source_to_compiled(
        PAYLOAD_SOURCE.read_text(encoding="utf-8"), BEGIN_PAYLOAD, END_PAYLOAD
    )
    text = _replace_or_insert_generated_section(text, compiled)
    for section, source_path in STREAM_SOURCES:
        begin, end = _markers(section)
        text = _replace_or_insert_section(
            text,
            _source_to_compiled(source_path.read_text(encoding="utf-8"), begin, end),
            begin,
            end,
        )
    if all(path.exists() for path in METHOD_GROUP_SOURCES):
        text = _insert_method_groups(text)
    text = _replace_payload_method_with_delegate(text)
    PIPE_FILE.write_text(text, encoding="utf-8", newline="\n")
    print(f"built {PIPE_FILE.relative_to(REPO_ROOT)}")


def refresh_template() -> None:
    if not PIPE_FILE.exists():
        raise RuntimeError(f"Cannot refresh template because {PIPE_FILE} is missing")
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    template_text = _strip_generated_sections(PIPE_FILE.read_text(encoding="utf-8"))
    TEMPLATE_SOURCE.write_text(template_text, encoding="utf-8", newline="\n")
    print(f"refreshed {TEMPLATE_SOURCE.relative_to(REPO_ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extract-payload", action="store_true", help="bootstrap request_payload.py from current monolith")
    parser.add_argument("--refresh-template", action="store_true", help="copy current anthropic_pipe.py into src/anthropic_pipe/pipe_template.py")
    args = parser.parse_args()
    if args.extract_payload:
        extract_payload()
    if args.refresh_template:
        refresh_template()
    build()


if __name__ == "__main__":
    main()
