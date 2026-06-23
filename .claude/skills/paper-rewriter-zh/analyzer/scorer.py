"""风险评分与优先级排序（中文学术写作）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from analyzer.syntax import analyze_syntax, split_sentences
from analyzer.vocabulary import analyze_vocabulary
from analyzer.ai_traces import analyze_ai_traces
from analyzer.structure import analyze_structure
from analyzer.paragraphs import split_paragraphs
from analyzer.patterns import PatternLibrary

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


def load_patterns() -> list:
    """加载模式库。"""
    patterns_dir = Path(__file__).parent.parent / "patterns"
    lib = PatternLibrary.load(patterns_dir)
    return lib.get_patterns()


def analyze_text(text: str) -> dict:
    """对文本进行全维度风险分析。

    三维度权重：syntax=0.25, vocabulary=0.35, ai_traces=0.40
    结构维度为全文级修正，在段落评分中叠加。
    """
    patterns = load_patterns()

    # 段落切分
    paragraphs = split_paragraphs(text)
    if not paragraphs:
        # 单段文本直接分析
        return _analyze_single(text, patterns)

    # 逐段评分
    para_scores = []
    for para in paragraphs:
        score = _score_paragraph(para["text"], para["section_type"], patterns)
        score["index"] = para["index"]
        para_scores.append(score)

    # 结构分析：全文级修正
    structure = analyze_structure(paragraphs)
    for s in para_scores:
        s["risk"] = round(min(s["risk"] + structure["score"] * 0.15, 1.0), 3)
        s["priority"] = round(s["risk"] * SECTION_WEIGHTS.get(s["section_type"], 1.0), 3)
    if structure["issues"]:
        for s in para_scores:
            s["issues"].extend(structure["issues"])

    para_scores.sort(key=lambda x: x["priority"], reverse=True)

    overall = round(sum(p["risk"] for p in para_scores) / len(para_scores), 3) if para_scores else 0.0

    return {
        "overall_risk": overall,
        "paragraph_scores": para_scores,
        "structure": structure,
        "paragraphs": paragraphs,
    }


def _analyze_single(text: str, patterns: list) -> dict:
    """单段文本分析。"""
    score = _score_paragraph(text, "body", patterns)
    return {
        "overall_risk": score["risk"],
        "paragraph_scores": [score],
        "structure": {"score": 0.0, "issues": []},
        "paragraphs": [{"index": 0, "text": text, "char_count": len(text), "section_type": "body"}],
    }


def _score_paragraph(text: str, section_type: str, patterns: list) -> dict:
    """对单个段落进行综合风险评分。"""
    syntax = analyze_syntax(text)
    vocabulary = analyze_vocabulary(text, patterns)
    ai_traces = analyze_ai_traces(text)

    all_issues = []
    all_issues.extend(syntax["issues"])
    all_issues.extend(vocabulary["issues"])
    all_issues.extend(ai_traces["issues"])

    risk = (
        syntax["score"] * 0.25 +
        vocabulary["score"] * 0.35 +
        ai_traces["score"] * 0.40
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


def _generate_suggestion(issues: list) -> str:
    if not issues:
        return "风险较低，无需大幅改写"

    suggestions = []
    types = {i["type"] for i in issues}

    if "cliche_detected" in types or "connector_overuse" in types:
        suggestions.append("替换连接词和套话")
    if "low_ttr" in types:
        suggestions.append("丰富词汇，减少重复")
    if "uniform_sentence_length" in types or "low_burstiness" in types:
        suggestions.append("变化句长，制造自然节奏")
    if "excessive_passive" in types:
        suggestions.append("减少被动语态，适当使用主动句")
    if "deep_nesting" in types or "excessive_parallelism" in types:
        suggestions.append("简化嵌套结构和并列结构")
    if "too_fluent" in types:
        suggestions.append("增加非正式标记（破折号、括号补充）")
    if "no_personal_voice" in types:
        suggestions.append("增加个人化表达（我们、笔者）")
    if "monotonous_openings" in types:
        suggestions.append("变化句式开头")
    if "uniform_para_length" in types:
        suggestions.append("调整段落长度，增加变化")
    if "uniform_para_start" in types:
        suggestions.append("改变段落开头模式")

    return "；".join(suggestions) if suggestions else "一般性改写"
