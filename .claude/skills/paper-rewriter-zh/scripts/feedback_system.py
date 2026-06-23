"""
反馈学习系统
记录改写结果、自动从客观指标学习、可选收集用户主观反馈
"""
from pathlib import Path
import json
import uuid
from datetime import datetime


# 所有 25 种技巧的规范名称（与 SKILL.md、chinese-specific.md 一致）
ALL_TECHNIQUES = {
    # 通用技巧（techniques.md）
    "句式重组": {"success": 0, "total": 0},
    "主被动转换": {"success": 0, "total": 0},
    "拆分长句": {"success": 0, "total": 0},
    "合并短句": {"success": 0, "total": 0},
    "引用位置移动": {"success": 0, "total": 0},
    "同义词替换": {"success": 0, "total": 0},
    "增加修饰语": {"success": 0, "total": 0},
    "删除冗余": {"success": 0, "total": 0},
    "调整语序": {"success": 0, "total": 0},
    "添加过渡词": {"success": 0, "total": 0},
    "具体化": {"success": 0, "total": 0},
    "抽象化": {"success": 0, "total": 0},
    "因果倒置": {"success": 0, "total": 0},
    "条件重组": {"success": 0, "total": 0},
    "否定反转": {"success": 0, "total": 0},
    # 中文特色技巧（chinese-specific.md）
    "四字词语重组": {"success": 0, "total": 0},
    "文言成分替换": {"success": 0, "total": 0},
    "句末语气词调整": {"success": 0, "total": 0},
    "把字句/被字句转换": {"success": 0, "total": 0},
    "话题-评论结构重组": {"success": 0, "total": 0},
    "量词替换": {"success": 0, "total": 0},
    "并列结构重组": {"success": 0, "total": 0},
    "否定表达重组": {"success": 0, "total": 0},
    "数量表达重组": {"success": 0, "total": 0},
    "时间表达重组": {"success": 0, "total": 0},
}

# 客观指标阈值（知网查重规则）
CNKI_THRESHOLD = 13          # 连续13字相同 = 抄袭
SUCCESS_CONSECUTIVE = 10     # 连续匹配 < 10 字 = 成功
SUCCESS_TRIGRAM = 0.20       # 三元组重叠 < 20% = 成功
EXCELLENT_CONSECUTIVE = 7    # 连续匹配 < 7 字 = 优秀
EXCELLENT_TRIGRAM = 0.10     # 三元组重叠 < 10% = 优秀


def evaluate_rewrite_quality(metrics: dict) -> dict:
    """
    基于客观指标自动评估改写质量

    返回:
        - verdict: "excellent" / "success" / "warning" / "fail"
        - score: 0-100 归一化分数
        - is_success: bool，是否达到成功标准
        - reason: 判定理由
    """
    mc = metrics.get("max_consecutive", 0)
    tri = metrics.get("trigram_overlap", 1.0)

    if mc >= CNKI_THRESHOLD:
        return {"verdict": "fail", "score": 0, "is_success": False,
                "reason": f"连续{mc}字匹配，超过知网{CNKI_THRESHOLD}字阈值"}
    elif mc >= SUCCESS_CONSECUTIVE or tri >= SUCCESS_TRIGRAM:
        # 归一化分数：连续匹配越少越好，三元组越低越好
        consecutive_score = max(0, (CNKI_THRESHOLD - mc) / CNKI_THRESHOLD * 50)
        trigram_score = max(0, (1 - tri) * 50)
        total = consecutive_score + trigram_score
        return {"verdict": "warning", "score": round(total), "is_success": False,
                "reason": f"连续{mc}字匹配（阈值{SUCCESS_CONSECUTIVE}），三元组{tri:.1%}（阈值{SUCCESS_TRIGRAM:.0%}）"}
    elif mc < EXCELLENT_CONSECUTIVE and tri < EXCELLENT_TRIGRAM:
        consecutive_score = max(0, (CNKI_THRESHOLD - mc) / CNKI_THRESHOLD * 50)
        trigram_score = max(0, (1 - tri) * 50)
        total = consecutive_score + trigram_score
        return {"verdict": "excellent", "score": round(total), "is_success": True,
                "reason": f"连续{mc}字匹配，三元组{tri:.1%}，改写效果优秀"}
    else:
        consecutive_score = max(0, (CNKI_THRESHOLD - mc) / CNKI_THRESHOLD * 50)
        trigram_score = max(0, (1 - tri) * 50)
        total = consecutive_score + trigram_score
        return {"verdict": "success", "score": round(total), "is_success": True,
                "reason": f"连续{mc}字匹配，三元组{tri:.1%}，改写达标"}


