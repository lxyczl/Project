"""
改写分析 + 反馈集成
SKILL.md 调用此脚本完成：相似度分析 → 会话记录 → 获取学习建议
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from feedback_system import FeedbackSystem, auto_evaluate
from similarity_calculator import calculate_similarity, format_report, find_sentence_level_matches


class RewriteWithFeedback:
    """改写分析 + 反馈系统"""

    def __init__(self, skill_dir: Path = None):
        if skill_dir is None:
            skill_dir = Path(__file__).parent.parent
        self.skill_dir = skill_dir
        self.feedback_system = FeedbackSystem(skill_dir)

    def analyze_rewrite(
        self,
        original: str,
        rewritten: str,
        domain: str = "general",
        intensity: str = "medium",
        section_type: str = "unknown",
        changes_made: list = None
    ) -> dict:
        """
        分析改写结果并记录会话。

        返回:
            session_id, similarity, suggestions, composite_score, report,
            auto_evaluation, hot_sentences, needs_iteration
        """
        similarity = calculate_similarity(original, rewritten)

        session = self.feedback_system.record_rewrite_session(
            original_text=original,
            rewritten_text=rewritten,
            domain=domain,
            intensity=intensity,
            section_type=section_type,
            changes_made=changes_made
        )

        # 自动评估
        auto_evaluation = auto_evaluate(similarity)

        # 句子级热点
        hot_sentences = find_sentence_level_matches(original, rewritten, threshold=0.5)

        # 为每个热点句子推荐技巧
        for sent in hot_sentences:
            sent["suggested_techniques"] = self._suggest_techniques_for_sentence(sent)

        # 迭代判断
        needs_iteration = (
            auto_evaluation["verdict"] == "fail" or
            (auto_evaluation["verdict"] == "warning" and len(hot_sentences) > 0)
        )

        suggestions = self.feedback_system.get_rewrite_suggestions(
            domain, intensity, current_metrics=similarity
        )

        return {
            "session_id": session["session_id"],
            "similarity": similarity,
            "auto_evaluation": auto_evaluation,
            "suggestions": suggestions,
            "composite_score": similarity["composite_score"],
            "report": format_report(original, rewritten),
            "hot_sentences": hot_sentences,
            "needs_iteration": needs_iteration,
        }

    def _suggest_techniques_for_sentence(self, sentence_metrics: dict) -> list[str]:
        """根据句子级指标推荐技巧"""
        mc = sentence_metrics.get("max_consecutive", 0)
        score = sentence_metrics.get("similarity_score", 0)

        if mc >= 8:
            return ["voice_conversion", "clause_insertion", "word_order_change"]
        elif mc >= 5:
            return ["voice_conversion", "synonym_replacement"]
        elif score >= 0.7:
            return ["synonym_replacement", "word_order_change"]
        else:
            return ["synonym_replacement"]

    def submit_feedback(self, session_id: str, **kwargs) -> dict:
        """提交用户反馈"""
        return self.feedback_system.collect_feedback(session_id=session_id, **kwargs)

    def get_suggestions(self, domain: str = "general", intensity: str = "medium") -> dict:
        """获取基于历史反馈的改写建议"""
        return self.feedback_system.get_rewrite_suggestions(domain, intensity)

    def get_strategy_report(self) -> str:
        """获取反馈学习策略报告"""
        return self.feedback_system.get_strategy_report()


# ── CLI 入口 ──────────────────────────────────────────────────────
# analyze / suggest / feedback / report 均支持 CLI

if __name__ == "__main__":
    import json

    def _usage():
        print("用法:")
        print("  $PY rewrite_with_feedback.py analyze <原文文件> <改写文件> [domain] [intensity]")
        print("  $PY rewrite_with_feedback.py suggest [domain] [intensity]")
        print("  $PY rewrite_with_feedback.py feedback <session_id> <v> <s> <t> <o>")
        print("  $PY rewrite_with_feedback.py report")
        sys.exit(1)

    if len(sys.argv) < 2:
        _usage()

    cmd = sys.argv[1]
    r = RewriteWithFeedback()

    if cmd == "analyze":
        if len(sys.argv) < 4:
            _usage()
        orig_file = Path(sys.argv[2])
        rew_file = Path(sys.argv[3])
        domain = sys.argv[4] if len(sys.argv) > 4 else "general"
        intensity = sys.argv[5] if len(sys.argv) > 5 else "medium"

        original = orig_file.read_text(encoding="utf-8")
        rewritten = rew_file.read_text(encoding="utf-8")

        result = r.analyze_rewrite(original, rewritten, domain, intensity)
        output = json.dumps({
            "session_id": result["session_id"],
            "composite_score": result["composite_score"],
            "auto_evaluation": result["auto_evaluation"],
            "hot_sentences": result["hot_sentences"],
            "needs_iteration": result["needs_iteration"],
            "report": result["report"],
        }, ensure_ascii=False, indent=2)
        sys.stdout.buffer.write(output.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")

    elif cmd == "suggest":
        domain = sys.argv[2] if len(sys.argv) > 2 else "general"
        intensity = sys.argv[3] if len(sys.argv) > 3 else "medium"
        suggestions = r.get_suggestions(domain, intensity)
        print(json.dumps(suggestions, ensure_ascii=False, indent=2))

    elif cmd == "feedback":
        if len(sys.argv) < 7:
            _usage()
        session_id = sys.argv[2]
        v, s, t, o = int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6])
        result = r.submit_feedback(session_id, vocabulary_score=v, structure_score=s,
                                   terminology_score=t, overall_score=o)
        print(f"反馈已记录: {result['session_id']}, 平均分: {sum(result['scores'].values())/4:.1f}/5")

    elif cmd == "report":
        print(r.get_strategy_report())

    else:
        _usage()
