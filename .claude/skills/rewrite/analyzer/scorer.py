"""风险评分与优先级排序。"""

from typing import List
from analyzer.syntax import analyze_syntax
from analyzer.vocabulary import analyze_vocabulary
from analyzer.ai_traces import analyze_ai_traces
from analyzer.chinese import analyze_chinese

# 章节权重 — 越高表示改写收益越大
SECTION_WEIGHTS = {
    "discussion": 1.3,
    "method": 1.2,
    "abstract": 1.1,
    "related_work": 1.0,
    "conclusion": 1.0,
    "introduction": 0.9,
    "results": 1.1,
    "body": 1.0,
}

# 章节默认阈值
SECTION_THRESHOLDS = {
    "abstract": 0.25,
    "introduction": 0.3,
    "method": 0.35,
    "results": 0.3,
    "discussion": 0.25,
    "conclusion": 0.3,
    "related_work": 0.4,
    "body": 0.3,
}


def score_paragraph(text: str, section_type: str, patterns: list) -> dict:
    """对单个段落进行综合风险评分。"""
    syntax = analyze_syntax(text)
    vocabulary = analyze_vocabulary(text, patterns)
    ai_traces = analyze_ai_traces(text)
    chinese = analyze_chinese(text)

    all_issues = []
    all_issues.extend(syntax["issues"])
    all_issues.extend(vocabulary["issues"])
    all_issues.extend(ai_traces["issues"])
    all_issues.extend(chinese["issues"])

    # 各维度独立贡献风险分，上限 1.0
    # 语义：每个维度独立检测，多维度同时命中时风险叠加
    risk = syntax["score"] + vocabulary["score"] + ai_traces["score"] + chinese["score"]
    risk = min(risk, 1.0)

    weight = SECTION_WEIGHTS.get(section_type, 1.0)
    priority = risk * weight

    return {
        "risk": round(risk, 3),
        "priority": round(priority, 3),
        "section_type": section_type,
        "issues": all_issues,
        "suggestion": _generate_suggestion(all_issues),
    }


def score_paragraphs(paragraphs: List[dict], patterns: list) -> List[dict]:
    """批量评分段落，按优先级排序。"""
    results = []
    for para in paragraphs:
        score = score_paragraph(para["text"], para["section_type"], patterns)
        score["index"] = para["index"]
        results.append(score)

    results.sort(key=lambda x: x["priority"], reverse=True)
    return results


def compute_overall_risk(paragraph_scores: List[dict]) -> float:
    """计算全文整体风险分。"""
    if not paragraph_scores:
        return 0.0
    total = sum(p["risk"] for p in paragraph_scores)
    return round(total / len(paragraph_scores), 3)


def get_threshold(section_type: str, global_threshold: float | None) -> float:
    """获取某章节的阈值。"""
    if global_threshold is not None:
        return global_threshold
    return SECTION_THRESHOLDS.get(section_type, 0.3)


def _generate_suggestion(issues: list) -> str:
    if not issues:
        return "风险较低，无需重点改写"

    suggestions = []
    types = {i["type"] for i in issues}

    if "cliche_detected" in types or "connector_overuse" in types:
        suggestions.append("替换连接词和套话")
    if "uniform_sentence_length" in types or "low_burstiness" in types:
        suggestions.append("打破句式规律")
    if "excessive_le" in types or "de_nesting" in types:
        suggestions.append("调整中文表达习惯")
    if "no_personal_voice" in types:
        suggestions.append("增加个人化表达")

    return "；".join(suggestions) if suggestions else "综合改写"
