"""反馈学习系统测试。"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from feedback_system import FeedbackSystem


def test_record_session(tmp_path):
    """记录会话应返回正确结构。"""
    fs = FeedbackSystem(tmp_path)
    result = fs.record_session(
        original_text="综上所述，本文提出了一种方法。",
        rewritten_text="从整体来看，本文的方案如下。",
        risk_before=0.8,
        risk_after=0.2,
        section_type="body",
        techniques_used=["cliche_replace"],
        issues_resolved=["cliche_detected"],
    )
    assert result["success"] is True
    assert result["risk_reduction"] == 0.6
    assert result["session_id"] is not None

    # 验证文件已保存
    session_file = tmp_path / "feedback" / "sessions" / f"{result['session_id']}.json"
    assert session_file.exists()


def test_record_failed_session(tmp_path):
    """失败会话应被记录。"""
    fs = FeedbackSystem(tmp_path)
    result = fs.record_session(
        original_text="原文",
        rewritten_text="改写后",
        risk_before=0.5,
        risk_after=0.6,
    )
    assert result["success"] is False
    assert result["risk_reduction"] < 0


def test_technique_effectiveness_tracking(tmp_path):
    """技巧有效性应被追踪。"""
    fs = FeedbackSystem(tmp_path)

    # 记录 3 次成功、1 次失败
    for _ in range(3):
        fs.record_session("原文", "改写", 0.8, 0.2, techniques_used=["cliche_replace"])
    fs.record_session("原文", "改写", 0.5, 0.6, techniques_used=["cliche_replace"])

    tech = fs.strategies["technique_effectiveness"]["cliche_replace"]
    assert tech["total"] == 4
    assert tech["success"] == 3


def test_section_patterns_tracking(tmp_path):
    """章节模式应被追踪。"""
    fs = FeedbackSystem(tmp_path)
    fs.record_session("原文", "改写", 0.8, 0.2, section_type="abstract",
                      issues_resolved=["cliche_detected"])
    fs.record_session("原文", "改写", 0.7, 0.3, section_type="abstract",
                      issues_resolved=["connector_overuse"])

    sp = fs.strategies["section_patterns"]["abstract"]
    assert sp["session_count"] == 2
    assert "cliche_detected" in sp["common_issues"]
    assert "connector_overuse" in sp["common_issues"]


def test_get_rewrite_suggestions(tmp_path):
    """建议应包含有效数据。"""
    fs = FeedbackSystem(tmp_path)

    # 先记录几次成功的会话
    for _ in range(3):
        fs.record_session("原文", "改写", 0.8, 0.2,
                          section_type="body",
                          techniques_used=["cliche_replace", "connector_replace"])

    suggestions = fs.get_rewrite_suggestions("body", "medium")
    assert suggestions["session_count"] == 3
    assert len(suggestions["effective_techniques"]) > 0
    assert suggestions["avg_reduction"] > 0


def test_strategy_report(tmp_path):
    """策略报告应为非空字符串。"""
    fs = FeedbackSystem(tmp_path)
    fs.record_session("原文", "改写", 0.8, 0.2, techniques_used=["cliche_replace"])
    report = fs.get_strategy_report()
    assert "反馈学习策略报告" in report
    assert "技巧有效性" in report


def test_vocabulary_preference(tmp_path):
    """词汇偏好应被记录。"""
    fs = FeedbackSystem(tmp_path)
    fs.record_vocabulary_preference("综上所述", "从整体来看")
    fs.record_vocabulary_preference("综上所述", "从整体来看")

    assert fs.strategies["vocabulary_preferences"]["综上所述→从整体来看"]["success"] == 2


def test_intensity_auto_adjust_on_failure(tmp_path):
    """失败时应自动加强改写强度。"""
    fs = FeedbackSystem(tmp_path)
    initial = fs.strategies["intensity_adjustments"]["medium"]["multiplier"]

    # 模拟一次严重失败（风险分升高）
    fs.record_session("原文", "改写", 0.3, 0.5)

    after = fs.strategies["intensity_adjustments"]["medium"]["multiplier"]
    assert after > initial


def test_intensity_auto_adjust_on_success(tmp_path):
    """大幅成功时应适当减弱改写强度。"""
    fs = FeedbackSystem(tmp_path)
    initial = fs.strategies["intensity_adjustments"]["medium"]["multiplier"]

    # 模拟一次大幅成功
    fs.record_session("原文", "改写", 0.8, 0.1)

    after = fs.strategies["intensity_adjustments"]["medium"]["multiplier"]
    assert after < initial


def test_problem_patterns_recorded(tmp_path):
    """失败时应记录问题模式。"""
    fs = FeedbackSystem(tmp_path)
    fs.record_session("原文", "改写", 0.5, 0.6,
                      section_type="discussion",
                      techniques_used=["cliche_replace"])

    assert len(fs.strategies["problem_patterns"]) == 1
    assert fs.strategies["problem_patterns"][0]["section"] == "discussion"


class TestAutoEvaluate:
    """测试自动评估"""

    def test_auto_evaluate_fail(self):
        """风险分没降应判定为 fail"""
        from feedback_system import auto_evaluate
        result = auto_evaluate(0.5, 0.6)
        assert result["verdict"] == "fail"
        assert result["is_success"] is False
        assert result["reduction"] < 0

    def test_auto_evaluate_marginal(self):
        """降低太少应判定为 marginal"""
        from feedback_system import auto_evaluate
        result = auto_evaluate(0.5, 0.47)
        assert result["verdict"] == "marginal"
        assert result["is_success"] is False

    def test_auto_evaluate_partial(self):
        """降了但没过阈值应判定为 partial"""
        from feedback_system import auto_evaluate
        result = auto_evaluate(0.8, 0.45, threshold=0.3)
        assert result["verdict"] == "partial"
        assert result["is_success"] is False

    def test_auto_evaluate_success(self):
        """正常成功"""
        from feedback_system import auto_evaluate
        result = auto_evaluate(0.5, 0.25, threshold=0.3)
        assert result["verdict"] == "success"
        assert result["is_success"] is True

    def test_auto_evaluate_excellent(self):
        """大幅降低应判定为 excellent"""
        from feedback_system import auto_evaluate
        result = auto_evaluate(0.9, 0.2)
        assert result["verdict"] == "excellent"
        assert result["is_success"] is True

    def test_auto_evaluate_has_reason(self):
        """应返回原因说明"""
        from feedback_system import auto_evaluate
        result = auto_evaluate(0.5, 0.6)
        assert "reason" in result
        assert len(result["reason"]) > 0


class TestClassifyFailure:
    """测试失败分类"""

    def test_risk_increased(self):
        """风险反升"""
        from feedback_system import classify_failure
        assert classify_failure(0.5, 0.6, [], []) == "risk_increased"

    def test_minimal_effect(self):
        """几乎没效果"""
        from feedback_system import classify_failure
        assert classify_failure(0.5, 0.47, [], []) == "minimal_effect"

    def test_cliche_persistent(self):
        """套话未消除"""
        from feedback_system import classify_failure
        issues_before = [{"type": "cliche_detected"}]
        issues_after = [{"type": "cliche_detected"}]
        assert classify_failure(0.8, 0.5, issues_before, issues_after) == "cliche_persistent"

    def test_connector_persistent(self):
        """连接词未解决"""
        from feedback_system import classify_failure
        issues_before = [{"type": "connector_overuse"}]
        issues_after = [{"type": "connector_overuse"}]
        assert classify_failure(0.8, 0.5, issues_before, issues_after) == "connector_persistent"

    def test_pattern_persistent(self):
        """句式模式未打破"""
        from feedback_system import classify_failure
        issues_before = [{"type": "low_burstiness"}]
        issues_after = [{"type": "low_burstiness"}]
        assert classify_failure(0.8, 0.5, issues_before, issues_after) == "pattern_persistent"

    def test_insufficient_reduction(self):
        """issue 解决但风险仍高"""
        from feedback_system import classify_failure
        issues_before = [{"type": "cliche_detected"}]
        issues_after = []
        assert classify_failure(0.8, 0.65, issues_before, issues_after) == "insufficient_reduction"

    def test_success_returns_none(self):
        """成功时返回 none"""
        from feedback_system import classify_failure
        assert classify_failure(0.8, 0.2, [], []) == "none"