def classify_failure(metrics: dict, verdict: str) -> str:
    """根据指标和已有 verdict 细分失败原因。

    verdict 由 evaluate_rewrite_quality 产生，此处不再重复阈值判断，
    而是基于 verdict + 指标细节做更细粒度的分类。
    """
    if verdict == "excellent":
        return "none"

    mc = metrics.get("max_consecutive", 0)
    tri = metrics.get("trigram_overlap", 0)

    if verdict == "fail":
        return "consecutive_too_long"
    elif verdict == "warning":
        if mc >= 10 and tri >= 0.25:
            return "structure_too_similar"
        elif mc >= 10:
            return "consecutive_risk"
        elif tri >= 0.20:
            return "trigram_risk"
        else:
            return "mixed_risk"
    else:  # success
        return "none"


class FeedbackSystem:
    """反馈学习系统"""

    def __init__(self, skill_dir: Path = None):
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
        """加载学习到的策略"""
        if self.strategies_file.exists():
            try:
                with open(self.strategies_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass

        return {
            "vocabulary_preferences": {},
            "technique_effectiveness": {k: dict(v) for k, v in ALL_TECHNIQUES.items()},
            "domain_patterns": {},
            "intensity_adjustments": {
                "轻度": {"multiplier": 1.0},
                "中度": {"multiplier": 1.0},
                "重度": {"multiplier": 1.0}
            },
            "technique_combinations": {},
            "problem_patterns": [],
            "new_terms": [],
            "last_updated": datetime.now().isoformat()
        }

    def _save_strategies(self):
        """保存策略到文件"""
        self.strategies["last_updated"] = datetime.now().isoformat()
        with open(self.strategies_file, 'w', encoding='utf-8') as f:
            json.dump(self.strategies, f, ensure_ascii=False, indent=2)

    def record_rewrite_session(
        self,
        original_text: str,
        rewritten_text: str,
        domain: str = "通用",
        intensity: str = "中度",
        section_type: str = "unknown",
        changes_made: list = None
    ) -> dict:
        """记录一次改写会话"""
        session_id = f"{datetime.now().strftime('%Y-%m-%d')}-{uuid.uuid4().hex[:8]}"

        session = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "domain": domain,
            "intensity": intensity,
            "section_type": section_type,
            "original_text": original_text,
            "rewritten_text": rewritten_text,
            "changes_made": changes_made or [],
            "scores": None,
            "feedback": None
        }

        session["metrics"] = self._calculate_metrics(original_text, rewritten_text)
        session["auto_evaluation"] = evaluate_rewrite_quality(session["metrics"])

        session_file = self.sessions_dir / f"{session_id}.json"
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session, f, ensure_ascii=False, indent=2)

        return session

    def _calculate_metrics(self, original: str, rewritten: str) -> dict:
        """计算改写质量指标"""
        from similarity_calculator import calculate_similarity
        return calculate_similarity(original, rewritten)

    def add_changes_to_session(self, session_id: str, changes_made: list) -> dict:
        """向已有会话追加 changes_made 记录"""
        session_file = self.sessions_dir / f"{session_id}.json"
        if not session_file.exists():
            raise ValueError(f"找不到会话: {session_id}")

        with open(session_file, 'r', encoding='utf-8') as f:
            session = json.load(f)

        session["changes_made"] = changes_made

        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session, f, ensure_ascii=False, indent=2)

        return session

    def auto_learn(self, session_id: str) -> dict:
        """
        基于客观指标自动学习（无需用户打分）

        从 session 的 metrics 和 auto_evaluation 中判定成功/失败，
        更新技巧有效性、词汇偏好、领域模式、强度调整。
        """
        session_file = self.sessions_dir / f"{session_id}.json"
        if not session_file.exists():
            raise ValueError(f"找不到会话: {session_id}")

        with open(session_file, 'r', encoding='utf-8') as f:
            session = json.load(f)

        metrics = session.get("metrics", {})
        evaluation = session.get("auto_evaluation") or evaluate_rewrite_quality(metrics)
        is_success = evaluation["is_success"]
        domain = session.get("domain", "通用")
        intensity = session.get("intensity", "中度")

        # 标记会话已自动学习
        session["auto_learned"] = True

        # 1. 学习词汇偏好
        if is_success:
            for change in session.get("changes_made", []):
                if change.get("type") == "同义词替换":
                    key = f"{change['original']}->{change['rewritten']}"
                    if key not in self.strategies["vocabulary_preferences"]:
                        self.strategies["vocabulary_preferences"][key] = {
                            "success": 0, "domain": domain
                        }
                    self.strategies["vocabulary_preferences"][key]["success"] += 1

        # 2. 学习技巧有效性
        for change in session.get("changes_made", []):
            tech_type = change.get("type", "同义词替换")
            if tech_type in self.strategies["technique_effectiveness"]:
                self.strategies["technique_effectiveness"][tech_type]["total"] += 1
                if is_success:
                    self.strategies["technique_effectiveness"][tech_type]["success"] += 1

        # 3.5 学习技巧组合
        changes = session.get("changes_made", [])
        tech_types = list(set(c.get("type", "") for c in changes if c.get("type")))
        if len(tech_types) >= 2:
            from itertools import combinations
            for t1, t2 in combinations(sorted(tech_types), 2):
                key = f"{t1}+{t2}"
                if key not in self.strategies["technique_combinations"]:
                    self.strategies["technique_combinations"][key] = {"success": 0, "total": 0}
                self.strategies["technique_combinations"][key]["total"] += 1
                if is_success:
                    self.strategies["technique_combinations"][key]["success"] += 1

        # 3. 学习领域模式
        if domain not in self.strategies["domain_patterns"]:
            self.strategies["domain_patterns"][domain] = {
                "avg_score": 0,
                "session_count": 0,
                "common_issues": [],
                "auto_success_count": 0,
                "auto_fail_count": 0
            }

        pattern = self.strategies["domain_patterns"][domain]
        pattern["session_count"] += 1
        if is_success:
            pattern["auto_success_count"] += 1
        else:
            pattern["auto_fail_count"] += 1
            # 失败时记录问题
            issue = evaluation["reason"]
            pattern["common_issues"].append(issue)
            pattern["common_issues"] = pattern["common_issues"][-10:]

        # 更新平均分（使用自动评分的归一化分数）
        auto_score_normalized = evaluation["score"] / 20  # 0-100 → 0-5
        pattern["avg_score"] = (
            (pattern["avg_score"] * (pattern["session_count"] - 1) + auto_score_normalized) /
            pattern["session_count"]
        )

        # 4. 学习强度调整（不对称学习率）
        if not is_success:
            current_mult = self.strategies["intensity_adjustments"][intensity]["multiplier"]
            self.strategies["intensity_adjustments"][intensity]["multiplier"] = min(
                1.5, current_mult + 0.05
            )
        elif evaluation["verdict"] == "excellent":
            current_mult = self.strategies["intensity_adjustments"][intensity]["multiplier"]
            self.strategies["intensity_adjustments"][intensity]["multiplier"] = max(
                0.5, current_mult - 0.02
            )

        # 5. 记录问题模式（失败时）
        if not is_success:
            failure_type = classify_failure(metrics, evaluation["verdict"])
            self.strategies["problem_patterns"].append({
                "issue": evaluation["reason"],
                "failure_type": failure_type,
                "domain": domain,
                "intensity": intensity,
                "max_consecutive": metrics.get("max_consecutive", 0),
                "trigram_overlap": metrics.get("trigram_overlap", 0),
                "timestamp": session.get("timestamp")
            })
            self.strategies["problem_patterns"] = self.strategies["problem_patterns"][-20:]

        # 保存
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session, f, ensure_ascii=False, indent=2)

        self._save_strategies()

        return {
            "session_id": session_id,
            "evaluation": evaluation,
            "learned": True
        }

    def collect_feedback(
        self,
        session_id: str,
        vocabulary_score: int = 3,
        structure_score: int = 3,
        terminology_score: int = 3,
        overall_score: int = 3,
        liked: str = "",
        improved: str = "",
        missing_terms: list = None,
        suggestions: str = ""
    ) -> dict:
        """
        收集用户主观反馈（可选，用于补充自动学习）

        大多数情况下 auto_learn 已经够用。
        只有用户明确想提供详细反馈时才调用此方法。
        """
        for name, score in [("vocabulary_score", vocabulary_score),
                            ("structure_score", structure_score),
                            ("terminology_score", terminology_score),
                            ("overall_score", overall_score)]:
            if not isinstance(score, int) or not (1 <= score <= 5):
                raise ValueError(f"{name} 必须是 1-5 的整数，收到: {score}")

        session_file = self.sessions_dir / f"{session_id}.json"
        if not session_file.exists():
            raise ValueError(f"找不到会话: {session_id}")

        with open(session_file, 'r', encoding='utf-8') as f:
            session = json.load(f)

        session["scores"] = {
            "vocabulary": vocabulary_score,
            "sentence_structure": structure_score,
            "terminology_preservation": terminology_score,
            "overall_satisfaction": overall_score
        }
        session["feedback"] = {
            "liked": liked,
            "improved": improved,
            "missing_terms": missing_terms or [],
            "other_suggestions": suggestions
        }

        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session, f, ensure_ascii=False, indent=2)

        self._learn_from_feedback(session)

        return session

    def _learn_from_feedback(self, session: dict):
        """从用户主观反馈中学习（补充自动学习）"""
        scores = session.get("scores", {})
        feedback = session.get("feedback", {})
        domain = session.get("domain", "通用")
        intensity = session.get("intensity", "中度")

        if not scores:
            return

        avg_score = sum(scores.values()) / len(scores)

        # 1. 学习词汇偏好
        if avg_score >= 4:
            for change in session.get("changes_made", []):
                if change.get("type") == "同义词替换":
                    key = f"{change['original']}->{change['rewritten']}"
                    if key not in self.strategies["vocabulary_preferences"]:
                        self.strategies["vocabulary_preferences"][key] = {
                            "success": 0, "domain": domain
                        }
                    self.strategies["vocabulary_preferences"][key]["success"] += 1

        # 2. 学习技巧有效性
        for change in session.get("changes_made", []):
            tech_type = change.get("type", "同义词替换")
            if tech_type in self.strategies["technique_effectiveness"]:
                self.strategies["technique_effectiveness"][tech_type]["total"] += 1
                if avg_score >= 4:
                    self.strategies["technique_effectiveness"][tech_type]["success"] += 1

        # 3. 学习领域模式
        if domain not in self.strategies["domain_patterns"]:
            self.strategies["domain_patterns"][domain] = {
                "avg_score": 0, "session_count": 0,
                "common_issues": [], "auto_success_count": 0, "auto_fail_count": 0
            }

        pattern = self.strategies["domain_patterns"][domain]
        pattern["avg_score"] = (
            (pattern["avg_score"] * pattern["session_count"] + avg_score) /
            (pattern["session_count"] + 1)
        )
        pattern["session_count"] += 1

        if feedback.get("improved"):
            pattern["common_issues"].append(feedback["improved"])
            pattern["common_issues"] = pattern["common_issues"][-10:]

        # 4. 学习强度调整
        if avg_score < 3:
            current_mult = self.strategies["intensity_adjustments"][intensity]["multiplier"]
            self.strategies["intensity_adjustments"][intensity]["multiplier"] = min(
                1.5, current_mult + 0.05
            )
        elif avg_score > 4:
            current_mult = self.strategies["intensity_adjustments"][intensity]["multiplier"]
            self.strategies["intensity_adjustments"][intensity]["multiplier"] = max(
                0.5, current_mult - 0.02
            )

        # 5. 记录问题模式
        if feedback.get("improved") and avg_score < 3:
            self.strategies["problem_patterns"].append({
                "issue": feedback["improved"],
                "domain": domain,
                "intensity": intensity,
                "timestamp": session.get("timestamp")
            })
            self.strategies["problem_patterns"] = self.strategies["problem_patterns"][-20:]

        # 6. 添加缺失术语
        if feedback.get("missing_terms"):
            self.strategies["new_terms"].extend(feedback["missing_terms"])
            self.strategies["new_terms"] = list(set(self.strategies["new_terms"]))[-50:]

        self._save_strategies()

    def get_rewrite_suggestions(
        self,
        domain: str = "通用",
        intensity: str = "中度"
    ) -> dict:
        """获取改写建议（基于学习到的策略）"""
        suggestions = {
            "preferred_vocabulary": [],
            "effective_techniques": [],
            "intensity_multiplier": 1.0,
            "domain_issues": [],
            "new_terms_to_preserve": []
        }

        for key, data in self.strategies["vocabulary_preferences"].items():
            if data["success"] >= 2:
                suggestions["preferred_vocabulary"].append(key)

        tech_eff = self.strategies["technique_effectiveness"]
        for tech, data in tech_eff.items():
            if data["total"] > 0:
                success_rate = data["success"] / data["total"]
                if success_rate >= 0.7:
                    suggestions["effective_techniques"].append({
                        "technique": tech,
                        "success_rate": round(success_rate, 2)
                    })

        if intensity in self.strategies["intensity_adjustments"]:
            suggestions["intensity_multiplier"] = self.strategies["intensity_adjustments"][intensity]["multiplier"]

        if domain in self.strategies["domain_patterns"]:
            pattern = self.strategies["domain_patterns"][domain]
            suggestions["domain_issues"] = pattern.get("common_issues", [])[-5:]

        suggestions["new_terms_to_preserve"] = self.strategies.get("new_terms", [])[-10:]

        # 有效技巧组合
        suggestions["effective_combinations"] = []
        for combo_key, combo_data in self.strategies.get("technique_combinations", {}).items():
            if combo_data["total"] >= 2:
                rate = combo_data["success"] / combo_data["total"]
                if rate >= 0.7:
                    suggestions["effective_combinations"].append({
                        "combination": combo_key,
                        "success_rate": round(rate, 2)
                    })

        return suggestions

    def get_strategy_report(self) -> str:
        """生成策略报告"""
        report = """
## 反馈学习策略报告

### 词汇偏好 (Top 10)
{vocab_prefs}

### 技巧有效性
{tech_effectiveness}

### 强度调整
{intensity_adj}

### 领域模式
{domain_patterns}

### 问题模式 (最近5个)
{problem_patterns}

### 新增术语 (待保护)
{new_terms}

### 策略更新时间
{last_updated}
"""

        vocab_prefs = ""
        sorted_vocab = sorted(
            self.strategies["vocabulary_preferences"].items(),
            key=lambda x: x[1]["success"],
            reverse=True
        )[:10]
        for key, data in sorted_vocab:
            vocab_prefs += f"- {key}: 成功 {data['success']} 次\n"
        if not vocab_prefs:
            vocab_prefs = "- 暂无数据\n"

        tech_effectiveness = ""
        for tech, data in self.strategies["technique_effectiveness"].items():
            if data["total"] > 0:
                rate = data["success"] / data["total"]
                bar = "█" * int(rate * 5) + "░" * (5 - int(rate * 5))
                tech_effectiveness += f"- {tech}: {bar} {rate:.0%} ({data['success']}/{data['total']})\n"
            else:
                tech_effectiveness += f"- {tech}: 暂无数据\n"

        intensity_adj = ""
        for intensity, data in self.strategies["intensity_adjustments"].items():
            mult = data["multiplier"]
            if mult > 1.0:
                intensity_adj += f"- {intensity}: 增加 {mult:.2f}x (改写不足，加强)\n"
            elif mult < 1.0:
                intensity_adj += f"- {intensity}: 降低 {mult:.2f}x (改写优秀，适当减弱)\n"
            else:
                intensity_adj += f"- {intensity}: 标准 1.00x\n"

        domain_patterns = ""
        for domain, data in self.strategies["domain_patterns"].items():
            avg = data["avg_score"]
            count = data["session_count"]
            ok = data.get("auto_success_count", 0)
            fail = data.get("auto_fail_count", 0)
            domain_patterns += f"- {domain}: 平均 {avg:.1f}/5 ({count} 次, 成功{ok}/失败{fail})\n"
        if not domain_patterns:
            domain_patterns = "- 暂无数据\n"

        problem_patterns = ""
        for problem in self.strategies["problem_patterns"][-5:]:
            problem_patterns += f"- [{problem['domain']}] {problem['issue']}\n"
        if not problem_patterns:
            problem_patterns = "- 暂无问题\n"

        new_terms = ""
        for term in self.strategies.get("new_terms", [])[-10:]:
            new_terms += f"- {term}\n"
        if not new_terms:
            new_terms = "- 暂无新术语\n"

        return report.format(
            vocab_prefs=vocab_prefs,
            tech_effectiveness=tech_effectiveness,
            intensity_adj=intensity_adj,
            domain_patterns=domain_patterns,
            problem_patterns=problem_patterns,
            new_terms=new_terms,
            last_updated=self.strategies.get("last_updated", "N/A")
        )
