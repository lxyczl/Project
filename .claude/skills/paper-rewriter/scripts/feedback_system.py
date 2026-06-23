"""
反馈学习系统
记录改写结果、收集用户满意度、自动调整改写策略
"""
from pathlib import Path
import json
import uuid
from datetime import datetime
from collections import defaultdict


def auto_evaluate(metrics: dict) -> dict:
    """基于客观指标自动判定成功/失败。Turnitin 比知网更敏感，阈值更严格。"""
    mc = metrics.get("max_consecutive", 0)
    tri = metrics.get("trigram_precision", 0)

    if mc >= 8:
        verdict = "fail"
    elif mc >= 5 or tri >= 0.30:
        verdict = "warning"
    elif tri < 0.15 and mc < 4:
        verdict = "excellent"
    else:
        verdict = "success"

    return {
        "verdict": verdict,
        "is_success": verdict in ("success", "excellent"),
        "max_consecutive": mc,
        "trigram_precision": tri,
        "reason": _verdict_reason(verdict, mc, tri),
    }


def _verdict_reason(verdict: str, mc: int, tri: float) -> str:
    """生成判定原因说明"""
    if verdict == "fail":
        return f"连续匹配 {mc} 词，超过 Turnitin 阈值（8 词）"
    elif verdict == "warning":
        if mc >= 5:
            return f"连续匹配 {mc} 词，接近阈值"
        return f"三元组精度 {tri:.1%}，句式相似度偏高"
    elif verdict == "excellent":
        return "改写充分，相似度低"
    return "可接受"


def classify_failure(metrics: dict, verdict: str) -> str:
    """根据指标和已有 verdict 细分失败原因。"""
    if verdict in ("excellent", "success"):
        return "none"

    mc = metrics.get("max_consecutive", 0)
    tri = metrics.get("trigram_precision", 0)

    if verdict == "fail":
        return "consecutive_too_long"
    elif verdict == "warning":
        if mc >= 5 and tri >= 0.25:
            return "structure_too_similar"
        elif mc >= 5:
            return "consecutive_risk"
        elif tri >= 0.20:
            return "trigram_risk"
        else:
            return "mixed_risk"
    return "none"


