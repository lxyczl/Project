"""测试反馈系统"""
import pytest
import sys
from pathlib import Path

scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))


class TestFeedbackSystem:
    """反馈系统核心功能"""

    def test_record_session(self, tmp_path):
        from feedback_system import FeedbackSystem
        fs = FeedbackSystem(tmp_path)
        session = fs.record_rewrite_session(
            original_text="深度学习是人工智能的核心技术",
            rewritten_text="机器学习是AI的关键技术",
            domain="计算机",
            intensity="中度"
        )
        assert "session_id" in session
        assert session["domain"] == "计算机"
        assert "auto_evaluation" in session

    def test_auto_evaluation(self, tmp_path):
        from feedback_system import FeedbackSystem
        fs = FeedbackSystem(tmp_path)
        session = fs.record_rewrite_session(
            original_text="测试文本",
            rewritten_text="改写后的文本内容",
            domain="通用",
            intensity="中度"
        )
        ev = session["auto_evaluation"]
        assert "verdict" in ev
        assert ev["verdict"] in ["excellent", "success", "warning", "fail"]

    def test_collect_feedback(self, tmp_path):
        from feedback_system import FeedbackSystem
        fs = FeedbackSystem(tmp_path)
        session = fs.record_rewrite_session(
            original_text="测试",
            rewritten_text="改写",
            domain="test",
            intensity="中度"
        )
        result = fs.collect_feedback(
            session_id=session["session_id"],
            vocabulary_score=4,
            structure_score=5,
            terminology_score=4,
            overall_score=4
        )
        assert result["scores"]["vocabulary"] == 4

    def test_get_suggestions(self, tmp_path):
        from feedback_system import FeedbackSystem
        fs = FeedbackSystem(tmp_path)
        suggestions = fs.get_rewrite_suggestions("通用", "中度")
        assert "effective_techniques" in suggestions
        assert "intensity_multiplier" in suggestions

    def test_evaluate_quality(self):
        from feedback_system import evaluate_rewrite_quality
        metrics = {"max_consecutive": 10, "trigram_overlap": 0.15}
        result = evaluate_rewrite_quality(metrics)
        assert "verdict" in result
        assert "score" in result

    def test_classify_failure(self):
        from feedback_system import classify_failure
        metrics = {"max_consecutive": 15, "trigram_overlap": 0.25}
        result = classify_failure(metrics, "fail")
        assert isinstance(result, str)


class TestAutoLearning:
    """自动学习"""

    def test_auto_learn(self, tmp_path):
        from feedback_system import FeedbackSystem
        fs = FeedbackSystem(tmp_path)
        session = fs.record_rewrite_session(
            original_text="测试",
            rewritten_text="改写",
            domain="test",
            intensity="中度"
        )
        learn_result = fs.auto_learn(session["session_id"])
        assert "learned" in learn_result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
