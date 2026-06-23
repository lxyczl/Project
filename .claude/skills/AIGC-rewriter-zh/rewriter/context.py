"""上下文窗口管理。

为改写任务提供目标段落及其上下文，帮助改写模型理解语境。
"""

from typing import List


def build_context(paragraphs: List[dict], target_index: int, window: int = 2) -> dict:
    """构建改写所需的上下文窗口。

    Args:
        paragraphs: 段落列表，每项为 dict，至少包含 "text" 键。
        target_index: 目标段落在列表中的索引。
        window: 上下文窗口大小，向前/向后各取 window 个段落。

    Returns:
        dict: 包含 before、after、target、target_section 的上下文字典。

    Raises:
        IndexError: target_index 超出段落列表范围。
    """
    if not paragraphs:
        raise ValueError("段落列表不能为空")
    if target_index < 0 or target_index >= len(paragraphs):
        raise IndexError(
            f"target_index={target_index} 超出范围 [0, {len(paragraphs) - 1}]"
        )

    before = paragraphs[max(0, target_index - window):target_index]
    after = paragraphs[target_index + 1:target_index + 1 + window]
    target = paragraphs[target_index]

    return {
        "before": [p["text"] for p in before],
        "after": [p["text"] for p in after],
        "target": target["text"],
        "target_section": target.get("section_type", "body"),
    }