class FeedbackSystem:
    """反馈学习系统"""

    def __init__(self, skill_dir: Path = None):
        """
        初始化反馈系统

        参数:
            skill_dir: 技能目录路径
        """
        if skill_dir is None:
            skill_dir = Path(__file__).parent.parent

        self.skill_dir = skill_dir
        self.feedback_dir = skill_dir / "feedback"
        self.sessions_dir = self.feedback_dir / "sessions"
        self.learning_dir = self.feedback_dir / "learning"
        self.strategies_file = self.learning_dir / "strategies.json"

        # 确保目录存在
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.learning_dir.mkdir(parents=True, exist_ok=True)

        # 加载策略
        self.strategies = self._load_strategies()

    def _load_strategies(self) -> dict:
        """加载学习到的策略"""
        if self.strategies_file.exists():
            try:
                with open(self.strategies_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass

        # 默认策略
        return {
            "vocabulary_preferences": {},
            "technique_effectiveness": {
                "voice_conversion": {"success": 0, "total": 0},
                "clause_insertion": {"success": 0, "total": 0},
                "sentence_combining": {"success": 0, "total": 0},
                "synonym_replacement": {"success": 0, "total": 0},
                "word_order_change": {"success": 0, "total": 0}
            },
            "technique_combinations": {},
            "domain_patterns": {},
            "intensity_adjustments": {
                "light": {"multiplier": 1.0, "consecutive_failures": 0, "consecutive_successes": 0},
                "medium": {"multiplier": 1.0, "consecutive_failures": 0, "consecutive_successes": 0},
                "heavy": {"multiplier": 1.0, "consecutive_failures": 0, "consecutive_successes": 0}
            },
            "problem_patterns": [],
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
        domain: str = "general",
        intensity: str = "medium",
        section_type: str = "unknown",
        changes_made: list = None
    ) -> dict:
        """
        记录一次改写会话

        参数:
            original_text: 原文
            rewritten_text: 改写后文本
            domain: 学科领域
            intensity: 改写强度
            section_type: 章节类型
            changes_made: 修改记录

        返回:
            会话信息
        """
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

        # 计算相似度指标
        session["metrics"] = self._calculate_metrics(original_text, rewritten_text)

        # 保存会话
        session_file = self.sessions_dir / f"{session_id}.json"
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session, f, ensure_ascii=False, indent=2)

        return session

    def _calculate_metrics(self, original: str, rewritten: str) -> dict:
        """计算改写质量指标（复用 similarity_calculator）"""
        from similarity_calculator import tokenize, lcs_ratio, vocabulary_overlap
        tok_orig = tokenize(original)
        tok_rew = tokenize(rewritten)
        return {
            "lcs_ratio": round(lcs_ratio(tok_orig, tok_rew), 3),
            "vocabulary_overlap": round(vocabulary_overlap(tok_orig, tok_rew), 3),
            "original_word_count": len(tok_orig),
            "rewritten_word_count": len(tok_rew),
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
        收集用户反馈

        参数:
            session_id: 会话ID
            vocabulary_score: 词汇评分 (1-5)
            structure_score: 句子结构评分 (1-5)
            terminology_score: 术语保留评分 (1-5)
            overall_score: 总体满意度 (1-5)
            liked: 用户喜欢的地方
            improved: 需要改进的地方
            missing_terms: 缺失的术语列表
            suggestions: 其他建议

        返回:
            更新后的会话信息
        """
        # 查找会话文件
        session_file = self.sessions_dir / f"{session_id}.json"
        if not session_file.exists():
            raise ValueError(f"找不到会话: {session_id}")

        # 加载会话
        with open(session_file, 'r', encoding='utf-8') as f:
            session = json.load(f)

        # 更新反馈
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

        # 保存更新
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session, f, ensure_ascii=False, indent=2)

        # 学习并更新策略
        self._learn_from_feedback(session)

        return session

    def _learn_from_feedback(self, session: dict):
        """从反馈中学习并更新策略"""
        scores = session.get("scores", {})
        feedback = session.get("feedback", {})
        domain = session.get("domain", "general")
        intensity = session.get("intensity", "medium")

        if not scores:
            return

        avg_score = sum(scores.values()) / len(scores)

        # 1. 学习词汇偏好
        if avg_score >= 4:
            # 高分：记录成功的词汇替换
            for change in session.get("changes_made", []):
                if change.get("type") == "vocabulary":
                    key = f"{change['original']}->{change['rewritten']}"
                    if key not in self.strategies["vocabulary_preferences"]:
                        self.strategies["vocabulary_preferences"][key] = {
                            "success": 0, "domain": domain
                        }
                    self.strategies["vocabulary_preferences"][key]["success"] += 1

        # 2. 学习技术有效性
        for change in session.get("changes_made", []):
            tech_type = change.get("type", "synonym_replacement")
            if tech_type in self.strategies["technique_effectiveness"]:
                self.strategies["technique_effectiveness"][tech_type]["total"] += 1
                if avg_score >= 4:
                    self.strategies["technique_effectiveness"][tech_type]["success"] += 1

        # 3b. 学习技巧组合
        is_success = avg_score >= 4  # 默认，后续自适应学习率可能覆盖
        techniques_used = list(set(
            c.get("type", "synonym_replacement")
            for c in session.get("changes_made", [])
        ))
        if len(techniques_used) >= 2:
            from itertools import combinations
            for t1, t2 in combinations(sorted(techniques_used), 2):
                combo_key = f"{t1}+{t2}"
                if combo_key not in self.strategies["technique_combinations"]:
                    self.strategies["technique_combinations"][combo_key] = {"success": 0, "total": 0}
                self.strategies["technique_combinations"][combo_key]["total"] += 1
                if is_success:
                    self.strategies["technique_combinations"][combo_key]["success"] += 1

        # 3. 学习领域模式
        if domain not in self.strategies["domain_patterns"]:
            self.strategies["domain_patterns"][domain] = {
                "avg_score": 0,
                "session_count": 0,
                "common_issues": []
            }

        pattern = self.strategies["domain_patterns"][domain]
        pattern["avg_score"] = (
            (pattern["avg_score"] * pattern["session_count"] + avg_score) /
            (pattern["session_count"] + 1)
        )
        pattern["session_count"] += 1

        # 记录常见问题
        if feedback.get("improved"):
            pattern["common_issues"].append(feedback["improved"])
            # 只保留最近的10个问题
            pattern["common_issues"] = pattern["common_issues"][-10:]

        # 4. 自适应学习率
        eval_result = None
        adjustment = self.strategies["intensity_adjustments"][intensity]
        if "consecutive_failures" not in adjustment:
            adjustment["consecutive_failures"] = 0
        if "consecutive_successes" not in adjustment:
            adjustment["consecutive_successes"] = 0

        verdict = "success"  # 默认
        if session.get("metrics"):
            eval_result = auto_evaluate(session["metrics"])
            verdict = eval_result["verdict"]
            is_success = eval_result["is_success"]

        if not is_success:
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
        else:  # success
            adjustment["consecutive_failures"] = 0
            adjustment["consecutive_successes"] = 0

        # 5. 记录问题模式
        if feedback.get("improved") and avg_score < 3:
            failure_type = "none"
            if session.get("metrics") and eval_result is not None:
                failure_type = classify_failure(session["metrics"], eval_result["verdict"])
            self.strategies["problem_patterns"].append({
                "issue": feedback["improved"],
                "failure_type": failure_type,
                "domain": domain,
                "intensity": intensity,
                "max_consecutive": session.get("metrics", {}).get("max_consecutive", 0),
                "trigram_precision": session.get("metrics", {}).get("trigram_precision", 0),
                "timestamp": session.get("timestamp")
            })
            # 只保留最近的20个问题模式
            self.strategies["problem_patterns"] = self.strategies["problem_patterns"][-20:]

        # 6. 添加缺失术语
        if feedback.get("missing_terms"):
            if "new_terms" not in self.strategies:
                self.strategies["new_terms"] = []
            self.strategies["new_terms"].extend(feedback["missing_terms"])
            self.strategies["new_terms"] = list(set(self.strategies["new_terms"]))[-50:]

        # 保存策略
        self._save_strategies()

    def get_rewrite_suggestions(
        self,
        domain: str = "general",
        intensity: str = "medium",
        current_metrics: dict = None
    ) -> dict:
        """
        获取改写建议（基于学习到的策略）

        参数:
            domain: 学科领域
            intensity: 改写强度
            current_metrics: 当前文本的相似度指标（max_consecutive, trigram_precision）

        返回:
            改写建议
        """
        suggestions = {
            "preferred_vocabulary": [],
            "effective_techniques": [],
            "intensity_multiplier": 1.0,
            "domain_issues": [],
            "new_terms_to_preserve": [],
            "targeted_advice": [],
            "priority_techniques": [],
            "effective_combinations": [],
        }

        # 1. 获取偏好词汇
        for key, data in self.strategies["vocabulary_preferences"].items():
            if data["success"] >= 2:  # 至少成功2次
                suggestions["preferred_vocabulary"].append(key)

        # 2. 获取有效技术
        tech_eff = self.strategies["technique_effectiveness"]
        for tech, data in tech_eff.items():
            if data["total"] > 0:
                success_rate = data["success"] / data["total"]
                if success_rate >= 0.7:  # 70%以上成功率
                    suggestions["effective_techniques"].append({
                        "technique": tech,
                        "success_rate": round(success_rate, 2)
                    })

        # 3. 获取强度调整
        if intensity in self.strategies["intensity_adjustments"]:
            suggestions["intensity_multiplier"] = self.strategies["intensity_adjustments"][intensity]["multiplier"]

        # 4. 获取领域问题
        if domain in self.strategies["domain_patterns"]:
            pattern = self.strategies["domain_patterns"][domain]
            suggestions["domain_issues"] = pattern.get("common_issues", [])[-5:]

        # 5. 获取新术语
        suggestions["new_terms_to_preserve"] = self.strategies.get("new_terms", [])[-10:]

        # 6. 有效技巧组合
        for combo_key, data in self.strategies.get("technique_combinations", {}).items():
            if data["total"] >= 2:
                success_rate = data["success"] / data["total"]
                if success_rate >= 0.7:
                    suggestions["effective_combinations"].append({
                        "combination": combo_key,
                        "success_rate": round(success_rate, 2)
                    })

        # 7. 基于历史问题模式生成建议
        recent_problems = [
            p for p in self.strategies.get("problem_patterns", [])
            if p.get("domain") == domain
        ][-5:]

        failure_type_advice = {
            "consecutive_too_long": "该学科历史改写中多次出现超长连续匹配，建议优先使用 voice_conversion + clause_insertion",
            "structure_too_similar": "该学科历史改写中句式相似度偏高，建议加强结构调整",
            "consecutive_risk": "该学科历史改写中连续匹配接近阈值，建议增加句式变化",
            "trigram_risk": "该学科历史改写中三元组重叠率偏高，建议加强结构调整",
        }
        seen_types = set()
        for problem in recent_problems:
            ft = problem.get("failure_type", "")
            if ft in failure_type_advice and ft not in seen_types:
                suggestions["targeted_advice"].append(failure_type_advice[ft])
                seen_types.add(ft)

        # 8. 基于当前文本指标生成建议
        if current_metrics:
            mc = current_metrics.get("max_consecutive", 0)
            tri = current_metrics.get("trigram_precision", 0)

            if mc >= 8:
                suggestions["priority_techniques"] = ["voice_conversion", "clause_insertion", "word_order_change"]
                suggestions["targeted_advice"].append(
                    f"存在 {mc} 词连续匹配（超过 Turnitin 阈值），必须使用句式重组打破结构"
                )
            elif mc >= 5:
                suggestions["priority_techniques"] = ["voice_conversion", "synonym_replacement", "word_order_change"]
                suggestions["targeted_advice"].append(
                    f"连续匹配 {mc} 词，接近阈值，建议使用句式重组+同义词替换"
                )
            elif tri >= 0.20:
                suggestions["priority_techniques"] = ["synonym_replacement", "word_order_change"]
                suggestions["targeted_advice"].append(
                    f"三元组精度 {tri:.1%}，需要改变句子结构和用词"
                )

        return suggestions

    def get_strategy_report(self) -> str:
        """生成策略报告"""
        report = """
## 反馈学习策略报告

### 词汇偏好 (Top 10)
{vocab_prefs}

### 技术有效性
{tech_effectiveness}

### 强度调整
{intensity_adj}

### 领域模式
{domain_patterns}

### 问题模式 (最近5个)
{problem_patterns}

### 新增术语 (待添加)
{new_terms}

### 策略更新时间
{last_updated}
"""

        # 词汇偏好
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

        # 技术有效性
        tech_effectiveness = ""
        for tech, data in self.strategies["technique_effectiveness"].items():
            if data["total"] > 0:
                rate = data["success"] / data["total"]
                bar = "█" * int(rate * 5) + "░" * (5 - int(rate * 5))
                tech_effectiveness += f"- {tech}: {bar} {rate:.0%} ({data['success']}/{data['total']})\n"
            else:
                tech_effectiveness += f"- {tech}: 暂无数据\n"

        # 强度调整
        intensity_adj = ""
        for intensity, data in self.strategies["intensity_adjustments"].items():
            mult = data["multiplier"]
            if mult > 1.0:
                intensity_adj += f"- {intensity}: 增加 {mult:.2f}x (低分反馈，加强改写)\n"
            elif mult < 1.0:
                intensity_adj += f"- {intensity}: 降低 {mult:.2f}x (高分反馈，适当减弱)\n"
            else:
                intensity_adj += f"- {intensity}: 标准 1.00x\n"

        # 领域模式
        domain_patterns = ""
        for domain, data in self.strategies["domain_patterns"].items():
            avg = data["avg_score"]
            count = data["session_count"]
            domain_patterns += f"- {domain}: 平均 {avg:.1f}/5 ({count} 次会话)\n"
        if not domain_patterns:
            domain_patterns = "- 暂无数据\n"

        # 问题模式
        problem_patterns = ""
        for problem in self.strategies["problem_patterns"][-5:]:
            problem_patterns += f"- [{problem['domain']}] {problem['issue']}\n"
        if not problem_patterns:
            problem_patterns = "- 暂无问题\n"

        # 新术语
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

    def apply_learned_strategies(self, text: str, domain: str, intensity: str) -> dict:
        """
        应用学习到的策略

        参数:
            text: 原文
            domain: 学科领域
            intensity: 改写强度

        返回:
            策略应用结果
        """
        suggestions = self.get_rewrite_suggestions(domain, intensity)

        return {
            "text": text,
            "domain": domain,
            "intensity": intensity,
            "suggestions": suggestions,
            "should_increase_intensity": suggestions["intensity_multiplier"] > 1.1,
            "should_decrease_intensity": suggestions["intensity_multiplier"] < 0.9,
            "preferred_techniques": [t["technique"] for t in suggestions["effective_techniques"]],
            "terms_to_preserve": suggestions["new_terms_to_preserve"]
        }
