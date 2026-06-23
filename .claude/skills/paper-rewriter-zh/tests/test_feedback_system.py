"""反馈学习系统测试"""
import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from feedback_system import FeedbackSystem, ALL_TECHNIQUES, evaluate_rewrite_quality, classify_failure
from rewrite_with_feedback import RewriteWithFeedback


class TestEvaluateRewriteQuality:
    """客观指标自动评估测试"""

    def test_fail_at_13_consecutive(self):
        metrics = {"max_consecutive": 13, "trigram_overlap": 0.5}
        result = evaluate_rewrite_quality(metrics)
        assert result["verdict"] == "fail"
        assert result["is_success"] is False

    def test_warning_at_10_consecutive(self):
        metrics = {"max_consecutive": 10, "trigram_overlap": 0.1}
        result = evaluate_rewrite_quality(metrics)
        assert result["verdict"] == "warning"
        assert result["is_success"] is False

    def test_warning_at_high_trigram(self):
        metrics = {"max_consecutive": 5, "trigram_overlap": 0.25}
        result = evaluate_rewrite_quality(metrics)
        assert result["verdict"] == "warning"
        assert result["is_success"] is False

    def test_success_at_low_metrics(self):
        metrics = {"max_consecutive": 8, "trigram_overlap": 0.15}
        result = evaluate_rewrite_quality(metrics)
        assert result["verdict"] == "success"
        assert result["is_success"] is True

    def test_excellent_at_very_low_metrics(self):
        metrics = {"max_consecutive": 3, "trigram_overlap": 0.05}
        result = evaluate_rewrite_quality(metrics)
        assert result["verdict"] == "excellent"
        assert result["is_success"] is True

    def test_score_range(self):
        for mc in range(0, 20):
            for tri in [0.0, 0.1, 0.2, 0.3, 0.5]:
                result = evaluate_rewrite_quality({"max_consecutive": mc, "trigram_overlap": tri})
                assert 0 <= result["score"] <= 100


