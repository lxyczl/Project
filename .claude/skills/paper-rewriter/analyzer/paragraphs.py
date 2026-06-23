"""段落切分与章节识别（英文）。"""

import re


SECTION_KEYWORDS = {
    "abstract": ["abstract"],
    "introduction": ["introduction"],
    "methods": ["method", "methodology", "materials", "experimental", "study area", "data"],
    "results": ["result", "findings"],
    "discussion": ["discussion"],
    "conclusion": ["conclusion", "summary"],
    "references": ["reference", "bibliography"],
}


def detect_section(heading_text: str) -> str:
    """识别章节类型。"""
    cleaned = re.sub(r'^(?:\d+\.?\s*)', '', heading_text.strip()).lower()

    all_matches = []
    for section_type, keywords in SECTION_KEYWORDS.items():
        for kw in keywords:
            if kw in cleaned:
                all_matches.append((section_type, len(kw)))

    if all_matches:
        all_matches.sort(key=lambda x: x[1], reverse=True)
        return all_matches[0][0]

    return "body"


def split_paragraphs(text: str) -> list[dict]:
    """将文本切分为段落，附带章节信息。"""
    if not text.strip():
        return []

    # 按空行分段
    raw_paragraphs = re.split(r'\n\s*\n', text)
    paragraphs = []
    current_section = "body"

    for i, para_text in enumerate(raw_paragraphs):
        para_text = para_text.strip()
        if not para_text:
            continue

        # 检测章节标题（独立短行）
        if len(para_text.split()) <= 8 and re.match(r'^(?:\d+\.?\s*)?[A-Z]', para_text):
            section = detect_section(para_text)
            if section != "body":
                current_section = section
                continue

        word_count = len(para_text.split())
        paragraphs.append({
            "index": len(paragraphs),
            "text": para_text,
            "word_count": word_count,
            "char_count": len(para_text),
            "section_type": current_section,
        })

    # 超长段落拆分
    result = []
    for para in paragraphs:
        if para["word_count"] > 300:
            result.extend(_split_long_paragraph(para))
        else:
            result.append(para)

    # 重新编号
    for i, p in enumerate(result):
        p["index"] = i

    return result


def _split_long_paragraph(para: dict) -> list[dict]:
    """按句号拆分超长段落。"""
    text = para["text"]
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)

    chunks = []
    current_chunk = []
    current_len = 0

    for sent in sentences:
        current_chunk.append(sent)
        current_len += len(sent.split())
        if current_len >= 200:
            chunks.append(' '.join(current_chunk))
            current_chunk = []
            current_len = 0

    if current_chunk:
        chunks.append(' '.join(current_chunk))

    result = []
    for chunk in chunks:
        result.append({
            "index": para["index"] + len(result),
            "text": chunk,
            "word_count": len(chunk.split()),
            "char_count": len(chunk),
            "section_type": para["section_type"],
            "is_sub_chunk": True,
        })

    return result
