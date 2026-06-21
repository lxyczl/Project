"""文本处理工具函数。"""

import re
from typing import List


def split_sentences(text: str) -> List[str]:
    """按中文标点分句。"""
    # 匹配句号、问号、感叹号、分号（中英文）
    pattern = r'([^。！？；.!?;]+[。！？；.!?;]?)'
    sentences = re.findall(pattern, text)
    return [s.strip() for s in sentences if s.strip()]


def count_chinese_chars(text: str) -> int:
    """统计中文字符数。"""
    return len(re.findall(r'[一-鿿]', text))


def is_heading_line(line: str, is_markdown: bool) -> bool:
    """判断是否为标题行。"""
    if is_markdown:
        return line.strip().startswith("#")
    return len(line.strip()) < 30 and line.strip() != ""