class TestFeedbackSystem:
    """反馈系统核心测试"""

    def _make_system(self):
        """创建临时反馈系统"""
        tmpdir = Path(tempfile.mkdtemp())
        return FeedbackSystem(skill_dir=tmpdir)

    def test_init_creates_directories(self):
        system = self._make_system()
        assert system.sessions_dir.exists()
        assert system.learning_dir.exists()

    def test_default_strategies_has_25_techniques(self):
        system = self._make_system()
        tech = system.strategies["technique_effectiveness"]
        assert len(tech) == 25
        assert "句式重组" in tech
        assert "同义词替换" in tech
        assert "具体化" in tech
        assert "四字词语重组" in tech
        assert "时间表达重组" in tech

    def test_all_techniques_constant(self):
        assert len(ALL_TECHNIQUES) == 25

    def test_record_session(self):
        system = self._make_system()
        session = system.record_rewrite_session(
            original_text="研究表明X很重要",
            rewritten_text="研究显示X具有重要意义",
            domain="生态水文",
            intensity="中度"
        )
        assert "session_id" in session
        assert session["domain"] == "生态水文"
        assert session["metrics"]["max_consecutive"] < 13

    def test_add_changes_to_session(self):
        system = self._make_system()
        session = system.record_rewrite_session(
            original_text="测试", rewritten_text="改写"
        )
        changes = [{"type": "同义词替换", "original": "研究", "rewritten": "探究"}]
        updated = system.add_changes_to_session(session["session_id"], changes)
        assert len(updated["changes_made"]) == 1
        assert updated["changes_made"][0]["type"] == "同义词替换"

    def test_add_changes_invalid_session_raises(self):
        system = self._make_system()
        try:
            system.add_changes_to_session("nonexistent", [{"type": "同义词替换"}])
            assert False, "应该抛出 ValueError"
        except ValueError:
            pass

    def test_collect_feedback(self):
        system = self._make_system()
        session = system.record_rewrite_session(
            original_text="测试文本",
            rewritten_text="改写文本",
            domain="通用"
        )
        result = system.collect_feedback(
            session_id=session["session_id"],
            vocabulary_score=5,
            structure_score=4,
            terminology_score=5,
            overall_score=4
        )
        assert result["scores"]["vocabulary"] == 5
        assert result["scores"]["overall_satisfaction"] == 4

    def test_feedback_score_validation(self):
        system = self._make_system()
        session = system.record_rewrite_session(
            original_text="测试", rewritten_text="改写"
        )
        for invalid_score in [0, 6, -1, 100]:
            try:
                system.collect_feedback(
                    session_id=session["session_id"],
                    vocabulary_score=invalid_score,
                    structure_score=3, terminology_score=3, overall_score=3
                )
                assert False, f"分数 {invalid_score} 应该被拒绝"
            except ValueError:
                pass

    def test_learning_updates_techniques(self):
        system = self._make_system()
        session = system.record_rewrite_session(
            original_text="测试",
            rewritten_text="改写",
            domain="通用",
            changes_made=[{"type": "同义词替换", "original": "研究", "rewritten": "探究"}]
        )
        system.collect_feedback(
            session_id=session["session_id"],
            vocabulary_score=5, structure_score=5,
            terminology_score=5, overall_score=5
        )
        tech = system.strategies["technique_effectiveness"]["同义词替换"]
        assert tech["total"] == 1
        assert tech["success"] == 1

    def test_learning_via_add_changes(self):
        """测试通过 add_changes 记录技巧后学习是否生效"""
        system = self._make_system()
        session = system.record_rewrite_session(original_text="测试", rewritten_text="改写")
        system.add_changes_to_session(session["session_id"], [
            {"type": "句式重组", "original": "A导致B", "rewritten": "B与A密切相关"},
            {"type": "同义词替换", "original": "研究", "rewritten": "探究"}
        ])
        system.collect_feedback(
            session_id=session["session_id"],
            vocabulary_score=5, structure_score=5,
            terminology_score=5, overall_score=5
        )
        assert system.strategies["technique_effectiveness"]["句式重组"]["total"] == 1
        assert system.strategies["technique_effectiveness"]["句式重组"]["success"] == 1
        assert system.strategies["technique_effectiveness"]["同义词替换"]["total"] == 1

    def test_learning_all_25_techniques_recognized(self):
        """验证所有25种技巧都能被学习系统识别"""
        system = self._make_system()
        for tech_name in ALL_TECHNIQUES:
            session = system.record_rewrite_session(
                original_text="测试", rewritten_text="改写",
                changes_made=[{"type": tech_name, "original": "A", "rewritten": "B"}]
            )
            system.collect_feedback(
                session_id=session["session_id"],
                vocabulary_score=5, structure_score=5,
                terminology_score=5, overall_score=5
            )
            assert system.strategies["technique_effectiveness"][tech_name]["total"] == 1, \
                f"技巧 {tech_name} 未被识别"

    def test_learning_low_score_increases_intensity(self):
        system = self._make_system()
        session = system.record_rewrite_session(
            original_text="测试", rewritten_text="改写", intensity="中度"
        )
        system.collect_feedback(
            session_id=session["session_id"],
            vocabulary_score=1, structure_score=1,
            terminology_score=1, overall_score=1
        )
        mult = system.strategies["intensity_adjustments"]["中度"]["multiplier"]
        assert mult > 1.0

    def test_learning_high_score_decreases_intensity(self):
        system = self._make_system()
        session = system.record_rewrite_session(
            original_text="测试", rewritten_text="改写", intensity="中度"
        )
        system.collect_feedback(
            session_id=session["session_id"],
            vocabulary_score=5, structure_score=5,
            terminology_score=5, overall_score=5
        )
        mult = system.strategies["intensity_adjustments"]["中度"]["multiplier"]
        assert mult < 1.0

    def test_learning_accumulates_new_terms(self):
        system = self._make_system()
        session = system.record_rewrite_session(
            original_text="测试", rewritten_text="改写"
        )
        system.collect_feedback(
            session_id=session["session_id"],
            vocabulary_score=3, structure_score=3,
            terminology_score=3, overall_score=3,
            missing_terms=["生态节点", "生态阻力面"]
        )
        assert "生态节点" in system.strategies["new_terms"]
        assert "生态阻力面" in system.strategies["new_terms"]

    def test_suggestions_after_learning(self):
        system = self._make_system()
        for _ in range(2):
            session = system.record_rewrite_session(
                original_text="测试", rewritten_text="改写",
                changes_made=[{"type": "同义词替换", "original": "研究", "rewritten": "探究"}]
            )
            system.collect_feedback(
                session_id=session["session_id"],
                vocabulary_score=5, structure_score=5,
                terminology_score=5, overall_score=5
            )
        suggestions = system.get_rewrite_suggestions("通用", "中度")
        assert "研究->探究" in suggestions["preferred_vocabulary"]

    def test_domain_isolation(self):
        system = self._make_system()
        session1 = system.record_rewrite_session(
            original_text="测试", rewritten_text="改写", domain="生态水文"
        )
        system.collect_feedback(
            session_id=session1["session_id"],
            vocabulary_score=5, structure_score=5,
            terminology_score=5, overall_score=5
        )
        session2 = system.record_rewrite_session(
            original_text="测试", rewritten_text="改写", domain="土木工程"
        )
        system.collect_feedback(
            session_id=session2["session_id"],
            vocabulary_score=2, structure_score=2,
            terminology_score=2, overall_score=2
        )
        assert system.strategies["domain_patterns"]["生态水文"]["avg_score"] > 4
        assert system.strategies["domain_patterns"]["土木工程"]["avg_score"] < 3

    def test_strategy_report(self):
        system = self._make_system()
        report = system.get_strategy_report()
        assert "反馈学习策略报告" in report
        assert "技巧有效性" in report

    def test_invalid_session_feedback_raises(self):
        system = self._make_system()
        try:
            system.collect_feedback("nonexistent-id", vocabulary_score=5)
            assert False, "应该抛出 ValueError"
        except ValueError:
            pass

    def test_auto_learn_success(self):
        """自动学习：改写达标时记为成功"""
        system = self._make_system()
        # 模拟一次成功的改写（连续匹配低）
        session = system.record_rewrite_session(
            original_text="研究表明该方法具有重要意义和价值",
            rewritten_text="相关研究证实此途径具有重大作用与贡献",
            domain="生态水文",
            changes_made=[{"type": "同义词替换", "original": "研究", "rewritten": "探究"}]
        )
        result = system.auto_learn(session["session_id"])
        assert result["learned"] is True
        # 检查技巧是否被记录
        tech = system.strategies["technique_effectiveness"]["同义词替换"]
        assert tech["total"] == 1

    def test_auto_learn_failure_increases_intensity(self):
        """自动学习：改写不达标时加强强度"""
        system = self._make_system()
        # 模拟一次失败的改写（完全相同的文本）
        session = system.record_rewrite_session(
            original_text="研究表明该方法具有重要意义",
            rewritten_text="研究表明该方法具有重要意义",  # 完全相同
            intensity="中度"
        )
        result = system.auto_learn(session["session_id"])
        assert result["evaluation"]["is_success"] is False
        mult = system.strategies["intensity_adjustments"]["中度"]["multiplier"]
        assert mult > 1.0

    def test_auto_learn_records_session_flag(self):
        """自动学习后会话标记 auto_learned"""
        system = self._make_system()
        session = system.record_rewrite_session(
            original_text="测试文本", rewritten_text="改写文本"
        )
        system.auto_learn(session["session_id"])
        # 重新加载会话检查标记
        session_file = system.sessions_dir / f"{session['session_id']}.json"
        with open(session_file, 'r', encoding='utf-8') as f:
            updated = json.load(f)
        assert updated.get("auto_learned") is True

    def test_auto_evaluation_in_session(self):
        """会话记录时自动包含 auto_evaluation"""
        system = self._make_system()
        session = system.record_rewrite_session(
            original_text="测试", rewritten_text="改写"
        )
        assert "auto_evaluation" in session
        assert "verdict" in session["auto_evaluation"]
        assert "is_success" in session["auto_evaluation"]


