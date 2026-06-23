"""AI 痕迹检测维度。"""

import re


def _split_sentences(text: str) -> list[str]:
    """按中文标点分句。"""
    pattern = r'([^。！？；.!?;]+[。！？；.!?;]?)'
    sentences = re.findall(pattern, text)
    return [s.strip() for s in sentences if s.strip()]


def analyze_ai_traces(text: str) -> dict:
    """检测 AI 生成痕迹，返回风险分和问题列表。"""
    issues = []
    sentences = _split_sentences(text)

    # 1. 流畅度异常 — 缺乏口语化断句
    # AI 文本通常句句完整，缺少省略号、破折号等不完整标记
    informal_markers = len(re.findall(r'[…—\-（(]', text))
    if len(sentences) > 5 and informal_markers / len(sentences) < 0.1:
        issues.append({"type": "too_fluent", "detail": f"口语化标记极少 ({informal_markers}/{len(sentences)})，行文过于工整"})

    # 2. 突发性 (Burstiness) — 句长变化是否自然
    if len(sentences) >= 5:
        lengths = [len(s) for s in sentences]
        # 检查是否有连续相似长度的句子
        consecutive_similar = 0
        max_consecutive = 0
        for i in range(1, len(lengths)):
            if abs(lengths[i] - lengths[i-1]) < 5:
                consecutive_similar += 1
                max_consecutive = max(max_consecutive, consecutive_similar)
            else:
                consecutive_similar = 0

        if max_consecutive >= 3:
            issues.append({"type": "low_burstiness", "detail": f"连续 {max_consecutive + 1} 句长度相近，缺乏变化"})

    # 3. 无个人化表达 — 缺少"笔者""我们""本文"等主观标记
    personal_markers = len(re.findall(r'笔者|我们认为|我们发现|我注意到|从我的角度来看', text))
    if len(sentences) > 8 and personal_markers == 0:
        issues.append({"type": "no_personal_voice", "detail": "缺少个人化表达标记"})

    score = _calculate_score(issues)
    return {"score": score, "issues": issues}


def _calculate_score(issues: list) -> float:
    base = 0.0
    for issue in issues:
        if issue["type"] == "too_fluent":
            base += 0.2
        elif issue["type"] == "low_burstiness":
            base += 0.25
        elif issue["type"] == "no_personal_voice":
            base += 0.2
    return min(base, 1.0)
