"""
完整工作流测试
测试从相似度分析到反馈的完整流程
"""
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from rewrite_with_feedback import RewriteWithFeedback
from similarity_calculator import calculate_similarity, format_report


class TestCompleteWorkflow:
    """完整工作流测试"""

    def test_analyze_and_record(self, tmp_path):
        """分析改写结果并记录会话"""
        system = RewriteWithFeedback(tmp_path)

        original = "The results show that the method is effective and reliable."
        rewritten = "The findings demonstrate that the approach exhibits considerable efficacy and dependability."

        analysis = system.analyze_rewrite(
            original, rewritten,
            domain="生态水文",
            intensity="medium",
            section_type="abstract"
        )

        assert "session_id" in analysis
        assert "similarity" in analysis
        assert "composite_score" in analysis
        assert "report" in analysis
        assert 0 <= analysis["composite_score"] <= 100

    def test_analyze_then_feedback(self, tmp_path):
        """分析后提交反馈"""
        system = RewriteWithFeedback(tmp_path)

        original = "The study area is located in the north of China."
        rewritten = "The research region is situated in northern China."

        analysis = system.analyze_rewrite(original, rewritten, domain="生态安全格局")

        feedback = system.submit_feedback(
            session_id=analysis["session_id"],
            vocabulary_score=4,
            structure_score=5,
            terminology_score=5,
            overall_score=4,
            liked="术语保留完整",
            improved="可以增加更多句式变化"
        )

        assert feedback["scores"]["overall_satisfaction"] == 4

    def test_get_suggestions_after_feedback(self, tmp_path):
        """反馈后获取建议"""
        system = RewriteWithFeedback(tmp_path)

        # 先做一次改写+反馈
        session = system.analyze_rewrite(
            "The model was used to calculate water yield.",
            "The model was employed to compute water yield.",
            domain="生态水文"
        )
        system.submit_feedback(session["session_id"], overall_score=5, missing_terms=["蒸散发"])

        # 获取建议
        suggestions = system.get_suggestions("生态水文", "medium")
        assert "effective_techniques" in suggestions
        assert "intensity_multiplier" in suggestions
        assert "蒸散发" in suggestions["new_terms_to_preserve"]

    def test_strategy_report_after_sessions(self, tmp_path):
        """多次会话后生成策略报告"""
        system = RewriteWithFeedback(tmp_path)

        texts = [
            ("The results show effectiveness", "The findings demonstrate efficacy"),
            ("The method is reliable", "The approach is dependable"),
            ("The study found that", "The investigation revealed that"),
        ]

        for orig, rew in texts:
            analysis = system.analyze_rewrite(orig, rew, domain="生态水文")
            system.submit_feedback(analysis["session_id"], overall_score=4)

        report = system.get_strategy_report()
        assert "反馈学习策略报告" in report
        assert "生态水文" in report

    def test_high_similarity_detected(self):
        """相同文本应该有高相似度"""
        text = "The results show that the method is effective."
        result = calculate_similarity(text, text)
        assert result["composite_score"] >= 80

    def test_low_similarity_for_paraphrased(self):
        """充分改写应该有低相似度"""
        original = "The results show that the method is effective."
        rewritten = "A comprehensive analysis was performed, revealing that the approach demonstrates considerable efficacy."
        result = calculate_similarity(original, rewritten)
        assert result["composite_score"] < 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