class TestClassifyFailure:
    """失败原因分类测试"""

    def test_excellent_returns_none(self):
        assert classify_failure({"max_consecutive": 3, "trigram_overlap": 0.05}, "excellent") == "none"

    def test_success_returns_none(self):
        assert classify_failure({"max_consecutive": 8, "trigram_overlap": 0.15}, "success") == "none"

    def test_fail_returns_consecutive_too_long(self):
        assert classify_failure({"max_consecutive": 15, "trigram_overlap": 0.5}, "fail") == "consecutive_too_long"

    def test_warning_consecutive_and_trigram(self):
        result = classify_failure({"max_consecutive": 11, "trigram_overlap": 0.30}, "warning")
        assert result == "structure_too_similar"

    def test_warning_consecutive_only(self):
        result = classify_failure({"max_consecutive": 11, "trigram_overlap": 0.10}, "warning")
        assert result == "consecutive_risk"

    def test_warning_trigram_only(self):
        result = classify_failure({"max_consecutive": 5, "trigram_overlap": 0.25}, "warning")
        assert result == "trigram_risk"

    def test_warning_mixed(self):
        result = classify_failure({"max_consecutive": 8, "trigram_overlap": 0.15}, "warning")
        assert result == "mixed_risk"


class TestTechniqueCombinations:
    """技巧组合学习测试"""

    def _make_system(self):
        tmpdir = Path(tempfile.mkdtemp())
        return FeedbackSystem(skill_dir=tmpdir)

    def test_default_strategies_has_combinations_field(self):
        system = self._make_system()
        assert "technique_combinations" in system.strategies

    def test_auto_learn_records_combinations(self):
        system = self._make_system()
        session = system.record_rewrite_session(
            original_text="测试文本足够长以通过检查",
            rewritten_text="改写文本也足够长以通过检查",
            changes_made=[
                {"type": "句式重组", "original": "A", "rewritten": "B"},
                {"type": "同义词替换", "original": "C", "rewritten": "D"},
            ]
        )
        system.auto_learn(session["session_id"])
        combos = system.strategies["technique_combinations"]
        # 排序后 key 应为 "句式重组+同义词替换"（Unicode 排序）
        key = "+".join(sorted(["句式重组", "同义词替换"]))
        assert key in combos
        assert combos[key]["total"] == 1

    def test_combinations_deduplicate(self):
        """同一技巧不与自身组合"""
        system = self._make_system()
        session = system.record_rewrite_session(
            original_text="测试", rewritten_text="改写",
            changes_made=[
                {"type": "同义词替换", "original": "A", "rewritten": "B"},
                {"type": "同义词替换", "original": "C", "rewritten": "D"},
            ]
        )
        system.auto_learn(session["session_id"])
        combos = system.strategies["technique_combinations"]
        # 只有一个技巧，不应产生组合
        assert len(combos) == 0 or all(v["total"] == 0 for v in combos.values())

    def test_suggestions_include_effective_combinations(self):
        system = self._make_system()
        # 成功 3 次
        for _ in range(3):
            session = system.record_rewrite_session(
                original_text="测试文本足够长", rewritten_text="改写文本也足够长",
                changes_made=[
                    {"type": "句式重组", "original": "A", "rewritten": "B"},
                    {"type": "同义词替换", "original": "C", "rewritten": "D"},
                ]
            )
            system.auto_learn(session["session_id"])
        suggestions = system.get_rewrite_suggestions("通用", "中度")
        assert "effective_combinations" in suggestions


