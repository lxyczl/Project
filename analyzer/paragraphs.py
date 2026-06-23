"""段落切分与章节识别。"""

import re
from typing import List


SECTION_KEYWORDS = {
    "abstract": ["摘要", "abstract", "提要"],
    "introduction": ["引言", "绪论", "introduction", "问题提出"],
    "method": ["方法", "方法论", "实验", "method", "methodology", "实验设计", "模型构建"],
    "results": ["结果", "实验结果", "results", "数据分析"],
    "discussion": ["讨论", "分析与讨论", "discussion", "结果分析"],
    "conclusion": ["结论", "总结", "conclusion", "结语"],
    "related_work": ["相关工作", "文献综述", "related work", "研究现状"],
}


def detect_section(heading_text: str) -> str:
    """识别章节类型。"""
    cleaned = re.sub(r'^#+\s*', '', heading_text.strip()).lower()

    # 按关键词长度降序排列，优先匹配更具体的关键词
    all_matches: List[tuple[str, int]] = []
    for section_type, keywords in SECTION_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in cleaned:
                all_matches.append((section_type, len(kw)))

    if all_matches:
        # 返回最长关键词对应的章节类型
        all_matches.sort(key=lambda x: x[1], reverse=True)
        return all_matches[0][0]

    return "body"


def split_paragraphs(text: str, is_markdown: bool) -> List[dict]:
    """将文本切分为段落，附带章节信息。"""
    if not text.strip():
        return []

    lines = text.split('\n')
    paragraphs: List[dict] = []
    current_section = "body"
    current_text_lines: List[str] = []
    pos = 0

    for line in lines:
        stripped = line.strip()

        # 检测标题（仅 Markdown 模式）
        if is_markdown and stripped.startswith('#'):
            # 先保存当前积累的段落
            pos = _flush_paragraph(current_text_lines, paragraphs, pos, current_section)
            current_text_lines = []
            current_section = detect_section(stripped)
            continue

        # 空行 = 段落分隔
        if not stripped:
            pos = _flush_paragraph(current_text_lines, paragraphs, pos, current_section)
            current_text_lines = []
            continue

        current_text_lines.append(stripped)

    # 处理最后一段
    _flush_paragraph(current_text_lines, paragraphs, pos, current_section)

    # 处理超长段落拆分
    result: List[dict] = []
    for para in paragraphs:
        if para["char_count"] > 2000:
            result.extend(_split_long_paragraph(para))
        else:
            result.append(para)

    # 重新编号
    for i, p in enumerate(result):
        p["index"] = i

    return result


def _flush_paragraph(
    current_text_lines: List[str],
    paragraphs: List[dict],
    pos: int,
    current_section: str,
) -> int:
    """将当前积累的行合并为一个段落并追加到列表，返回更新后的 pos。"""
    if current_text_lines:
        para_text = '\n'.join(current_text_lines).strip()
        if para_text:
            paragraphs.append(_make_para(len(paragraphs), para_text, pos, current_section))
            return pos + len(para_text) + 1
    return pos


def _make_para(index: int, text: str, start: int, section_type: str) -> dict:
    """构造段落字典。"""
    return {
        "index": index,
        "text": text,
        "start": start,
        "end": start + len(text),
        "char_count": len(text),
        "section_type": section_type,
    }


def _split_long_paragraph(para: dict) -> List[dict]:
    """按句号/分号拆分超长段落。"""
    text = para["text"]
    pattern = r'([^。！？；.!?;]+[。！？；.!?;]?)'
    sentences = [s.strip() for s in re.findall(pattern, text) if s.strip()]

    chunks: List[str] = []
    current_chunk: List[str] = []
    current_len = 0

    for sent in sentences:
        current_chunk.append(sent)
        current_len += len(sent)
        if current_len >= 1500:
            chunks.append(''.join(current_chunk))
            current_chunk = []
            current_len = 0

    if current_chunk:
        chunks.append(''.join(current_chunk))

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
