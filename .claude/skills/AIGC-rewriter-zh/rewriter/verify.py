"""准确性验证。

检查改写结果是否保留了关键术语、数值，以及长度是否合理。
"""

import re
from typing import Set


def verify_accuracy(original: str, rewritten: str, protected_terms: Set[str]) -> dict:
    """验证改写结果的准确性。

    检查改写后是否丢失关键术语、数值，以及长度变化是否在合理范围内。

    Args:
        original: 原始文本。
        rewritten: 改写后的文本。
        protected_terms: 需要保护的专业术语集合。

    Returns:
        dict: 包含 is_safe (bool) 和 suspects (list) 的验证结果。
            suspects 中每项为 {"type": str, "detail": str, "severity": str}。
    """
    if not original or not rewritten:
        return {
            "is_safe": False,
            "suspects": [{
                "type": "empty_text",
                "detail": "原文或改写文本为空",
                "severity": "high",
            }],
        }

    suspects: list[dict] = []

    # 1. 检查术语是否被替换
    for term in protected_terms:
        if term in original and term not in rewritten:
            suspects.append({
                "type": "term_replaced",
                "detail": f"术语 '{term}' 在改写后消失",
                "severity": "high",
            })

    # 2. 检查数值变化
    original_numbers = set(re.findall(r'\d+\.?\d*%?', original))
    rewritten_numbers = set(re.findall(r'\d+\.?\d*%?', rewritten))
    lost_numbers = original_numbers - rewritten_numbers
    if lost_numbers:
        suspects.append({
            "type": "number_changed",
            "detail": f"数值变化: {', '.join(sorted(lost_numbers)[:3])}",
            "severity": "high",
        })

    # 3. 检查长度变化（过于激进的改写）
    len_ratio = len(rewritten) / max(len(original), 1)
    if len_ratio < 0.5 or len_ratio > 2.0:
        suspects.append({
            "type": "length_anomaly",
            "detail": f"改写后长度变化过大: {len_ratio:.1%}",
            "severity": "medium",
        })

    is_safe = all(s["severity"] != "high" for s in suspects)

    return {
        "is_safe": is_safe,
        "suspects": suspects,
    }
