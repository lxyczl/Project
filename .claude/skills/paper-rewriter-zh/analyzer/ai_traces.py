"""AI 痕迹检测维度（中文学术写作）。"""
import re
from analyzer.syntax import split_sentences


def analyze_ai_traces(text: str) -> dict:
    """检测 AI 生成痕迹，返回风险分和问题列表。"""
    issues = []
    sentences = split_sentences(text)

    # 1. 流畅度异常 — 缺乏口语化/非正式标记
    informal_markers = len(re.findall(r'[—–\-（(…「]', text))
    if len(sentences) > 5 and informal_markers / len(sentences) < 0.1:
        issues.append({
            "type": "too_fluent",
            "detail": f"非正式标记过少（{informal_markers}/{len(sentences)}），文本过于工整"
        })

    # 2. 突发性 — 句长变化是否自然
    if len(sentences) >= 5:
        lengths = [len(s) for s in sentences]
        consecutive_similar = 0
        max_consecutive = 0
        for i in range(1, len(lengths)):
            if abs(lengths[i] - lengths[i-1]) < 5:
                consecutive_similar += 1
                max_consecutive = max(max_consecutive, consecutive_similar)
            else:
                consecutive_similar = 0

        if max_consecutive >= 3:
            issues.append({
                "type": "low_burstiness",
                "detail": f"{max_consecutive + 1} 个连续句子长度相近"
            })

    # 3. 无个人化表达 — 缺少"我们""笔者""作者"等主观标记
    personal_markers = len(re.findall(r'(?:我们|笔者|作者|本文|本研究)', text))
    if len(sentences) > 6 and personal_markers == 0:
        issues.append({
            "type": "no_personal_voice",
            "detail": "未检测到个人化表达（我们/笔者/本文）"
        })

    # 4. 句式单调 — 所有句子都用"该""此""其"开头
    the_starts = len(re.findall(r'^(?:该|此|其|这|那)', text, re.MULTILINE))
    total_sentences = len(sentences)
    if total_sentences > 4 and the_starts / total_sentences > 0.7:
        issues.append({
            "type": "monotonous_openings",
            "detail": f"{the_starts}/{total_sentences}={the_starts/total_sentences:.0%} 句子以'该/此/其'开头"
        })

    score = _calculate_score(issues)
    return {"score": score, "issues": issues}


def _calculate_score(issues: list) -> float:
    base = 0.0
    for issue in issues:
        t = issue["type"]
        if t == "too_fluent":
            base += 0.2
        elif t == "low_burstiness":
            base += 0.25
        elif t == "no_personal_voice":
            base += 0.15
        elif t == "monotonous_openings":
            base += 0.2
    return min(base, 1.0)
