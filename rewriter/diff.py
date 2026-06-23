"""Diff 报告生成。

将改写结果汇总为 Markdown 表格，便于人工审阅。
"""

from typing import List


def generate_diff_report(results: List[dict]) -> str:
    """生成 Markdown 表格格式的 diff 报告。

    Args:
        results: 改写结果列表，每项为 dict，预期包含以下键：
            - index: 段落编号
            - section_type: 章节类型
            - original_risk: 原文风险值
            - rewritten_risk: 改写后风险值
            - original_text: 原文（截断显示）
            - rewritten_text: 改写结果（截断显示）
            - suspects: 验证可疑项列表

    Returns:
        str: Markdown 表格字符串。无结果时返回空字符串。
    """
    if not results:
        return ""

    lines = [
        "| 段落 | 章节 | 原文风险 | 改写风险 | 原文 | 改写结果 | 可疑项 |",
        "|------|------|---------|---------|------|---------|--------|",
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
            suspect_str = "无"

        lines.append(
            f"| {index} | {section} | {orig_risk:.2f} | {new_risk:.2f} "
            f"| {original} | {rewritten} | {suspect_str} |"
        )

    return "\n".join(lines)
