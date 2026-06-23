"""英文学术写作特有特征分析。"""

import re


def analyze_english(text: str) -> dict:
    """分析英文学术写作特有特征，返回风险分和问题列表。"""
    issues = []
    text_lower = text.lower()
    words = text.split()
    word_count = len(words)

    if word_count < 20:
        return {"score": 0.0, "issues": []}

    # 1. 冠词过度使用 — "the" 占比过高
    the_count = len(re.findall(r'\bthe\b', text_lower))
    the_ratio = the_count / word_count
    if the_ratio > 0.12:
        issues.append({
            "type": "excessive_the",
            "detail": f"'the' ratio={the_ratio:.1%}, overuse detected"
        })

    # 2. 模糊限定词过多 — may/might/could/possibly 频率
    hedging_words = re.findall(r'\b(?:may|might|could|possibly|potentially|arguably|perhaps|somewhat)\b', text_lower)
    if len(hedging_words) / max(1, word_count / 100) > 3:
        issues.append({
            "type": "excessive_hedging",
            "detail": f"Hedging words: {len(hedging_words)} instances, too many"
        })

    # 3. 名词化过度 — -tion/-ment/-ness/-ity 后缀密度
    nominalizations = re.findall(r'\b\w{3,}(?:tion|ment|ness|ity|ence|ance)s?\b', text_lower)
    NOM_EXCEPTIONS = {
        "nation", "attention", "mention", "condition", "position",
        "question", "section", "action", "relation", "information",
        "station", "situation", "direction", "collection", "connection",
        "election", "protection", "production", "reduction", "education",
        "government", "environment", "development", "management", "movement",
        "statement", "agreement", "requirement", "treatment", "assessment"
    }
    nominalizations = [w for w in nominalizations if w not in NOM_EXCEPTIONS]
    nom_ratio = len(nominalizations) / word_count
    if nom_ratio > 0.08:
        issues.append({
            "type": "excessive_nominalization",
            "detail": f"Nominalization ratio={nom_ratio:.1%}, text is overly nominal"
        })

    # 4. 学术套话密度 — "in order to", "due to the fact that" 等冗长短语
    verbose_phrases = [
        "in order to", "due to the fact that", "in the event that",
        "for the purpose of", "in the process of", "at this point in time",
        "in spite of the fact", "on the basis of", "in the vicinity of",
        "with respect to", "in accordance with", "with the exception of",
    ]
    verbose_count = sum(1 for p in verbose_phrases if p in text_lower)
    if verbose_count >= 3:
        issues.append({
            "type": "verbose_phrases",
            "detail": f"Verbose phrases detected: {verbose_count} instances"
        })

    # 5. 段首句模式单调 — 连续 "The" / "In" / "It" 开头
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    if len(sentences) >= 4:
        first_words = [s.split()[0] if s.split() else "" for s in sentences[:8]]
        the_in_it = sum(1 for w in first_words if w.lower() in ("the", "in", "it", "this", "these"))
        if the_in_it / len(first_words) > 0.7:
            issues.append({
                "type": "monotonous_para_start",
                "detail": f"{the_in_it}/{len(first_words)} sentences start with The/In/It/This"
            })

    score = _calculate_score(issues)
    return {"score": score, "issues": issues}


def _calculate_score(issues: list) -> float:
    base = 0.0
    for issue in issues:
        if issue["type"] == "excessive_the":
            base += 0.15
        elif issue["type"] == "excessive_hedging":
            base += 0.15
        elif issue["type"] == "excessive_nominalization":
            base += 0.2
        elif issue["type"] == "verbose_phrases":
            base += 0.2
        elif issue["type"] == "monotonous_para_start":
            base += 0.15
    return min(base, 1.0)
