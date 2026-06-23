"""Tests for structure analysis dimension."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzer.structure import analyze_structure


class TestAnalyzeStructure:
    def test_uniform_paragraph_length(self):
        paragraphs = [
            {"char_count": 100, "text": "First paragraph with some content here."},
            {"char_count": 102, "text": "Second paragraph with similar length here."},
            {"char_count": 98, "text": "Third paragraph also with similar length."},
            {"char_count": 101, "text": "Fourth paragraph with matching length here."},
        ]
        result = analyze_structure(paragraphs)
        issue_types = {i["type"] for i in result["issues"]}
        assert "uniform_para_length" in issue_types

    def test_varied_paragraph_length(self):
        paragraphs = [
            {"char_count": 50, "text": "Short."},
            {"char_count": 200, "text": "This is a much longer paragraph with more content and detail."},
            {"char_count": 100, "text": "Medium length paragraph here."},
            {"char_count": 300, "text": "This is the longest paragraph in the set with significantly more text and content than the others combined."},
        ]
        result = analyze_structure(paragraphs)
        issue_types = {i["type"] for i in result["issues"]}
        assert "uniform_para_length" not in issue_types

    def test_uniform_paragraph_start(self):
        paragraphs = [
            {"char_count": 100, "text": "The model was trained on data for testing."},
            {"char_count": 100, "text": "The model was evaluated on benchmark datasets."},
            {"char_count": 100, "text": "The model was compared against baselines."},
            {"char_count": 100, "text": "The model was deployed in production systems."},
        ]
        result = analyze_structure(paragraphs)
        issue_types = {i["type"] for i in result["issues"]}
        assert "uniform_para_start" in issue_types

    def test_too_few_paragraphs(self):
        paragraphs = [
            {"char_count": 100, "text": "First paragraph."},
            {"char_count": 100, "text": "Second paragraph."},
        ]
        result = analyze_structure(paragraphs)
        assert result["score"] == 0.0
        assert result["issues"] == []

    def test_empty_paragraphs(self):
        result = analyze_structure([])
        assert result["score"] == 0.0
        assert result["issues"] == []
