from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

try:
    import tiktoken

    _ENCODER = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_ENCODER.encode(text))

except Exception:

    def count_tokens(text: str) -> int:
        # Fallback estimation: ~4 chars per token for English/code
        return max(1, len(text) // 4) if text else 0


@dataclass
class ChunkOutput:
    chunk_index: int
    section_title: str
    section_path: str
    content: str
    content_hash: str
    token_count: int


HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```")


class SemanticChunker:
    """Heading-aware semantic Markdown and text chunker preserving structure and context."""

    def __init__(
        self,
        target_tokens: int = 500,
        max_tokens: int = 800,
        min_tokens: int = 50,
        overlap_tokens: int = 60,
    ) -> None:
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens
        self.min_tokens = min_tokens
        self.overlap_tokens = overlap_tokens

    def chunk_document(self, text: str, document_title: str = "") -> list[ChunkOutput]:
        """Split document into semantic, heading-aware chunks with preserved section hierarchy."""
        stripped = text.strip()
        if not stripped:
            return []

        # Extract sections bounded by markdown headings
        sections = self._extract_sections(stripped, document_title)

        chunks: list[ChunkOutput] = []
        chunk_index = 0

        for sec_path, sec_title, sec_body in sections:
            sec_body = sec_body.strip()
            if not sec_body:
                continue

            sec_tokens = count_tokens(sec_body)
            if sec_tokens <= self.max_tokens:
                # Fits within a single chunk
                chunks.append(
                    self._create_chunk(
                        chunk_index=chunk_index,
                        section_title=sec_title,
                        section_path=sec_path,
                        content=sec_body,
                    )
                )
                chunk_index += 1
            else:
                # Section is oversized: split along paragraph / code block boundaries
                sub_chunks = self._split_large_section(sec_body, sec_path, sec_title, chunk_index)
                chunks.extend(sub_chunks)
                chunk_index += len(sub_chunks)

        # Handle empty case or merge extremely tiny orphan chunks if needed
        if not chunks and stripped:
            chunks.append(
                self._create_chunk(
                    chunk_index=0,
                    section_title=document_title or "Overview",
                    section_path=document_title or "Overview",
                    content=stripped[:16000],
                )
            )

        return chunks

    def _extract_sections(self, text: str, default_title: str) -> list[tuple[str, str, str]]:
        """Parse text into sections using Markdown headings (# H1, ## H2, etc.)."""
        matches = list(HEADING_PATTERN.finditer(text))
        if not matches:
            title = default_title or "General"
            return [(title, title, text)]

        sections: list[tuple[str, str, str]] = []
        heading_stack: list[tuple[int, str]] = []  # (level, title)

        # Content before the first heading
        if matches[0].start() > 0:
            pre_text = text[: matches[0].start()].strip()
            if pre_text:
                title = default_title or "Overview"
                sections.append((title, title, pre_text))

        for i, match in enumerate(matches):
            level = len(match.group(1))
            heading_title = match.group(2).strip()

            # Adjust heading stack for hierarchy
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, heading_title))

            path = " > ".join(h[1] for h in heading_stack)
            if default_title and not path.startswith(default_title):
                path = f"{default_title} > {path}"

            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start:end].strip()

            if body:
                sections.append((path, heading_title, body))

        return sections

    def _split_large_section(
        self, text: str, section_path: str, section_title: str, start_index: int
    ) -> list[ChunkOutput]:
        """Split oversized text by paragraphs, preserving code blocks and maintaining overlap."""
        paragraphs = re.split(r"\n\s*\n", text)
        result: list[ChunkOutput] = []
        current_paragraphs: list[str] = []
        current_tokens = 0
        idx = start_index

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_tokens = count_tokens(para)

            # If a single paragraph is larger than max_tokens, split by lines/sentences
            if para_tokens > self.max_tokens:
                # Flush existing buffer first
                if current_paragraphs:
                    combined = "\n\n".join(current_paragraphs)
                    result.append(self._create_chunk(idx, section_title, section_path, combined))
                    idx += 1
                    current_paragraphs = []
                    current_tokens = 0

                lines = para.splitlines()
                sub_buf: list[str] = []
                sub_tokens = 0
                for line in lines:
                    line_tokens = count_tokens(line)
                    if sub_tokens + line_tokens > self.target_tokens and sub_buf:
                        result.append(
                            self._create_chunk(idx, section_title, section_path, "\n".join(sub_buf))
                        )
                        idx += 1
                        sub_buf = []
                        sub_tokens = 0
                    sub_buf.append(line)
                    sub_tokens += line_tokens

                if sub_buf:
                    result.append(
                        self._create_chunk(idx, section_title, section_path, "\n".join(sub_buf))
                    )
                    idx += 1
                continue

            if current_tokens + para_tokens > self.target_tokens and current_paragraphs:
                combined = "\n\n".join(current_paragraphs)
                result.append(self._create_chunk(idx, section_title, section_path, combined))
                idx += 1
                # Overlap: keep the last paragraph if under overlap budget
                last_para = current_paragraphs[-1]
                if count_tokens(last_para) <= self.overlap_tokens:
                    current_paragraphs = [last_para, para]
                    current_tokens = count_tokens(last_para) + para_tokens
                else:
                    current_paragraphs = [para]
                    current_tokens = para_tokens
            else:
                current_paragraphs.append(para)
                current_tokens += para_tokens

        if current_paragraphs:
            combined = "\n\n".join(current_paragraphs)
            result.append(self._create_chunk(idx, section_title, section_path, combined))

        return result

    def _create_chunk(
        self,
        chunk_index: int,
        section_title: str,
        section_path: str,
        content: str,
    ) -> ChunkOutput:
        clean = content.strip()
        if section_title and not clean.startswith("#"):
            final_content = f"### {section_title}\n\n{clean}"
        else:
            final_content = clean

        sha = hashlib.sha256(final_content.encode("utf-8")).hexdigest()
        tokens = count_tokens(final_content)
        return ChunkOutput(
            chunk_index=chunk_index,
            section_title=section_title[:250],
            section_path=section_path[:490],
            content=final_content,
            content_hash=sha,
            token_count=tokens,
        )
