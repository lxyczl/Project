"""Accuracy verification.

Checks whether rewrite preserves key terms, numbers, and reasonable length.
"""

import re
from typing import Set


def verify_accuracy(original: str, rewritten: str, protected_terms: Set[str]) -> dict:
    """Verify rewrite accuracy.

    Checks for lost key terms, numbers, and reasonable length change.

    Args:
        original: Original text.
        rewritten: Rewritten text.
        protected_terms: Set of protected professional terms.

    Returns:
        dict: Contains is_safe (bool) and suspects (list).
            Each suspect: {"type": str, "detail": str, "severity": str}.
    """
    if not original or not rewritten:
        return {
            "is_safe": False,
            "suspects": [{
                "type": "empty_text",
                "detail": "Original or rewritten text is empty",
                "severity": "high",
            }],
        }

    suspects: list[dict] = []

    # 1. Check if terms were replaced
    for term in protected_terms:
        if term in original and term not in rewritten:
            suspects.append({
                "type": "term_replaced",
                "detail": f"Term '{term}' disappeared after rewrite",
                "severity": "high",
            })

    # 2. Check number changes
    original_numbers = set(re.findall(r'\d+\.?\d*%?', original))
    rewritten_numbers = set(re.findall(r'\d+\.?\d*%?', rewritten))
    lost_numbers = original_numbers - rewritten_numbers
    if lost_numbers:
        suspects.append({
            "type": "number_changed",
            "detail": f"Numbers changed: {', '.join(sorted(lost_numbers)[:3])}",
            "severity": "high",
        })

    # 3. Check length change (overly aggressive rewrite)
    len_ratio = len(rewritten) / max(len(original), 1)
    if len_ratio < 0.5 or len_ratio > 2.0:
        suspects.append({
            "type": "length_anomaly",
            "detail": f"Length change too large: {len_ratio:.1%}",
            "severity": "medium",
        })

    is_safe = all(s["severity"] != "high" for s in suspects)

    return {
        "is_safe": is_safe,
        "suspects": suspects,
    }
