"""Structure pattern analysis dimension.

Language-independent, reused from Chinese version.
"""

import statistics
from collections import Counter


def analyze_structure(paragraphs: list[dict]) -> dict:
    """Analyze paragraph structure patterns, return risk score and issues."""
    if len(paragraphs) < 3:
        return {"score": 0.0, "issues": []}

    issues = []

    # 1. Paragraph length variance — too uniform
    lengths = [p["char_count"] for p in paragraphs]
    if len(lengths) >= 3:
        try:
            mean_len = statistics.mean(lengths)
            cv = statistics.stdev(lengths) / mean_len if mean_len > 0 else 0
        except statistics.StatisticsError:
            cv = 0
        if cv < 0.25:
            issues.append({"type": "uniform_para_length", "detail": f"Paragraph length CV={cv:.2f}, paragraphs too uniform"})

    # 2. Paragraph opening pattern — same structure in each paragraph
    first_sentences = []
    for p in paragraphs:
        text = p["text"]
        first_sent = text[:min(30, len(text))]
        first_sentences.append(first_sent)

    if len(first_sentences) >= 3:
        # Check: first 3 words (space-separated) repetition
        prefixes = []
        for s in first_sentences:
            words = s.split()[:3]
            if len(words) >= 2:
                prefixes.append(" ".join(words).lower())
        if len(prefixes) >= 3:
            most_common = Counter(prefixes).most_common(1)
            if most_common and most_common[0][1] >= 3:
                issues.append({"type": "uniform_para_start", "detail": f"Paragraph opening pattern repeats: '{most_common[0][0]}...' appears {most_common[0][1]} times"})

    score = _calculate_score(issues)
    return {"score": score, "issues": issues}


def _calculate_score(issues: list) -> float:
    base = 0.0
    for issue in issues:
        if issue["type"] == "uniform_para_length":
            base += 0.3
        elif issue["type"] == "uniform_para_start":
            base += 0.3
    return min(base, 1.0)
