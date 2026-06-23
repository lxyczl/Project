"""Integration tests for the full pipeline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzer.scorer import score_paragraph
from analyzer.patterns import PatternLibrary
from analyzer.paragraphs import split_paragraphs


class TestFullPipeline:
    def test_end_to_end(self, patterns_dir, sample_academic_text):
        """Test complete analysis pipeline."""
        # Load patterns
        lib = PatternLibrary.load(patterns_dir)
        patterns = lib.get_patterns()

        # Split paragraphs
        paragraphs = split_paragraphs(sample_academic_text, is_markdown=False)
        assert len(paragraphs) > 0

        # Score each paragraph
        for para in paragraphs:
            result = score_paragraph(para["text"], para["section_type"], patterns)
            assert "risk" in result
            assert "issues" in result
            assert 0 <= result["risk"] <= 1

    def test_high_risk_text(self, patterns_dir):
        """Test that high-risk text gets elevated scores."""
        text = "In recent years, it is worth noting that this plays a crucial role. Furthermore, it has gained significant attention."
        lib = PatternLibrary.load(patterns_dir)
        result = score_paragraph(text, "body", lib.get_patterns())
        assert result["risk"] > 0.1  # Should have some risk from cliches

    def test_low_risk_text(self, patterns_dir, sample_normal_text):
        """Test that normal text gets low scores."""
        lib = PatternLibrary.load(patterns_dir)
        result = score_paragraph(sample_normal_text, "body", lib.get_patterns())
        assert result["risk"] < 0.5

    def test_section_detection_integration(self):
        """Test section detection with paragraph splitting."""
        text = """# Abstract

This is the abstract.

# Method

This is the method section.

# Results

These are the results."""
        paragraphs = split_paragraphs(text, is_markdown=True)
        sections = {p["section_type"] for p in paragraphs}
        assert "abstract" in sections
        assert "method" in sections
        assert "results" in sections
