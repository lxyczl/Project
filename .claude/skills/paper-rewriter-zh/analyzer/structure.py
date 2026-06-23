"""结构规律分析维度（全文级，中文适配）。"""
import statistics
from collections import Counter


def analyze_structure(paragraphs: list[dict]) -> dict:
    """分析段落结构规律，返回风险分和问题列表。"""
    if len(paragraphs) < 3:
        return {"score": 0.0, "issues": []}

    issues = []

    # 1. 段落长度方差 — 过于均匀
    lengths = [p.get("char_count", len(p["text"])) for p in paragraphs]
    if len(lengths) >= 3:
        mean_len = statistics.mean(lengths)
        if mean_len > 0:
            try:
                cv = statistics.stdev(lengths) / mean_len
            except statistics.StatisticsError:
                cv = 0
            if cv < 0.2:
                issues.append({
                    "type": "uniform_para_length",
                    "detail": f"段落长度 CV={cv:.2f}，段落过于均匀"
                })

    # 2. 段首句模式 — 每段首句结构相同
    first_sentences = []
    for p in paragraphs:
        text = p["text"]
        first_sent = text[:min(15, len(text))]
        first_sentences.append(first_sent)

    if len(first_sentences) >= 3:
        prefixes = []
        for s in first_sentences:
            chars = s[:4]
            if len(chars) >= 2:
                prefixes.append(chars)

        if len(prefixes) >= 3:
            most_common = Counter(prefixes).most_common(1)
            if most_common and most_common[0][1] >= 3:
                issues.append({
                    "type": "uniform_para_start",
                    "detail": f"段首模式重复：'{most_common[0][0]}...' 出现 {most_common[0][1]} 次"
                })

    score = _calculate_score(issues)
    return {"score": score, "issues": issues}


def _calculate_score(issues: list) -> float:
    base = 0.0
    for issue in issues:
        t = issue["type"]
        if t == "uniform_para_length":
            base += 0.3
        elif t == "uniform_para_start":
            base += 0.3
    return min(base, 1.0)
