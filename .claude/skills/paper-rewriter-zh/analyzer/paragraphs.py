"""段落切分与章节识别（中文学术写作）。"""
import re


SECTION_KEYWORDS = {
    "abstract": ["摘要", "abstract"],
    "introduction": ["引言", "绪论", "introduction"],
    "methods": ["方法", "研究方法", "实验", "材料与方法", "研究区", "数据", "method", "materials"],
    "results": ["结果", "研究结果", "实验结果", "result", "findings"],
    "discussion": ["讨论", "分析与讨论", "discussion"],
    "conclusion": ["结论", "结语", "总结", "conclusion", "summary"],
    "references": ["参考文献", "reference", "bibliography"],
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

    raw_paragraphs = re.split(r'\n\s*\n', text)
    paragraphs = []
    current_section = "body"

    for para_text in raw_paragraphs:
        para_text = para_text.strip()
        if not para_text:
            continue

        # 检测章节标题（独立短行，或以数字开头的短句）
        if len(para_text) <= 20 and re.match(r'^(?:\d+\.?\s*)?[一-鿿A-Z]', para_text):
            section = detect_section(para_text)
            if section != "body":
                current_section = section
                continue

        char_count = len(para_text)
        paragraphs.append({
            "index": len(paragraphs),
            "text": para_text,
            "char_count": char_count,
            "section_type": current_section,
        })

    # 超长段落拆分（超过 500 字）
    result = []
    for para in paragraphs:
        if para["char_count"] > 500:
            result.extend(_split_long_paragraph(para))
        else:
            result.append(para)

    for i, p in enumerate(result):
        p["index"] = i

    return result


def _split_long_paragraph(para: dict) -> list[dict]:
    """按句号拆分超长段落。"""
    text = para["text"]
    sentences = re.split(r'[。！？]', text)

    chunks = []
    current_chunk = []
    current_len = 0

    for sent in sentences:
        if not sent.strip():
            continue
        current_chunk.append(sent)
        current_len += len(sent)
        if current_len >= 300:
            chunks.append('。'.join(current_chunk) + '。')
            current_chunk = []
            current_len = 0

    if current_chunk:
        chunks.append('。'.join(current_chunk) + '。')

    result = []
    for chunk in chunks:
        result.append({
            "index": para["index"] + len(result),
            "text": chunk,
            "char_count": len(chunk),
            "section_type": para["section_type"],
            "is_sub_chunk": True,
        })

    return result
