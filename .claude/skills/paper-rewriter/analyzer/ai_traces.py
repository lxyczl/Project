"""AI 痕迹检测维度（英文学术写作）。"""

import re
from analyzer.syntax import split_sentences


def analyze_ai_traces(text: str) -> dict:
    """检测 AI 生成痕迹，返回风险分和问题列表。"""
    issues = []
    sentences = split_sentences(text)

    # 1. 流畅度异常 — 缺乏口语化/非正式标记
    # 人类写作通常有破折号、括号补充、省略号等
    informal_markers = len(re.findall(r'[—–\-（(…]', text))
    if len(sentences) > 5 and informal_markers / len(sentences) < 0.1:
        issues.append({
            "type": "too_fluent",
            "detail": f"Few informal markers ({informal_markers}/{len(sentences)}), text is overly polished"
        })

    # 2. 突发性 (Burstiness) — 句长变化是否自然
    if len(sentences) >= 5:
        lengths = [len(s.split()) for s in sentences]
        consecutive_similar = 0
        max_consecutive = 0
        for i in range(1, len(lengths)):
            if abs(lengths[i] - lengths[i-1]) < 4:
                consecutive_similar += 1
                max_consecutive = max(max_consecutive, consecutive_similar)
            else:
                consecutive_similar = 0

        if max_consecutive >= 3:
            issues.append({
                "type": "low_burstiness",
                "detail": f"{max_consecutive + 1} consecutive sentences with similar length"
            })

    # 3. 无个人化表达 — 缺少 "we", "our", "I" 等主观标记
    personal_markers = len(re.findall(r'\b(?:we|our|I|my|the author|the researchers)\b', text, re.IGNORECASE))
    if len(sentences) > 6 and personal_markers == 0:
        issues.append({
            "type": "no_personal_voice",
            "detail": "No personal voice markers (we/our/I) detected"
        })

    # 4. 句式单调 — 所有句子都用 "The X is/was/has" 开头
    the_starts = len(re.findall(r'^(?:The|This|These|It)\s', text, re.MULTILINE))
    total_sentences = len(sentences)
    if total_sentences > 4 and the_starts / total_sentences > 0.7:
        issues.append({
            "type": "monotonous_openings",
            "detail": f"{the_starts}/{total_sentences}={the_starts/total_sentences:.0%} sentences start with 'The/This/These/It'"
        })

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
            base += 0.15
        elif issue["type"] == "monotonous_openings":
            base += 0.2
    return min(base, 1.0)
