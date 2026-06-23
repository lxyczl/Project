"""Tests for scorer module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzer.scorer import (
    score_paragraph,
    score_paragraphs,
    compute_overall_risk,
    get_threshold,
    SECTION_WEIGHTS,
    SECTION_THRESHOLDS,
)


class TestScoreParagraph:
    def test_normal_text(self, sample_normal_text, patterns_dir):
        from analyzer.patterns import PatternLibrary
        lib = PatternLibrary.load(patterns_dir)
        result = score_paragraph(sample_normal_text, "body", lib.get_patterns())
        assert "risk" in result
        assert "priority" in result
        assert "issues" in result
        assert result["risk"] < 0.5

    def test_cliche_text(self, patterns_dir):
        text = "In recent years, it is worth noting that this plays a crucial role."
        from analyzer.patterns import PatternLibrary
        lib = PatternLibrary.load(patterns_dir)
        result = score_paragraph(text, "body", lib.get_patterns())
        assert result["risk"] > 0.1  # Should have some risk from cliches

    def test_section_weights(self):
        assert "discussion" in SECTION_WEIGHTS
        assert SECTION_WEIGHTS["discussion"] > SECTION_WEIGHTS["introduction"]


class TestScoreParagraphs:
    def test_batch_scoring(self, patterns_dir):
        paragraphs = [
            {"index": 0, "text": "Normal text about the experiment.", "section_type": "body", "char_count": 30},
            {"index": 1, "text": "In recent years, it is worth noting.", "section_type": "body", "char_count": 35},
        ]
        from analyzer.patterns import PatternLibrary
        lib = PatternLibrary.load(patterns_dir)
        results = score_paragraphs(paragraphs, lib.get_patterns())
        assert len(results) == 2
        # Should be sorted by priority
        assert results[0]["priority"] >= results[1]["priority"]


class TestComputeOverallRisk:
    def test_empty(self):
        assert compute_overall_risk([]) == 0.0

    def test_single(self):
        scores = [{"risk": 0.5}]
        assert compute_overall_risk(scores) == 0.5

    def test_multiple(self):
        scores = [{"risk": 0.3}, {"risk": 0.6}, {"risk": 0.9}]
        expected = round((0.3 + 0.6 + 0.9) / 3, 3)
        assert compute_overall_risk(scores) == expected


class TestGetThreshold:
    def test_known_section(self):
        assert get_threshold("abstract", None) == 0.25
        assert get_threshold("method", None) == 0.35
        assert get_threshold("related_work", None) == 0.4

    def test_unknown_section(self):
        assert get_threshold("unknown", None) == 0.3

    def test_global_override(self):
        assert get_threshold("abstract", 0.5) == 0.5
        assert get_threshold("method", 0.2) == 0.2
