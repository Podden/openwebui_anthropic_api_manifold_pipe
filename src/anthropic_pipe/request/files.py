"""Compiled Pipe method group: file handling (native PDF documents, Anthropic Files API upload, Skills validation, code_execution file download). Compiled into class Pipe."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class PipeRequestFilesMethods:
    async def _get_pdf_base64_from_file_id(self, file_id: str) -> Optional[tuple[str, str]]:
        """
        Read a PDF file from storage and return base64 encoded data.

        Args:
            file_id: The OpenWebUI file ID

        Returns:
            tuple[str, str]: (base64_data, filename) or None if not available
        """
        if not FILES_AVAILABLE:
            logger.warning("Files/Storage modules not available for PDF native upload")
            return None

        try:
            file = await Files.get_file_by_id(file_id)
            if not file:
                logger.warning(f"File not found: {file_id}")
                return None

            # Check if it's a PDF
            content_type = file.meta.get("content_type", "")
            filename = file.meta.get("name", file.filename)

            if content_type != "application/pdf" and not filename.lower().endswith(
                ".pdf"
            ):
                logger.debug(f"File {file_id} is not a PDF: {content_type}")
                return None

            # Get file path from storage
            file_path = Storage.get_file(file.path)
            file_path = Path(file_path)

            if not file_path.is_file():
                logger.warning(f"PDF file not found on disk: {file_path}")
                return None

            # Read and encode the PDF
            with open(file_path, "rb") as pdf_file:
                pdf_data = pdf_file.read()
                encoded_data = base64.b64encode(pdf_data).decode("utf-8")

            # Check size limits (Anthropic has 32MB request limit, be conservative)
            MAX_PDF_SIZE = 25 * 1024 * 1024  # 25 MB
            if len(pdf_data) > MAX_PDF_SIZE:
                logger.warning(
                    f"PDF too large for native upload: {len(pdf_data)} bytes"
                )
                return None

            logger.debug(
                f"Successfully encoded PDF: {filename} ({len(pdf_data)} bytes)"
            )
            return (encoded_data, filename)

        except Exception as e:
            logger.error(f"Error reading PDF file {file_id}: {e}")
            return None

    @staticmethod
    def _collect_file_ids(value: Any) -> List[str]:
        """Recursively collect file/id-like identifiers from a nested dict/list structure."""
        ids: List[str] = []
        if isinstance(value, dict):
            for key in ("id", "file_id"):
                file_id_value = value.get(key)
                if isinstance(file_id_value, str) and file_id_value:
                    ids.append(file_id_value)
            for key in ("file", "meta", "metadata"):
                nested = value.get(key)
                if nested is not None:
                    ids.extend(Pipe._collect_file_ids(nested))
        elif isinstance(value, list):
            for item in value:
                ids.extend(Pipe._collect_file_ids(item))
        return ids

    @classmethod
    def _resolve_full_context_anchors(
        cls,
        marker_kind: str,
        accept,
        __files__: Optional[List[Dict[str, Any]]],
        previous_marker_metadata: List[str],
        processed_messages: List[Dict[str, Any]],
        raw_messages: Optional[List[Dict[str, Any]]] = None,
    ) -> tuple[Dict[str, int], Dict[str, str]]:
        """Decide which user message each full-context file belongs to.

        Shared by the native-PDF path and the plain-text path: both must pin a
        file to the message it was attached to, because a block that moves to
        the newest message every turn rewrites the cache prefix every turn.

        Anchor priority per file:
          1) a marker persisted by an earlier pipe turn,
          2) ownership in OpenWebUI's raw ``message.files``,
          3) the latest user message, for genuinely new uploads.

        Files known only from prior markers are re-included, because OpenWebUI
        does not reliably re-send full-context files in ``__files__`` on
        follow-up turns; dropping them would make the block vanish mid-history.

        ``accept`` filters by filename (PDF vs. everything else). Returns
        ``(file_id -> anchor_msg_idx, file_id -> filename)``, both ordered by
        (anchor, file_id) so the rendered block order cannot drift between turns
        just because the underlying dicts were populated from different sources.
        """
        prior_msg_idx: Dict[str, int] = {}
        prior_filename: Dict[str, str] = {}
        for entry in previous_marker_metadata or []:
            parts = entry.split(":", 2)
            if len(parts) < 3 or parts[1] != marker_kind:
                continue
            try:
                msg_idx = int(parts[0])
            except ValueError:
                continue
            decoded = unquote(parts[2])
            file_id_part, _, fname_part = decoded.partition(":")
            if file_id_part:
                prior_msg_idx[file_id_part] = msg_idx
                if fname_part:
                    prior_filename[file_id_part] = fname_part

        user_msg_count = sum(1 for m in processed_messages if m.get("role") == "user")
        latest_user_msg_idx = max(0, user_msg_count - 1)

        raw_file_msg_idx: Dict[str, int] = {}
        if raw_messages:
            raw_user_msg_idx = -1
            for raw_msg in raw_messages:
                if not isinstance(raw_msg, dict) or raw_msg.get("role") != "user":
                    continue
                raw_user_msg_idx += 1
                for file_id in cls._collect_file_ids(raw_msg.get("files")):
                    raw_file_msg_idx.setdefault(file_id, raw_user_msg_idx)

        anchor: Dict[str, int] = {}
        filename: Dict[str, str] = {}

        for file in __files__ or []:
            if file.get("type") != "file" or file.get("context") != "full":
                continue
            file_id = file.get("id")
            if not file_id:
                continue
            file_name = file.get("name", "")
            if not accept(file_name):
                continue
            anchor[file_id] = prior_msg_idx.get(
                file_id, raw_file_msg_idx.get(file_id, latest_user_msg_idx)
            )
            filename[file_id] = file_name

        for file_id, msg_idx in prior_msg_idx.items():
            if file_id in anchor:
                continue
            anchor[file_id] = msg_idx
            if file_id in prior_filename:
                filename[file_id] = prior_filename[file_id]

        ordered = sorted(anchor.items(), key=lambda kv: (kv[1], kv[0]))
        return (
            {fid: idx for fid, idx in ordered},
            {fid: filename[fid] for fid, _ in ordered if fid in filename},
        )

    async def _get_file_text_from_file_id(self, file_id: str) -> Optional[str]:
        """Return the plain text OpenWebUI extracted for a file, or None.

        This is the same content OpenWebUI itself injects into its ``<context>``
        template for a full-context file, so reading it here changes what the
        model sees only in position, not in substance -- and it keeps working on
        later turns, when the file is gone from ``__files__``.
        """
        if not FILES_AVAILABLE:
            return None
        try:
            file = await Files.get_file_by_id(file_id)
        except Exception as e:
            logger.warning(f"Full-context text: could not load file {file_id}: {e}")
            return None
        if not file:
            return None
        data = getattr(file, "data", None)
        content = data.get("content") if isinstance(data, dict) else None
        if isinstance(content, str) and content.strip():
            return content.strip()
        return None

    async def _get_full_context_texts(
        self,
        __files__: Optional[List[Dict[str, Any]]],
        previous_marker_metadata: List[str],
        processed_messages: List[Dict[str, Any]],
        raw_messages: Optional[List[Dict[str, Any]]] = None,
        exclude_pdfs: bool = True,
    ) -> tuple[Dict[int, List[Dict[str, Any]]], List[str], List[str]]:
        """Turn non-native full-context uploads into anchored, cacheable text blocks.

        A file uploaded with Full Context arrives inside OpenWebUI's
        ``### Task: ... <context><source>...`` template, merged into the last
        user message. The cache-control pass has to treat that template as
        volatile -- for retrieved RAG chunks it genuinely is, they are re-ranked
        against every new question -- so the breakpoint lands *before* it and the
        file is re-sent uncached on every single turn. For a 2 MB EPUB that is
        the whole book, every turn.

        A full-context file is not volatile, though: it is the entire file, the
        same bytes each turn. So it gets the same treatment PDFs already get --
        anchored to the user message it was attached to, placed ahead of the
        prose, and cut out of the RAG template by the caller. From there the
        existing breakpoint covers it and the book is written to cache once.

        Returns ``(anchor_msg_idx -> blocks, markers, filenames)``; the filenames
        are what the caller must strip from the RAG template.
        """
        blocks_by_user_msg: Dict[int, List[Dict[str, Any]]] = {}
        markers: List[str] = []
        filenames: List[str] = []

        if not FILES_AVAILABLE:
            return blocks_by_user_msg, markers, filenames

        anchors, names = self._resolve_full_context_anchors(
            "fctx",
            lambda name: not (exclude_pdfs and name.lower().endswith(".pdf")),
            __files__,
            previous_marker_metadata,
            processed_messages,
            raw_messages,
        )

        for file_id, anchor_msg_idx in anchors.items():
            content = await self._get_file_text_from_file_id(file_id)
            if not content:
                continue
            title = names.get(file_id) or file_id
            blocks_by_user_msg.setdefault(anchor_msg_idx, []).append(
                {
                    "type": "text",
                    "text": f'<source name="{title}">\n{content}\n</source>',
                }
            )
            filenames.append(title)
            markers.append(
                self._create_metadata_marker(
                    "fctx", f"{file_id}:{title}", messagenum=anchor_msg_idx
                )
            )

        if filenames:
            logger.debug(
                f"📎 Full-context text: anchored {len(filenames)} file(s) as cacheable blocks"
            )
        return blocks_by_user_msg, markers, filenames

    async def _get_full_context_pdfs(
        self,
        __files__: Optional[List[Dict[str, Any]]],
        previous_marker_metadata: List[str],
        processed_messages: List[Dict[str, Any]],
        raw_messages: Optional[List[Dict[str, Any]]] = None,
    ) -> tuple[Dict[int, List[Dict[str, Any]]], List[str]]:
        """
        Extract PDFs from __files__ that should be uploaded as native documents.

        Each PDF is anchored to the user-message it was first attached to so that
        the byte-prefix of the conversation stays cache-stable across turns. New
        PDFs are anchored to the most recent user message; PDFs that were already
        anchored on previous turns are restored at the same anchor index by
        re-loading the base64 from disk.

        Args:
            __files__: List of file objects from OpenWebUI (current turn).
            previous_marker_metadata: Marker entries extracted from the prior
                assistant message. Each entry is "msg_idx:id:url_encoded_value".
            processed_messages: Full message list — used to count user messages
                and decide where to anchor new PDFs.
            raw_messages: Original OpenWebUI messages. Historical user messages
                can carry a `files` list, which is the most reliable source for
                restoring the original PDF attachment turn when OpenWebUI keeps
                passing old full-context files in `__files__`.

        Returns:
            tuple:
              - dict[int, list[dict]] mapping user_msg_index → list of document
                blocks to prepend to that message's content.
              - list of metadata markers (already formatted strings) that should
                be appended to the next assistant text response.
        """
        blocks_by_user_msg: Dict[int, List[Dict[str, Any]]] = {}
        markers: List[str] = []

        if not FILES_AVAILABLE:
            return blocks_by_user_msg, markers

        pdf_anchor, pdf_filename = self._resolve_full_context_anchors(
            "pdf",
            lambda name: name.lower().endswith(".pdf"),
            __files__,
            previous_marker_metadata,
            processed_messages,
            raw_messages,
        )

        for file_id, anchor_msg_idx in pdf_anchor.items():
            # Re-load base64 every turn (Anthropic native PDF blocks have no
            # file-id reuse; the bytes must be present for the cache prefix to
            # remain stable)
            result = await self._get_pdf_base64_from_file_id(file_id)
            if not result:
                continue
            encoded_data, filename = result
            title = pdf_filename.get(file_id) or filename

            blocks_by_user_msg.setdefault(anchor_msg_idx, []).append(
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": encoded_data,
                    },
                    "title": title,
                }
            )
            markers.append(
                self._create_metadata_marker(
                    "pdf", f"{file_id}:{title}", messagenum=anchor_msg_idx
                )
            )

        return blocks_by_user_msg, markers

    async def _generate_file_download_link(
        self,
        file_id: str,
        api_key: str,
        user_id: str,
    ) -> str:
        """Download file from Anthropic Files API, save to OpenWebUI, return markdown link."""
        try:
            from anthropic import AsyncAnthropic
            import hashlib
            import io
            import uuid

            client = self._build_anthropic_client(api_key)

            # Get file metadata first
            file_meta = await client.beta.files.retrieve_metadata(file_id=file_id)
            filename = getattr(file_meta, "filename", file_id) or file_id

            # Download file content (async binary response — .read() is a coroutine)
            response = await client.beta.files.download(file_id=file_id)
            content = await response.read()

            # Save to OpenWebUI storage. upload_file(file: BinaryIO, filename, tags)
            # returns a (contents, file_path) tuple; tags is required.
            owui_file_id = str(uuid.uuid4())
            storage_filename = f"code_exec_{owui_file_id}_{filename}"
            _, file_path = Storage.upload_file(io.BytesIO(content), storage_filename, {})

            # Create OpenWebUI file record
            file_hash = hashlib.sha256(content).hexdigest()
            await Files.insert_new_file(
                user_id=user_id,
                form_data=type("FileForm", (), {
                    "model_dump": lambda self_: {
                        "id": owui_file_id,
                        "hash": file_hash,
                        "filename": filename,
                        "path": file_path,
                        "data": {},
                        "meta": {
                            "content_type": getattr(file_meta, "mime_type", "application/octet-stream"),
                            "size": len(content),
                            "source": "anthropic_code_execution",
                            "anthropic_file_id": file_id,
                        },
                    }
                })(),
            )

            # Return markdown download link
            base_url = os.environ.get("WEBUI_URL", "")
            download_url = f"{base_url}/api/v1/files/{owui_file_id}/content"
            return f"[📥 {filename}]({download_url})"

        except Exception as e:
            logger.error(f"Failed to download file {file_id}: {e}")
            return f"⚠️ Failed to download file {file_id}"

    async def _process_files_api_data(
        self,
        __files__: Optional[List[Dict[str, Any]]],
        __event_emitter__: Callable[[Dict[str, Any]], Awaitable[None]],
        processed_messages: List[Dict[str, Any]],
    ) -> tuple[Dict[int, List[Dict[str, Any]]], List[str]]:
        """
        Process files for Anthropic Files API using container_upload.

        Uploads files to Anthropic and caches the file_id in OpenWebUI file metadata.
        Tracks which user message each file belongs to for correct positioning.

        Returns:
            tuple: (
                Dict mapping user_msg_number → list of container_upload blocks,
                List of filenames that were processed (for RAG source removal)
            )
        """
        blocks_by_user_msg: Dict[int, List[Dict[str, Any]]] = {}
        processed_filenames: List[str] = []
        status_cls = globals().get("StatusEmitter")
        status = status_cls(__event_emitter__) if status_cls else None

        async def emit_status(description: str, *, done: bool = False) -> None:
            """Emit a status update via StatusEmitter if available, else fall back to a raw status event."""
            if status:
                if done:
                    await status.complete(description)
                else:
                    await status.activity(description)
                return
            await self.emit_event(
                {"type": "status", "data": {"description": description, "done": done}},
                __event_emitter__,
            )

        async def emit_notification(content: str, *, type: str = "warning") -> None:
            """Emit a notification via StatusEmitter if available, else fall back to a raw notification event."""
            if status and hasattr(status, "notification"):
                await status.notification(content, type=type)
                return
            await self.emit_event(
                {"type": "notification", "data": {"type": type, "content": content}},
                __event_emitter__,
            )

        if not __files__:
            return blocks_by_user_msg, processed_filenames
        if not FILES_AVAILABLE:
            await emit_status("Files API unavailable", done=True)
            await emit_notification(
                "Anthropic Files API mode was requested, but OpenWebUI Files/Storage support is unavailable in this runtime."
            )
            return blocks_by_user_msg, processed_filenames

        import io

        # Count user messages to determine "current" position for new files
        user_msg_count = sum(1 for m in processed_messages if m["role"] == "user")
        current_user_msg_num = max(0, user_msg_count - 1)  # 0-based

        client = None
        try:
            from anthropic import AsyncAnthropic
            client = self._build_anthropic_client(self.valves.ANTHROPIC_API_KEY)
        except ImportError:
            logger.warning("Anthropic SDK not available for file upload")
            return blocks_by_user_msg, processed_filenames

        for file in __files__:
            # Skip non-file entries (RAG chunks, knowledge base refs, etc.)
            if (
                file.get("type") != "file"
                or file.get("context") != "full"
                or file.get("collection_name")
                or file.get("docs")
            ):
                continue

            file_id_owui = file.get("id")
            file_name = file.get("name", "unknown")
            if not file_id_owui:
                continue

            # Skip images — they use Vision (base64/URL), not Files API
            content_type = file.get("content_type", "")
            if not content_type:
                # Fallback: check OpenWebUI file meta for content_type
                file_record_check = await Files.get_file_by_id(file_id_owui)
                if file_record_check and file_record_check.meta:
                    content_type = file_record_check.meta.get("content_type", "")
            if content_type and content_type.startswith("image/"):
                logger.debug(f"Skipping image file for Files API: {file_name} ({content_type})")
                continue

            # Look up OpenWebUI file record for cached anthropic_file_id
            file_record = await Files.get_file_by_id(file_id_owui)
            if not file_record:
                logger.warning(f"File not found in DB: {file_id_owui}")
                continue

            meta = file_record.meta or {}
            anthropic_file_id = meta.get("anthropic_file_id")
            msg_num = meta.get("anthropic_file_msg_idx")

            if anthropic_file_id:
                # Cached — reuse without re-uploading
                if msg_num is None:
                    msg_num = current_user_msg_num
                logger.debug(f"♻️ Reusing cached file {file_name} → {anthropic_file_id} (msg {msg_num})")
            else:
                # New file — upload to Anthropic
                try:
                    file_path = Storage.get_file(file_record.path)
                    if not file_path or not Path(file_path).is_file():
                        logger.warning(f"File not on disk: {file_id_owui}")
                        continue

                    with open(file_path, "rb") as f:
                        file_content = f.read()

                    await emit_status(f"☁️ Uploading {file_name}...")

                    upload_result = await client.beta.files.upload(
                        file=(file_name, io.BytesIO(file_content)),
                    )
                    anthropic_file_id = upload_result.id
                    msg_num = current_user_msg_num

                    # Cache in OpenWebUI file metadata
                    await Files.update_file_metadata_by_id(file_id_owui, {
                        "anthropic_file_id": anthropic_file_id,
                        "anthropic_file_msg_idx": msg_num,
                    })

                    logger.info(f"☁️ Uploaded {file_name} → {anthropic_file_id} (msg {msg_num})")

                    await emit_status(f"☁️ Uploaded {file_name}", done=True)
                except Exception as e:
                    logger.error(f"Failed to upload {file_name}: {e}")
                    await emit_notification(f"Failed to upload {file_name}: {str(e)[:100]}")
                    continue

            # Group container_upload block by user message number
            if msg_num not in blocks_by_user_msg:
                blocks_by_user_msg[msg_num] = []
            blocks_by_user_msg[msg_num].append({
                "type": "container_upload",
                "file_id": anthropic_file_id,
            })
            processed_filenames.append(file_name)

        return blocks_by_user_msg, processed_filenames

    async def _validate_and_get_skills(
        self,
        skill_names: List[str],
        api_key: str,
        __event_emitter__: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Validate user-specified skill names against the Anthropic List Skills API.

        Skills can be specified as:
        - Anthropic skills: Short names like "pptx", "xlsx", "docx", "pdf"
        - Custom skills: Full IDs like "skill_01AbCdEfGhIjKlMnOpQrStUv"

        Validation results are cached per API key to avoid repeated API calls.

        Args:
            skill_names: List of skill names/IDs from user's SKILLS valve
            api_key: Anthropic API key
            __event_emitter__: Optional event emitter for status updates

        Returns:
            List of validated skill configurations for the container parameter
        """
        if not skill_names:
            return []

        status = None
        if __event_emitter__:
            status_cls = globals().get("StatusEmitter")
            status = status_cls(__event_emitter__) if status_cls else None

        async def emit_status(description: str, *, done: bool = False, hidden: bool | None = None) -> None:
            """Emit a status update via StatusEmitter if available, else fall back to a raw status event."""
            if not __event_emitter__:
                return
            if status:
                await status.emit(description, done=done, hidden=hidden)
                return
            data: dict[str, Any] = {"description": description, "done": done}
            if hidden is not None:
                data["hidden"] = hidden
            await self.emit_event({"type": "status", "data": data}, __event_emitter__)

        async def emit_notification(content: str, *, type: str = "warning") -> None:
            """Emit a notification via StatusEmitter if available, else fall back to a raw notification event."""
            if not __event_emitter__:
                return
            if status and hasattr(status, "notification"):
                await status.notification(content, type=type)
                return
            await self.emit_event(
                {"type": "notification", "data": {"type": type, "content": content}},
                __event_emitter__,
            )

        # Initialize cache for this API key if needed
        if api_key not in self._validated_skills_cache:
            self._validated_skills_cache[api_key] = {}

        cache = self._validated_skills_cache[api_key]

        # Check which skills need validation
        skills_to_validate = [s for s in skill_names if s not in cache]

        # If we have skills to validate, fetch from API
        if skills_to_validate:
            logger.debug(
                f"🔧 Validating {len(skills_to_validate)} skills via API: {skills_to_validate}"
            )

            await emit_status("🔧 Validating Skills...", hidden=True)

            try:
                from anthropic import AsyncAnthropic

                client = self._build_anthropic_client(api_key)

                # Fetch all available skills
                available_skills = {}

                def index_skill(info: dict[str, Any]) -> None:
                    """Index a skill under its id/display_title and common format aliases (xlsx/pptx/docx/pdf)."""
                    skill_id = info.get("id", "")
                    display_title = info.get("display_title", "") or skill_id
                    for key in (skill_id, skill_id.lower(), display_title.lower()):
                        if key:
                            available_skills[key] = info
                    haystack = f"{skill_id} {display_title}".lower()
                    if "xlsx" in haystack or "excel" in haystack or "spreadsheet" in haystack:
                        available_skills.setdefault("xlsx", info)
                    if "pptx" in haystack or "powerpoint" in haystack or "presentation" in haystack:
                        available_skills.setdefault("pptx", info)
                    if "docx" in haystack or "word" in haystack or "document" in haystack:
                        available_skills.setdefault("docx", info)
                    if "pdf" in haystack:
                        available_skills.setdefault("pdf", info)

                # Fetch Anthropic skills
                try:
                    anthropic_skills = await client.beta.skills.list(
                        source="anthropic", betas=["skills-2025-10-02"]
                    )
                    for skill in anthropic_skills.data:
                        # Store by both id and display_title for flexible matching
                        info = {
                            "id": skill.id,
                            "type": "anthropic",
                            "source": "anthropic",
                            "display_title": getattr(skill, "display_title", skill.id),
                            "latest_version": getattr(
                                skill, "latest_version", "latest"
                            ),
                        }
                        index_skill(info)
                except Exception as e:
                    logger.warning(f"Failed to fetch Anthropic skills: {e}")

                # Fetch custom skills
                try:
                    custom_skills = await client.beta.skills.list(
                        source="custom", betas=["skills-2025-10-02"]
                    )
                    for skill in custom_skills.data:
                        info = {
                            "id": skill.id,
                            "type": "custom",
                            "source": "custom",
                            "display_title": getattr(skill, "display_title", skill.id),
                            "latest_version": getattr(
                                skill, "latest_version", "latest"
                            ),
                        }
                        index_skill(info)
                except Exception as e:
                    logger.warning(f"Failed to fetch custom skills: {e}")

                logger.debug(f"🔧 Found {len(available_skills)} available skills")

                # Validate each skill
                for skill_name in skills_to_validate:
                    skill_lower = skill_name.lower().strip()

                    # Try exact match first
                    if skill_name in available_skills:
                        cache[skill_name] = available_skills[skill_name]
                        logger.debug(f"✓ Validated skill '{skill_name}' (exact match)")
                    # Try lowercase match
                    elif skill_lower in available_skills:
                        cache[skill_name] = available_skills[skill_lower]
                        logger.debug(
                            f"✓ Validated skill '{skill_name}' (case-insensitive match)"
                        )
                    else:
                        # Mark as invalid
                        cache[skill_name] = None
                        logger.warning(
                            f"✗ Invalid skill '{skill_name}' - not found in available skills"
                        )

            except Exception as e:
                logger.error(f"Failed to validate skills: {e}")
                # Mark all as failed validation
                for skill_name in skills_to_validate:
                    cache[skill_name] = None

        # Build the validated skills list
        validated_skills = []
        invalid_skills = []

        for skill_name in skill_names:
            skill_info = cache.get(skill_name)
            if skill_info:
                requested_short_id = skill_name.lower().strip()
                skill_id = (
                    requested_short_id
                    if skill_info.get("type") == "anthropic"
                    and requested_short_id in {"pptx", "xlsx", "docx", "pdf"}
                    else skill_info["id"]
                )
                validated_skills.append(
                    {
                        "type": skill_info["type"],
                        "skill_id": skill_id,
                        "version": "latest",
                    }
                )
            else:
                invalid_skills.append(skill_name)

        if invalid_skills:
            await emit_notification(
                f"⚠️ Invalid Anthropic API Skills ignored: {', '.join(invalid_skills)}. "
                "These are Anthropic API Skills, not OpenWebUI Skills."
            )

        logger.debug(f"🔧 Returning {len(validated_skills)} validated skills")
        return validated_skills
