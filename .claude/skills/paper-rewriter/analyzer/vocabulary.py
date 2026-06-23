"""词汇分布分析维度（英文学术写作）。"""

import re


# AI 高频连接词
AI_CONNECTORS = [
    "furthermore", "moreover", "consequently", "nevertheless", "additionally",
    "subsequently", "accordingly", "hence", "thus", "therefore",
    "however", "nonetheless", "likewise", "meanwhile", "otherwise",
]

# AI 高频填充短语
FILLER_PHRASES = [
    "it is worth noting that",
    "it should be noted that",
    "it is important to mention",
    "it is well known that",
    "as a matter of fact",
    "in light of the above",
    "in the realm of",
    "in the context of",
    "with regard to",
    "in terms of",
    "plays a crucial role",
    "plays an important role",
    "has gained significant attention",
    "has attracted considerable interest",
    "in recent years",
    "over the past few decades",
    "a growing body of evidence",
    "the results indicate that",
    "the findings suggest that",
    "this study aims to",
]


def tokenize(text: str) -> list[str]:
    """分词为小写单词列表。"""
    return re.findall(r'\b[a-z]+(?:-[a-z]+)*\b', text.lower())


def analyze_vocabulary(text: str, patterns: list) -> dict:
    """分析词汇分布，返回风险分和问题列表。"""
    issues = []

    # 1. CTTR (Corrected Type-Token Ratio) — 对文本长度不敏感的词汇丰富度
    words = tokenize(text)
    if len(words) > 10:
        cttr = len(set(words)) / (2 * len(words)) ** 0.5
        if cttr < 0.5:
            issues.append({
                "type": "low_ttr",
                "detail": f"Vocabulary richness CTTR={cttr:.2f}, too low"
            })

    # 2. 连接词频率
    text_lower = text.lower()
    conn_count = sum(text_lower.count(c) for c in AI_CONNECTORS)
    sentence_count = max(1, len(re.split(r'[.!?]', text)) - 1)
    if conn_count / sentence_count > 0.4:
        issues.append({
            "type": "connector_overuse",
            "detail": f"Connector frequency {conn_count}/{sentence_count}={conn_count/sentence_count:.1f}, too high"
        })

    # 3. 套话检测（内置 + 模式库）
    cliche_matches = []

    # 内置套话
    for phrase in FILLER_PHRASES:
        if phrase in text_lower:
            cliche_matches.append(phrase)

    # 模式库规则
    _PATTERN_TYPES = {"cliche", "formal", "connector", "sentence_pattern"}
    for pattern in patterns:
        if pattern.get("type") not in _PATTERN_TYPES:
            continue
        match_str = pattern["match"]
        try:
            if re.search(match_str, text, re.IGNORECASE):
                cliche_matches.append(match_str)
        except re.error:
            if match_str.lower() in text_lower:
                cliche_matches.append(match_str)

    if cliche_matches:
        unique = list(dict.fromkeys(cliche_matches))[:5]  # 去重取前5
        issues.append({
            "type": "cliche_detected",
            "detail": f"Cliche phrases detected: {', '.join(unique)}"
        })

    score = _calculate_score(issues, len(cliche_matches))
    return {"score": score, "issues": issues}


def _calculate_score(issues: list, cliche_count: int = 0) -> float:
    base = 0.0
    for issue in issues:
        if issue["type"] == "low_ttr":
            base += 0.2
        elif issue["type"] == "connector_overuse":
            base += 0.2
        elif issue["type"] == "cliche_detected":
            base += min(0.1 + cliche_count * 0.05, 0.35)
    return min(base, 1.0)
