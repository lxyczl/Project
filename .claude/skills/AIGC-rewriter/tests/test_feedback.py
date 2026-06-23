"""Tests for feedback learning system."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.feedback_system import FeedbackSystem, auto_evaluate, classify_failure


class TestAutoEvaluate:
    def test_fail(self):
        result = auto_evaluate(0.5, 0.6)
        assert result["verdict"] == "fail"
        assert not result["is_success"]

    def test_marginal(self):
        result = auto_evaluate(0.5, 0.47)
        assert result["verdict"] == "marginal"
        assert not result["is_success"]

    def test_partial(self):
        result = auto_evaluate(0.8, 0.5, threshold=0.3)
        assert result["verdict"] == "partial"
        assert not result["is_success"]

    def test_success(self):
        # reduction = 0.15, risk_after = 0.25 <= threshold 0.3, reduction < 0.3 → success
        result = auto_evaluate(0.4, 0.25, threshold=0.3)
        assert result["verdict"] == "success"
        assert result["is_success"]

    def test_excellent(self):
        # reduction >= 0.3 and risk_after <= threshold
        result = auto_evaluate(0.8, 0.3, threshold=0.3)
        assert result["verdict"] == "excellent"
        assert result["is_success"]


class TestClassifyFailure:
    def test_risk_increased(self):
        result = classify_failure(0.5, 0.6, [], [])
        assert result == "risk_increased"

    def test_minimal_effect(self):
        result = classify_failure(0.5, 0.48, [], [])
        assert result == "minimal_effect"

    def test_cliche_persistent(self):
        issues_before = [{"type": "cliche_detected"}]
        issues_after = [{"type": "cliche_detected"}]
        result = classify_failure(0.5, 0.4, issues_before, issues_after)
        assert result == "cliche_persistent"


class TestFeedbackSystem:
    def test_init(self, tmp_path):
        fs = FeedbackSystem(tmp_path)
        assert fs.strategies["session_count"] == 0

    def test_record_session(self, tmp_path):
        fs = FeedbackSystem(tmp_path)
        session = fs.record_session(
            original_text="original",
            rewritten_text="rewritten",
            risk_before=0.8,
            risk_after=0.3,
            section_type="body",
            techniques_used=["cliche_replace"],
        )
        assert session["session_id"] is not None
        assert fs.strategies["session_count"] == 1

    def test_get_suggestions(self, tmp_path):
        fs = FeedbackSystem(tmp_path)
        suggestions = fs.get_rewrite_suggestions("body", "medium")
        assert "effective_techniques" in suggestions
        assert "intensity_multiplier" in suggestions
