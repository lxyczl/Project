"""风险评分与优先级排序。"""

from typing import List
from analyzer.syntax import analyze_syntax
from analyzer.vocabulary import analyze_vocabulary
from analyzer.ai_traces import analyze_ai_traces
from analyzer.chinese import analyze_chinese
from analyzer.structure import analyze_structure

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


def score_paragraph(text: str, section_type: str, patterns: list,
                    platform: str | None = None) -> dict:
    """对单个段落进行综合风险评分。

    四维度权重之和为 1.0：
        syntax=0.2, vocabulary=0.3, ai_traces=0.25, chinese=0.25

    结构维度（structure）为全文级修正，在 score_paragraphs 中叠加。
    """
    syntax = analyze_syntax(text)
    vocabulary = analyze_vocabulary(text, patterns, platform)
    ai_traces = analyze_ai_traces(text)
    chinese = analyze_chinese(text)

    all_issues = []
    all_issues.extend(syntax["issues"])
    all_issues.extend(vocabulary["issues"])
    all_issues.extend(ai_traces["issues"])
    all_issues.extend(chinese["issues"])

    # 四维度加权，总和 = 1.0
    risk = (
        syntax["score"] * 0.2 +
        vocabulary["score"] * 0.3 +
        ai_traces["score"] * 0.25 +
        chinese["score"] * 0.25
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


def score_paragraphs(paragraphs: List[dict], patterns: list,
                     platform: str | None = None) -> List[dict]:
    """批量评分段落，按优先级排序。

    结构维度（structure）为全文级修正，叠加在单段评分之上，
    叠加后 risk 不超过 1.0。
    """
    results = []
    for para in paragraphs:
        score = score_paragraph(para["text"], para["section_type"], patterns, platform)
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
        return "风险较低，无需重点改写"

    suggestions = []
    types = {i["type"] for i in issues}

    # 词汇层面
    if "cliche_detected" in types or "connector_overuse" in types:
        suggestions.append("替换连接词和套话")
    if "low_ttr" in types:
        suggestions.append("丰富用词，减少重复")

    # 句法层面
    if "uniform_sentence_length" in types or "low_burstiness" in types:
        suggestions.append("打破句式规律，制造长短交错")
    if "deep_nesting" in types or "excessive_parallelism" in types:
        suggestions.append("拆分长句，减少并列和嵌套")

    # AI 痕迹层面
    if "too_fluent" in types:
        suggestions.append("加入口语化标记（破折号、括号补充等）")
    if "no_personal_voice" in types:
        suggestions.append("增加个人化表达（笔者、我们等）")

    # 中文特化层面
    if "excessive_le" in types:
        suggestions.append("减少'了'字使用")
    if "de_nesting" in types:
        suggestions.append("拆分'的'字长定语为独立分句")
    if "idiom_overuse" in types:
        suggestions.append("用直白描述替换成语")
    if "bei_suo_pattern" in types:
        suggestions.append("改'被...所...'为主动语态")

    # 结构层面（全文级）
    if "uniform_para_length" in types:
        suggestions.append("调整段落长短，避免等长")
    if "uniform_para_start" in types:
        suggestions.append("改变段首句开头方式")

    return "；".join(suggestions) if suggestions else "综合改写"
