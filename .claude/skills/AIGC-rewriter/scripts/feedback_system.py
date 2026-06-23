"""Feedback learning system.

Records rewrite sessions, tracks technique effectiveness, generates suggestions, outputs strategy reports.
Risk-score driven, no manual scoring needed.
"""

import json
import uuid
from datetime import datetime
from itertools import combinations
from pathlib import Path
from typing import Optional


def auto_evaluate(risk_before: float, risk_after: float,
                  threshold: float = 0.3) -> dict:
    """Auto-evaluate rewrite result based on risk score change."""
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
    """Generate verdict reason description."""
    if verdict == "fail":
        return f"Risk score did not decrease ({risk_after:.2f})"
    elif verdict == "marginal":
        return f"Reduction insufficient (only {reduction:.3f})"
    elif verdict == "partial":
        return f"Risk reduced to {risk_after:.2f}, still above threshold {threshold:.2f}"
    elif verdict == "excellent":
        return f"Major reduction {reduction:.3f}, rewrite highly effective"
    return "Rewrite successful"


def classify_failure(risk_before: float, risk_after: float,
                     issues_before: list, issues_after: list) -> str:
    """Classify failure type for targeted suggestions."""
    # Success case
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
    """Feedback learning system."""

    def __init__(self, skill_dir: Optional[Path] = None):
        if skill_dir is None:
            skill_dir = Path(__file__).parent.parent

        self.skill_dir = skill_dir
        self.feedback_dir = skill_dir / "feedback"
        self.sessions_dir = self.feedback_dir / "sessions"
        self.learning_dir = self.feedback_dir / "learning"
        self.strategies_file = self.learning_dir / "strategies.json"

        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.learning_dir.mkdir(parents=True, exist_ok=True)

        self.strategies = self._load_strategies()

    def _load_strategies(self) -> dict:
        """Load learned strategies."""
        if self.strategies_file.exists():
            try:
                data = json.loads(self.strategies_file.read_text(encoding="utf-8"))
                # Backward compatibility: fill missing fields
                if "technique_combinations" not in data:
                    data["technique_combinations"] = {}
                if "intensity_adjustments" in data:
                    for level in ("light", "medium", "heavy"):
                        if level in data["intensity_adjustments"]:
                            adj = data["intensity_adjustments"][level]
                            if "consecutive_failures" not in adj:
                                adj["consecutive_failures"] = 0
                            if "consecutive_successes" not in adj:
                                adj["consecutive_successes"] = 0
                return data
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        return {
            "vocabulary_preferences": {},
            "technique_effectiveness": {
                "cliche_replace": {"success": 0, "total": 0},
                "connector_replace": {"success": 0, "total": 0},
                "passive_convert": {"success": 0, "total": 0},
                "nominalization_convert": {"success": 0, "total": 0},
                "sentence_restructure": {"success": 0, "total": 0},
                "synonym_replace": {"success": 0, "total": 0},
            },
            "section_patterns": {},
            "intensity_adjustments": {
                "light": {"multiplier": 1.0, "consecutive_failures": 0, "consecutive_successes": 0},
                "medium": {"multiplier": 1.0, "consecutive_failures": 0, "consecutive_successes": 0},
                "heavy": {"multiplier": 1.0, "consecutive_failures": 0, "consecutive_successes": 0},
            },
            "technique_combinations": {},
            "problem_patterns": [],
            "session_count": 0,
            "total_paragraphs_rewritten": 0,
            "total_risk_reduction": 0.0,
            "last_updated": datetime.now().isoformat(),
        }

    def _save_strategies(self) -> None:
        """Save strategies to file."""
        self.strategies["last_updated"] = datetime.now().isoformat()
        self.strategies_file.write_text(
            json.dumps(self.strategies, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ── Session Recording ──

    def record_session(
        self,
        original_text: str,
        rewritten_text: str,
        risk_before: float,
        risk_after: float,
        section_type: str = "body",
        techniques_used: Optional[list] = None,
        issues_resolved: Optional[list] = None,
        issues_before: Optional[list] = None,
        issues_after: Optional[list] = None,
        intensity: str = "medium",
    ) -> dict:
        """Record a rewrite session.

        Args:
            original_text: Original text
            rewritten_text: Rewritten text
            risk_before: Risk score before rewrite
            risk_after: Risk score after rewrite
            section_type: Section type
            techniques_used: List of techniques used
            issues_resolved: List of resolved issue types
            issues_before: Issues detected before rewrite (for failure classification)
            issues_after: Issues remaining after rewrite (for failure classification)
            intensity: Rewrite intensity level (light/medium/heavy)

        Returns:
            Session info dict
        """
        session_id = f"{datetime.now().strftime('%Y-%m-%d')}-{uuid.uuid4().hex[:8]}"
        risk_reduction = round(risk_before - risk_after, 3)

        # Auto-evaluate
        eval_result = auto_evaluate(risk_before, risk_after)
        success = eval_result["is_success"]

        # Failure classification
        failure_type = classify_failure(
            risk_before, risk_after,
            issues_before or [], issues_after or [],
        ) if not success else None

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
            "auto_evaluation": eval_result,
            "failure_type": failure_type,
            "techniques_used": techniques_used or [],
            "issues_resolved": issues_resolved or [],
            "issues_before": issues_before or [],
            "issues_after": issues_after or [],
            "intensity": intensity,
        }

        session_file = self.sessions_dir / f"{session_id}.json"
        session_file.write_text(
            json.dumps(session, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # Learn
        self._learn_from_session(session)

        return session

    # ── Learning Logic ──

    def _learn_from_session(self, session: dict) -> None:
        """Learn from session and update strategies."""
        section = session["section_type"]
        techniques = session["techniques_used"]
        issues = session["issues_resolved"]
        reduction = session["risk_reduction"]

        eval_result = auto_evaluate(session["risk_before"], session["risk_after"])
        success = eval_result["is_success"]
        verdict = eval_result["verdict"]

        # 1. Global stats
        self.strategies["session_count"] += 1
        self.strategies["total_paragraphs_rewritten"] += 1
        self.strategies["total_risk_reduction"] = round(
            self.strategies["total_risk_reduction"] + reduction, 3
        )

        # 2. Technique effectiveness
        for tech in techniques:
            if tech not in self.strategies["technique_effectiveness"]:
                self.strategies["technique_effectiveness"][tech] = {"success": 0, "total": 0}
            self.strategies["technique_effectiveness"][tech]["total"] += 1
            if success:
                self.strategies["technique_effectiveness"][tech]["success"] += 1

        # 3. Technique combination learning
        if len(techniques) >= 2:
            for t1, t2 in combinations(sorted(techniques), 2):
                combo_key = f"{t1}+{t2}"
                if combo_key not in self.strategies["technique_combinations"]:
                    self.strategies["technique_combinations"][combo_key] = {"success": 0, "total": 0}
                self.strategies["technique_combinations"][combo_key]["total"] += 1
                if success:
                    self.strategies["technique_combinations"][combo_key]["success"] += 1

        # 4. Section patterns
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

        for issue in issues:
            if issue not in sp["common_issues"]:
                sp["common_issues"].append(issue)
        sp["common_issues"] = sp["common_issues"][-10:]

        for tech in techniques:
            if tech not in sp["effective_techniques"]:
                sp["effective_techniques"][tech] = {"success": 0, "total": 0}
            sp["effective_techniques"][tech]["total"] += 1
            if success:
                sp["effective_techniques"][tech]["success"] += 1

        # 5. Adaptive learning rate
        intensity = session.get("intensity", "medium")
        adjustment = self.strategies["intensity_adjustments"][intensity]

        if not success:
            count = adjustment["consecutive_failures"]
            step = min(0.10, 0.05 + count * 0.01)
            adjustment["multiplier"] = min(1.5, adjustment["multiplier"] + step)
            adjustment["consecutive_failures"] = count + 1
            adjustment["consecutive_successes"] = 0
        elif verdict == "excellent":
            count = adjustment["consecutive_successes"]
            step = max(0.01, 0.02 - count * 0.003)
            adjustment["multiplier"] = max(0.5, adjustment["multiplier"] - step)
            adjustment["consecutive_successes"] = count + 1
            adjustment["consecutive_failures"] = 0
        else:
            adjustment["consecutive_failures"] = 0
            adjustment["consecutive_successes"] = 0

        # 6. Problem patterns (with failure type)
        if not success:
            failure_type = classify_failure(
                session["risk_before"], session["risk_after"],
                session.get("issues_before", []), session.get("issues_after", [])
            )
            self.strategies["problem_patterns"].append({
                "section": section,
                "risk_before": session["risk_before"],
                "risk_after": session["risk_after"],
                "failure_type": failure_type,
                "techniques": techniques,
                "timestamp": session["timestamp"],
            })
            self.strategies["problem_patterns"] = self.strategies["problem_patterns"][-20:]

        self._save_strategies()

    # ── Suggestion Generation ──

    def get_rewrite_suggestions(
        self,
        section_type: str = "body",
        intensity: str = "medium",
        current_metrics: dict = None,
    ) -> dict:
        """Get rewrite suggestions based on historical learning.

        Returns:
            {
                "effective_techniques": [...],
                "intensity_multiplier": float,
                "section_issues": [...],
                "preferred_vocabulary": [...],
                "session_count": int,
                "avg_reduction": float,
                "targeted_advice": [...],
                "priority_techniques": [...],
                "effective_combinations": [...],
            }
        """
        suggestions = {
            "effective_techniques": [],
            "intensity_multiplier": 1.0,
            "section_issues": [],
            "preferred_vocabulary": [],
            "session_count": self.strategies["session_count"],
            "avg_reduction": 0.0,
            "targeted_advice": [],
            "priority_techniques": [],
            "effective_combinations": [],
        }

        # 1. Globally effective techniques (success rate >= 60%)
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

        # 2. Section-specific suggestions
        if section_type in self.strategies["section_patterns"]:
            sp = self.strategies["section_patterns"][section_type]
            suggestions["section_issues"] = sp.get("common_issues", [])[-5:]

            for tech, data in sp.get("effective_techniques", {}).items():
                if data["total"] >= 2:
                    rate = data["success"] / data["total"]
                    if rate >= 0.6:
                        existing = {t["technique"] for t in suggestions["effective_techniques"]}
                        if tech not in existing:
                            suggestions["effective_techniques"].append({
                                "technique": tech,
                                "success_rate": round(rate, 2),
                                "count": data["total"],
                                "section_specific": True,
                            })

        # 3. Intensity adjustment
        if intensity in self.strategies["intensity_adjustments"]:
            suggestions["intensity_multiplier"] = self.strategies[
                "intensity_adjustments"
            ][intensity]["multiplier"]

        # 4. Vocabulary preferences
        for key, data in self.strategies["vocabulary_preferences"].items():
            if data.get("success", 0) >= 2:
                suggestions["preferred_vocabulary"].append(key)

        # 5. Average risk reduction
        count = self.strategies["session_count"]
        if count > 0:
            suggestions["avg_reduction"] = round(
                self.strategies["total_risk_reduction"] / count, 3
            )

        # 6. Effective technique combinations (success rate >= 70%, total >= 2)
        for combo_key, data in self.strategies.get("technique_combinations", {}).items():
            if data["total"] >= 2:
                rate = data["success"] / data["total"]
                if rate >= 0.7:
                    suggestions["effective_combinations"].append({
                        "combination": combo_key,
                        "success_rate": round(rate, 2),
                    })

        # 7. Targeted advice based on current metrics
        if current_metrics:
            failure_type = current_metrics.get("failure_type", "")

            advice_map = {
                "risk_increased": ("Reduce rewrite aggressiveness, preserve more original structure", ["cliche_replace"]),
                "minimal_effect": ("Increase rewrite intensity, use sentence_restructure", ["sentence_restructure", "cliche_replace"]),
                "cliche_persistent": ("Cliches not eliminated, prioritize cliche_replace", ["cliche_replace"]),
                "connector_persistent": ("Connector issue unresolved, use connector_replace", ["connector_replace"]),
                "pattern_persistent": ("Sentence pattern not broken, use sentence_restructure", ["sentence_restructure"]),
            }

            if failure_type in advice_map:
                advice, techniques = advice_map[failure_type]
                suggestions["targeted_advice"].append(advice)
                suggestions["priority_techniques"] = techniques

        # 8. Suggestions based on historical problem patterns
        recent_problems = [
            p for p in self.strategies.get("problem_patterns", [])
            if p.get("section") == section_type
        ][-5:]

        failure_type_advice = {
            "risk_increased": "Historical rewrites in this section show risk increase, reduce aggressiveness",
            "minimal_effect": "Historical rewrites in this section had minimal effect, increase intensity",
            "cliche_persistent": "Historical rewrites in this section struggled with cliches, prioritize cliche replacement",
        }

        seen_types = set()
        for problem in recent_problems:
            ft = problem.get("failure_type", "")
            if ft in failure_type_advice and ft not in seen_types:
                suggestions["targeted_advice"].append(failure_type_advice[ft])
                seen_types.add(ft)

        return suggestions

    # ── Strategy Report ──

    def get_strategy_report(self) -> str:
        """Generate strategy report (Markdown format)."""
        s = self.strategies
        lines = ["## Feedback Learning Strategy Report", ""]

        # Overview
        count = s["session_count"]
        total_red = s["total_risk_reduction"]
        avg_red = round(total_red / count, 3) if count > 0 else 0
        lines.append(f"**Total sessions**: {count}  |  **Total risk reduction**: {total_red:.3f}  |  **Average reduction**: {avg_red:.3f}")
        lines.append("")

        # Technique effectiveness
        lines.append("### Technique Effectiveness")
        for tech, data in s["technique_effectiveness"].items():
            if data["total"] > 0:
                rate = data["success"] / data["total"]
                bar = "█" * int(rate * 5) + "░" * (5 - int(rate * 5))
                lines.append(f"- {tech}: {bar} {rate:.0%} ({data['success']}/{data['total']})")
            else:
                lines.append(f"- {tech}: No data yet")
        lines.append("")

        # Section patterns
        lines.append("### Section Patterns")
        for sec, data in s["section_patterns"].items():
            avg = data["avg_reduction"]
            cnt = data["session_count"]
            lines.append(f"- {sec}: avg reduction {avg:.3f} ({cnt} sessions)")
            if data.get("common_issues"):
                lines.append(f"  Common issues: {', '.join(data['common_issues'][-3:])}")
        lines.append("")

        # Intensity adjustments
        lines.append("### Intensity Adjustments")
        for level, data in s["intensity_adjustments"].items():
            mult = data["multiplier"]
            if mult > 1.05:
                lines.append(f"- {level}: {mult:.2f}x ↑ (low effect, increase intensity)")
            elif mult < 0.95:
                lines.append(f"- {level}: {mult:.2f}x ↓ (high effect, reduce intensity)")
            else:
                lines.append(f"- {level}: {mult:.2f}x (standard)")
        lines.append("")

        # Problem patterns
        problems = s.get("problem_patterns", [])
        if problems:
            lines.append("### Recent Issues (last 5)")
            for p in problems[-5:]:
                ft = p.get("failure_type", "unknown")
                lines.append(f"- [{p['section']}] {p['risk_before']:.2f}→{p['risk_after']:.2f} type: {ft} techniques: {', '.join(p.get('techniques', []))}")
            lines.append("")

        lines.append(f"*Last updated: {s.get('last_updated', 'N/A')}*")
        return "\n".join(lines)

    # ── Vocabulary Preference Recording ──

    def record_vocabulary_preference(self, original: str, rewritten: str) -> None:
        """Record a successful vocabulary replacement."""
        key = f"{original}→{rewritten}"
        if key not in self.strategies["vocabulary_preferences"]:
            self.strategies["vocabulary_preferences"][key] = {"success": 0}
        self.strategies["vocabulary_preferences"][key]["success"] += 1
        self._save_strategies()
