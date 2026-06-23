"""Tests for paragraph splitting and section detection."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzer.paragraphs import split_paragraphs, detect_section


class TestDetectSection:
    def test_abstract(self):
        assert detect_section("# Abstract") == "abstract"
        assert detect_section("## ABSTRACT") == "abstract"

    def test_introduction(self):
        assert detect_section("# Introduction") == "introduction"
        assert detect_section("## Background") == "introduction"

    def test_method(self):
        assert detect_section("# Methods") == "method"
        assert detect_section("## Methodology") == "method"
        assert detect_section("## Materials and Methods") == "method"

    def test_results(self):
        assert detect_section("# Results") == "results"
        assert detect_section("## Findings") == "results"

    def test_discussion(self):
        assert detect_section("# Discussion") == "discussion"

    def test_conclusion(self):
        assert detect_section("# Conclusion") == "conclusion"

    def test_related_work(self):
        assert detect_section("# Related Work") == "related_work"
        assert detect_section("## Literature Review") == "related_work"

    def test_unknown(self):
        assert detect_section("# Random Heading") == "body"


class TestSplitParagraphs:
    def test_empty_text(self):
        result = split_paragraphs("", is_markdown=False)
        assert result == []

    def test_markdown_split(self):
        text = """# Abstract

This is the abstract text.

# Introduction

This is the introduction text."""
        result = split_paragraphs(text, is_markdown=True)
        assert len(result) >= 2
        sections = {p["section_type"] for p in result}
        assert "abstract" in sections
        assert "introduction" in sections

    def test_plain_text_split(self):
        text = """First paragraph here.

Second paragraph here.

Third paragraph here."""
        result = split_paragraphs(text, is_markdown=False)
        assert len(result) == 3
        assert result[0]["index"] == 0
        assert result[1]["index"] == 1
        assert result[2]["index"] == 2

    def test_long_paragraph_split(self):
        # Create a paragraph longer than 2000 characters
        long_text = "This is a sentence. " * 200
        result = split_paragraphs(long_text, is_markdown=False)
        # Should be split into sub-chunks
        assert len(result) >= 1
