"""Compiled Pipe method group extracted from pipe_template.py."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class PipeStreamSupportMethods:
    @staticmethod
    def _encode_block_payload(payload: Any) -> str:
        """Base64-encode a server-tool block payload (JSON) for byte-exact
        round-trip through OpenWebUI storage."""
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return base64.b64encode(raw.encode("utf-8")).decode("ascii")

    @staticmethod
    def _decode_block_payload(payload_b64: str) -> Optional[Any]:
        """Decode a base64-encoded JSON payload. Returns None on failure."""
        try:
            return json.loads(base64.b64decode(payload_b64).decode("utf-8"))
        except Exception:
            return None

    @staticmethod
    def _block_visibility_key(name: str) -> str:
        """Map a tool name or *_tool_result block type onto its visibility key.

        A single logical block reaches the formatters under several names
        (`tool_search_tool_bm25` for the call, `tool_search_tool_result` for the
        result), but the user hides *one* concept. Normalising here keeps the
        HIDE_BLOCKS valve spelled in concepts rather than wire names.
        """
        key = name[: -len("_tool_result")] if name.endswith("_tool_result") else name
        if key.startswith("tool_search"):
            return "tool_search"
        # bash_code_execution / text_editor_code_execution are variants of the
        # same user-facing concept; hiding "code_execution" must cover all three.
        if key.endswith("code_execution"):
            return "code_execution"
        return key

    def _is_block_hidden(self, name: str) -> bool:
        """True when HIDE_BLOCKS opts this block concept out of visible rendering.

        Read from the request-scoped HIDDEN_BLOCKS ContextVar, which pipe() fills
        from the requesting user's UserValves — hiding a collapsible is a personal
        display preference, not an admin-wide one.
        """
        if SLIM_OUTPUT.get():
            return True
        hidden = HIDDEN_BLOCKS.get()
        if not hidden:
            return False
        return self._block_visibility_key(name) in hidden

    @staticmethod
    def _parse_hidden_blocks(raw: Any) -> frozenset:
        """Normalize the HIDE_BLOCKS valve into a set of block concept keys.

        The valve is a multiselect (``list[str]``) since v0.9.25. Values saved
        under the previous comma-separated ``str`` form are still accepted so an
        upgrade does not silently drop a user's preference.
        """
        if isinstance(raw, str):
            raw = raw.split(",")
        if not raw:
            return frozenset()
        return frozenset(str(part).strip() for part in raw if str(part).strip())

    def _format_hidden_block(self, payloads: list, label_id: str = "") -> str:
        """Render API blocks as an invisible, replay-stable markdown carrier.

        A markdown *link reference definition* is consumed by the tokenizer into
        the link table and produces no token at all, so OpenWebUI renders exactly
        nothing — unlike an HTML comment (shown as escaped text) or an empty
        `[](...)` link (an empty paragraph taking vertical space). The payload
        rides in the destination, which may not contain spaces; base64 satisfies
        that. Read back by ``PATTERN_HIDDEN_BLOCK`` on replay.

        The leading BLANK line is load-bearing, and a single newline is not
        enough: with only one, markdown absorbs the definition into the
        preceding paragraph as a lazy continuation line and renders the whole
        payload as visible text. Verified against marked 9.1.6 with OpenWebUI's
        `breaks: true` — "prose\\n[def]" leaks, "prose\\n\\n[def]" yields no token.
        """
        if SLIM_OUTPUT.get():
            # Nothing will ever replay this run, and the parent agent pays for
            # every byte of it. Drop the carrier entirely.
            return ""
        suffix = f"-{re.sub(r'[^A-Za-z0-9_]', '', label_id)}" if label_id else ""
        return f"\n\n[anthropic-hidden{suffix}]: #{self._encode_block_payload(payloads)}\n"

    @staticmethod
    def _stringify_terminal_result(result: Any) -> str:
        """Normalize Open Terminal callable results to a plain string.

        ``execute_tool_server`` returns a ``(data, headers)`` tuple where
        ``headers`` is a ``CIMultiDictProxy`` (not JSON-serializable). The
        OpenWebUI middleware unpacks ``[0]`` before dumping; we do the same
        here, then JSON-encode the data half.
        """
        if isinstance(result, tuple) and result:
            result = result[0]
        if isinstance(result, str):
            return result
        try:
            return json.dumps(result, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            return str(result)

    async def _emit_terminal_event(
        self,
        emitter: Optional[Callable],
        event_type: str,
        path: str = "",
    ) -> None:
        """Emit a ``terminal:*`` UI event so Open Terminal refreshes the panel.

        Mirrors OpenWebUI's ``terminal_event_handler``: run_command → empty
        data, file ops → ``{"path": ...}``. Best-effort — event emission must
        never break tool execution, so failures are swallowed.
        """
        if not emitter:
            return
        data = {"path": path} if path else {}
        try:
            await emitter({"type": f"terminal:{event_type}", "data": data})
        except Exception:
            logger.debug("terminal:%s event emit failed", event_type, exc_info=True)

    async def _dispatch_bash_tool(
        self,
        tool_input: dict,
        __tools__: dict,
        emitter: Optional[Callable] = None,
    ) -> str:
        """Bridge native bash tool calls to Open Terminal's run_command callable.

        Open Terminal's `run_command` is *asynchronous*: it returns a process
        descriptor (``id``, ``status="running"``, empty ``output``) immediately
        and the actual stdout/stderr must be polled via ``get_process_status``.
        This wrapper hides that detail from the model — it polls until the
        process completes (or times out) and returns a single concatenated
        result string, so Claude's bash tool semantics ("send command, receive
        output") are preserved.

        - {command: "..."}  → run_command + poll until done.
        - {restart: true}   → no native restart endpoint exists; reset CWD via `cd ~`.
        """
        try:
            run_cmd = __tools__.get("run_command", {}).get("callable")
            if not run_cmd:
                return "Error: run_command callable is not available."
            if tool_input.get("restart"):
                await run_cmd(command="cd ~")
                await self._emit_terminal_event(emitter, "run_command")
                return "Bash session reset (working dir → $HOME)."
            command = tool_input.get("command", "")
            if not command:
                return "Error: missing required parameter `command`."

            result = await self._run_terminal_command(__tools__, command)
            await self._emit_terminal_event(emitter, "run_command")
            return result
        except Exception as e:
            logger.exception("bash dispatch failed")
            return f"Error executing bash command: {e}"

    async def _run_terminal_command(self, __tools__: dict, command: str) -> str:
        """Run a shell command via Open Terminal and wait for its result.

        Open Terminal's ``run_command`` is asynchronous by default, but both
        ``run_command`` and ``get_process_status`` accept a server-side
        long-poll ``wait`` (≤300s) that returns early when the process exits.
        Prefer that; fall back to sleep-polling for older terminal builds.
        Path/query parameter names must match the OpenAPI spec exactly
        (``process_id``, not ``id``) — OpenWebUI's tool wrapper silently drops
        unknown parameters, which turns into 404 "Process not found"."""
        run_cmd = __tools__.get("run_command", {}).get("callable")
        if not run_cmd:
            return "Error: run_command callable is not available."
        timeout_s = max(5, int(self.valves.BASH_TOOL_TIMEOUT))
        deadline = time.monotonic() + timeout_s
        try:
            raw = await run_cmd(command=command, wait=min(timeout_s, 300))
        except TypeError:
            raw = await run_cmd(command=command)
        data = self._parse_terminal_payload(raw)

        # Synchronous path: server returned a final status (no id, or already done).
        if not isinstance(data, dict) or "id" not in data:
            return self._stringify_terminal_result(raw)
        status = data.get("status")
        if status and status != "running":
            return self._format_bash_process_result(data)

        process_id = data["id"]
        poll_cb = __tools__.get("get_process_status", {}).get("callable")
        if not poll_cb:
            # No polling tool available — surface the async descriptor as-is.
            return self._stringify_terminal_result(raw)

        delay = 0.25  # exponential backoff: 0.25 → 0.5 → 1 → 2 (cap)
        offset = 0
        collected: list = list(data.get("output") or [])
        last_status: dict = data
        use_wait = True
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                last_status["status"] = last_status.get("status") or "timeout"
                last_status["timed_out_after_s"] = timeout_s
                break
            try:
                if use_wait:
                    poll_raw = await poll_cb(
                        process_id=process_id, offset=offset, wait=min(remaining, 25)
                    )
                else:
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 2.0)
                    poll_raw = await poll_cb(process_id=process_id, offset=offset)
            except TypeError:
                # Older terminal builds may not accept `wait` / `offset`
                if use_wait:
                    use_wait = False
                    continue
                poll_raw = await poll_cb(process_id=process_id)
            poll_data = self._parse_terminal_payload(poll_raw)
            if not isinstance(poll_data, dict):
                last_status = {"id": process_id, "status": "unknown"}
                break
            if "status" not in poll_data and "output" not in poll_data:
                # Error payload (e.g. {"detail": "Process not found"}) — stop
                # instead of hammering the endpoint until the deadline.
                collected.append(json.dumps(poll_data))
                last_status = {"id": process_id, "status": "error"}
                break
            last_status = poll_data
            new_chunk = poll_data.get("output") or []
            if isinstance(new_chunk, list):
                collected.extend(new_chunk)
                offset = poll_data.get("next_offset", offset + len(new_chunk))
            if poll_data.get("status") and poll_data["status"] != "running":
                break

        last_status["output"] = collected
        return self._format_bash_process_result(last_status)

    async def _await_tool_approval(self, tool_call_data: dict) -> tuple[bool, Any]:
        """Ask the user to allow this tool call when approval mode is 'ask'.

        OpenWebUI 0.11.1 added human-in-the-loop tool approval, but it is enforced
        inside `utils/middleware.py` — i.e. only around OpenWebUI's OWN tool loop.
        A manifold that runs its own loop (this one) would execute tools
        unchallenged while the UI claims approval is on, so the gate is
        reproduced here at the single point where a tool coroutine is awaited.

        Returns ``(approved, denial_payload)``. The denial payload is fed back to
        Claude as this call's tool result, so a refusal reads as a normal
        (negative) result and the tool loop continues instead of stalling.
        """
        mode, event_call = TOOL_APPROVAL.get()
        if mode != "ask" or event_call is None:
            return True, None

        name = tool_call_data.get("name", "tool")
        try:
            args = json.dumps(
                tool_call_data.get("input") or {}, ensure_ascii=False, indent=2
            )
        except (TypeError, ValueError):
            args = str(tool_call_data.get("input"))
        if len(args) > 2000:
            args = args[:2000] + "\n… (truncated)"

        try:
            answer = await event_call(
                {
                    "type": "confirmation",
                    "data": {
                        "title": f"Run tool: {name}?",
                        "message": f"The model wants to call `{name}` with:\n\n```json\n{args}\n```",
                    },
                }
            )
        except Exception as e:
            # A broken approval channel must not silently turn into free
            # execution — that is the exact failure the gate exists to prevent.
            logger.warning("Tool approval prompt failed for '%s': %s", name, e)
            answer = False

        if answer:
            logger.info("Tool '%s' approved by user", name)
            return True, None

        logger.info("Tool '%s' denied by user", name)
        return False, json.dumps(
            {"error": f"The user denied permission to run '{name}'."},
            ensure_ascii=False,
        )

    async def _await_tool_task_result(
        self,
        tool_call_data: dict,
        awaitable: Awaitable[Any],
        timeout_s: Optional[float] = None,
    ) -> tuple[dict, Any, Optional[Exception]]:
        """Await a tool coroutine and keep its tool_use metadata attached.

        ``timeout_s`` overrides the generic TOOL_CALL_TIMEOUT valve — the Open
        Terminal bash/text_editor bridges poll internally up to
        BASH_TOOL_TIMEOUT and must not be killed early by the generic limit."""
        if timeout_s is None:
            timeout_s = getattr(self.valves, "TOOL_CALL_TIMEOUT", self.TOOL_CALL_TIMEOUT)

        approved, denial = await self._await_tool_approval(tool_call_data)
        if not approved:
            if hasattr(awaitable, "close"):
                awaitable.close()  # never started; release it without a warning
            return tool_call_data, denial, None

        try:
            result = await asyncio.wait_for(awaitable, timeout=max(1, float(timeout_s)))
            return tool_call_data, result, None
        except asyncio.TimeoutError:
            return tool_call_data, None, TimeoutError(
                f"tool call timed out after {timeout_s}s"
            )
        except Exception as e:
            return tool_call_data, None, e

    @staticmethod
    def _parse_terminal_payload(raw: Any) -> Any:
        """Normalize an Open Terminal callable result into a Python object.

        ``execute_tool_server`` returns ``(data, headers)``. ``data`` is usually
        already a dict, but some callables stringify their JSON. Handle both."""
        if isinstance(raw, tuple) and raw:
            raw = raw[0]
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except (TypeError, ValueError):
                return raw
        return raw

    @staticmethod
    def _format_bash_process_result(data: dict) -> str:
        """Render a completed Open Terminal process descriptor as a readable
        text payload for Claude. Concatenates ``output`` lines (which may be
        ``{stream: stdout|stderr, data: "..."}`` objects or plain strings) and
        appends exit metadata."""
        chunks_out: list[str] = []
        chunks_err: list[str] = []
        for entry in data.get("output") or []:
            if isinstance(entry, dict):
                stream = entry.get("stream") or entry.get("type") or "stdout"
                text = entry.get("data") or entry.get("text") or ""
                (chunks_err if stream == "stderr" else chunks_out).append(str(text))
            else:
                chunks_out.append(str(entry))
        stdout = "".join(chunks_out).rstrip()
        stderr = "".join(chunks_err).rstrip()

        parts: list[str] = []
        if stdout:
            parts.append(stdout)
        if stderr:
            parts.append(f"[stderr]\n{stderr}")

        meta_bits: list[str] = []
        status = data.get("status")
        # Open Terminal reports success as "done"; older builds may use "completed".
        if status and status not in ("done", "completed"):
            meta_bits.append(f"status={status}")
        exit_code = data.get("exit_code")
        if exit_code not in (None, 0):
            meta_bits.append(f"exit_code={exit_code}")
        if data.get("truncated"):
            meta_bits.append("truncated=true")
        if "timed_out_after_s" in data:
            meta_bits.append(f"timed_out_after_s={data['timed_out_after_s']}")
        if meta_bits:
            parts.append("[" + " ".join(meta_bits) + "]")

        if not parts:
            return "(no output)"
        return "\n".join(parts)

    async def _dispatch_text_editor_tool(
        self,
        tool_input: dict,
        __tools__: dict,
        emitter: Optional[Callable] = None,
    ) -> str:
        """Bridge native text_editor (str_replace_based_edit_tool) calls to
        Open Terminal's write_file / replace_file_content + run_command fallback
        for view/insert operations.
        """
        try:
            command = tool_input.get("command", "")
            path = tool_input.get("path", "")
            run_cmd = __tools__.get("run_command", {}).get("callable")

            if command == "view":
                # Prefer run_command with sed/cat -n; directory listings use ls.
                if not run_cmd:
                    return "Error: run_command callable required for `view`."
                view_range = tool_input.get("view_range")
                # Escape path minimally for shell
                safe_path = path.replace("'", "'\\''")
                if view_range and isinstance(view_range, list) and len(view_range) == 2:
                    start, end = view_range
                    if end == -1:
                        shell = f"sed -n '{int(start)},$p' '{safe_path}' | nl -ba -s': ' -w1"
                    else:
                        shell = f"sed -n '{int(start)},{int(end)}p' '{safe_path}' | nl -ba -s': ' -v{int(start)} -w1"
                else:
                    # Detect directory vs file, fall back to ls for dirs
                    shell = (
                        f"if [ -d '{safe_path}' ]; then ls -la '{safe_path}'; "
                        f"else cat -n '{safe_path}'; fi"
                    )
                text = await self._run_terminal_command(__tools__, shell)
                # view is read-only → open the file preview in the panel.
                await self._emit_terminal_event(emitter, "display_file", path)
                max_chars = self.valves.TEXT_EDITOR_MAX_CHARACTERS
                if len(text) > max_chars:
                    text = text[:max_chars] + f"\n…[truncated to {max_chars} chars]"
                return text

            elif command == "str_replace":
                replace_cb = __tools__.get("replace_file_content", {}).get("callable")
                if not replace_cb:
                    return "Error: replace_file_content callable is not available."
                old_str = tool_input.get("old_str", "")
                new_str = tool_input.get("new_str", "")
                result = await replace_cb(path=path, old_str=old_str, new_str=new_str)
                await self._emit_terminal_event(emitter, "replace_file_content", path)
                return self._stringify_terminal_result(result)

            elif command == "create":
                write_cb = __tools__.get("write_file", {}).get("callable")
                if not write_cb:
                    return "Error: write_file callable is not available."
                file_text = tool_input.get("file_text", "")
                result = await write_cb(path=path, content=file_text)
                await self._emit_terminal_event(emitter, "write_file", path)
                return self._stringify_terminal_result(result)

            elif command == "insert":
                # Implement via run_command: read → splice → write back.
                if not run_cmd:
                    return "Error: run_command callable required for `insert`."
                insert_line = int(tool_input.get("insert_line", 0))
                insert_text = tool_input.get("insert_text", "")
                payload = json.dumps({
                    "path": path,
                    "line": insert_line,
                    "text": insert_text,
                }, ensure_ascii=False)
                # Embed the JSON inside a python3 heredoc; parse with json.loads
                # so newlines/quotes in payload are safe.
                shell = (
                    "python3 <<'PYEOF'\n"
                    "import json\n"
                    f"d=json.loads({json.dumps(payload)})\n"
                    "p=d['path']; ln=d['line']; t=d['text']\n"
                    "with open(p,'r',encoding='utf-8') as f: lines=f.readlines()\n"
                    "ins=t if t.endswith('\\n') else t+'\\n'\n"
                    "lines.insert(ln, ins)\n"
                    "with open(p,'w',encoding='utf-8') as f: f.writelines(lines)\n"
                    "print(f'Inserted {len(ins.splitlines())} line(s) at position {ln} in {p}')\n"
                    "PYEOF"
                )
                result_text = await self._run_terminal_command(__tools__, shell)
                # insert mutates the file → treat as a content replacement refresh.
                await self._emit_terminal_event(emitter, "replace_file_content", path)
                return result_text

            else:
                return f"Error: unsupported text_editor command '{command}'."
        except Exception as e:
            logger.exception("text_editor dispatch failed")
            return f"Error in text_editor.{tool_input.get('command', '?')}: {e}"

    def _format_server_tool_use_block(
        self,
        tool_name: str,
        tool_use_id: str,
        tool_input: Any,
        display_body: str = "",
        *,
        result_payload: Optional[Any] = None,
        result_block_type: str = "",
        result_summary: str = "",
        result_display_body: str = "",
    ) -> str:
        """Persist a server_tool_use block (web_search, web_fetch, code_execution…)
        as collapsible <details> HTML carrying the opaque payload in a
        ``data-payload-b64`` attribute. Needed so the block can be
        reconstructed byte-exact on the next turn's API replay — otherwise
        thinking-block positions shift and the API rejects the assistant
        message with "thinking blocks cannot be modified".

        If ``result_payload`` + ``result_block_type`` are provided, the carrier
        ALSO embeds the matching *_tool_result payload via ``data-result-payload-b64``
        and ``data-result-block-type``. This lets a single visible collapsible
        represent BOTH the tool call and its result (API replay still emits
        two separate blocks in their original order).
        """
        payload = {
            "type": "server_tool_use",
            "id": tool_use_id,
            "name": tool_name,
            "input": tool_input if isinstance(tool_input, (dict, list)) else {},
        }
        payload_b64 = self._encode_block_payload(payload)
        icon = {
            "web_search": "🔍",
            "web_fetch": "🌐",
            "tool_search_tool_regex": "🧰",
            "tool_search_tool_bm25": "🧰",
            "advisor": "🧑‍⚖️",
        }.get(tool_name, "🔧")
        hint = ""
        if isinstance(tool_input, dict):
            hint = tool_input.get("query") or tool_input.get("url") or ""
            if not hint:
                # tool_search_tool_regex uses "patterns" (list),
                # tool_search_tool_bm25 uses "queries" (list).
                for list_key in ("patterns", "queries"):
                    val = tool_input.get(list_key)
                    if isinstance(val, list) and val:
                        hint = ", ".join(str(v) for v in val[:3])
                        break
        default_summary = f"{icon} {tool_name}"
        if hint:
            default_summary += f": {str(hint)[:120]}"

        result_attrs = ""
        result_payload_dict = (
            {
                "type": result_block_type,
                "tool_use_id": tool_use_id,
                "content": result_payload,
            }
            if result_payload is not None and result_block_type
            else None
        )

        if self._is_block_hidden(tool_name):
            # Hidden: the whole <details> goes, not just its body. The status
            # emitter carries the user-facing information for this turn; the
            # carrier below only has to survive replay.
            blocks = [payload] + ([result_payload_dict] if result_payload_dict else [])
            return self._format_hidden_block(blocks, tool_use_id)

        if result_payload_dict is not None:
            result_payload_b64 = self._encode_block_payload(result_payload_dict)
            # NOTE: attribute key MUST NOT contain "type=" as a substring.
            # marked's attribute tokenizer `(\w+)="(.*?)"` greedily picks up
            # `type="..."` anywhere in the tag and overwrites the primary
            # `type="tool_calls"`. Using `data-result-kind` instead of
            # `data-result-block-type` avoids that collision.
            result_attrs = (
                f' data-result-kind="{html.escape(result_block_type)}"'
                f' data-result-payload-b64="{result_payload_b64}"'
            )
            summary_text = result_summary or default_summary
            body_src = result_display_body or display_body
        else:
            summary_text = default_summary
            body_src = display_body

        # NOTE: type="tool_calls" (not "server_tool_use") is intentional —
        # OpenWebUI's Svelte parser only groups consecutive <details> into a
        # single "Exploring/Explored" bubble when each one carries
        # type ∈ {tool_calls, reasoning, code_interpreter}. A custom type
        # between reasoning and code_interpreter would break the group.
        # data-block-kind disambiguates our carriers from regular OpenWebUI
        # tool_calls UI artifacts (which we still strip on replay).
        #
        # CRITICAL: empty body MUST NOT produce a blank line between
        # <summary> and </details>. Markdown tokenizer treats `\n\n` as
        # block break and splits the adjacent <details> out of the group.
        body_part = f"{body_src}\n" if body_src else ""
        return (
            f'<details type="tool_calls" done="true"'
            f' data-block-kind="server_tool_use"'
            f' data-tool-name="{html.escape(tool_name)}"'
            f' data-tool-use-id="{html.escape(tool_use_id)}"'
            f' data-payload-b64="{payload_b64}"'
            f'{result_attrs}>\n'
            f'<summary>{html.escape(summary_text)}</summary>\n'
            f"{body_part}"
            f"</details>\n"
        )

    def _format_server_tool_result_block(
        self,
        block_type: str,
        tool_use_id: str,
        content_payload: Any,
        display_body: str = "",
        summary_text: str = "",
    ) -> str:
        """Persist a *_tool_result block (web_search/web_fetch/code_execution
        results) as collapsible <details> HTML with opaque payload in
        ``data-payload-b64``. See _format_server_tool_use_block for rationale.
        """
        payload = {
            "type": block_type,
            "tool_use_id": tool_use_id,
            "content": content_payload,
        }
        if self._is_block_hidden(block_type):
            return self._format_hidden_block([payload], tool_use_id)
        payload_b64 = self._encode_block_payload(payload)
        summary = summary_text or block_type
        # NOTE: type="tool_calls" — see _format_server_tool_use_block.
        # Empty body avoids `\n\n` which breaks markdown grouping.
        body_part = f"{display_body}\n" if display_body else ""
        return (
            f'<details type="tool_calls" done="true"'
            f' data-block-kind="server_tool_result"'
            f' data-block-type="{html.escape(block_type)}"'
            f' data-tool-use-id="{html.escape(tool_use_id)}"'
            f' data-payload-b64="{payload_b64}">\n'
            f"<summary>{html.escape(summary)}</summary>\n"
            f"{body_part}"
            f"</details>\n"
        )

    def _serialize_tool_result_content(self, result_block: Any) -> Optional[Any]:
        """Best-effort serialization of a Claude server-tool result payload
        into a JSON-serializable form. Returns None if nothing to persist."""
        if result_block is None:
            return None
        if hasattr(result_block, "model_dump"):
            try:
                return result_block.model_dump(exclude_none=True, mode="json")
            except Exception:
                try:
                    return result_block.model_dump(exclude_none=True)
                except Exception:
                    return None
        if isinstance(result_block, (dict, list, str, int, float, bool)):
            return result_block
        return None

    async def _persist_server_tool_result(
        self,
        content_block: Any,
        block_type: str,
        emit_message_delta,
        summary_text: str = "",
    ) -> None:
        """Emit a hidden <details type="server_tool_result"> carrying the full
        API payload, so the next turn can reconstruct the exact assistant
        block sequence. Required alongside the visible display block
        (<details type="code_interpreter">) which is stripped on replay."""
        tool_use_id = getattr(content_block, "tool_use_id", "") or ""
        if not tool_use_id:
            return
        result_block = getattr(content_block, "content", None)
        serialized = self._serialize_tool_result_content(result_block)
        if serialized is None:
            serialized = {}
        persisted = self._format_server_tool_result_block(
            block_type=block_type,
            tool_use_id=tool_use_id,
            content_payload=serialized,
            display_body="",
            summary_text=summary_text or block_type,
        )
        await emit_message_delta(persisted)

    def _format_compaction_block(self, summary: str) -> str:
        """Format a compaction block as a collapsible <details> for display/storage."""
        if self._is_block_hidden("compaction"):
            return self._format_hidden_block([{"type": "compaction", "content": summary}])
        return (
            '<details type="compaction">\n'
            "<summary>📦 Context Summary</summary>\n\n"
            f"{summary}\n\n"
            "</details>\n\n"
        )

    @staticmethod
    def _append_block_to_text(text: str, block: str) -> str:
        """Append a rendered block with a safe markdown/html separator."""
        if not text:
            return block
        if not block:
            return text
        if text.endswith(("\n", "\r")) or block.startswith(("\n", "\r")):
            return text + block
        return f"{text}\n{block}"

    def _format_thinking_block(
        self, content: str, duration: Optional[float] = None,
        signature: Optional[str] = None,
    ) -> str:
        """Format a thinking block with OpenWebUI native <details type='reasoning'> format.

        This produces the same format that OpenWebUI's built-in pipes use,
        enabling proper spinner, localized text, and collapsible behavior.

        ``signature`` (when provided) is persisted as an HTML attribute so the
        block can be reconstructed as a valid Claude API ``thinking`` block on
        subsequent turns. The signature is an opaque server-issued token that
        must be sent back byte-exact; without it, the API rejects replayed
        thinking blocks with a 400 error.
        """
        if SLIM_OUTPUT.get():
            # A sub-agent's reasoning is not part of its answer. The parent only
            # needs the conclusion, and the signature is worthless here because
            # the block is never replayed.
            return ""

        # Escape content and add > prefix per line (OpenWebUI quota block style)
        escaped_lines = "\n".join(
            f"> {html.escape(line)}" if not line.startswith(">") else html.escape(line)
            for line in content.splitlines()
        )

        sig_attr = f' data-signature="{html.escape(signature)}"' if signature else ""

        if duration is not None:
            duration_int = int(duration)
            return (
                f'<details type="reasoning" done="true" duration="{duration_int}"{sig_attr}>\n'
                f"<summary>Thought for {duration_int} seconds</summary>\n"
                f"{escaped_lines}\n"
                f"</details>\n"
            )
        else:
            return (
                f'<details type="reasoning" done="false"{sig_attr}>\n'
                f"<summary>Thinking…</summary>\n"
                f"{escaped_lines}\n"
                f"</details>\n"
            )

    def _format_tool_result_block(
        self,
        tool_call_id: str,
        tool_name: str,
        tool_input: dict,
        tool_output: str,
        is_error: bool = False,
        done: bool = True,
        embeds: list = None,
        files: list = None,
    ) -> str:
        """Format a tool result block with OpenWebUI native <details type='tool_calls'> format.

        This produces the same format that OpenWebUI's built-in pipes use,
        enabling proper spinner, localized text, and collapsible behavior.

        Args:
            done: If True, shows "Tool Executed". If False, shows "Executing..." with spinner.
            embeds: List of embed content (HTML strings, URLs) from process_tool_result.
            files: List of file dicts from process_tool_result.
        """
        if SLIM_OUTPUT.get():
            # The tool ran; only its effect on the answer matters to the parent
            # agent. Arguments, raw result, embeds and file chips are markup a
            # human would expand -- nobody will.
            return ""

        # Escape arguments for HTML attribute
        escaped_args = (
            html.escape(json.dumps(tool_input, ensure_ascii=False))
            if tool_input
            else ""
        )

        done_str = "true" if done else "false"
        summary = "Tool Executed" if done else "Executing..."
        error_attr = ' error="true"' if is_error and done else ""

        if done:
            # Escape result for HTML attribute
            try:
                if isinstance(tool_output, str):
                    try:
                        parsed = json.loads(tool_output)
                        escaped_result = html.escape(
                            json.dumps(parsed, ensure_ascii=False)
                        )
                    except (json.JSONDecodeError, ValueError):
                        escaped_result = html.escape(
                            json.dumps(tool_output, ensure_ascii=False)
                        )
                else:
                    escaped_result = html.escape(
                        json.dumps(tool_output, ensure_ascii=False)
                    )
            except Exception:
                escaped_result = html.escape(
                    json.dumps(str(tool_output), ensure_ascii=False)
                )

            escaped_embeds = (
                html.escape(json.dumps(embeds, ensure_ascii=False))
                if embeds
                else ""
            )

            return (
                f'<details type="tool_calls" done="{done_str}" id="{html.escape(tool_call_id)}" name="{html.escape(tool_name)}" '
                f'arguments="{escaped_args}" result="{escaped_result}" '
                f'files="{html.escape(json.dumps(files)) if files else ""}" '
                f'embeds="{escaped_embeds}"{error_attr}>\n'
                f"<summary>{summary}</summary>\n"
                f"</details>\n"
            )
        else:
            # In-progress tool call - no result yet
            return (
                f'<details type="tool_calls" done="{done_str}" id="{html.escape(tool_call_id)}" name="{html.escape(tool_name)}" '
                f'arguments="{escaped_args}">\n'
                f"<summary>{summary}</summary>\n"
                f"</details>\n"
            )

    def _format_code_execution_block(
        self,
        code: str,
        language: str = "python",
        done: bool = False,
        duration: float = None,
        stdout: str = "",
        stderr: str = "",
        return_code: int = None,
        download_links: list = None,
        tool_calls_info: list = None,
    ) -> str:
        """Format code execution as <details type="code_interpreter"> matching OpenWebUI native format.

        Uses the same HTML structure as OpenWebUI's built-in code_interpreter,
        giving us spinner, Analyzing.../Analyzed transitions, and output display for free.
        """
        if self._is_block_hidden("code_execution"):
            # Reached directly by the code-execution handlers rather than through
            # the server-tool formatters, so it needs its own guard. Covers both
            # SLIM_OUTPUT (sub-agent runs) and an explicit HIDE_BLOCKS opt-out —
            # without this, hiding "code_execution" silently did nothing.
            return ""

        done_str = "true" if done else "false"
        summary = "Analyzed" if done else "Analyzing…"

        # Build display content (code block inside details body)
        display = f"```{language}\n{code}\n```" if code else ""

        # Build output JSON for the output attribute
        # CodeBlock.svelte expects {stdout, stderr, result} keys
        output_data = {}
        if stdout:
            output_data["stdout"] = stdout
        if stderr:
            output_data["stderr"] = stderr
        # Build a result summary for tool calls and other info
        result_parts = []
        if return_code is not None and return_code != 0:
            result_parts.append(f"Exit code: {return_code}")
        if tool_calls_info:
            for tc in tool_calls_info:
                name = tc.get("name", "?")
                res = tc.get("result", "")[:200]
                error = " ❌" if tc.get("is_error") else ""
                result_parts.append(f"🔧 {name}: {res}{error}")
        if download_links:
            result_parts.append("Files: " + ", ".join(download_links))
        if result_parts:
            output_data["result"] = "\n".join(result_parts)

        # Build attributes
        attrs = f'type="code_interpreter" done="{done_str}"'
        if duration is not None and done:
            attrs += f' duration="{duration:.1f}"'
        if output_data:
            output_json = json.dumps(output_data, ensure_ascii=False)
            attrs += f' output="{html.escape(output_json)}"'

        return f"<details {attrs}>\n<summary>{summary}</summary>\n{display}\n</details>\n"

    async def _emit_code_execution_source(
        self,
        emit_event_local: Callable,
        code: str,
        language: str,
        stdout: str = "",
        stderr: str = "",
        return_code: int = None,
        download_links: list = None,
        tool_calls_info: list = None,
    ) -> None:
        """Emit code execution output as a source/citation event for the citation panel."""
        output_parts = []
        if stdout:
            output_parts.append(f"stdout:\n{stdout}")
        if stderr:
            output_parts.append(f"stderr:\n{stderr}")
        if return_code is not None and return_code != 0:
            output_parts.append(f"Return code: {return_code}")
        if download_links:
            output_parts.append("Files:\n" + "\n".join(download_links))

        output_text = "\n\n".join(output_parts) if output_parts else "(no output)"

        # Build a concise code summary for the source name
        code_preview = code[:80].replace("\n", " ").strip() + "..." if code and len(code) > 80 else (code or "").replace("\n", " ").strip()
        source_name = f"💻 {language}: {code_preview}" if code_preview else f"💻 Code Execution ({language})"

        source_data = {
            "source": {
                "name": source_name,
            },
            "document": [output_text],
            "metadata": [
                {
                    "source": f"code_execution_{language}_{id(code)}",
                    "name": source_name,
                }
            ],
        }

        await emit_event_local({"type": "source", "data": source_data})

    @staticmethod
    def _try_parse_partial_json(buffer: str):
        """Try to parse partial JSON by attempting various closing strategies.

        During input_json_delta streaming, the input JSON arrives incrementally.
        This attempts to close the partial JSON to extract a parseable value
        for live UI updates. Returns parsed dict/list/value on success, None on failure.
        """
        if not buffer or not buffer.strip():
            return None
        # Try as-is first (might already be complete)
        for suffix in ("", "}", '"}', '"}}', "]}"):
            try:
                return json.loads(buffer + suffix)
            except (json.JSONDecodeError, ValueError):
                continue
        return None
