import hashlib
import re
from dataclasses import dataclass, replace

from paysentineliq.domain.knowledge import KnowledgeChunk, KnowledgeDocument

_LAYOUT_GAP_RE = re.compile(r"\S {2,}\S")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ChunkingConfig:
    target_chars: int = 1200
    overlap_chars: int = 150
    min_chars: int = 200

    def __post_init__(self) -> None:
        if self.target_chars <= 0:
            raise ValueError("target_chars must be positive")
        if not 0 <= self.overlap_chars < self.target_chars:
            raise ValueError("overlap_chars must be between 0 and target_chars")
        if self.min_chars < 0:
            raise ValueError("min_chars must be non-negative")


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _is_layout_line(line: str) -> bool:
    return "|" in line or "\t" in line or _LAYOUT_GAP_RE.search(line) is not None


def _is_layout_block(block: str) -> bool:
    return any(_is_layout_line(line) for line in block.splitlines())


def _split_long_line(line: str, max_chars: int) -> list[str]:
    if len(line) <= max_chars:
        return [line]
    words = line.split(" ")
    pieces: list[str] = []
    current: list[str] = []
    current_len = 0
    for word in words:
        addition = len(word) + (1 if current else 0)
        if current and current_len + addition > max_chars:
            pieces.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += addition
    if current:
        pieces.append(" ".join(current))
    return pieces


def _pieces(text: str, max_chars: int) -> list[tuple[str, int]]:
    result: list[tuple[str, int]] = []
    offset = 0
    for block in re.split(r"(\n\s*\n)", text):
        if not block.strip():
            offset += len(block)
            continue
        if _is_layout_block(block):
            result.append((block.strip(), offset))
        else:
            line_offset = offset
            current: list[str] = []
            current_len = 0
            for line in block.splitlines(keepends=True):
                stripped = line.rstrip("\n")
                for piece in _split_long_line(stripped, max_chars):
                    addition = len(piece) + (1 if current else 0)
                    if current and current_len + addition > max_chars:
                        result.append(("\n".join(current), line_offset))
                        line_offset += current_len + 1
                        current = [piece]
                        current_len = len(piece)
                    else:
                        current.append(piece)
                        current_len += addition
                if current and current_len >= max_chars:
                    result.append(("\n".join(current), line_offset))
                    line_offset += current_len
                    current = []
                    current_len = 0
            if current:
                result.append(("\n".join(current), line_offset))
        offset += len(block)
    return result


def _split_text(
    text: str,
    *,
    document_key: str,
    section: str,
    position_base: int,
    config: ChunkingConfig,
) -> list[KnowledgeChunk]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    stripped = normalized.strip()
    if not stripped:
        return []
    if len(stripped) <= config.target_chars:
        return [
            KnowledgeChunk(
                document_key=document_key,
                index=0,
                section=section,
                position=position_base,
                content=stripped,
                content_hash=_content_hash(stripped),
            ),
        ]

    pieces = _pieces(normalized, config.target_chars)
    if not pieces:
        return []

    chunks: list[KnowledgeChunk] = []
    current = ""
    current_start = position_base

    def flush() -> None:
        nonlocal current
        content = current.strip()
        if not content:
            current = ""
            return
        chunks.append(
            KnowledgeChunk(
                document_key=document_key,
                index=len(chunks),
                section=section,
                position=current_start,
                content=content,
                content_hash=_content_hash(content),
            ),
        )
        current = ""

    for piece, offset in pieces:
        piece = piece.strip()
        if not piece:
            continue
        if current and len(current) + 1 + len(piece) > config.target_chars:
            overlap = current[-config.overlap_chars :] if config.overlap_chars else ""
            flush()
            current_start = max(
                position_base,
                position_base + offset - len(overlap),
            )
            current = f"{overlap}\n{piece}" if overlap else piece
        else:
            if not current:
                current_start = position_base + offset
            current = f"{current}\n{piece}" if current else piece
    flush()

    if (
        len(chunks) > 1
        and len(chunks[-1].content) < config.min_chars
        and chunks[-1].section == chunks[-2].section
    ):
        merged_content = f"{chunks[-2].content}\n{chunks[-1].content}"
        chunks[-2] = replace(
            chunks[-2],
            content=merged_content,
            content_hash=_content_hash(merged_content),
        )
        chunks.pop()
    return chunks


def chunk_pages(
    document: KnowledgeDocument,
    config: ChunkingConfig | None = None,
) -> tuple[KnowledgeChunk, ...]:
    actual = config if config is not None else ChunkingConfig()
    chunks: list[KnowledgeChunk] = []
    offset = 0
    for page in document.pages:
        page_chunks = _split_text(
            page.text,
            document_key=document.key,
            section=f"page {page.number}",
            position_base=offset,
            config=actual,
        )
        for chunk in page_chunks:
            chunks.append(replace(chunk, index=len(chunks)))
        offset += len(page.text) + 2
    return tuple(chunks)


def chunk_markdown(
    text: str,
    *,
    document_key: str,
    config: ChunkingConfig | None = None,
) -> tuple[KnowledgeChunk, ...]:
    actual = config if config is not None else ChunkingConfig()
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        return tuple(
            _split_text(
                text,
                document_key=document_key,
                section="document",
                position_base=0,
                config=actual,
            ),
        )

    sections: list[tuple[str, int, str]] = []
    stack: list[tuple[int, str]] = []
    for index, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        section = " > ".join(item[1] for item in stack)
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content:
            sections.append((section, start, content))

    chunks: list[KnowledgeChunk] = []
    for section, start, content in sections:
        for chunk in _split_text(
            content,
            document_key=document_key,
            section=section,
            position_base=start,
            config=actual,
        ):
            chunks.append(replace(chunk, index=len(chunks)))
    return tuple(chunks)
