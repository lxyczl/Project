"""中文特化分析维度。"""

import re


def analyze_chinese(text: str) -> dict:
    """分析中文 AIGC 特征，返回风险分和问题列表。"""
    issues = []
    char_count = len(text)

    if char_count < 50:
        return {"score": 0.0, "issues": []}

    # 1. "了"字集中度
    le_count = text.count("了")
    le_density = le_count / char_count
    if le_density > 0.03:  # 每 100 字超过 3 个"了"
        issues.append({"type": "excessive_le", "detail": f"'了'字密度 {le_density:.3f} ({le_count} 次/{char_count} 字)，偏高"})

    # 2. "的"字冗余嵌套
    de_nesting = len(re.findall(r'的[^。，！？；\n]{0,8}的[^。，！？；\n]{0,8}的', text))
    if de_nesting > 2:
        issues.append({"type": "de_nesting", "detail": f"检测到 {de_nesting} 处'的'字三层以上嵌套"})

    # 3. 四字成语密度
    idiom_pattern = r'[一-鿿]{4}'
    four_char_groups = re.findall(idiom_pattern, text)
    # 简化：用常见成语后缀检测
    idiom_suffixes = ["不可", "有所", "日益", "层出不穷", "举足轻重", "息息相关", "不可否认", "不容忽视"]
    idiom_count = sum(1 for g in four_char_groups if any(s in g for s in idiom_suffixes))
    if len(four_char_groups) > 0 and idiom_count / len(four_char_groups) > 0.1:
        issues.append({"type": "idiom_overuse", "detail": f"四字表达密度偏高: {idiom_count}/{len(four_char_groups)}"})

    # 4. "被…所…"频率
    bei_suo = len(re.findall(r'被[^。，！？]{0,20}所', text))
    if bei_suo > 2:
        issues.append({"type": "bei_suo_pattern", "detail": f"'被…所…'句式出现 {bei_suo} 次"})

    score = _calculate_score(issues)
    return {"score": score, "issues": issues}


def _calculate_score(issues: list) -> float:
    base = 0.0
    for issue in issues:
        if issue["type"] == "excessive_le":
            base += 0.2
        elif issue["type"] == "de_nesting":
            base += 0.2
        elif issue["type"] == "idiom_overuse":
            base += 0.2
        elif issue["type"] == "bei_suo_pattern":
            base += 0.15
    return min(base, 1.0)
