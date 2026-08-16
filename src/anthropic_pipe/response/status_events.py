"""The status line: one entry per phase of work the turn actually goes through.

OpenWebUI keeps every status event it receives in `message.statusHistory` and
renders the list (Chat.svelte pushes unconditionally — there is no de-duplication
on the frontend). So every emission is a permanent visible line, and a status that
does not describe real work is noise the user has to scroll past.

The rule that follows: **a status is emitted by whatever is starting, never to
clear whatever finished.** A block that ends emits nothing; the next block
describes itself when it starts. This replaces an earlier pair of workarounds —
`response_started_once` (fired once per turn, so text resuming after a tool showed
nothing) and `resume_after_tool` (bolted on to compensate, writing a meaningless
"Responding..." after every single tool result).

`done=True` closes the line and stops its shimmer, so it belongs only on the final
status of a turn — never mid-stream.

Recognized status fields (open-webui `StatusHistory/StatusItem.svelte`):
`action`, `description`, `done`, `hidden`, `query`, `queries`, `urls`, `items`,
`count`. `action="web_search"` together with `urls` renders Anthropic's results as
OpenWebUI's native clickable source list instead of a plain line.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable


class StatusEmitter:
    def __init__(self, emit_event: Callable[[dict[str, Any]], Awaitable[None]]):
        """Wrap an OpenWebUI ``emit_event`` callback with dedup state for status events."""
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
        """Emit an OpenWebUI ``status`` event, skipping an identical repeat.

        Dedup is what keeps the phase model cheap: a block family can announce
        itself on every block without stuttering the history when several blocks
        of the same kind arrive in a row (web-search answers split prose into many
        text blocks around their citation markers).
        """
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
        """Before the first byte: the request is out, nothing has come back yet."""
        await self.emit("Waiting for response...", hidden=False, force=True)

    async def thinking(self) -> None:
        """A thinking block is streaming."""
        await self.emit("💭 Thinking...")

    async def responding(self) -> None:
        """A text block is streaming — the model is writing the answer.

        Emitted on every text block, not once per turn: after a tool runs, text
        resuming is a real phase change the user should see.
        """
        await self.emit("Responding...")

    async def searching_web(self, query: str = "") -> None:
        """A web_search server tool call is running."""
        await self.emit(f"🔍 Searching: {query}" if query else "🔍 Searching the web...")

    async def web_search_done(self, urls: list[str], query: str = "") -> None:
        """Report finished web search results using OpenWebUI's native renderer.

        With `action="web_search"` and `urls`, the frontend renders a clickable
        source list rather than a plain text line.
        """
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
        """A web_fetch server tool call is running."""
        await self.emit(f"🌐 Fetching {url}" if url else "🌐 Fetching URL...")

    async def running_code(self) -> None:
        """Anthropic-side code execution is running."""
        await self.emit("🐍 Running code...")

    async def running_command(self) -> None:
        """Anthropic-side bash execution is running."""
        await self.emit("💻 Running bash command...")

    async def editing_file(self) -> None:
        """Anthropic-side text editor tool is running."""
        await self.emit("📝 Editing file...")

    async def consulting_advisor(self) -> None:
        """The advisor tool is running."""
        await self.emit("🧑‍⚖️ Consulting advisor...")

    async def searching_tools(self, query: str = "") -> None:
        """The tool-search server tool is running."""
        await self.emit(f"🔍 Searching tools: {query}" if query else "🔍 Searching tools...")

    async def running_tool(self, tool_name: str) -> None:
        """An OpenWebUI-side tool call is being dispatched."""
        await self.emit(f"🔧 Running {tool_name}..." if tool_name else "🔧 Running tool...")

    async def compacting(self) -> None:
        """Server-side context compaction is running."""
        await self.emit("📦 Compacting conversation context...")

    async def activity(self, description: str) -> None:
        """Free-form in-progress phase, for one-off states without a named phase."""
        await self.emit(description, done=False)

    async def complete(self, description: str) -> None:
        """Close the status line for this turn. Only the final status is `done`."""
        await self.emit(description, done=True, force=True)

    async def notification(self, content: str, *, type: str = "warning") -> None:
        """Emit an OpenWebUI ``notification`` event (e.g. warning/error toast)."""
        await self._emit_event(
            {"type": "notification", "data": {"type": type, "content": content}}
        )