class TestRewriteWithFeedback:
    """CLI 编排器测试"""

    def _make_rewriter(self):
        tmpdir = Path(tempfile.mkdtemp())
        return RewriteWithFeedback(skill_dir=tmpdir)

    def test_analyze_rewrite(self):
        r = self._make_rewriter()
        result = r.analyze_rewrite(
            original="研究表明该方法具有重要意义",
            rewritten="研究显示此方法具有重大价值",
            domain="生态水文",
            intensity="中度"
        )
        assert "session_id" in result
        assert "similarity" in result
        assert "suggestions" in result
        assert "report" in result

    def test_add_changes(self):
        r = self._make_rewriter()
        analysis = r.analyze_rewrite("原文", "改写", "通用", "中度")
        changes_json = json.dumps([{"type": "同义词替换", "original": "研究", "rewritten": "探究"}])
        session = r.add_changes(analysis["session_id"], changes_json)
        assert len(session["changes_made"]) == 1

    def test_submit_and_get_suggestions(self):
        r = self._make_rewriter()
        analysis = r.analyze_rewrite("原文", "改写", "通用", "中度")
        r.submit_feedback(
            session_id=analysis["session_id"],
            vocabulary_score=4, structure_score=4,
            terminology_score=4, overall_score=4
        )
        suggestions = r.get_suggestions("通用", "中度")
        assert "preferred_vocabulary" in suggestions

    def test_full_flow_auto_learn(self):
        """完整流程（自动学习，无需打分）：analyze → changes → learn → suggest"""
        r = self._make_rewriter()
        for _ in range(2):
            # 1. 分析（用不同文本避免连续匹配）
            analysis = r.analyze_rewrite(
                "研究表明该方法具有重要意义和价值",
                "相关研究证实此途径具有重大作用与贡献",
                "生态水文", "中度"
            )
            # 2. 记录修改
            changes = json.dumps([
                {"type": "句式重组", "original": "A导致B", "rewritten": "B与A相关"},
                {"type": "同义词替换", "original": "研究", "rewritten": "探究"}
            ])
            r.add_changes(analysis["session_id"], changes)
            # 3. 自动学习（无需打分！）
            learn_result = r.auto_learn(analysis["session_id"])
            assert learn_result["learned"] is True
        # 4. 获取建议
        suggestions = r.get_suggestions("生态水文", "中度")
        assert "研究->探究" in suggestions["preferred_vocabulary"]


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
