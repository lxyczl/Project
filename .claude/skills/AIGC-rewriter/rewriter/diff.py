"""Diff report generation.

Generates Markdown table format diff for human review.
"""

from typing import List


def generate_diff_report(results: List[dict]) -> str:
    """Generate Markdown table format diff report.

    Args:
        results: List of rewrite result dicts, expected keys:
            - index: paragraph number
            - section_type: section type
            - original_risk: original risk score
            - rewritten_risk: rewritten risk score
            - original_text: original text (truncated for display)
            - rewritten_text: rewritten text (truncated for display)
            - suspects: list of verification suspect items

    Returns:
        str: Markdown table string. Empty string if no results.
    """
    if not results:
        return ""

    lines = [
        "| Para | Section | Orig Risk | New Risk | Original | Rewritten | Suspects |",
        "|------|---------|-----------|----------|----------|-----------|----------|",
    ]

    for r in results:
        index = r.get("index", "?")
        section = r.get("section_type", "body")
        orig_risk = r.get("original_risk", 0)
        new_risk = r.get("rewritten_risk", 0)

        original = r.get("original_text", "")
        if len(original) > 50:
            original = original[:50] + "..."

        rewritten = r.get("rewritten_text", "")
        if len(rewritten) > 50:
            rewritten = rewritten[:50] + "..."

        suspects = r.get("suspects", [])
        if suspects:
            suspect_str = "; ".join(s["detail"] for s in suspects[:2])
        else:
            suspect_str = "None"

        lines.append(
            f"| {index} | {section} | {orig_risk:.2f} | {new_risk:.2f} "
            f"| {original} | {rewritten} | {suspect_str} |"
        )

    return "\n".join(lines)
