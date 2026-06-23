"""Risk scoring and priority ranking."""

from typing import List
from analyzer.syntax import analyze_syntax
from analyzer.vocabulary import analyze_vocabulary
from analyzer.ai_traces import analyze_ai_traces
from analyzer.english import analyze_english
from analyzer.structure import analyze_structure

# Section weights — higher = more benefit from rewriting
SECTION_WEIGHTS = {
    "discussion": 1.3,
    "method": 1.2,
    "abstract": 1.1,
    "related_work": 0.8,
    "conclusion": 1.0,
    "introduction": 0.9,
    "results": 1.1,
    "body": 1.0,
}

# Default thresholds per section
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
                    platform: str | None = None, no_learn: bool = False) -> dict:
    """Score a single paragraph for AIGC risk.

    Four dimension weights sum to 1.0:
        vocabulary=0.25, ai_traces=0.30, english=0.25, syntax=0.20

    Structure dimension is a full-text correction, applied in score_paragraphs().

    Args:
        no_learn: Reserved parameter. When True, skip loading learned patterns.
                  Currently not implemented (learned patterns always loaded via PatternLibrary).
    """
    vocabulary = analyze_vocabulary(text, patterns, platform)
    ai_traces = analyze_ai_traces(text, section_type)
    english = analyze_english(text, section_type)
    syntax = analyze_syntax(text)

    all_issues = []
    all_issues.extend(vocabulary["issues"])
    all_issues.extend(ai_traces["issues"])
    all_issues.extend(english["issues"])
    all_issues.extend(syntax["issues"])

    # Four dimensions weighted, sum = 1.0
    risk = (
        vocabulary["score"] * 0.25 +
        ai_traces["score"] * 0.30 +
        english["score"] * 0.25 +
        syntax["score"] * 0.20
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
    """Batch score paragraphs, sorted by priority.

    Structure dimension is a full-text correction, added on top of per-paragraph scores.
    Total risk capped at 1.0.
    """
    results = []
    for para in paragraphs:
        score = score_paragraph(para["text"], para["section_type"], patterns, platform)
        score["index"] = para["index"]
        results.append(score)

    # Structure analysis: full-text global correction (+0.15 when structure issues detected)
    structure = analyze_structure(paragraphs)
    if structure["issues"]:
        structure_bonus = 0.15
        for s in results:
            s["risk"] = round(min(s["risk"] + structure_bonus, 1.0), 3)
            s["priority"] = round(s["risk"] * SECTION_WEIGHTS.get(s["section_type"], 1.0), 3)
            s["issues"].extend(structure["issues"])

    results.sort(key=lambda x: x["priority"], reverse=True)
    return results


def compute_overall_risk(paragraph_scores: List[dict]) -> float:
    """Compute overall risk score for the full text."""
    if not paragraph_scores:
        return 0.0
    total = sum(p["risk"] for p in paragraph_scores)
    return round(total / len(paragraph_scores), 3)


def get_threshold(section_type: str, global_threshold: float | None) -> float:
    """Get threshold for a section type."""
    if global_threshold is not None:
        return global_threshold
    return SECTION_THRESHOLDS.get(section_type, 0.3)


def _generate_suggestion(issues: list) -> str:
    if not issues:
        return "Low risk, no major rewrite needed"

    suggestions = []
    types = {i["type"] for i in issues}

    # Vocabulary level
    if "cliche_detected" in types or "connector_overuse" in types:
        suggestions.append("Replace connectors and cliches")
    if "low_cttr" in types:
        suggestions.append("Enrich vocabulary, reduce repetition")

    # Syntax level
    if "uniform_sentence_length" in types or "low_burstiness" in types:
        suggestions.append("Break sentence patterns, create long/short variation")
    if "deep_nesting" in types or "excessive_parallelism" in types:
        suggestions.append("Split long sentences, reduce parallelism and nesting")

    # AI traces level
    if "too_fluent" in types:
        suggestions.append("Add informal markers (em dashes, parenthetical notes, etc.)")
    if "no_personal_voice" in types:
        suggestions.append("Add personal expressions (I argue, we found, etc.)")

    # English-specific level
    if "excessive_passive" in types:
        suggestions.append("Convert passive to active voice where appropriate")
    if "nominalization_overuse" in types:
        suggestions.append("Restore nominalizations to verb forms")
    if "hedging_overuse" in types:
        suggestions.append("Remove excess hedging, use direct expressions")

    # Structure level (full-text)
    if "uniform_para_length" in types:
        suggestions.append("Vary paragraph lengths")
    if "uniform_para_start" in types:
        suggestions.append("Change paragraph opening styles")

    return "; ".join(suggestions) if suggestions else "Comprehensive rewrite"
