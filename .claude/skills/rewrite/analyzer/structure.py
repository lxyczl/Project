"""结构规律分析维度。"""

import statistics
from collections import Counter


def analyze_structure(paragraphs: list[dict]) -> dict:
    """分析段落结构规律，返回风险分和问题列表。"""
    if len(paragraphs) < 3:
        return {"score": 0.0, "issues": []}

    issues = []

    # 1. 段落长度方差 — 过于均匀
    lengths = [p["char_count"] for p in paragraphs]
    if len(lengths) >= 3:
        try:
            cv = statistics.stdev(lengths) / statistics.mean(lengths) if statistics.mean(lengths) > 0 else 0
        except statistics.StatisticsError:
            cv = 0
        if cv < 0.25:
            issues.append({"type": "uniform_para_length", "detail": f"段落长度变异系数 {cv:.2f}，段落等长"})

    # 2. 段首句模式 — 每段首句结构相同
    first_sentences = []
    for p in paragraphs:
        text = p["text"]
        first_sent = text[:min(20, len(text))]
        first_sentences.append(first_sent)

    # 检查是否有重复的开头模式
    if len(first_sentences) >= 3:
        # 简单检查：前几个字是否相同
        prefixes = [s[:5] for s in first_sentences if len(s) >= 5]
        if len(prefixes) >= 3:
            most_common = Counter(prefixes).most_common(1)
            if most_common and most_common[0][1] >= 3:
                issues.append({"type": "uniform_para_start", "detail": f"段首句模式重复: '{most_common[0][0]}...' 出现 {most_common[0][1]} 次"})

    score = _calculate_score(issues)
    return {"score": score, "issues": issues}


def _calculate_score(issues: list) -> float:
    base = 0.0
    for issue in issues:
        if issue["type"] == "uniform_para_length":
            base += 0.3
        elif issue["type"] == "uniform_para_start":
            base += 0.3
    return min(base, 1.0)
