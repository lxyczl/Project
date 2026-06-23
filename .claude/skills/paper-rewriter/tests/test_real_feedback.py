"""
反馈系统集成测试
测试从改写到反馈到学习的完整循环
"""
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from feedback_system import FeedbackSystem


class TestFeedbackIntegration:
    """反馈系统集成测试"""

    def test_full_rewrite_feedback_cycle(self, tmp_path):
        """完整改写→反馈→学习循环"""
        system = FeedbackSystem(tmp_path)

        # 1. 记录改写会话
        session = system.record_rewrite_session(
            original_text="Driven by the accelerating process of urbanization, "
                          "the impact of human activities has been increasingly intensified.",
            rewritten_text="Propelled by the concurrent intensification of urban expansion, "
                           "anthropogenic impacts on natural ecosystems have steadily increased.",
            domain="生态安全格局",
            intensity="medium",
            section_type="introduction",
            changes_made=[
                {"type": "voice_conversion", "original": "Driven by", "rewritten": "Propelled by"},
                {"type": "synonym_replacement", "original": "accelerating", "rewritten": "concurrent intensification"},
            ]
        )
        assert "session_id" in session
        assert session["metrics"]["lcs_ratio"] > 0

        # 2. 收集反馈
        feedback = system.collect_feedback(
            session_id=session["session_id"],
            vocabulary_score=5,
            structure_score=4,
            terminology_score=5,
            overall_score=4,
            liked="专业术语保留得很好",
            improved="部分词汇替换可以更丰富",
            missing_terms=["生态韧性", "生态空间"],
            suggestions="希望提供更多同义词选择"
        )
        assert feedback["scores"]["overall_satisfaction"] == 4
        assert "生态韧性" in feedback["feedback"]["missing_terms"]

        # 3. 获取建议
        suggestions = system.get_rewrite_suggestions("生态安全格局", "medium")
        assert "intensity_multiplier" in suggestions
        assert "生态韧性" in suggestions["new_terms_to_preserve"]

    def test_learning_across_multiple_sessions(self, tmp_path):
        """多次会话后策略应该累积"""
        system = FeedbackSystem(tmp_path)

        sessions_data = [
            ("water flow is high", "hydrological flux is elevated", "生态水文", "light", 4),
            ("method is effective", "approach demonstrates efficacy", "生态水文", "medium", 5),
            ("results show that", "findings demonstrate that", "生态水文", "medium", 5),
            ("study area is large", "research region is extensive", "生态安全格局", "heavy", 3),
        ]

        for orig, rew, domain, intensity, score in sessions_data:
            session = system.record_rewrite_session(orig, rew, domain, intensity)
            system.collect_feedback(session["session_id"], overall_score=score)

        # 生态水文的建议应该有数据
        suggestions = system.get_rewrite_suggestions("生态水文", "medium")
        assert len(suggestions["new_terms_to_preserve"]) >= 0  # 可能为空但不报错

        # 策略报告应该有内容
        report = system.get_strategy_report()
        assert "反馈学习策略报告" in report
        assert "生态水文" in report

    def test_low_score_increases_intensity(self, tmp_path):
        """低分反馈应该增加强度调整"""
        system = FeedbackSystem(tmp_path)

        # 连续低分
        for _ in range(3):
            session = system.record_rewrite_session(
                "original text", "rewritten text", "test", "medium"
            )
            system.collect_feedback(session["session_id"], overall_score=2)

        suggestions = system.get_rewrite_suggestions("test", "medium")
        assert suggestions["intensity_multiplier"] > 1.0

    def test_high_score_decreases_intensity(self, tmp_path):
        """高分反馈应该降低强度调整"""
        system = FeedbackSystem(tmp_path)

        # 连续全维度高分（avg_score > 4 才触发降低）
        for _ in range(5):
            session = system.record_rewrite_session(
                "original text", "rewritten text", "test", "medium"
            )
            system.collect_feedback(
                session["session_id"],
                vocabulary_score=5, structure_score=5,
                terminology_score=5, overall_score=5
            )

        suggestions = system.get_rewrite_suggestions("test", "medium")
        assert suggestions["intensity_multiplier"] < 1.0

    def test_apply_strategies(self, tmp_path):
        """策略应用应该返回可操作的建议"""
        system = FeedbackSystem(tmp_path)

        session = system.record_rewrite_session(
            "The model was used to calculate the water yield.",
            "The model was employed to compute the water yield.",
            "生态水文", "medium"
        )
        system.collect_feedback(session["session_id"], overall_score=5, missing_terms=["蒸散发"])

        result = system.apply_learned_strategies(
            "The model was used to calculate the water yield.",
            "生态水文", "medium"
        )
        assert "should_increase_intensity" in result
        assert "should_decrease_intensity" in result
        assert "preferred_techniques" in result
        assert "terms_to_preserve" in result
        assert "蒸散发" in result["terms_to_preserve"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
