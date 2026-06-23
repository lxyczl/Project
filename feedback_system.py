"""反馈学习系统。

记录改写会话、追踪技巧有效性、生成改写建议、输出策略报告。
风险分驱动，无需用户手动打分。
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional


def auto_evaluate(risk_before: float, risk_after: float,
                  threshold: float = 0.3) -> dict:
    """基于风险分变化自动判定改写结果。"""
    reduction = risk_before - risk_after

    if risk_after >= risk_before:
        verdict = "fail"
    elif reduction < 0.05:
        verdict = "marginal"
    elif risk_after > threshold:
        verdict = "partial"
    elif reduction >= 0.3:
        verdict = "excellent"
    else:
        verdict = "success"

    return {
        "verdict": verdict,
        "is_success": verdict in ("success", "excellent"),
        "reduction": round(reduction, 3),
        "reason": _verdict_reason(verdict, reduction, risk_after, threshold),
    }


def _verdict_reason(verdict: str, reduction: float,
                    risk_after: float, threshold: float) -> str:
    """生成判定原因说明"""
    if verdict == "fail":
        return f"风险分未降低（{risk_after:.2f}）"
    elif verdict == "marginal":
        return f"降低幅度不足（仅 {reduction:.3f}）"
    elif verdict == "partial":
        return f"风险分降至 {risk_after:.2f}，仍高于阈值 {threshold:.2f}"
    elif verdict == "excellent":
        return f"大幅降低 {reduction:.3f}，改写效果显著"
    return "改写成功"


def classify_failure(risk_before: float, risk_after: float,
                     issues_before: list, issues_after: list) -> str:
    """细分失败原因，用于针对性建议。"""
    # 成功时返回 none
    if risk_after < risk_before and (risk_before - risk_after) >= 0.05:
        before_types = {i["type"] for i in issues_before}
        after_types = {i["type"] for i in issues_after}
        remaining = before_types & after_types
        if not remaining and (risk_before - risk_after) >= 0.2:
            return "none"

    if risk_after >= risk_before:
        return "risk_increased"

    reduction = risk_before - risk_after
    if reduction < 0.05:
        return "minimal_effect"

    before_types = {i["type"] for i in issues_before}
    after_types = {i["type"] for i in issues_after}
    remaining = before_types & after_types

    if "cliche_detected" in remaining:
        return "cliche_persistent"
    if "connector_overuse" in remaining:
        return "connector_persistent"
    if "low_burstiness" in remaining:
        return "pattern_persistent"
    if remaining:
        return "issues_remain"

    return "insufficient_reduction"


class FeedbackSystem:
    """反馈学习系统"""

    def __init__(self, skill_dir: Optional[Path] = None):
        if skill_dir is None:
            skill_dir = Path(__file__).parent

        self.skill_dir = skill_dir
        self.feedback_dir = skill_dir / "feedback"
        self.sessions_dir = self.feedback_dir / "sessions"
        self.learning_dir = self.feedback_dir / "learning"
        self.strategies_file = self.learning_dir / "strategies.json"

        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.learning_dir.mkdir(parents=True, exist_ok=True)

        self.strategies = self._load_strategies()

    def _load_strategies(self) -> dict:
        """加载学习到的策略。"""
        if self.strategies_file.exists():
            try:
                return json.loads(self.strategies_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        return {
            "vocabulary_preferences": {},
            "technique_effectiveness": {
                "connector_replace": {"success": 0, "total": 0},
                "sentence_restructure": {"success": 0, "total": 0},
                "cliche_replace": {"success": 0, "total": 0},
                "passive_to_active": {"success": 0, "total": 0},
                "personal_voice_add": {"success": 0, "total": 0},
                "paragraph_reorganize": {"success": 0, "total": 0},
            },
            "section_patterns": {},
            "intensity_adjustments": {
                "light": {"multiplier": 1.0},
                "medium": {"multiplier": 1.0},
                "heavy": {"multiplier": 1.0},
            },
            "problem_patterns": [],
            "session_count": 0,
            "total_paragraphs_rewritten": 0,
            "total_risk_reduction": 0.0,
            "last_updated": datetime.now().isoformat(),
        }

    def _save_strategies(self) -> None:
        """保存策略到文件。"""
        self.strategies["last_updated"] = datetime.now().isoformat()
        self.strategies_file.write_text(
            json.dumps(self.strategies, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ── 会话记录 ──

    def record_session(
        self,
        original_text: str,
        rewritten_text: str,
        risk_before: float,
        risk_after: float,
        section_type: str = "body",
        techniques_used: Optional[list] = None,
        issues_resolved: Optional[list] = None,
    ) -> dict:
        """记录一次改写会话。

        Args:
            original_text: 原文
            rewritten_text: 改写后文本
            risk_before: 改写前风险分
            risk_after: 改写后风险分
            section_type: 章节类型
            techniques_used: 使用的改写技巧列表
            issues_resolved: 解决的 issue type 列表

        Returns:
            会话信息 dict
        """
        session_id = f"{datetime.now().strftime('%Y-%m-%d')}-{uuid.uuid4().hex[:8]}"
        risk_reduction = round(risk_before - risk_after, 3)
        success = risk_after < risk_before

        session = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "section_type": section_type,
            "original_text": original_text[:200],
            "rewritten_text": rewritten_text[:200],
            "risk_before": risk_before,
            "risk_after": risk_after,
            "risk_reduction": risk_reduction,
            "success": success,
            "techniques_used": techniques_used or [],
            "issues_resolved": issues_resolved or [],
        }

        session_file = self.sessions_dir / f"{session_id}.json"
        session_file.write_text(
            json.dumps(session, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 学习
        self._learn_from_session(session)

        return session

    # ── 学习逻辑 ──

    def _learn_from_session(self, session: dict) -> None:
        """从会话中学习并更新策略。"""
        success = session["success"]
        section = session["section_type"]
        techniques = session["techniques_used"]
        issues = session["issues_resolved"]
        reduction = session["risk_reduction"]

        # 1. 全局统计
        self.strategies["session_count"] += 1
        self.strategies["total_paragraphs_rewritten"] += 1
        self.strategies["total_risk_reduction"] = round(
            self.strategies["total_risk_reduction"] + reduction, 3
        )

        # 2. 技巧有效性
        for tech in techniques:
            if tech not in self.strategies["technique_effectiveness"]:
                self.strategies["technique_effectiveness"][tech] = {"success": 0, "total": 0}
            self.strategies["technique_effectiveness"][tech]["total"] += 1
            if success:
                self.strategies["technique_effectiveness"][tech]["success"] += 1

        # 3. 章节模式
        if section not in self.strategies["section_patterns"]:
            self.strategies["section_patterns"][section] = {
                "avg_reduction": 0.0,
                "session_count": 0,
                "common_issues": [],
                "effective_techniques": {},
            }

        sp = self.strategies["section_patterns"][section]
        count = sp["session_count"]
        sp["avg_reduction"] = round(
            (sp["avg_reduction"] * count + reduction) / (count + 1), 3
        )
        sp["session_count"] += 1

        # 记录该章节的常见 issue
        for issue in issues:
            if issue not in sp["common_issues"]:
                sp["common_issues"].append(issue)
        sp["common_issues"] = sp["common_issues"][-10:]

        # 记录该章节的有效技巧
        for tech in techniques:
            if tech not in sp["effective_techniques"]:
                sp["effective_techniques"][tech] = {"success": 0, "total": 0}
            sp["effective_techniques"][tech]["total"] += 1
            if success:
                sp["effective_techniques"][tech]["success"] += 1

        # 4. 强度自适应
        if not success and reduction < -0.1:
            # 风险分反而升高，加强改写强度
            for level in ("light", "medium"):
                cur = self.strategies["intensity_adjustments"][level]["multiplier"]
                self.strategies["intensity_adjustments"][level]["multiplier"] = min(
                    1.5, round(cur + 0.05, 2)
                )
        elif success and reduction > 0.3:
            # 大幅降低，可以稍微减弱
            cur = self.strategies["intensity_adjustments"]["medium"]["multiplier"]
            self.strategies["intensity_adjustments"]["medium"]["multiplier"] = max(
                0.5, round(cur - 0.02, 2)
            )

        # 5. 问题模式
        if not success:
            self.strategies["problem_patterns"].append({
                "section": section,
                "risk_before": session["risk_before"],
                "risk_after": session["risk_after"],
                "techniques": techniques,
                "timestamp": session["timestamp"],
            })
            self.strategies["problem_patterns"] = self.strategies["problem_patterns"][-20:]

        self._save_strategies()

    # ── 建议生成 ──

    def get_rewrite_suggestions(
        self,
        section_type: str = "body",
        intensity: str = "medium",
    ) -> dict:
        """获取改写建议（基于历史学习）。

        Returns:
            {
                "effective_techniques": [...],
                "intensity_multiplier": float,
                "section_issues": [...],
                "preferred_vocabulary": [...],
                "session_count": int,
                "avg_reduction": float,
            }
        """
        suggestions = {
            "effective_techniques": [],
            "intensity_multiplier": 1.0,
            "section_issues": [],
            "preferred_vocabulary": [],
            "session_count": self.strategies["session_count"],
            "avg_reduction": 0.0,
        }

        # 1. 全局有效技巧（成功率 ≥ 60%）
        for tech, data in self.strategies["technique_effectiveness"].items():
            if data["total"] > 0:
                rate = data["success"] / data["total"]
                if rate >= 0.6:
                    suggestions["effective_techniques"].append({
                        "technique": tech,
                        "success_rate": round(rate, 2),
                        "count": data["total"],
                    })
        suggestions["effective_techniques"].sort(
            key=lambda x: x["success_rate"], reverse=True
        )

        # 2. 章节特定建议
        if section_type in self.strategies["section_patterns"]:
            sp = self.strategies["section_patterns"][section_type]
            suggestions["section_issues"] = sp.get("common_issues", [])[-5:]

            # 章节特定有效技巧
            for tech, data in sp.get("effective_techniques", {}).items():
                if data["total"] >= 2:
                    rate = data["success"] / data["total"]
                    if rate >= 0.6:
                        # 检查是否已在全局列表中
                        existing = {t["technique"] for t in suggestions["effective_techniques"]}
                        if tech not in existing:
                            suggestions["effective_techniques"].append({
                                "technique": tech,
                                "success_rate": round(rate, 2),
                                "count": data["total"],
                                "section_specific": True,
                            })

        # 3. 强度调整
        if intensity in self.strategies["intensity_adjustments"]:
            suggestions["intensity_multiplier"] = self.strategies[
                "intensity_adjustments"
            ][intensity]["multiplier"]

        # 4. 词汇偏好（成功 ≥ 2 次的替换对）
        for key, data in self.strategies["vocabulary_preferences"].items():
            if data.get("success", 0) >= 2:
                suggestions["preferred_vocabulary"].append(key)

        # 5. 平均风险降低
        count = self.strategies["session_count"]
        if count > 0:
            suggestions["avg_reduction"] = round(
                self.strategies["total_risk_reduction"] / count, 3
            )

        return suggestions

    # ── 策略报告 ──

    def get_strategy_report(self) -> str:
        """生成策略报告（Markdown 格式）。"""
        s = self.strategies
        lines = ["## 反馈学习策略报告", ""]

        # 概览
        count = s["session_count"]
        total_red = s["total_risk_reduction"]
        avg_red = round(total_red / count, 3) if count > 0 else 0
        lines.append(f"**总会话数**: {count}  |  **总风险降低**: {total_red:.3f}  |  **平均降低**: {avg_red:.3f}")
        lines.append("")

        # 技巧有效性
        lines.append("### 技巧有效性")
        for tech, data in s["technique_effectiveness"].items():
            if data["total"] > 0:
                rate = data["success"] / data["total"]
                bar = "█" * int(rate * 5) + "░" * (5 - int(rate * 5))
                lines.append(f"- {tech}: {bar} {rate:.0%} ({data['success']}/{data['total']})")
            else:
                lines.append(f"- {tech}: 暂无数据")
        lines.append("")

        # 章节模式
        lines.append("### 章节模式")
        for sec, data in s["section_patterns"].items():
            avg = data["avg_reduction"]
            cnt = data["session_count"]
            lines.append(f"- {sec}: 平均降低 {avg:.3f} ({cnt} 次)")
            if data.get("common_issues"):
                lines.append(f"  常见 issue: {', '.join(data['common_issues'][-3:])}")
        lines.append("")

        # 强度调整
        lines.append("### 强度调整")
        for level, data in s["intensity_adjustments"].items():
            mult = data["multiplier"]
            if mult > 1.05:
                lines.append(f"- {level}: {mult:.2f}x ↑（低效果，加强改写）")
            elif mult < 0.95:
                lines.append(f"- {level}: {mult:.2f}x ↓（高效果，适当减弱）")
            else:
                lines.append(f"- {level}: {mult:.2f}x（标准）")
        lines.append("")

        # 问题模式
        problems = s.get("problem_patterns", [])
        if problems:
            lines.append("### 最近问题（最近 5 个）")
            for p in problems[-5:]:
                lines.append(f"- [{p['section']}] {p['risk_before']:.2f}→{p['risk_after']:.2f} 技巧: {', '.join(p.get('techniques', []))}")
            lines.append("")

        lines.append(f"*更新时间: {s.get('last_updated', 'N/A')}*")
        return "\n".join(lines)

    # ── 词汇偏好记录 ──

    def record_vocabulary_preference(self, original: str, rewritten: str) -> None:
        """记录一次成功的词汇替换。"""
        key = f"{original}→{rewritten}"
        if key not in self.strategies["vocabulary_preferences"]:
            self.strategies["vocabulary_preferences"][key] = {"success": 0}
        self.strategies["vocabulary_preferences"][key]["success"] += 1
        self._save_strategies()
