"""句法特征分析维度。"""

import re
import statistics


def _split_sentences(text: str) -> list[str]:
    """按中文标点分句。"""
    pattern = r'([^。！？；.!?;]+[。！？；.!?;]?)'
    sentences = re.findall(pattern, text)
    return [s.strip() for s in sentences if s.strip()]


def analyze_syntax(text: str) -> dict:
    """分析句法特征，返回风险分和问题列表。"""
    sentences = _split_sentences(text)
    if len(sentences) < 2:
        return {"score": 0.0, "issues": []}

    issues = []

    # 1. 句长方差 — 过于均匀 = 高风险
    lengths = [len(s) for s in sentences]
    if len(lengths) >= 3:
        try:
            cv = statistics.stdev(lengths) / statistics.mean(lengths) if statistics.mean(lengths) > 0 else 0
        except statistics.StatisticsError:
            cv = 0
        # 变异系数 < 0.3 表示句长过于均匀
        if cv < 0.3:
            issues.append({"type": "uniform_sentence_length", "detail": f"句长变异系数 {cv:.2f}，过于均匀"})

    # 2. 并列结构频率 — 用非贪婪匹配避免回溯
    parallel_markers = len(re.findall(r'[，,].*?[，,].*?[，,]', text))
    if parallel_markers > len(sentences) * 0.5:
        issues.append({"type": "excessive_parallelism", "detail": f"并列结构过多: {parallel_markers} 处"})

    # 3. 从句嵌套深度 — 限制在句内匹配，避免跨句回溯
    deep_nested = len(re.findall(r'的[^。，！？；\n]{0,15}的[^。，！？；\n]{0,15}的[^。，！？；\n]{0,15}的', text))
    if deep_nested > 0:
        issues.append({"type": "deep_nesting", "detail": f"检测到 {deep_nested} 处深层嵌套"})

    score = _calculate_score(issues)
    return {"score": score, "issues": issues}


def _calculate_score(issues: list) -> float:
    base = 0.0
    for issue in issues:
        if issue["type"] == "uniform_sentence_length":
            base += 0.3
        elif issue["type"] == "excessive_parallelism":
            base += 0.2
        elif issue["type"] == "deep_nesting":
            base += 0.15
    return min(base, 1.0)
