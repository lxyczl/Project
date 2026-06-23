"""风险评分与优先级排序（英文）。"""

from typing import List
from analyzer.syntax import analyze_syntax
from analyzer.vocabulary import analyze_vocabulary
from analyzer.ai_traces import analyze_ai_traces
from analyzer.english import analyze_english
from analyzer.structure import analyze_structure

# 章节权重 — 越高表示改写收益越大
SECTION_WEIGHTS = {
    "abstract": 1.2,
    "introduction": 1.0,
    "methods": 1.1,
    "results": 1.1,
    "discussion": 1.3,
    "conclusion": 1.0,
    "body": 1.0,
}

# 章节默认阈值
SECTION_THRESHOLDS = {
    "abstract": 0.25,
    "introduction": 0.3,
    "methods": 0.35,
    "results": 0.3,
    "discussion": 0.25,
    "conclusion": 0.3,
    "body": 0.3,
}


def score_paragraph(text: str, section_type: str, patterns: list) -> dict:
    """对单个段落进行综合风险评分。

    四维度权重之和为 1.0：
        syntax=0.2, vocabulary=0.3, ai_traces=0.25, english=0.25

    结构维度（structure）为全文级修正，在 score_paragraphs 中叠加。
    """
    syntax = analyze_syntax(text)
    vocabulary = analyze_vocabulary(text, patterns)
    ai_traces = analyze_ai_traces(text)
    english = analyze_english(text)

    all_issues = []
    all_issues.extend(syntax["issues"])
    all_issues.extend(vocabulary["issues"])
    all_issues.extend(ai_traces["issues"])
    all_issues.extend(english["issues"])

    # 四维度加权，总和 = 1.0
    risk = (
        syntax["score"] * 0.2 +
        vocabulary["score"] * 0.3 +
        ai_traces["score"] * 0.25 +
        english["score"] * 0.25
    )
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

    # 结构分析：全文维度的全局修正（最多加 0.15）
    structure = analyze_structure(paragraphs)
    structure_weight = 0.15
    for s in results:
        s["risk"] = round(min(s["risk"] + structure["score"] * structure_weight, 1.0), 3)
        s["priority"] = round(s["risk"] * SECTION_WEIGHTS.get(s["section_type"], 1.0), 3)
    if structure["issues"]:
        for s in results:
            s["issues"].extend(structure["issues"])

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
        return "Low risk, no major rewriting needed"

    suggestions = []
    types = {i["type"] for i in issues}

    # 词汇层面
    if "cliche_detected" in types or "connector_overuse" in types:
        suggestions.append("Replace connectors and cliche phrases")
    if "low_ttr" in types:
        suggestions.append("Enrich vocabulary, reduce repetition")
    if "verbose_phrases" in types:
        suggestions.append("Simplify verbose expressions")

    # 句法层面
    if "uniform_sentence_length" in types or "low_burstiness" in types:
        suggestions.append("Vary sentence length, create natural rhythm")
    if "excessive_passive" in types:
        suggestions.append("Reduce passive voice, use active where appropriate")
    if "deep_nesting" in types or "excessive_parallelism" in types:
        suggestions.append("Simplify nested clauses and parallel structures")

    # AI 痕迹层面
    if "too_fluent" in types:
        suggestions.append("Add informal markers (dashes, parenthetical notes)")
    if "no_personal_voice" in types:
        suggestions.append("Add personal voice (we, our, the authors)")
    if "monotonous_openings" in types:
        suggestions.append("Vary sentence openings")

    # 英文特化层面
    if "excessive_the" in types:
        suggestions.append("Reduce 'the' overuse, use specific nouns")
    if "excessive_hedging" in types:
        suggestions.append("Reduce hedging words, be more direct")
    if "excessive_nominalization" in types:
        suggestions.append("Convert nominalizations to verbs")
    if "monotonous_para_start" in types:
        suggestions.append("Vary paragraph opening patterns")

    # 结构层面
    if "uniform_para_length" in types:
        suggestions.append("Adjust paragraph lengths for variety")
    if "uniform_para_start" in types:
        suggestions.append("Change paragraph opening patterns")

    return "; ".join(suggestions) if suggestions else "General rewriting"
