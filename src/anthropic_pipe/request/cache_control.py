"""Compiled Pipe method group extracted from pipe_template.py."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class PipeCacheControlMethods:
    def _cache_control_marker(self, scope: str = "messages") -> dict:
        """Return the cache_control dict for one breakpoint scope.

        `tools_system` may run a longer TTL than `messages`: the tools array and
        system prompt are stable across turns, so a 1h entry pays for its doubled
        write cost, while messages change every turn and would just re-pay it.

        The API requires longer TTLs to sit *before* shorter ones in the prompt
        (render order is tools -> system -> messages), so tools/system may be
        longer than messages but never shorter. A configuration that inverts that
        is clamped to the messages TTL rather than sent and silently mis-billed.
        """
        setting = self.valves.CACHE_TTL
        if scope == "tools_system":
            override = getattr(self.valves, "CACHE_TTL_FOR_TOOLS_AND_SYSTEM_PROMT", "same as CACHE_TTL")
            if override != "same as CACHE_TTL":
                if override == "5 minutes" and self.valves.CACHE_TTL == "1 hour":
                    logger.warning(
                        "CACHE_TTL_FOR_TOOLS_AND_SYSTEM_PROMT=5 minutes with CACHE_TTL=1 hour is not a "
                        "valid ordering (longer TTLs must come first); using 1 hour for "
                        "tools/system instead."
                    )
                else:
                    setting = override

        marker = {"type": "ephemeral"}
        if setting == "1 hour":
            marker["ttl"] = "1h"
        return marker

    @staticmethod
    def _dump_sdk_obj(obj: Any) -> Any:
        """Recursively convert an Anthropic SDK object (or plain dict/list) to a
        plain Python structure suitable for JSON serialisation."""
        if obj is None:
            return None
        if hasattr(obj, "model_dump"):
            try:
                return obj.model_dump(exclude_none=True)
            except TypeError:
                return obj.model_dump()
        if isinstance(obj, dict):
            return {k: Pipe._dump_sdk_obj(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [Pipe._dump_sdk_obj(v) for v in obj]
        if isinstance(obj, (str, int, float, bool)):
            return obj
        return str(obj)

    @staticmethod
    def _canonicalize_block(node):
        """Rewrite a content block with a deterministic key order.

        Anthropic hashes the serialized bytes of the prompt prefix, so two dicts
        with identical content but different key order are two different
        prefixes. That is exactly what happened: live blocks are dumped from SDK
        objects in the SDK's field order (``citations, text, type``), while
        replayed blocks are literal dicts written in reading order
        (``type, text, citations``). Same content, different bytes, guaranteed
        cache miss on the first turn after any tool use -- and invisible to any
        content-level comparison, which is why the pipe's own diff logger keeps
        a separate insertion-order hash to catch it.

        Normalising at one choke point beats matching orders at every
        construction site: whatever built the block, the wire format is the same.
        ``type`` leads because it is the discriminator and makes payload dumps
        readable; the rest is alphabetical. Key ORDER is all that changes, never
        keys or values, so the request itself is unaffected -- JSON objects are
        order-insensitive to the API's parser.
        """
        def _walk(n):
            if isinstance(n, dict):
                items = sorted(n.items(), key=lambda kv: (kv[0] != "type", kv[0]))
                return {k: _walk(v) for k, v in items}
            if isinstance(n, list):
                return [_walk(v) for v in n]
            return n

        return _walk(node)

    @staticmethod
    def _strip_payload(payload: dict, max_str: int = 20) -> dict:
        """Return a copy of the outgoing Anthropic payload with *minimal*
        structural changes, safe for debug logging.

        Only two things change:
          1. ``tools`` is replaced with a small summary (count + names +
             indices carrying cache_control).
          2. Every string value reachable inside ``messages`` is truncated to
             ``max_str`` chars + ``…[Nc]`` length marker.

        Everything else — key order, whitespace inside non-messages strings,
        `system`, `cache_control`, booleans, numbers, None values, extra
        top-level fields — is left **byte-for-byte** untouched so that two
        consecutive dumps can be diffed to locate cache-invalidating drift
        (double newlines, missing spaces, re-ordered keys, etc).
        """
        def _clip(s):
            """Truncate a string to max_str chars, appending a length+hash marker."""
            if isinstance(s, str) and len(s) > max_str:
                import hashlib as _hl
                _h = _hl.sha1(s.encode("utf-8", "replace")).hexdigest()[:8]
                return f"{s[:max_str]}…[{len(s)}c#{_h}]"
            return s

        def _walk(node):
            """Recursively clip every string value found within a dict/list structure."""
            if isinstance(node, dict):
                return {k: _walk(v) for k, v in node.items()}
            if isinstance(node, list):
                return [_walk(v) for v in node]
            if isinstance(node, str):
                return _clip(node)
            return node

        stripped: dict = {}
        for k, v in payload.items():
            if k == "tools":
                import hashlib as _hl
                import json as _json
                tools = v or []
                # Serialize each tool the way it goes over the wire so two dumps
                # reveal both size (which segment owns the cache_creation tokens)
                # and byte drift (a schema that re-orders or re-renders per turn).
                _blobs = [
                    _json.dumps(t, sort_keys=False, separators=(",", ":"), default=str)
                    for t in tools if isinstance(t, dict)
                ]
                stripped["tools"] = {
                    "__tools_count__": len(tools),
                    "__tools_bytes__": sum(len(b) for b in _blobs),
                    "__tools_sha__": _hl.sha1("".join(_blobs).encode("utf-8", "replace")).hexdigest()[:10],
                    "names": [
                        (t.get("name") or t.get("type") or "?")
                        for t in tools if isinstance(t, dict)
                    ],
                    "per_tool": [
                        f"{len(b)}c#{_hl.sha1(b.encode('utf-8', 'replace')).hexdigest()[:8]}"
                        for b in _blobs
                    ],
                    "cache_control_idx": [
                        i for i, t in enumerate(tools)
                        if isinstance(t, dict) and "cache_control" in t
                    ],
                }
            elif k == "messages":
                stripped["messages"] = _walk(v)
            else:
                stripped[k] = v
        return stripped

    def _log_message_hash_diff(self, chat_id: Optional[str], payload: dict) -> None:
        """Compare the current outgoing payload.messages[] against the previous
        request for the same chat_id. Log first divergence index + per-message
        hash table so we can pinpoint which assistant/user message mutated
        between turns and broke the Anthropic prompt cache prefix.

        Uses hashlib.sha1 on ``json.dumps(sort_keys=True, separators=(",", ":"))``
        of each message (minus cache_control markers, which legitimately move).
        """
        if not chat_id:
            return
        try:
            msgs = payload.get("messages", []) or []

            def _strip_cache_control(obj):
                """Recursively remove all ``cache_control`` keys from a dict/list structure."""
                if isinstance(obj, dict):
                    return {
                        k: _strip_cache_control(v)
                        for k, v in obj.items()
                        if k != "cache_control"
                    }
                if isinstance(obj, list):
                    return [_strip_cache_control(v) for v in obj]
                return obj

            def _preview(canon: str, limit: int = 6000) -> str:
                """Return canon as-is if short, else a truncated preview with a trailing sha1 digest."""
                if len(canon) <= limit:
                    return canon
                import hashlib
                digest = hashlib.sha1(canon.encode("utf-8", "replace")).hexdigest()[:10]
                return f"{canon[:limit]}...(truncated {len(canon)}c sha1={digest})"

            def _hash_msg(m: dict) -> tuple[str, str, str]:
                """Return (insertion_order_hash, sorted_hash, preview). The SDK sends
                dicts in Python insertion order, so insertion_order_hash is
                what the API actually sees for cache purposes. sorted_hash
                tells us whether the *content* matches regardless of order.

                ``cache_control`` markers are stripped from both hashes because
                they are placement hints that legitimately move between turns;
                treating them as message drift creates false positives.
                """
                import hashlib
                stripped = _strip_cache_control(m)
                try:
                    canon_ins = json.dumps(stripped, sort_keys=False, separators=(",", ":"), ensure_ascii=False,
                                           default=lambda o: repr(o))
                except Exception:
                    canon_ins = repr(stripped)
                try:
                    canon_sorted = json.dumps(stripped, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                                              default=lambda o: repr(o))
                except Exception:
                    canon_sorted = repr(stripped)
                ins_h = hashlib.sha1(canon_ins.encode("utf-8")).hexdigest()[:10]
                sort_h = hashlib.sha1(canon_sorted.encode("utf-8")).hexdigest()[:10]
                return (ins_h, sort_h, _preview(canon_ins))

            def _summarize(m: dict) -> str:
                """Build a short human-readable summary of a message's role and content blocks."""
                role = m.get("role", "?")
                content = m.get("content", "")
                if isinstance(content, str):
                    return f"{role}:text({len(content)}c)"
                if isinstance(content, list):
                    parts = []
                    for b in content:
                        if not isinstance(b, dict):
                            parts.append(type(b).__name__)
                            continue
                        bt = b.get("type", "?")
                        if bt == "text":
                            parts.append(f"text({len(b.get('text', ''))}c)")
                        elif bt == "tool_use":
                            parts.append(f"tool_use({b.get('name', '?')})")
                        elif bt == "tool_result":
                            c = b.get("content", "")
                            clen = len(c) if isinstance(c, str) else len(c) if isinstance(c, list) else 0
                            parts.append(f"tool_result({clen})")
                        else:
                            parts.append(bt)
                    return f"{role}:[{','.join(parts)}]"
                return f"{role}:?"

            hash_pairs = [_hash_msg(m) for m in msgs]
            ins_hashes = [h[0] for h in hash_pairs]
            sort_hashes = [h[1] for h in hash_pairs]
            previews = [h[2] for h in hash_pairs]
            summaries = [_summarize(m) for m in msgs]

            def _breakpoint_index(messages: list):
                """Where the messages cache_control marker sits: (msg, block).

                Everything up to and including that BLOCK forms the prefix the
                next turn tries to read back. The block half matters: volatile
                context is normalised into trailing blocks, so the breakpoint now
                usually sits inside the very message whose tail is expected to
                differ. Judging at message granularity would report every single
                healthy turn as a break.
                """
                for idx in range(len(messages) - 1, -1, -1):
                    content = messages[idx].get("content", [])
                    if not isinstance(content, list):
                        continue
                    for bidx in range(len(content) - 1, -1, -1):
                        block = content[bidx]
                        if isinstance(block, dict) and "cache_control" in block:
                            return (idx, bidx)
                return None

            def _prefix_hash(messages: list, bp) -> Optional[str]:
                """Hash of the breakpoint message truncated at the breakpoint block.

                Lets the next turn tell "the tail of this message changed"
                (harmless, expected) from "the cached part changed" (a real break)
                without needing a per-block hash table.
                """
                if bp is None:
                    return None
                midx, bidx = bp
                if midx >= len(messages):
                    return None
                content = messages[midx].get("content", [])
                if not isinstance(content, list):
                    return None
                return _hash_msg({"role": messages[midx].get("role"),
                                  "content": content[: bidx + 1]})[0]

            bp = _breakpoint_index(msgs)
            bp_idx = bp[0] if bp else None
            prev_state = self._cache_diff_state.get(chat_id) or {}
            prev_pairs = prev_state.get("msgs", [])
            prev_bp_pair = prev_state.get("bp_pair")
            prev_bp = prev_state.get("bp")
            prev_bp_prefix = prev_state.get("bp_prefix")
            prev_ins = [p[0] for p in prev_pairs]
            prev_sort = [p[1] for p in prev_pairs]
            prev_previews = [p[2] if len(p) > 2 else "(previous preview unavailable)" for p in prev_pairs]

            if prev_pairs:
                overlap = min(len(prev_pairs), len(hash_pairs))
                # Check insertion-order (what the API actually sees)
                ins_first_diff = None
                for i in range(overlap):
                    if prev_ins[i] != ins_hashes[i]:
                        ins_first_diff = i
                        break
                # Check sorted/content (what we'd naively consider "the same")
                sort_first_diff = None
                for i in range(overlap):
                    if prev_sort[i] != sort_hashes[i]:
                        sort_first_diff = i
                        break

                # Only divergence at or before the *previous* breakpoint can cost
                # a cache read -- that is the prefix this turn tries to reuse.
                # Anything after it is replay noise (the memory/RAG appendix on
                # the last message is expected to differ) and must not be logged
                # as a break, or the real breaks drown in false positives.
                first_diff = ins_first_diff if ins_first_diff is not None else sort_first_diff
                if first_diff is None or prev_bp is None:
                    harmful = False
                elif first_diff < prev_bp:
                    # Divergence strictly before the breakpoint message: the
                    # cached prefix definitely changed.
                    harmful = True
                elif first_diff > prev_bp:
                    harmful = False
                else:
                    # Same message as the breakpoint. Only the part up to the
                    # breakpoint BLOCK was cached, and its tail is expected to
                    # differ -- that is where the memory/RAG appendix lives.
                    now_prefix = _prefix_hash(msgs, prev_bp_pair)
                    harmful = (
                        prev_bp_prefix is not None
                        and now_prefix is not None
                        and now_prefix != prev_bp_prefix
                    )
                _log = logger.warning if harmful else logger.info
                scope = f"prev_bp=msg[{prev_bp}]" if prev_bp is not None else "prev_bp=none"

                if ins_first_diff is None and sort_first_diff is None:
                    logger.info(
                        f"🧊 CACHE-DIFF chat={chat_id}: prefix FULLY STABLE (ins+sort) over {overlap} msgs "
                        f"(prev={len(prev_pairs)}, now={len(hash_pairs)}, appended={len(hash_pairs) - overlap}) ✓"
                    )
                elif not harmful:
                    logger.info(
                        f"🧊 CACHE-DIFF chat={chat_id}: divergence at msg[{first_diff}] is BEHIND the cached "
                        f"prefix ({scope}) — harmless, expected for per-request context on the last message ✓"
                    )
                elif ins_first_diff is not None and sort_first_diff is None:
                    # CRITICAL: content equal but KEY ORDER diverged → API cache miss!
                    logger.warning(
                        f"🔥🔑 CACHE-DIFF chat={chat_id}: KEY-ORDER drift at msg[{ins_first_diff}] "
                        f"(content identical, but dict insertion order differs → API sees different bytes)"
                    )
                elif ins_first_diff == sort_first_diff:
                    logger.warning(
                        f"🔥 CACHE-DIFF chat={chat_id}: prefix DIVERGES at msg[{ins_first_diff}] "
                        f"(content+order both differ, overlap={overlap}, prev={len(prev_pairs)}, now={len(hash_pairs)})"
                    )
                else:
                    logger.warning(
                        f"🔥 CACHE-DIFF chat={chat_id}: ins_diff@{ins_first_diff}, sort_diff@{sort_first_diff} "
                        f"(overlap={overlap})"
                    )

                if ins_first_diff is not None and harmful:
                    lo = max(0, ins_first_diff - 1)
                    hi = min(max(len(prev_pairs), len(hash_pairs)), ins_first_diff + 3)
                    for i in range(lo, hi):
                        pi = prev_ins[i] if i < len(prev_ins) else "----------"
                        ps = prev_sort[i] if i < len(prev_sort) else "----------"
                        ni = ins_hashes[i] if i < len(ins_hashes) else "----------"
                        ns = sort_hashes[i] if i < len(sort_hashes) else "----------"
                        sm = summaries[i] if i < len(summaries) else "(absent)"
                        marker = "  " if pi == ni and ps == ns else "**"
                        logger.warning(
                            f"  {marker} msg[{i}]: ins prev={pi} now={ni} | sort prev={ps} now={ns} {sm}"
                        )
                    # Dump FULL JSON (insertion order) for diffing
                    if ins_first_diff < len(prev_previews):
                        logger.warning(
                            f"  ** msg[{ins_first_diff}] PREV-INS-ORDER: "
                            f"{prev_previews[ins_first_diff]}"
                        )
                    if ins_first_diff < len(previews):
                        logger.warning(
                            f"  ** msg[{ins_first_diff}] NOW-INS-ORDER: "
                            f"{previews[ins_first_diff]}"
                        )

            self._cache_diff_state[chat_id] = {
                "msgs": hash_pairs,
                "bp": bp_idx,
                "bp_pair": bp,
                "bp_prefix": _prefix_hash(msgs, bp),
            }
            # Bound memory: keep only last ~20 chats
            if len(self._cache_diff_state) > 20:
                # drop oldest inserted (FIFO)
                oldest = next(iter(self._cache_diff_state))
                if oldest != chat_id:
                    self._cache_diff_state.pop(oldest, None)
        except Exception as e:
            logger.debug(f"_log_message_hash_diff failed: {e}")

    # From which tool-loop iteration on the in-turn breakpoint is worth its write.
    #
    # That breakpoint sits on the newest message, i.e. BEHIND the volatile
    # blocks, so its entry covers them. Within a turn that is fine and useful --
    # the payload is built once and only extended, so the appendix does not move
    # and the next iteration reads it. Across turns the entry is dead, because
    # the appendix vanishes from that message.
    #
    # So it pays off only while more iterations follow, and the write of the
    # LAST iteration is always wasted. Measured on a real conversation, the
    # wasted writes were 551, 571 and 8721 tokens -- the last one being a turn
    # with thinking plus three tool calls. Since most loops stop after one tool
    # round, waiting until the loop has proven itself deep avoids the common
    # waste and keeps the benefit where loops actually get long.
    TOOL_LOOP_VOLATILE_CACHE_MIN_ITERATION = 4

    def _apply_cache_control(
        self, payload: dict, is_tool_loop: bool = False, iteration: int = 1
    ) -> None:
        """Apply cache_control breakpoints to the payload right before sending to the API.

        Called once before the initial request and once before each tool loop iteration.
        Strips all existing cache_control markers first, then applies fresh ones
        based on the current payload state and valve configuration.

        ``iteration`` is the 1-based tool-loop iteration. It gates the in-turn
        breakpoint (see TOOL_LOOP_VOLATILE_CACHE_MIN_ITERATION); a caller that
        omits it gets the conservative behaviour of never placing one.

        Anthropic rules:
        - Max 4 breakpoints, hierarchy: tools → system → messages
        - Cache prefixes are cumulative (hash depends on all prior blocks)
        - Never add cache_control to thinking/redacted_thinking blocks (API rejects extra fields)
        - 20-block lookback window from each explicit breakpoint
        - Minimum cacheable: 1024-4096 tokens depending on model
        - Tool_result blocks CAN have cache_control (unless programmatic calling)
        """
        cache_level = self.valves.CACHE_CONTROL
        if cache_level == "cache disabled":
            return

        # --- Step 1: Strip all existing cache_control from entire payload ---
        for tool in payload.get("tools", []):
            tool.pop("cache_control", None)
        for block in payload.get("system", []):
            block.pop("cache_control", None)
        for msg in payload.get("messages", []):
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        block.pop("cache_control", None)

        # --- Step 2: Cache tools (breakpoint 1) ---
        # Always cache tools at every non-disabled level — tools rarely change
        # and having a separate breakpoint ensures cache hits even when system/messages change.
        # Tools and system share one marker; messages get their own further down,
        # so the two can run different TTLs.
        cache_marker = self._cache_control_marker("tools_system")

        tools = payload.get("tools", [])
        if tools:
            # Find last non-deferred tool for the breakpoint
            placed = False
            for i in range(len(tools) - 1, -1, -1):
                if not tools[i].get("defer_loading", False):
                    tools[i]["cache_control"] = cache_marker
                    placed = True
                    break
            if not placed:
                # All deferred — cache the last one anyway
                tools[-1]["cache_control"] = cache_marker

        if cache_level == "cache tools array only":
            return

        # --- Step 3: Cache system prompt (breakpoint 2) ---
        system = payload.get("system", [])
        if system:
            # Find last text block with content
            for i in range(len(system) - 1, -1, -1):
                block = system[i]
                if block.get("type") == "text" and block.get("text", "").strip():
                    block["cache_control"] = cache_marker
                    break

        if cache_level == "cache tools array and system prompt":
            return

        # --- Step 4: Cache messages (breakpoint 3) ---
        # "cache tools array, system prompt and messages"
        messages = payload.get("messages", [])
        if not messages:
            return

        if is_tool_loop:
            # Two different jobs during a tool loop, and conflating them is what
            # made a whole history get rewritten every turn.
            volatile_msg, volatile_at = None, None
            for msg in reversed(messages):
                idx = self._first_volatile_block_index(msg)
                if idx is not None:
                    volatile_msg, volatile_at = msg, idx
                    break

            if volatile_msg is None:
                # Nothing volatile in this conversation (no memories, no RAG), so
                # the newest message replays byte-identically next turn. One
                # breakpoint serves both jobs.
                place_in_turn = True
            else:
                # Job 1, always: anchor a breakpoint that ends right BEFORE the
                # volatile blocks. That is the furthest point still reproducible
                # once the appendix is gone, so it is the only entry the next
                # turn can read.
                if volatile_at > 0:
                    self._place_cache_on_last_cacheable_block(
                        volatile_msg.get("content", [])[:volatile_at]
                    )
                # Job 2, conditionally: the in-turn breakpoint below sits on the
                # newest message, so its entry also covers the volatile blocks
                # and the tool results. Inside the turn that is correct and
                # useful -- the payload is only extended, so the appendix does
                # not move and the next iteration reads it. It is worthless
                # across turns though, so it is only worth its 1.25x write while
                # further iterations are still coming.
                #
                # Budget note: tools and system claim one breakpoint each of
                # Anthropic's four, so messages may spend two. Overshooting is a
                # 400, not a degraded cache.
                place_in_turn = (
                    iteration >= self.TOOL_LOOP_VOLATILE_CACHE_MIN_ITERATION
                    and self._count_message_breakpoints(messages) < 2
                )

            # EXCEPTION: Programmatic tool calling — API rejects cache_control on
            # tool_result blocks routed through code_execution.
            if not place_in_turn:
                pass
            elif self.valves.ENABLE_PROGRAMMATIC_TOOL_CALLING:
                # With programmatic calling, cache the last assistant message block instead
                # (thinking blocks excluded — find last text or tool_use block)
                for msg in reversed(messages):
                    if msg.get("role") == "assistant":
                        self._place_cache_on_last_cacheable_block(msg.get("content", []))
                        break
            else:
                # Standard tool loop: cache the last user message block (tool_result)
                for msg in reversed(messages):
                    if msg.get("role") == "user":
                        content = msg.get("content", [])
                        if content:
                            # tool_result blocks are cacheable
                            content[-1]["cache_control"] = cache_marker
                        break
        else:
            # Initial request: cache the last stable user message
            self._cache_last_stable_message(messages)

    def _place_cache_on_last_cacheable_block(self, content_blocks: list) -> None:
        """Add cache_control to the last block that isn't thinking/redacted_thinking
        or a tool_use called by code execution (API rejects cache_control on those)."""
        if not content_blocks:
            return
        for i in range(len(content_blocks) - 1, -1, -1):
            block = content_blocks[i]
            if isinstance(block, dict):
                btype = block.get("type")
                if btype in ("thinking", "redacted_thinking"):
                    continue
                # tool_use blocks called by code_execution cannot have cache_control
                if btype == "tool_use" and block.get("caller"):
                    continue
                block["cache_control"] = self._cache_control_marker()
                return

    @staticmethod
    def _message_carries_volatile_context(msg: dict) -> bool:
        """True when a message carries per-request context that never repeats.

        Two sources, same problem. OpenWebUI re-retrieves both on every request
        against the current question:
          * RAG chunks, injected into the last user message as <context> or as a
            "### Task:" template wrapping <source> elements.
          * Memories, which this pipe relocates out of the system prompt onto the
            last user message (see MEMORY_CONTEXT_APPENDIX_HEADER).

        Only the *last* message ever receives them, so on the next turn the very
        same message is replayed without them and the prefix diverges right there.
        Caching such a message poisons the whole history: the API then reports
        messages_changed and re-writes everything from that index onward, turn
        after turn. Cache the message before it instead.
        """
        return Pipe._first_volatile_block_index(msg) is not None

    @staticmethod
    def _count_message_breakpoints(messages: list) -> int:
        """How many cache_control markers the messages array already carries."""
        total = 0
        for msg in messages:
            content = msg.get("content", [])
            if not isinstance(content, list):
                continue
            total += sum(
                1 for b in content if isinstance(b, dict) and "cache_control" in b
            )
        return total

    @staticmethod
    def _first_volatile_block_index(msg: dict) -> Optional[int]:
        """Index of the first block carrying per-request context, or None.

        Both sources are normalised into trailing blocks of their own before this
        runs (see _split_rag_into_trailing_block and the memory appendix), so the
        returned index marks where the stable part of the message ends.
        """
        content = msg.get("content", [])
        if not isinstance(content, list):
            return None
        for i, block in enumerate(content):
            if not isinstance(block, dict) or block.get("type") != "text":
                continue
            text = block.get("text", "")
            if (
                "<context>" in text
                or ("### Task:" in text and "<source" in text)
                or MEMORY_CONTEXT_APPENDIX_HEADER in text
            ):
                return i
        return None

    def _cache_last_stable_message(self, messages: list) -> None:
        """Place the messages breakpoint on the newest message that will replay
        byte-identically next turn, skipping volatile per-request context and
        thinking/redacted_thinking blocks.
        """
        if not messages:
            return

        last = messages[-1]
        volatile_at = self._first_volatile_block_index(last)

        if volatile_at is None:
            self._place_cache_on_last_cacheable_block(last.get("content", []))
            return

        if volatile_at > 0:
            # The stable head of this very message can still be cached: volatile
            # context is normalised into trailing blocks, so a breakpoint on the
            # last block before them ends the prefix exactly where the message
            # stops being reproducible. This is what lets the FIRST request of a
            # conversation cache at all -- it used to fall through to the
            # len < 2 guard below and cache nothing but the tools.
            content = last.get("content", [])
            self._place_cache_on_last_cacheable_block(content[:volatile_at])
            return

        if len(messages) < 2:
            # The whole message is volatile and there is nothing before it.
            # Placing the breakpoint anyway would write an entry that cannot be
            # read back next turn; tools and system keep their own breakpoints.
            return

        self._place_cache_on_last_cacheable_block(messages[-2].get("content", []))
