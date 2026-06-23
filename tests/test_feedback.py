"""反馈学习系统测试。"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from feedback_system import FeedbackSystem, auto_evaluate


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


class TestTargetedAdvice:
    """测试针对性建议"""

    def test_targeted_advice_on_failure(self, tmp_path):
        """失败时应生成针对性建议"""
        fs = FeedbackSystem(tmp_path)
        suggestions = fs.get_rewrite_suggestions("body", "medium", current_metrics={
            "failure_type": "cliche_persistent"
        })
        assert len(suggestions["targeted_advice"]) > 0
        assert len(suggestions["priority_techniques"]) > 0

    def test_targeted_advice_from_history(self, tmp_path):
        """历史问题应生成建议"""
        fs = FeedbackSystem(tmp_path)
        fs.strategies["problem_patterns"] = [
            {"section": "body", "failure_type": "risk_increased",
             "risk_before": 0.5, "risk_after": 0.6}
        ]
        fs._save_strategies()
        suggestions = fs.get_rewrite_suggestions("body", "medium")
        assert len(suggestions["targeted_advice"]) > 0

    def test_no_targeted_advice_when_success(self, tmp_path):
        """成功时不应有针对失败的建议"""
        fs = FeedbackSystem(tmp_path)
        suggestions = fs.get_rewrite_suggestions("body", "medium", current_metrics={
            "failure_type": "none"
        })
        assert len(suggestions["targeted_advice"]) == 0

    def test_priority_techniques_for_cliche(self, tmp_path):
        """cliche_persistent 应推荐 cliche_replace"""
        fs = FeedbackSystem(tmp_path)
        suggestions = fs.get_rewrite_suggestions("body", "medium", current_metrics={
            "failure_type": "cliche_persistent"
        })
        assert "cliche_replace" in suggestions["priority_techniques"]

    def test_priority_techniques_for_pattern(self, tmp_path):
        """pattern_persistent 应推荐 sentence_restructure"""
        fs = FeedbackSystem(tmp_path)
        suggestions = fs.get_rewrite_suggestions("body", "medium", current_metrics={
            "failure_type": "pattern_persistent"
        })
        assert "sentence_restructure" in suggestions["priority_techniques"]


class TestEffectiveCombinations:
    """测试有效技巧组合"""

    def test_effective_combinations_in_suggestions(self, tmp_path):
        """高成功率组合应出现在建议中"""
        fs = FeedbackSystem(tmp_path)
        fs.strategies["technique_combinations"] = {
            "cliche_replace+connector_replace": {"success": 5, "total": 5}
        }
        fs._save_strategies()
        suggestions = fs.get_rewrite_suggestions("body", "medium")
        assert len(suggestions["effective_combinations"]) > 0
        assert suggestions["effective_combinations"][0]["combination"] == "cliche_replace+connector_replace"
        assert suggestions["effective_combinations"][0]["success_rate"] == 1.0

    def test_low_rate_excluded(self, tmp_path):
        """低成功率组合不应出现"""
        fs = FeedbackSystem(tmp_path)
        fs.strategies["technique_combinations"] = {
            "cliche_replace+connector_replace": {"success": 1, "total": 5}
        }
        fs._save_strategies()
        suggestions = fs.get_rewrite_suggestions("body", "medium")
        assert len(suggestions["effective_combinations"]) == 0

    def test_low_total_excluded(self, tmp_path):
        """总次数不足的组合不应出现"""
        fs = FeedbackSystem(tmp_path)
        fs.strategies["technique_combinations"] = {
            "cliche_replace+connector_replace": {"success": 1, "total": 1}
        }
        fs._save_strategies()
        suggestions = fs.get_rewrite_suggestions("body", "medium")
        assert len(suggestions["effective_combinations"]) == 0


class TestIssuesRemainFailure:
    """测试 issues_remain 失败类型"""

    def test_issues_remain_generic(self):
        """非特定 issue 类型残留应返回 issues_remain"""
        from feedback_system import classify_failure
        issues_before = [{"type": "low_ttr"}]
        issues_after = [{"type": "low_ttr"}]
        assert classify_failure(0.8, 0.5, issues_before, issues_after) == "issues_remain"


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


# ── Task 3: _learn_from_session 集成测试 ──


class TestTechniqueCombinationLearning:
    """技巧组合学习测试"""

    def test_combo_tracked_for_two_techniques(self, tmp_path):
        """两个技巧应产生一个组合"""
        fs = FeedbackSystem(tmp_path)
        session = {
            "section_type": "body",
            "techniques_used": ["cliche_replace", "connector_replace"],
            "issues_resolved": [],
            "risk_before": 0.8,
            "risk_after": 0.2,
            "risk_reduction": 0.6,
            "timestamp": "2026-01-01T00:00:00",
        }
        fs._learn_from_session(session)

        combos = fs.strategies["technique_combinations"]
        assert "cliche_replace+connector_replace" in combos
        assert combos["cliche_replace+connector_replace"]["total"] == 1
        assert combos["cliche_replace+connector_replace"]["success"] == 1

    def test_combo_not_tracked_for_single_technique(self, tmp_path):
        """单个技巧不应产生组合"""
        fs = FeedbackSystem(tmp_path)
        session = {
            "section_type": "body",
            "techniques_used": ["cliche_replace"],
            "issues_resolved": [],
            "risk_before": 0.8,
            "risk_after": 0.2,
            "risk_reduction": 0.6,
            "timestamp": "2026-01-01T00:00:00",
        }
        fs._learn_from_session(session)

        assert len(fs.strategies["technique_combinations"]) == 0

    def test_combo_failure_not_counted_as_success(self, tmp_path):
        """失败时组合不应计入成功"""
        fs = FeedbackSystem(tmp_path)
        session = {
            "section_type": "body",
            "techniques_used": ["cliche_replace", "connector_replace"],
            "issues_resolved": [],
            "risk_before": 0.5,
            "risk_after": 0.6,
            "risk_reduction": -0.1,
            "timestamp": "2026-01-01T00:00:00",
        }
        fs._learn_from_session(session)

        combo = fs.strategies["technique_combinations"]["cliche_replace+connector_replace"]
        assert combo["total"] == 1
        assert combo["success"] == 0


class TestAdaptiveLearningRate:
    """自适应学习率测试"""

    def test_consecutive_failures_increase_step(self, tmp_path):
        """连续失败应逐步加大调整步长"""
        fs = FeedbackSystem(tmp_path)
        adj = fs.strategies["intensity_adjustments"]["medium"]
        initial = adj["multiplier"]

        session = {
            "section_type": "body",
            "techniques_used": [],
            "issues_resolved": [],
            "risk_before": 0.5,
            "risk_after": 0.6,
            "risk_reduction": -0.1,
            "timestamp": "2026-01-01T00:00:00",
        }
        fs._learn_from_session(session)
        first_fail = adj["multiplier"]
        assert first_fail > initial
        assert adj["consecutive_failures"] == 1

        fs._learn_from_session(session)
        second_fail = adj["multiplier"]
        assert second_fail > first_fail
        assert adj["consecutive_failures"] == 2

    def test_consecutive_successes_decrease_step(self, tmp_path):
        """连续 excellent 应逐步降低强度"""
        fs = FeedbackSystem(tmp_path)
        adj = fs.strategies["intensity_adjustments"]["medium"]
        initial = adj["multiplier"]

        session = {
            "section_type": "body",
            "techniques_used": [],
            "issues_resolved": [],
            "risk_before": 0.9,
            "risk_after": 0.1,
            "risk_reduction": 0.8,
            "timestamp": "2026-01-01T00:00:00",
        }
        fs._learn_from_session(session)
        first_success = adj["multiplier"]
        assert first_success < initial
        assert adj["consecutive_successes"] == 1

        fs._learn_from_session(session)
        second_success = adj["multiplier"]
        assert second_success < first_success
        assert adj["consecutive_successes"] == 2

    def test_failure_resets_successes(self, tmp_path):
        """失败应重置连续成功计数"""
        fs = FeedbackSystem(tmp_path)
        adj = fs.strategies["intensity_adjustments"]["medium"]

        success_session = {
            "section_type": "body",
            "techniques_used": [],
            "issues_resolved": [],
            "risk_before": 0.9,
            "risk_after": 0.1,
            "risk_reduction": 0.8,
            "timestamp": "2026-01-01T00:00:00",
        }
        fs._learn_from_session(success_session)
        assert adj["consecutive_successes"] == 1

        fail_session = {
            "section_type": "body",
            "techniques_used": [],
            "issues_resolved": [],
            "risk_before": 0.5,
            "risk_after": 0.6,
            "risk_reduction": -0.1,
            "timestamp": "2026-01-01T00:00:00",
        }
        fs._learn_from_session(fail_session)
        assert adj["consecutive_successes"] == 0
        assert adj["consecutive_failures"] == 1

    def test_multiplier_bounds(self, tmp_path):
        """乘数不应超出 [0.5, 1.5] 范围"""
        fs = FeedbackSystem(tmp_path)
        adj = fs.strategies["intensity_adjustments"]["medium"]

        fail_session = {
            "section_type": "body",
            "techniques_used": [],
            "issues_resolved": [],
            "risk_before": 0.5,
            "risk_after": 0.6,
            "risk_reduction": -0.1,
            "timestamp": "2026-01-01T00:00:00",
        }
        for _ in range(50):
            fs._learn_from_session(fail_session)
        assert adj["multiplier"] <= 1.5

        # 重置后多次成功
        adj["multiplier"] = 1.0
        adj["consecutive_failures"] = 0
        adj["consecutive_successes"] = 0
        success_session = {
            "section_type": "body",
            "techniques_used": [],
            "issues_resolved": [],
            "risk_before": 0.9,
            "risk_after": 0.1,
            "risk_reduction": 0.8,
            "timestamp": "2026-01-01T00:00:00",
        }
        for _ in range(50):
            fs._learn_from_session(success_session)
        assert adj["multiplier"] >= 0.5


class TestProblemPatternsWithFailureType:
    """问题模式应包含 failure_type"""

    def test_failure_pattern_includes_type(self, tmp_path):
        """失败记录应包含 failure_type 字段"""
        fs = FeedbackSystem(tmp_path)
        session = {
            "section_type": "discussion",
            "techniques_used": ["cliche_replace"],
            "issues_resolved": [],
            "risk_before": 0.5,
            "risk_after": 0.6,
            "risk_reduction": -0.1,
            "timestamp": "2026-01-01T00:00:00",
        }
        fs._learn_from_session(session)

        assert len(fs.strategies["problem_patterns"]) == 1
        pattern = fs.strategies["problem_patterns"][0]
        assert "failure_type" in pattern
        assert pattern["failure_type"] == "risk_increased"

    def test_success_no_problem_pattern(self, tmp_path):
        """成功不应记录问题模式"""
        fs = FeedbackSystem(tmp_path)
        session = {
            "section_type": "body",
            "techniques_used": ["cliche_replace"],
            "issues_resolved": [],
            "risk_before": 0.8,
            "risk_after": 0.2,
            "risk_reduction": 0.6,
            "timestamp": "2026-01-01T00:00:00",
        }
        fs._learn_from_session(session)

        assert len(fs.strategies["problem_patterns"]) == 0


class TestAutoEvaluateIntegration:
    """auto_evaluate 集成到 _learn_from_session 的行为测试"""

    def test_partial_failure_not_counted_as_success(self, tmp_path):
        """auto_evaluate 判定 partial 时不应计入技巧成功"""
        fs = FeedbackSystem(tmp_path)

        # 0.8→0.45 降低 0.35，但 risk_after=0.45 > threshold=0.3 → partial
        session = {
            "section_type": "body",
            "techniques_used": ["cliche_replace"],
            "issues_resolved": [],
            "risk_before": 0.8,
            "risk_after": 0.45,
            "risk_reduction": 0.35,
            "timestamp": "2026-01-01T00:00:00",
        }
        fs._learn_from_session(session)

        tech = fs.strategies["technique_effectiveness"]["cliche_replace"]
        assert tech["total"] == 1
        assert tech["success"] == 0  # partial 不算成功

    def test_marginal_failure_not_counted(self, tmp_path):
        """marginal 不应计入技巧成功"""
        fs = FeedbackSystem(tmp_path)

        # 0.5→0.47 降低 0.03 < 0.05 → marginal
        session = {
            "section_type": "body",
            "techniques_used": ["cliche_replace"],
            "issues_resolved": [],
            "risk_before": 0.5,
            "risk_after": 0.47,
            "risk_reduction": 0.03,
            "timestamp": "2026-01-01T00:00:00",
        }
        fs._learn_from_session(session)

        tech = fs.strategies["technique_effectiveness"]["cliche_replace"]
        assert tech["success"] == 0
