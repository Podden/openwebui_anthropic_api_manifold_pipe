"""Compiled Pipe method group: RAG source removal and inline metadata marker handling (memory extraction, marker create/extract). Compiled into class Pipe."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class PipeRequestRagMethods:
    def _remove_sources_from_rag(
        self, rag_content: str, filenames_to_remove: List[str]
    ) -> str:
        """
        Remove specific <source> tags from RAG content by filename.

        Args:
            rag_content: RAG message with <context> and <source> tags
            filenames_to_remove: List of filenames to remove from RAG sources

        Returns:
            str: RAG content with specified sources removed, or empty string if all sources removed
        """
        if not filenames_to_remove:
            return rag_content

        # Remove each source tag that matches the filenames
        modified = rag_content
        for filename in filenames_to_remove:
            # Match source tags with this filename in the name attribute
            # Need to escape the filename for regex but match it exactly
            pattern = re.compile(
                rf'<source[^>]*name="{re.escape(filename)}"[^>]*>.*?</source>\s*',
                re.DOTALL,
            )
            modified = pattern.sub("", modified)

        # Check if all sources were removed (only <context></context> or empty context remains)
        if PATTERN_EMPTY_CONTEXT.search(modified) or not PATTERN_SOURCE_TAGS.search(
            modified
        ):
            # All sources removed - remove entire RAG template
            logger.debug(f"📋 RAG: All sources removed, clearing entire RAG message")
            return ""

        logger.debug(
            f"📋 RAG: Removed {len(filenames_to_remove)} source(s) from RAG content"
        )
        return modified

    def _remove_specific_sources_from_rag_message(
        self,
        processed_messages: List[Dict[str, Any]],
        filenames_to_remove: List[str],
    ) -> None:
        """
        Remove specific sources from RAG messages by filename.
        Only removes the sources matching the given filenames, keeps other sources.
        If all sources are removed, the entire RAG template is removed.

        Args:
            processed_messages: List of messages to process
            filenames_to_remove: List of filenames whose sources should be removed from RAG
        """
        if not filenames_to_remove:
            return

        # Find the last user message with RAG content
        for i in range(len(processed_messages) - 1, -1, -1):
            msg = processed_messages[i]
            if msg.get("role") != "user":
                continue

            content = msg.get("content")
            if not isinstance(content, list):
                continue

            modified = False
            new_content: List[Dict[str, Any]] = []

            for block in content:
                if block.get("type") != "text":
                    new_content.append(block)
                    continue

                text = block.get("text", "")
                match = PATTERN_RAG_MESSAGE.search(text)

                if not match:
                    new_content.append(block)
                    continue

                # Found RAG content - extract and modify it
                rag_content = match.group(0)
                modified_rag = self._remove_sources_from_rag(
                    rag_content, filenames_to_remove
                )

                start, end = match.span()
                if not modified_rag:
                    # All sources removed - remove entire RAG block
                    new_text = text[:start] + text[end:]
                    logger.debug(
                        f"📋 RAG: Removed entire RAG block (all sources matched)"
                    )
                else:
                    # Some sources remain - update with modified RAG
                    new_text = text[:start] + modified_rag + text[end:]
                    logger.debug(
                        f"📋 RAG: Kept partial RAG content (some sources remain)"
                    )

                # Strip whitespace to prevent cache invalidation from leftover newlines
                new_text = new_text.strip()
                if new_text:
                    new_block = dict(block)
                    new_block["text"] = new_text
                    new_content.append(new_block)

                modified = True

            if modified:
                processed_messages[i]["content"] = new_content
                return  # Only process the first matching user message

    def _extract_and_remove_memories(self, text: str) -> tuple[str, Optional[str]]:
        """
        Extract memories injected by the OpenWebUI Memory System out of the system
        prompt and remove them from it.

        Two injection formats are recognised, because OpenWebUI changed shape:
          * ``<memory_context>...</memory_context>`` (current, utils/memory.py) —
            can sit anywhere in the system message.
          * ``\nUser Context:\n...`` (legacy) — runs to the end of the string.

        Both are re-retrieved and re-ranked per request, so they are never stable
        across turns. Leaving them in ``system`` costs a full prefix rewrite every
        turn (the API reports it as cache_miss_reason=system_changed); the caller
        relocates the return value to the last user message instead.

        Returns:
            tuple[str, Optional[str]]: (cleaned_text, extracted_context)
            - cleaned_text: Original text with all memory blocks removed (stripped)
            - extracted_context: The extracted memories with label, or None if none found
        """
        # Fast path: two substring scans are far cheaper than two regex scans,
        # and presence of the marker is the ground truth. Deliberately *not*
        # gated on a config flag — OpenWebUI decides to inject based on the
        # request's `features.memory` plus an admin-level ConfigVar, neither of
        # which the pipe can observe reliably. A gate that disagrees with what
        # actually arrived is what broke the cache in the first place.
        if "<memory_context>" not in text and "User Context:" not in text:
            return text.strip(), None

        extracted_parts: list[str] = []

        # <memory_context> may appear anywhere; strip every occurrence.
        def _take_memory_context(match) -> str:
            content = match.group(1).strip()
            if content:
                extracted_parts.append(content)
            return ""

        cleaned_text = PATTERN_MEMORY_CONTEXT.sub(_take_memory_context, text)

        # Legacy tail form.
        match = PATTERN_USER_CONTEXT.search(cleaned_text)
        if match:
            context_content = match.group(1).strip()
            if context_content:
                extracted_parts.append(f"User Context:\n{context_content}")
            # Remove "\nUser Context:\n" and everything after it
            cleaned_text = cleaned_text[: match.start()]

        extracted_context = "\n\n".join(extracted_parts) if extracted_parts else None
        return cleaned_text.strip(), extracted_context

    def _create_metadata_marker(self, id: str, value: str, messagenum: int = 0) -> str:
        """Build a URL-encoded inline metadata marker string for embedding in assistant text."""
        # URL-encode to handle special characters
        encoded_value = quote(value, safe="")
        return f" [](anthropic:{messagenum}:{id}:{encoded_value}) "

    def _extract_metadata_marker_from_message(self, message) -> List[str]:
        """
        Extract Anthropic metadata from the LAST assistant message in conversation.
        """
        metadata: List[str] = []
        if not isinstance(message, dict):
            return metadata
        if message.get("role") == "assistant":
            text = None
            content = message.get("content")
            if isinstance(content, list):
                # Join all text blocks for searching, but also update blocks in-place
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        block_text = block.get("text", "")
                        matches = self.METADATA_PATTERN.findall(block_text)
                        for match in matches:
                            metadata.append(match)
                        # Remove all metadata markers from this block
                        cleaned_text = self.METADATA_PATTERN.sub("", block_text)
                        block["text"] = cleaned_text
            elif isinstance(content, str):
                matches = self.METADATA_PATTERN.findall(content)
                for match in matches:
                    metadata.append(match)
                # Remove all metadata markers from the string
                message["content"] = self.METADATA_PATTERN.sub("", content)
        return metadata
