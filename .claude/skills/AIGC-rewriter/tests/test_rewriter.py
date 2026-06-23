"""Tests for rewriter modules."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rewriter.context import build_context
from rewriter.diff import generate_diff_report
from rewriter.verify import verify_accuracy


class TestBuildContext:
    def test_basic_context(self):
        paragraphs = [
            {"text": "Para 1", "section_type": "introduction"},
            {"text": "Para 2", "section_type": "method"},
            {"text": "Para 3", "section_type": "results"},
            {"text": "Para 4", "section_type": "discussion"},
        ]
        result = build_context(paragraphs, 1, window=1)
        assert result["target"] == "Para 2"
        assert result["target_section"] == "method"
        assert len(result["before"]) == 1
        assert len(result["after"]) == 1

    def test_boundary_index(self):
        paragraphs = [{"text": "Para 1"}, {"text": "Para 2"}]
        result = build_context(paragraphs, 0, window=1)
        assert result["target"] == "Para 1"
        assert len(result["before"]) == 0
        assert len(result["after"]) == 1

    def test_out_of_range(self):
        paragraphs = [{"text": "Para 1"}]
        try:
            build_context(paragraphs, 5)
            assert False, "Should have raised IndexError"
        except IndexError:
            pass

    def test_empty_paragraphs(self):
        try:
            build_context([], 0)
            assert False, "Should have raised ValueError"
        except ValueError:
            pass


class TestGenerateDiffReport:
    def test_empty_results(self):
        assert generate_diff_report([]) == ""

    def test_with_results(self):
        results = [
            {
                "index": 0,
                "section_type": "body",
                "original_risk": 0.8,
                "rewritten_risk": 0.3,
                "original_text": "Original text here",
                "rewritten_text": "Rewritten text here",
                "suspects": [],
            },
        ]
        report = generate_diff_report(results)
        assert "0.80" in report
        assert "0.30" in report
        assert "Original text" in report


class TestVerifyAccuracy:
    def test_safe_rewrite(self):
        result = verify_accuracy(
            "Deep learning is effective.",
            "Deep neural networks are effective.",
            {"deep learning"}
        )
        assert result["is_safe"]
        assert len(result["suspects"]) == 0

    def test_term_replaced(self):
        result = verify_accuracy(
            "Deep learning is effective.",
            "Machine learning is effective.",
            {"Deep learning"}
        )
        assert not result["is_safe"]
        assert any(s["type"] == "term_replaced" for s in result["suspects"])

    def test_number_changed(self):
        result = verify_accuracy(
            "The accuracy was 95%.",
            "The accuracy was 80%.",
            set()
        )
        assert not result["is_safe"]
        assert any(s["type"] == "number_changed" for s in result["suspects"])

    def test_empty_texts(self):
        result = verify_accuracy("", "", set())
        assert not result["is_safe"]
