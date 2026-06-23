"""词汇分布分析维度。"""

import re
import jieba


# AI 高频连接词（用于连接词频率统计）
AI_CONNECTORS = [
    "因此", "然而", "此外", "同时", "总之", "另外", "并且",
    "进而", "随后", "首先", "其次", "最后", "综上", "故而",
]


def analyze_vocabulary(text: str, patterns: list, platform: str | None = None) -> dict:
    """分析词汇分布，返回风险分和问题列表。

    Args:
        text: 待分析文本。
        patterns: 模式库规则列表。
        platform: 目标检测平台（cnki/vip/wanfang/paperpass），None 表示不加权。
    """
    issues = []

    # 1. TTR (Type-Token Ratio) — 词汇丰富度（用 jieba 分词，按词计算）
    words = [w for w in jieba.cut(text) if w.strip()]
    if len(words) > 5:
        ttr = len(set(words)) / len(words)
        if ttr < 0.4:
            issues.append({"type": "low_ttr", "detail": f"词汇丰富度 TTR={ttr:.2f}，偏低"})

    # 2. 连接词频率
    conn_count = sum(text.count(c) for c in AI_CONNECTORS)
    sentence_count = len(re.split(r'[。！？；.!?;]', text))
    if sentence_count > 0 and conn_count / sentence_count > 0.5:
        issues.append({"type": "connector_overuse", "detail": f"连接词频率 {conn_count}/{sentence_count}，过高"})

    # 3. 套话检测（完全依赖模式库，支持正则和平台加权）
    cliche_matches: list[str] = []
    _PATTERN_TYPES = {"cliche", "formal", "connector", "sentence_pattern",
                      "chinese_pattern", "idiom", "passive"}
    for pattern in patterns:
        if pattern.get("type") not in _PATTERN_TYPES:
            continue
        match_str = pattern["match"]
        hit = False
        try:
            hit = bool(re.search(match_str, text))
        except re.error:
            hit = match_str in text
        if hit:
            weight = _get_platform_weight(pattern, platform)
            if weight > 0:
                cliche_matches.append((match_str, weight))

    if cliche_matches:
        # 按平台权重排序，优先展示高权重的
        cliche_matches.sort(key=lambda x: x[1], reverse=True)
        names = [m[0] for m in cliche_matches[:5]]
        issues.append({"type": "cliche_detected", "detail": f"检测到套话: {', '.join(names)}"})

    score = _calculate_score(issues, cliche_matches)
    return {"score": score, "issues": issues}


def _get_platform_weight(pattern: dict, platform: str | None) -> float:
    """获取 pattern 在指定平台下的权重。"""
    if platform is None:
        return 1.0
    weights = pattern.get("platform_weight", {})
    return weights.get(platform, 0.5)  # 未知平台默认 0.5


def _calculate_score(issues: list, cliche_matches: list | None = None) -> float:
    base = 0.0
    for issue in issues:
        if issue["type"] == "low_ttr":
            base += 0.2
        elif issue["type"] == "connector_overuse":
            base += 0.25
        elif issue["type"] == "cliche_detected":
            # 套话得分基于命中数量和平台权重
            if cliche_matches:
                weighted_sum = sum(w for _, w in cliche_matches)
                base += min(0.15 + weighted_sum * 0.05, 0.35)
            else:
                base += 0.3
    return min(base, 1.0)
