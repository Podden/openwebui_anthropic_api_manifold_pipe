"""OpenWebUI output items: stream a turn as items, read them back (OpenWebUI >= 0.12.2).

The pipe streams a turn as Responses-API style events instead of HTML in
``content``. OpenWebUI keeps them as structured ``output`` items, renders
thinking and tool calls natively, writes the database once at the end and
serves reloads and reconnects from its own snapshot. On the next turn it
replays them as OpenAI messages:

- reasoning item       -> ``reasoning_details`` of the assistant message
- message item         -> assistant ``content`` (parts joined with "", items with "\\n")
- function_call        -> ``tool_calls`` entry. ``provider_function`` replaces its
                          name/arguments in the replay, so it carries the exact
                          Anthropic blocks under ``__anthropic__``.
- function_call_output -> ``tool`` message. It also ends the assistant message,
                          so a turn comes back as one assistant message per tool round.

``rebuild_run`` turns such a run back into Anthropic messages. The tool loop
inside a turn builds its next request the same way (``owui_messages`` mirrors
OpenWebUI's replay), so what goes to the API mid-turn and on the next turn is
the same bytes: the prompt cache cannot drift between the two.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

ANTHROPIC_KEY = "__anthropic__"
DETAIL_TYPE = "anthropic.block"
DETAIL_FORMAT = "anthropic-messages-v1"
REASONING_BLOCKS = ("thinking", "redacted_thinking")
CALL_BLOCKS = ("tool_use", "server_tool_use", "mcp_tool_use")
SUMMARY_LIMIT = 8000
_DATA_IMAGE = re.compile(r"data:image/[a-z]+;base64,[A-Za-z0-9+/]+=*")


def _new_id(prefix: str) -> str:
    """Item id; only has to be unique within one chat."""
    return f"{prefix}_{os.urandom(8).hex()}"


def _clone(value: Any) -> Any:
    """Deep copy through JSON: events are serialized later, items keep changing."""
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def result_summary(block: dict) -> str:
    """Readable output of a server tool result. The exact block rides in provider_function."""
    btype = block.get("type", "")
    content = block.get("content")
    if isinstance(content, dict) and str(content.get("type", "")).endswith("_error"):
        return f"Error: {content.get('error_code', 'unknown')}"
    if btype == "web_search_tool_result" and isinstance(content, list):
        lines = [f"- {r.get('title') or r.get('url')} ({r.get('url')})" for r in content if isinstance(r, dict)]
        return "\n".join(lines) or "No results"
    if btype == "web_fetch_tool_result" and isinstance(content, dict):
        doc = content.get("content")
        title = doc.get("title") if isinstance(doc, dict) else None
        return f"{title or 'Fetched'}: {content.get('url', '')}"
    if isinstance(content, dict) and ("stdout" in content or "stderr" in content):
        text = "\n".join(p for p in (content.get("stdout"), content.get("stderr")) if p)
        return (text or f"(no output, exit code {content.get('return_code')})")[:SUMMARY_LIMIT]
    if btype == "tool_search_tool_result" and isinstance(content, dict):
        names = [r.get("tool_name", "") for r in content.get("tool_references") or [] if isinstance(r, dict)]
        return ", ".join(names) or "No tools found"
    if isinstance(content, str):
        return content[:SUMMARY_LIMIT]
    if isinstance(content, list):
        texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
        if texts:
            return "\n".join(texts)[:SUMMARY_LIMIT]
    if content is None:
        return ""
    return json.dumps(content, ensure_ascii=False, default=str)[:SUMMARY_LIMIT]


def display_text(text: str) -> str:
    """Tool output for the UI: inline base64 images would only be noise there."""
    return _DATA_IMAGE.sub("[image]", text or "")


class _StoredBlock:
    """content_block_start/stop stand-in for a block that comes from storage, not a stream."""

    def __init__(self, block: dict) -> None:
        self.index = "stored"
        self.content_block = self
        self.type, self.id, self.name = block.get("type"), block.get("id"), block.get("name")


class ItemStream:
    """The output items of one pipe() call, streamed to OpenWebUI as they form.

    ``items`` mirrors OpenWebUI's ``output`` list index for index: ``done``
    events address items by position. Every event is queued as a deep copy,
    because the item it describes keeps changing until it is done.
    """

    def __init__(self) -> None:
        """Start with no items; the consumer drains ``queue``."""
        self.queue: asyncio.Queue = asyncio.Queue()
        self.items: list[dict] = []
        self._blocks: dict[Any, tuple] = {}
        self._message: Optional[int] = None
        self._calls: dict[str, dict] = {}
        self._client_called = False
        self._response = 0
        self._client_responses: set = set()
        self._attempt: tuple = (0, {}, {})
        self.usage: dict = {}

    # -- events ------------------------------------------------------------
    def _emit(self, event: dict) -> None:
        self.queue.put_nowait(_clone(event))

    def _add(self, item: dict) -> int:
        idx = len(self.items)
        self.items.append(item)
        self._emit({"type": "response.output_item.added", "output_index": idx, "item": item})
        return idx

    def _done(self, idx: int) -> None:
        self._emit({"type": "response.output_item.done", "output_index": idx, "item": self.items[idx]})

    def _close_message(self) -> None:
        if self._message is None:
            return
        self.items[self._message]["status"] = "completed"
        self._done(self._message)
        self._message = None

    def _open_message(self) -> int:
        if self._message is None:
            self._message = self._add(
                {"id": _new_id("msg"), "type": "message", "role": "assistant", "status": "in_progress", "content": []}
            )
        return self._message

    # -- stream projection ---------------------------------------------------
    def begin_response(self) -> None:
        """A new API response starts: a client call from the previous one no longer counts."""
        self._close_message()
        self._client_called = False
        self._response += 1
        self._blocks.clear()
        # What rollback() restores if this attempt fails and is retried.
        self._attempt = (
            len(self.items),
            {cid: dict(call) for cid, call in self._calls.items()},
            {call["idx"]: _clone(self.items[call["idx"]]) for call in self._calls.values()},
        )

    def rollback(self) -> None:
        """The current API attempt failed and is retried: undo what it streamed.

        OpenWebUI has no event that removes an item, but ``output_item.done``
        replaces one in place: the attempt's items become empty messages, which
        neither render nor replay, and calls it completed are reopened.
        """
        mark, calls, before = self._attempt
        for idx in range(mark, len(self.items)):
            self.items[idx] = {"id": self.items[idx].get("id") or _new_id("msg"), "type": "message",
                               "role": "assistant", "status": "completed", "content": []}
            self._done(idx)
        for idx, item in before.items():
            if self.items[idx] != item:
                self.items[idx] = item
                self._done(idx)
        self._calls = calls
        self._message = None
        self._blocks.clear()
        self._client_called = False

    def end_response(self) -> None:
        """The API response is complete; its trailing text item is done."""
        self._close_message()

    def on_start(self, event: Any) -> None:
        """content_block_start: open the item the block belongs to."""
        block = getattr(event, "content_block", None)
        index = getattr(event, "index", None)
        btype = getattr(block, "type", "") or ""
        if btype in REASONING_BLOCKS:
            self._close_message()
            idx = self._add({"id": _new_id("rs"), "type": "reasoning", "status": "in_progress",
                             "content": [], "summary": []})
            self._blocks[index] = ("reasoning", idx, time.time())
        elif btype == "text":
            idx = self._open_message()
            parts = self.items[idx]["content"]
            parts.append({"type": "output_text", "text": "", "annotations": []})
            self._blocks[index] = ("text", idx, len(parts) - 1)
        elif btype in CALL_BLOCKS:
            self._close_message()
            call_id = getattr(block, "id", "") or _new_id("call")
            name = getattr(block, "name", "") or btype
            idx = self._add({"id": _new_id("fc"), "type": "function_call", "call_id": call_id, "name": name,
                             "arguments": "", "status": "in_progress"})
            client = btype == "tool_use"
            # A server tool the model calls after a client tool in the same
            # response runs only after the client round trip: its result opens
            # the next assistant message (see rebuild_run).
            self._calls[call_id] = {"idx": idx, "client": client, "response": self._response,
                                    "after_client": not client and self._client_called}
            self._client_called = self._client_called or client
            if client:
                self._client_responses.add(self._response)
            self._blocks[index] = ("call", idx, call_id)
        else:
            self._close_message()
            self._blocks[index] = ("other", None, btype)

    def on_delta(self, event: Any) -> None:
        """content_block_delta: stream thinking, text and tool input as they arrive."""
        entry = self._blocks.get(getattr(event, "index", None))
        delta = getattr(event, "delta", None)
        if entry is None or delta is None:
            return
        kind, idx = entry[0], entry[1]
        dtype = getattr(delta, "type", "")
        if kind == "reasoning" and dtype == "thinking_delta":
            text = getattr(delta, "thinking", "") or ""
            parts = self.items[idx]["content"]
            if not parts:
                parts.append({"type": "reasoning_text", "text": ""})
            parts[0]["text"] += text
            self._emit({"type": "response.reasoning_text.delta", "item_id": self.items[idx]["id"],
                        "output_index": idx, "content_index": 0, "delta": text})
        elif kind == "text" and dtype == "text_delta":
            text = getattr(delta, "text", "") or ""
            self.items[idx]["content"][entry[2]]["text"] += text
            self._emit({"type": "response.output_text.delta", "item_id": self.items[idx]["id"],
                        "output_index": idx, "content_index": entry[2], "delta": text})
        elif kind == "call" and dtype == "input_json_delta":
            text = getattr(delta, "partial_json", "") or ""
            self.items[idx]["arguments"] += text
            self._emit({"type": "response.function_call_arguments.delta", "item_id": self.items[idx]["id"],
                        "output_index": idx, "delta": text})

    def on_stop(self, event: Any, api_block: Optional[dict]) -> None:
        """content_block_stop: finish the item from the exact block the API will see again."""
        entry = self._blocks.pop(getattr(event, "index", None), None)
        if entry is None:
            return
        kind = entry[0]
        if kind == "reasoning":
            item = self.items[entry[1]]
            text = (api_block or {}).get("thinking", "") or ""
            item.update(
                status="completed",
                duration=max(1, round(time.time() - entry[2])),
                content=[{"type": "reasoning_text", "text": text}] if text else [],
                reasoning_details=[{"type": DETAIL_TYPE, "format": DETAIL_FORMAT, "block": api_block}] if api_block else [],
            )
            self._done(entry[1])
        elif kind == "text":
            # The finished block is authoritative; deltas only showed it growing.
            if api_block is not None:
                self.items[entry[1]]["content"][entry[2]]["text"] = api_block.get("text", "")
        elif kind == "call":
            call = self._calls.get(entry[2])
            if call is None:
                return
            call["use"] = api_block
            item = self.items[entry[1]]
            if api_block is not None:
                item["arguments"] = json.dumps(api_block.get("input", {}), ensure_ascii=False)
                # The tool loop's next request needs the exact call before its result exists.
                payload = {"v": 1, "use": api_block, **({"after_client": True} if call["after_client"] else {})}
                item["provider_function"] = {"name": item["name"], "arguments": {ANTHROPIC_KEY: payload}}
            self._done(entry[1])  # still in_progress: waits for its result
        elif kind == "other" and api_block is not None:
            use_id = api_block.get("tool_use_id")
            if use_id and use_id in self._calls:
                self._finish_call(use_id, api_block, result_summary(api_block))
            else:
                self._inline(api_block)

    def add_block(self, block: dict) -> None:
        """A finished block from storage (legacy chat migration): start and stop it at once."""
        event = _StoredBlock(block)
        self.on_start(event)
        self.on_stop(event, block)

    # -- tool results ------------------------------------------------------
    def tool_result(self, call_id: str, result_block: dict, text: str) -> None:
        """A client tool ran: complete its call and show what it returned."""
        if call_id in self._calls:
            self._finish_call(call_id, result_block, display_text(text))

    def _finish_call(self, call_id: str, result: Optional[dict], text: str, status: str = "completed") -> None:
        call = self._calls.pop(call_id)
        item = self.items[call["idx"]]
        # A server call made before a client call in the same response can get
        # its result only in the next response, after the client round: that
        # result opens the next assistant message as well.
        if (result is not None and not call["client"] and call["response"] != self._response
                and call["response"] in self._client_responses):
            call["after_client"] = True
        payload: dict = {"v": 1}
        if result is not None:
            result = dict(result)
            # The tool message carries the text already; store it once.
            if result.get("content") == text and isinstance(text, str):
                result.pop("content")
            payload["use"] = call.get("use")
            payload["result"] = result
        elif call["client"]:
            payload["use"] = call.get("use")
        # A server call that never got its result is left out of the replay:
        # the API rejects a server_tool_use without one.
        if call.get("after_client"):
            payload["after_client"] = True
        item["status"] = status
        item["provider_function"] = {"name": item["name"], "arguments": {ANTHROPIC_KEY: payload}}
        self._done(call["idx"])
        out = self._add({"id": _new_id("fco"), "type": "function_call_output", "call_id": call_id,
                         "status": "completed", "output": [{"type": "input_text", "text": text}]})
        self._done(out)

    def _inline(self, block: dict) -> None:
        """A block that is neither text, thinking nor a call (compaction, container upload)."""
        name = block.get("type", "block")
        label = "Context compacted" if name == "compaction" else name
        call_id = _new_id("inl")
        idx = self._add({"id": _new_id("fc"), "type": "function_call", "call_id": call_id, "name": name,
                         "arguments": "{}", "status": "completed",
                         "provider_function": {"name": name, "arguments": {ANTHROPIC_KEY: {"v": 1, "use": block}}}})
        self._done(idx)
        out = self._add({"id": _new_id("fco"), "type": "function_call_output", "call_id": call_id,
                         "status": "completed", "output": [{"type": "input_text", "text": label}]})
        self._done(out)

    def open_client_calls(self) -> list[str]:
        """Client calls still waiting for a result."""
        return [cid for cid, c in self._calls.items() if c["client"]]

    # -- text outside content blocks ---------------------------------------
    def note(self, text: str) -> None:
        """Pipe-authored text (limits, errors, the metadata marker) as part of the answer."""
        if not text:
            return
        idx = self._open_message()
        parts = self.items[idx]["content"]
        parts.append({"type": "output_text", "text": text, "annotations": []})
        self._emit({"type": "response.output_text.delta", "item_id": self.items[idx]["id"],
                    "output_index": idx, "content_index": len(parts) - 1, "delta": text})

    def finish(self, reason: str = "") -> None:
        """Close everything still open, so OpenWebUI never runs a call itself."""
        self._close_message()
        text = f"Not completed{': ' + reason if reason else ''}"
        for call_id, call in list(self._calls.items()):
            result = {"type": "tool_result", "tool_use_id": call_id, "content": text, "is_error": True}
            self._finish_call(call_id, result if call["client"] else None, text, status="failed")
        self._blocks.clear()

    def completed(self, usage: Optional[dict] = None) -> None:
        """Last event of the stream."""
        self._emit({"type": "response.completed",
                    "response": {"id": _new_id("resp"), "output": [], "usage": usage or {}}})


def owui_messages(items: list[dict]) -> list[dict]:
    """The OpenAI messages OpenWebUI replays for these items.

    Mirrors convert_output_to_messages (OpenWebUI 0.12.2+) for the item types
    the pipe writes. One deliberate difference: calls still waiting for their
    result are kept, because the next request inside the tool loop needs them;
    by the end of the turn every call has an output and both agree.
    """
    messages: list[dict] = []
    content: list[str] = []
    calls: list[dict] = []
    details: list[dict] = []
    outputs: list[dict] = []

    def flush() -> None:
        if content or calls or details:
            msg: dict = {"role": "assistant", "content": "\n".join(content)}
            if calls:
                msg["tool_calls"] = list(calls)
            if details:
                msg["reasoning_details"] = list(details)
            messages.append(msg)
        content.clear()
        calls.clear()
        details.clear()

    def flush_outputs() -> None:
        if outputs:
            flush()
            messages.extend(outputs)
            outputs.clear()

    for item in items:
        itype = item.get("type")
        if itype != "function_call_output":
            flush_outputs()
        if itype == "message":
            text = "".join(p.get("text", "") for p in item.get("content") or [] if p.get("type") == "output_text")
            if text:
                content.append(text)
        elif itype == "function_call":
            fn = item.get("provider_function") or item
            args = fn.get("arguments", "{}")
            calls.append({"id": item.get("call_id", ""), "type": "function",
                          "function": {"name": fn.get("name", ""),
                                       "arguments": args if isinstance(args, str) else json.dumps(args)}})
        elif itype == "function_call_output":
            text = "".join(p.get("text", "") for p in item.get("output") or [] if p.get("type") == "input_text")
            outputs.append({"role": "tool", "tool_call_id": item.get("call_id", ""), "content": text})
        elif itype == "reasoning":
            details.extend(d for d in item.get("reasoning_details") or [] if isinstance(d, dict))
    flush_outputs()
    flush()
    return messages


def _loads(arguments: Any) -> Any:
    if isinstance(arguments, dict):
        return arguments
    try:
        return json.loads(arguments or "{}")
    except (TypeError, ValueError):
        return {}


def _tool_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return ""


def is_item_run_start(message: dict) -> bool:
    """An assistant message OpenWebUI rebuilt from output items with calls or thinking."""
    return message.get("role") == "assistant" and bool(message.get("tool_calls") or message.get("reasoning_details"))


def group_item_runs(messages: list[dict]) -> list[dict]:
    """Fold each replayed turn (assistant + tool messages) into one ``__item_run__`` entry.

    A run starts at an assistant message with tool calls or thinking and takes
    every following assistant/tool message up to the next user or system
    message: the text after the last tool round belongs to the same turn.
    """
    grouped: list[dict] = []
    run: Optional[list] = None
    for msg in messages:
        role = msg.get("role")
        if run is not None and role in ("assistant", "tool"):
            run.append(msg)
            continue
        run = None
        if is_item_run_start(msg):
            run = [msg]
            grouped.append({"role": "__item_run__", "messages": run})
        else:
            grouped.append(msg)
    return grouped


def rebuild_run(messages: list[dict]) -> list[dict]:
    """Anthropic messages for one turn's replay (assistant + tool messages).

    Server tool results go back into the assistant message right after their
    call; client tool results become the next user message. The returned
    blocks are fresh copies: callers add cache_control to them.
    """
    out: list[dict] = []
    current: Optional[list] = None
    results: list[dict] = []
    carry: list[dict] = []
    payloads: dict[str, Optional[dict]] = {}
    dropped: set[str] = set()
    kept: set = set()

    def close() -> None:
        nonlocal current, results
        if current:
            out.append({"role": "assistant", "content": current})
        if results:
            out.append({"role": "user", "content": results})
        current, results = None, []

    for msg in messages:
        role = msg.get("role")
        if role == "assistant":
            if results:
                close()
            if current is None:
                current, carry = list(carry), []
            for detail in msg.get("reasoning_details") or []:
                if isinstance(detail, dict) and detail.get("format") == DETAIL_FORMAT and isinstance(detail.get("block"), dict):
                    current.append(detail["block"])
            text = msg.get("content")
            if isinstance(text, str) and text.strip():
                current.append({"type": "text", "text": text})
            for call in msg.get("tool_calls") or []:
                fn = call.get("function") or {}
                args = _loads(fn.get("arguments"))
                payload = args.get(ANTHROPIC_KEY) if isinstance(args, dict) else None
                if isinstance(payload, dict):
                    use = payload.get("use")
                    host = (use.get("caller") or {}).get("tool_id") if isinstance(use, dict) else None
                    if not use or (host and host not in kept):
                        # A server call that never got its result is left out (the
                        # API rejects it unpaired), and so are the calls its code made.
                        dropped.add(call.get("id", ""))
                        continue
                    payloads[call.get("id", "")] = payload
                    kept.add(use.get("id"))
                    current.append(use)
                else:
                    payloads[call.get("id", "")] = None
                    current.append({"type": "tool_use", "id": call.get("id", ""), "name": fn.get("name", ""),
                                    "input": args if isinstance(args, dict) else {}})
        elif role == "tool":
            call_id = msg.get("tool_call_id", "")
            if call_id in dropped:
                continue
            payload = payloads.get(call_id)
            use = (payload or {}).get("use") or {}
            if payload is None or use.get("type") == "tool_use":
                result = dict((payload or {}).get("result") or {"type": "tool_result", "tool_use_id": call_id})
                if "content" not in result:
                    result["content"] = _tool_text(msg.get("content"))
                results.append(result)
            elif payload.get("result") and use:
                if payload.get("after_client"):
                    carry.append(payload["result"])
                elif current is not None:
                    current.append(payload["result"])
    close()
    if carry:
        out.append({"role": "assistant", "content": carry})
    return _clone(out)
