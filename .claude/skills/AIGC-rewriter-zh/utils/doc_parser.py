"""统一文档解析模块。

支持格式：.txt / .md / .docx / .pdf（文字型）
扫描型 PDF 提取不到文字时抛出 ValueError 并给出提示。
"""

from __future__ import annotations

from pathlib import Path

SUPPORTED_SUFFIXES = {".txt", ".md", ".docx", ".pdf"}


def read_document(path_str: str) -> tuple[str, str]:
    """读取文档，返回 (文本内容, 文件后缀)。

    后缀返回原始后缀（如 ".docx"），调用方可据此判断 is_markdown 等。

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 不支持的格式 / 扫描型 PDF 无法提取文字
    """
    p = Path(path_str)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {p}")

    suffix = p.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(
            f"不支持的格式: {suffix}。"
            f"支持: {', '.join(sorted(SUPPORTED_SUFFIXES))}"
        )

    if suffix in (".txt", ".md"):
        text = _read_text_file(p)
    elif suffix == ".docx":
        text = _read_docx(p)
    else:  # .pdf
        text = _read_pdf(p)

    return text, suffix


def _read_text_file(p: Path) -> str:
    """读取纯文本文件，UTF-8 优先，GBK 兜底。"""
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return p.read_text(encoding="gbk")


def _read_docx(p: Path) -> str:
    """从 .docx 提取正文文字。"""
    try:
        from docx import Document
    except ImportError:
        raise ImportError(
            "需要 python-docx 库: pip install python-docx"
        )

    doc = Document(str(p))
    paragraphs = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)

    if not paragraphs:
        raise ValueError(f"文档 {p.name} 未检测到正文内容")

    return "\n\n".join(paragraphs)


def _read_pdf(p: Path) -> str:
    """从文字型 PDF 提取文字。

    扫描型 PDF 提取结果为空时抛出 ValueError。
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError(
            "需要 PyMuPDF 库: pip install PyMuPDF"
        )

    doc = fitz.open(str(p))
    pages = []
    for page in doc:
        text = page.get_text().strip()
        if text:
            pages.append(text)
    doc.close()

    if not pages:
        raise ValueError(
            f"PDF {p.name} 未提取到文字，可能是扫描版 PDF。"
            f"建议：用 OCR 工具转为文字版，或将文字复制到 .txt 文件后重试。"
        )

    return "\n\n".join(pages)
