"""段落切分与章节识别测试。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyzer.paragraphs import split_paragraphs, detect_section


class TestDetectSection:
    def test_chinese_abstract(self):
        assert detect_section("摘要") == "abstract"
        assert detect_section("## 摘要") == "abstract"

    def test_chinese_introduction(self):
        assert detect_section("1 引言") == "introduction"

    def test_chinese_method(self):
        assert detect_section("3 实验方法") == "method"

    def test_chinese_results(self):
        assert detect_section("4 实验结果") == "results"

    def test_chinese_discussion(self):
        assert detect_section("5 讨论") == "discussion"

    def test_chinese_conclusion(self):
        assert detect_section("6 结论") == "conclusion"

    def test_english_abstract(self):
        assert detect_section("Abstract") == "abstract"

    def test_english_method(self):
        assert detect_section("## Methodology") == "method"

    def test_longer_keyword_wins(self):
        # "实验结果" 比 "实验" 更长，应匹配 results 而非 method
        assert detect_section("实验结果与分析") == "results"

    def test_unmatched(self):
        assert detect_section("任意标题") == "body"


class TestSplitParagraphs:
    def test_plain_text(self):
        text = "第一段内容。\n\n第二段内容。\n\n第三段内容。"
        paras = split_paragraphs(text, is_markdown=False)
        assert len(paras) == 3
        assert paras[0]["text"] == "第一段内容。"
        assert paras[1]["text"] == "第二段内容。"
        assert paras[2]["index"] == 2

    def test_markdown_with_headings(self):
        text = "# 标题\n\n## 摘要\n\n这是摘要内容。\n\n## 引言\n\n这是引言内容。"
        paras = split_paragraphs(text, is_markdown=True)
        section_types = [p["section_type"] for p in paras]
        assert "abstract" in section_types
        assert "introduction" in section_types

    def test_empty_text(self):
        paras = split_paragraphs("", is_markdown=False)
        assert paras == []

    def test_whitespace_only(self):
        paras = split_paragraphs("   \n\n   ", is_markdown=False)
        assert paras == []

    def test_long_paragraph_split(self):
        """单段 > 2000 字应拆分。"""
        text = "这是一个测试。" * 500  # 约 3000 字
        paras = split_paragraphs(text, is_markdown=False)
        assert len(paras) > 1

    def test_char_count(self):
        text = "测试段落。"
        paras = split_paragraphs(text, is_markdown=False)
        assert paras[0]["char_count"] == 5

    def test_section_persists_across_paragraphs(self):
        """同一章节下的多个段落应继承章节类型。"""
        text = "## 方法\n\n第一段方法。\n\n第二段方法。"
        paras = split_paragraphs(text, is_markdown=True)
        assert all(p["section_type"] == "method" for p in paras)
