"""Context window management.

Provides target paragraph and its surrounding context for rewriting.
"""

from typing import List


def build_context(paragraphs: List[dict], target_index: int, window: int = 2) -> dict:
    """Build context window for rewriting.

    Args:
        paragraphs: List of paragraph dicts, each must have "text" key.
        target_index: Index of target paragraph in list.
        window: Context window size, take window paragraphs before/after.

    Returns:
        dict: Context dict with before, after, target, target_section.

    Raises:
        IndexError: target_index out of range.
    """
    if not paragraphs:
        raise ValueError("Paragraph list cannot be empty")
    if target_index < 0 or target_index >= len(paragraphs):
        raise IndexError(
            f"target_index={target_index} out of range [0, {len(paragraphs) - 1}]"
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
