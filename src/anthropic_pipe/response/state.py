"""Request-local stream state for Anthropic content-block handlers.

The monolithic pipe used hundreds of loose local variables.  This module makes
handler ownership explicit, which is the key to debugging cache/replay drift:
when a block is not reproduced byte-exactly, the relevant state group points to
one handler instead of the full pipe method.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TextState:
    chunk: str = ""
    chunk_count: int = 0
    current_search_query: str = ""
    citation_counter: int = 0
    pending_citation_markers: list[int] = field(default_factory=list)

    def reset_for_iteration(self) -> None:
        """Drop per-turn text/citation state before the next tool-loop iteration."""
        self.chunk = ""
        self.chunk_count = 0
        self.current_search_query = ""
        self.citation_counter = 0
        self.pending_citation_markers = []

    def reset_for_retry(self) -> None:
        """Reset for a retried stream, discarding the partial response entirely."""
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
        """Drop partial reasoning from a truncated stream before retrying it."""
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
        """Clear dispatched-tool bookkeeping before the next tool-loop iteration."""
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
        """Close out a code-execution session once its result block has rendered."""
        self.in_code_execution = False
        self.is_web_filtering = False
        self.has_user_tools = False
        self.had_web_tools = False
        self.tool_calls_info = []
        self.stream_start_idx = -1

    def reset_for_retry(self) -> None:
        """Drop a truncated stream's server-tool state before retrying it."""
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
    """Every mutable per-request stream value, grouped by the handler that owns it.

    Reached via ``ctx.state``. There is no group for the tool loop itself: that state
    (retry counts, stop reason, usage totals) stays local to ``pipe()``, which is the
    only thing that reads it — handlers see one block at a time and have no business
    steering the loop.
    """

    text: TextState = field(default_factory=TextState)
    thinking: ThinkingState = field(default_factory=ThinkingState)
    compaction: CompactionState = field(default_factory=CompactionState)
    tool_use: ToolUseState = field(default_factory=ToolUseState)
    server_tool: ServerToolState = field(default_factory=ServerToolState)

    def reset_current_block(self) -> None:
        """Forget which block type is open; called after every content_block_stop."""
        self.tool_use.current_block_type = None
