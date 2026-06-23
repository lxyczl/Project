"""
改写分析 + 反馈集成
SKILL.md 调用此脚本完成：相似度分析 → 会话记录 → 自动学习
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from feedback_system import FeedbackSystem, evaluate_rewrite_quality
from similarity_calculator import calculate_similarity, format_report, find_sentence_level_matches


class RewriteWithFeedback:
    """改写分析 + 反馈系统"""

    def __init__(self, data_dir: Path = None):
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / "feedback"
        self.data_dir = data_dir
        self.feedback_system = FeedbackSystem(data_dir)

    def analyze_rewrite(
        self,
        original: str,
        rewritten: str,
        domain: str = "通用",
        intensity: str = "中度",
        section_type: str = "unknown"
    ) -> dict:
        """分析改写结果并记录会话。"""
        similarity = calculate_similarity(original, rewritten)

        session = self.feedback_system.record_rewrite_session(
            original_text=original,
            rewritten_text=rewritten,
            domain=domain,
            intensity=intensity,
            section_type=section_type
        )

        suggestions = self.feedback_system.get_rewrite_suggestions(domain, intensity, current_metrics=similarity)

        # 句子级热点
        hot_sentences = find_sentence_level_matches(original, rewritten, threshold=0.5)
        for sent in hot_sentences:
            sent["suggested_techniques"] = self._suggest_techniques_for_sentence(sent)

        auto_evaluation = session["auto_evaluation"]
        needs_iteration = (
            auto_evaluation["verdict"] == "fail" or
            (auto_evaluation["verdict"] == "warning" and len(hot_sentences) > 0)
        )

        return {
            "session_id": session["session_id"],
            "similarity": similarity,
            "auto_evaluation": auto_evaluation,
            "suggestions": suggestions,
            "report": format_report(original, rewritten),
            "hot_sentences": hot_sentences,
            "needs_iteration": needs_iteration,
        }

    def _suggest_techniques_for_sentence(self, sentence_metrics: dict) -> list[str]:
        """根据句子级指标推荐技巧"""
        mc = sentence_metrics.get("max_consecutive", 0)
        tri = sentence_metrics.get("trigram_overlap", 0)

        if mc >= 13:
            return ["句式重组", "拆分长句", "主被动转换"]
        elif mc >= 10:
            return ["句式重组", "同义词替换"]
        elif tri >= 0.25:
            return ["同义词替换", "因果倒置", "条件重组"]
        else:
            return ["同义词替换", "调整语序"]

    def add_changes(self, session_id: str, changes_json: str) -> dict:
        """向会话追加 changes_made 记录"""
        import json
        changes = json.loads(changes_json)
        if not isinstance(changes, list):
            raise ValueError("changes 必须是 JSON 数组")
        return self.feedback_system.add_changes_to_session(session_id, changes)

    def auto_learn(self, session_id: str) -> dict:
        """基于客观指标自动学习"""
        return self.feedback_system.auto_learn(session_id)

    def submit_feedback(self, session_id: str, **kwargs) -> dict:
        """提交用户主观反馈（可选）"""
        return self.feedback_system.collect_feedback(session_id=session_id, **kwargs)

    def get_suggestions(self, domain: str = "通用", intensity: str = "中度", current_metrics: dict = None) -> dict:
        """获取基于历史反馈的改写建议，可选带当前文本指标"""
        return self.feedback_system.get_rewrite_suggestions(domain, intensity, current_metrics=current_metrics)

    def get_strategy_report(self) -> str:
        """获取反馈学习策略报告"""
        return self.feedback_system.get_strategy_report()


# ── CLI 入口 ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    def _usage():
        print("用法:")
        print("  $PY rewrite_with_feedback.py suggest [domain] [intensity]")
        print("  $PY rewrite_with_feedback.py analyze <original_file> <rewritten_file> [domain] [intensity]")
        print("  $PY rewrite_with_feedback.py changes <session_id> '<json_array>'")
        print("  $PY rewrite_with_feedback.py learn <session_id>          # 自动学习（无需打分）")
        print("  $PY rewrite_with_feedback.py feedback <session_id> <v> <s> <t> <o>  # 手动反馈（可选）")
        print("  $PY rewrite_with_feedback.py report")
        sys.exit(1)

    if len(sys.argv) < 2:
        _usage()

    cmd = sys.argv[1]
    r = RewriteWithFeedback()

    if cmd == "suggest":
        domain = sys.argv[2] if len(sys.argv) > 2 else "通用"
        intensity = sys.argv[3] if len(sys.argv) > 3 else "中度"
        suggestions = r.get_suggestions(domain, intensity)
        print(json.dumps(suggestions, ensure_ascii=False, indent=2))

    elif cmd == "analyze":
        if len(sys.argv) < 4:
            _usage()
        orig_file, rew_file = sys.argv[2], sys.argv[3]
        domain = sys.argv[4] if len(sys.argv) > 4 else "通用"
        intensity = sys.argv[5] if len(sys.argv) > 5 else "中度"
        try:
            original = Path(orig_file).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            original = Path(orig_file).read_text(encoding="gbk")
        try:
            rewritten = Path(rew_file).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            rewritten = Path(rew_file).read_text(encoding="gbk")
        result = r.analyze_rewrite(original, rewritten, domain, intensity)
        ev = result["auto_evaluation"]
        print(f"会话ID: {result['session_id']}")
        print(f"自动评估: {ev['verdict']} ({ev['score']}/100) — {ev['reason']}")
        print(result["report"])
        print("\n### 学习建议")
        print(json.dumps(result["suggestions"], ensure_ascii=False, indent=2))

    elif cmd == "changes":
        if len(sys.argv) < 4:
            print("用法: $PY rewrite_with_feedback.py changes <session_id> '<json_array>'")
            sys.exit(1)
        session_id = sys.argv[2]
        changes_json = sys.argv[3]
        session = r.add_changes(session_id, changes_json)
        print(f"已记录 {len(session['changes_made'])} 条修改到会话 {session_id}")

    elif cmd == "learn":
        if len(sys.argv) < 3:
            print("用法: $PY rewrite_with_feedback.py learn <session_id>")
            sys.exit(1)
        session_id = sys.argv[2]
        result = r.auto_learn(session_id)
        ev = result["evaluation"]
        print(f"自动学习完成: {ev['verdict']} ({ev['score']}/100)")
        print(f"判定: {ev['reason']}")

    elif cmd == "feedback":
        if len(sys.argv) < 7:
            _usage()
        session_id = sys.argv[2]
        try:
            v, s, t, o = int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6])
        except ValueError:
            print("错误: 评分必须是整数")
            sys.exit(1)
        try:
            result = r.submit_feedback(session_id, vocabulary_score=v, structure_score=s,
                                       terminology_score=t, overall_score=o)
        except ValueError as e:
            print(f"错误: {e}")
            sys.exit(1)
        avg = sum(result["scores"].values()) / 4
        print(f"反馈已记录: {result['session_id']}, 平均分: {avg:.1f}/5")

    elif cmd == "report":
        print(r.get_strategy_report())

    else:
        _usage()
