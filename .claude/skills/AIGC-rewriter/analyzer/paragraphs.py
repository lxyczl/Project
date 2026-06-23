"""Paragraph splitting and section detection."""

import re
from typing import List


# English section keywords (case-insensitive)
SECTION_KEYWORDS = {
    "abstract": ["abstract", "summary"],
    "introduction": ["introduction", "background"],
    "method": ["method", "methodology", "materials and methods", "experimental setup"],
    "results": ["results", "findings"],
    "discussion": ["discussion", "implications"],
    "conclusion": ["conclusion", "concluding remarks", "summary and conclusion"],
    "related_work": ["related work", "literature review", "prior work"],
}


def detect_section(heading_text: str) -> str:
    """Detect section type from heading text."""
    cleaned = re.sub(r'^#+\s*', '', heading_text.strip()).lower()

    # Sort by keyword length descending, match longest first
    all_matches: List[tuple[str, int]] = []
    for section_type, keywords in SECTION_KEYWORDS.items():
        for kw in keywords:
            if kw in cleaned:
                all_matches.append((section_type, len(kw)))

    if all_matches:
        all_matches.sort(key=lambda x: x[1], reverse=True)
        return all_matches[0][0]

    return "body"


def split_paragraphs(text: str, is_markdown: bool) -> List[dict]:
    """Split text into paragraphs with section info."""
    if not text.strip():
        return []

    lines = text.split('\n')
    paragraphs: List[dict] = []
    current_section = "body"
    current_text_lines: List[str] = []
    pos = 0

    for line in lines:
        stripped = line.strip()

        # Detect heading (Markdown mode only)
        if is_markdown and stripped.startswith('#'):
            # Save accumulated paragraphs first
            pos = _flush_paragraph(current_text_lines, paragraphs, pos, current_section)
            current_text_lines = []
            current_section = detect_section(stripped)
            continue

        # Empty line = paragraph separator
        if not stripped:
            pos = _flush_paragraph(current_text_lines, paragraphs, pos, current_section)
            current_text_lines = []
            continue

        current_text_lines.append(stripped)

    # Process last paragraph
    _flush_paragraph(current_text_lines, paragraphs, pos, current_section)

    # Handle ultra-long paragraphs by splitting
    result: List[dict] = []
    for para in paragraphs:
        if para["char_count"] > 2000:
            result.extend(_split_long_paragraph(para))
        else:
            result.append(para)

    # Re-number
    for i, p in enumerate(result):
        p["index"] = i

    return result


def _flush_paragraph(
    current_text_lines: List[str],
    paragraphs: List[dict],
    pos: int,
    current_section: str,
) -> int:
    """Merge accumulated lines into a paragraph and append to list."""
    if current_text_lines:
        para_text = '\n'.join(current_text_lines).strip()
        if para_text:
            paragraphs.append(_make_para(len(paragraphs), para_text, pos, current_section))
            return pos + len(para_text) + 1
    return pos


def _make_para(index: int, text: str, start: int, section_type: str) -> dict:
    """Construct paragraph dict."""
    return {
        "index": index,
        "text": text,
        "start": start,
        "end": start + len(text),
        "char_count": len(text),
        "section_type": section_type,
    }


def _split_long_paragraph(para: dict) -> List[dict]:
    """Split ultra-long paragraph at sentence boundaries."""
    text = para["text"]
    pattern = r'[^.!?;]+[.!?;]?'
    sentences = [s.strip() for s in re.findall(pattern, text) if s.strip()]

    chunks: List[str] = []
    current_chunk: List[str] = []
    current_len = 0

    for sent in sentences:
        current_chunk.append(sent)
        current_len += len(sent)
        if current_len >= 1500:
            chunks.append(' '.join(current_chunk))
            current_chunk = []
            current_len = 0

    if current_chunk:
        chunks.append(' '.join(current_chunk))

    result: List[dict] = []
    for chunk in chunks:
        result.append({
            "index": para["index"] + len(result),
            "text": chunk,
            "start": para["start"],
            "end": para["start"] + len(chunk),
            "char_count": len(chunk),
            "section_type": para["section_type"],
            "is_sub_chunk": True,
        })

    return result
