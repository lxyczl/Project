"""Tests for edge case detection."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.edge_cases import detect_edge_cases, should_skip_rewrite, _load_protected_terms


class TestShortText:
    def test_short_text(self):
        issues = detect_edge_cases("Short text.")
        types = {i["type"] for i in issues}
        assert "short_text" in types

    def test_normal_length(self):
        text = " ".join(["word"] * 60)
        issues = detect_edge_cases(text)
        types = {i["type"] for i in issues}
        assert "short_text" not in types


class TestNonEnglish:
    def test_chinese_only(self):
        issues = detect_edge_cases("这是一段中文文本")
        types = {i["type"] for i in issues}
        assert "non_english" in types

    def test_english_with_chinese(self):
        # Mixed text should not trigger non_english (has English words)
        issues = detect_edge_cases("This is English text with 中文")
        types = {i["type"] for i in issues}
        assert "non_english" not in types


class TestNonAcademic:
    def test_colloquial(self):
        issues = detect_edge_cases("This is lol omg tbh great research indeed.")
        types = {i["type"] for i in issues}
        assert "non_academic" in types

    def test_academic(self):
        text = " ".join(["The"] + ["research"] * 60)
        issues = detect_edge_cases(text)
        types = {i["type"] for i in issues}
        assert "non_academic" not in types


class TestLongText:
    def test_long_text(self):
        text = " ".join(["word"] * 1100)
        issues = detect_edge_cases(text)
        types = {i["type"] for i in issues}
        assert "long_text" in types


class TestFormulaHeavy:
    def test_many_citations(self):
        text = "The method [1] was used [2] to analyze [3] the data [4] from [5] sources [6] and [7] references [8]. " * 10
        issues = detect_edge_cases(text)
        types = {i["type"] for i in issues}
        assert "formulas_citations" in types or "formula_heavy" in types

    def test_no_formulas(self):
        text = " ".join(["The"] + ["research"] * 60)
        issues = detect_edge_cases(text)
        types = {i["type"] for i in issues}
        assert "formulas_citations" not in types
        assert "formula_heavy" not in types


class TestDirectQuotes:
    def test_many_quotes(self):
        text = 'This is a "very long direct quote that exceeds twenty characters" and another "second long quote for testing purposes" plus "third long quote here for the test" and more text.'
        issues = detect_edge_cases(text)
        types = {i["type"] for i in issues}
        assert "direct_quotes" in types


class TestShouldSkip:
    def test_skip_on_error(self):
        issues = [{"type": "test", "skip_rewrite": True}]
        assert should_skip_rewrite(issues) is True

    def test_no_skip(self):
        issues = [{"type": "test", "skip_rewrite": False}]
        assert should_skip_rewrite(issues) is False

    def test_empty(self):
        assert should_skip_rewrite([]) is False


class TestProtectedTermsLoader:
    def test_load_terms(self):
        terms = _load_protected_terms()
        assert len(terms) > 0
        assert "deep learning" in terms
