"""词汇分布分析维度。"""

import re


# AI 高频连接词
AI_CONNECTORS = [
    "因此", "然而", "此外", "同时", "总之", "另外", "并且",
    "进而", "随后", "首先", "其次", "最后", "综上", "故而",
]

# AI 套话
AI_CLICHES = [
    "综上所述", "值得注意的是", "具有重要意义", "引起了广泛关注",
    "取得了较好的效果", "在此基础上", "本文提出了一种",
    "实验结果表明", "近年来", "如图所示", "如表所示",
]


def analyze_vocabulary(text: str, patterns: list) -> dict:
    """分析词汇分布，返回风险分和问题列表。"""
    issues = []

    # 1. TTR (Type-Token Ratio) — 词汇丰富度
    words = list(text)  # 中文按字计算
    if len(words) > 10:
        ttr = len(set(words)) / len(words)
        if ttr < 0.3:
            issues.append({"type": "low_ttr", "detail": f"词汇丰富度 TTR={ttr:.2f}，偏低"})

    # 2. 连接词频率
    conn_count = sum(text.count(c) for c in AI_CONNECTORS)
    sentence_count = len(re.split(r'[。！？；.!?;]', text))
    if sentence_count > 0 and conn_count / sentence_count > 0.5:
        issues.append({"type": "connector_overuse", "detail": f"连接词频率 {conn_count}/{sentence_count}，过高"})

    # 3. 套话检测（结合模式库）
    cliche_matches = []
    for pattern in patterns:
        if pattern.get("type") in ("cliche", "formal", "connector"):
            if pattern["match"] in text:
                cliche_matches.append(pattern["match"])

    # 内置套话检测
    for cliche in AI_CLICHES:
        if cliche in text and cliche not in cliche_matches:
            cliche_matches.append(cliche)

    if cliche_matches:
        issues.append({"type": "cliche_detected", "detail": f"检测到套话: {', '.join(cliche_matches[:5])}"})

    score = _calculate_score(issues)
    return {"score": score, "issues": issues}


def _calculate_score(issues: list) -> float:
    base = 0.0
    for issue in issues:
        if issue["type"] == "low_ttr":
            base += 0.2
        elif issue["type"] == "connector_overuse":
            base += 0.25
        elif issue["type"] == "cliche_detected":
            base += 0.3
    return min(base, 1.0)
