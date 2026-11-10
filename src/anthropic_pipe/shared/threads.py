"""Message threads (beta, ``message-threads-2026-08-12``) for the tool loop of one turn.

Without a thread every request of a tool loop uploads the whole conversation
again. With one, the first request of the turn creates a thread and each later
request sends only the messages added since (the tool results) plus the id of
the previous response; the API rebuilds the conversation itself.

The pipe stays the source of truth: it keeps building the full payload and this
class only decides what part of it goes over the wire. Whenever the full
payload is not "previous request + its response + new messages", or the API
rejects a threaded request, the full conversation is sent instead.

ponytail: one thread per turn. Carrying a thread into the next user turn
(threads live 5 minutes) would need the last response id per chat and a
guarantee that OpenWebUI replays the stored conversation unchanged; add it when
first-request latency of long chats matters.
"""
from __future__ import annotations

import json
from typing import Any, Optional

MESSAGE_THREADS_BETA = "message-threads-2026-08-12"


def _without_cache_control(value: Any) -> Any:
    """Copy of ``value`` without cache_control: breakpoints move between requests."""
    if isinstance(value, dict):
        return {k: _without_cache_control(v) for k, v in value.items() if k != "cache_control"}
    if isinstance(value, list):
        return [_without_cache_control(v) for v in value]
    return value


def _fingerprint(messages: list) -> list[str]:
    return [
        json.dumps(_without_cache_control(m), sort_keys=True, default=str, ensure_ascii=False)
        for m in messages
    ]


class MessageThread:
    def __init__(self) -> None:
        self.enabled = True
        self.threaded = False  # was the request built last sent with `thread`?
        self._previous_id: Optional[str] = None
        self._stored: list[str] = []  # fingerprints of the messages the API holds
        self._pending: list[str] = []

    @staticmethod
    def supports(payload: dict) -> bool:
        """Threads reject compaction / context editing (thread_unsupported_request)."""
        return "context_management" not in payload and "context_management" not in (
            payload.get("extra_body") or {}
        )

    def request(self, payload: dict) -> dict:
        """The request to send for ``payload``: a thread create, a continue, or the payload itself."""
        self.threaded = False
        if not self.enabled or not self.supports(payload):
            return payload
        messages = payload.get("messages") or []
        fingerprints = _fingerprint(messages)
        stored = len(self._stored)
        continues = (
            self._previous_id is not None
            and len(messages) > stored
            and fingerprints[:stored] == self._stored
            # the message right after the stored ones is the previous response
            and messages[stored].get("role") == "assistant"
        )
        if continues:
            request = {k: v for k, v in payload.items() if k not in ("system", "tools")}
            request["messages"] = self._cached_tail(messages, stored + 1)
            thread = {"type": "continue", "previous_message_id": self._previous_id}
        else:
            request = dict(payload)
            thread = {"type": "create"}
        betas = list(payload.get("betas") or [])
        if MESSAGE_THREADS_BETA not in betas:
            betas.append(MESSAGE_THREADS_BETA)
        request["betas"] = betas
        # extra_body rather than a keyword: `thread` only exists from SDK 2.2.
        request["extra_body"] = {**(payload.get("extra_body") or {}), "thread": thread}
        self._pending = fingerprints
        self.threaded = True
        return request

    @staticmethod
    def _cached_tail(messages: list, start: int) -> list:
        """The new messages, with a cache breakpoint at their end.

        The pipe's in-loop breakpoints can sit on messages the thread already
        holds, and a continue request cannot move those. Without a breakpoint in
        what is actually sent, nothing of this request is written to the cache
        and the next one pays for it uncached (measured: a web search result,
        9.8k tokens). The marker is copied from the payload so the TTL matches;
        a payload without any (caching off) stays without.
        """
        new = messages[start:]
        marker = next(
            (
                b["cache_control"]
                for m in reversed(messages)
                if isinstance(m.get("content"), list)
                for b in m["content"]
                if isinstance(b, dict) and b.get("cache_control")
            ),
            None,
        )
        has_marker = any(
            isinstance(b, dict) and b.get("cache_control")
            for m in new
            if isinstance(m.get("content"), list)
            for b in m["content"]
        )
        if marker is None or has_marker or not new or not isinstance(new[-1].get("content"), list):
            return new
        # Calls made from code execution: neither the call nor its result takes a marker
        # (400 "called by code execution cannot have cache_control").
        from_code = {
            b.get("id")
            for m in messages
            if isinstance(m.get("content"), list)
            for b in m["content"]
            if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("caller")
        }
        content = list(new[-1]["content"])
        for i in range(len(content) - 1, -1, -1):
            block = content[i]
            if (
                isinstance(block, dict)
                and block.get("type") not in ("thinking", "redacted_thinking")
                and not block.get("caller")
                and block.get("tool_use_id") not in from_code
            ):
                content[i] = {**block, "cache_control": dict(marker)}
                return [*new[:-1], {**new[-1], "content": content}]
        return new

    def responded(self, message: Any) -> None:
        """Record a finished response; the next request can continue from it if the API stored it."""
        if not self.threaded:
            return
        usage = getattr(message, "usage", None)
        fallback = any(
            getattr(i, "type", None) == "fallback_message"
            for i in (getattr(usage, "iterations", None) or [])
        )
        stop_reason = getattr(message, "stop_reason", None)
        message_id = getattr(message, "id", None)
        # Not stored by the API: a fallback model's answer, a refusal, a cut-off stream.
        if fallback or not message_id or stop_reason in (None, "refusal", "max_tokens"):
            self._previous_id = None
            self._stored = []
            return
        self._previous_id = message_id
        self._stored = self._pending

    def disable(self) -> None:
        """Send full requests for the rest of the turn."""
        self.enabled = False
        self.threaded = False
        self._previous_id = None
        self._stored = []
