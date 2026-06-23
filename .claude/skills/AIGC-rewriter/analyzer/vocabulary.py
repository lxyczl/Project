"""Vocabulary distribution analysis dimension."""

import re
import math

# AI高频连接词
AI_CONNECTORS = [
    "however", "therefore", "furthermore", "moreover", "consequently",
    "nevertheless", "additionally", "thus", "hence", "likewise",
    "meanwhile", "subsequently", "accordingly", "conversely",
    "notwithstanding", "alternatively", "similarly", "specifically",
    "namely", "indeed",
]

# Pattern types for cliche detection
_PATTERN_TYPES = {"cliche", "formal", "connector", "sentence_pattern",
                  "english_pattern", "passive"}


def _tokenize(text: str) -> list[str]:
    """Tokenize English text. Try nltk first, fallback to regex."""
    try:
        import nltk
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt', quiet=True)
        try:
            nltk.data.find('tokenizers/punkt_tab')
        except LookupError:
            nltk.download('punkt_tab', quiet=True)
        return [w for w in nltk.word_tokenize(text) if w.strip()]
    except ImportError:
        # Fallback: regex tokenizer
        return re.findall(r"[a-zA-Z]+(?:'[a-z]+)?|\d+\.?\d*%?", text)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences by English punctuation."""
    pattern = r'[^.!?;]+[.!?;]?'
    sentences = re.findall(pattern, text)
    return [s.strip() for s in sentences if s.strip()]


def analyze_vocabulary(text: str, patterns: list, platform: str | None = None) -> dict:
    """Analyze vocabulary distribution, return risk score and issues.

    Args:
        text: Text to analyze.
        patterns: Pattern library rules.
        platform: Target detection platform (turnitin/gptzero), None = no weighting.
    """
    issues = []

    # 1. CTTR (Carroll's Corrected TTR) — vocabulary richness
    words = _tokenize(text)
    if len(words) > 5:
        ttr = len(set(words)) / len(words)
        cttr = ttr / math.sqrt(2 * len(words))
        if cttr < 0.5:
            issues.append({"type": "low_cttr", "detail": f"CTTR={cttr:.3f}, vocabulary richness low"})

    # 2. Connector frequency
    sentences = _split_sentences(text)
    conn_count = sum(1 for w in words if w.lower() in AI_CONNECTORS)
    sentence_count = max(len(sentences), 1)
    if conn_count / sentence_count > 0.5:
        issues.append({"type": "connector_overuse", "detail": f"Connector frequency {conn_count}/{sentence_count}, too high"})

    # 3. Cliche detection (rely on pattern library, with platform weighting)
    cliche_matches: list[tuple[str, float]] = []
    for pattern in patterns:
        if pattern.get("type") not in _PATTERN_TYPES:
            continue
        match_str = pattern.get("match", "")
        if not match_str:
            continue
        hit = False
        try:
            hit = bool(re.search(match_str, text, re.IGNORECASE))
        except re.error:
            hit = match_str.lower() in text.lower()
        if hit:
            weight = _get_platform_weight(pattern, platform)
            if weight > 0:
                cliche_matches.append((match_str, weight))

    if cliche_matches:
        cliche_matches.sort(key=lambda x: x[1], reverse=True)
        names = [m[0] for m in cliche_matches[:5]]
        issues.append({"type": "cliche_detected", "detail": f"AI cliche detected: {', '.join(names)}"})

    score = _calculate_score(issues, cliche_matches)
    return {"score": score, "issues": issues}


def _get_platform_weight(pattern: dict, platform: str | None) -> float:
    """Get pattern weight for specified platform."""
    if platform is None:
        return 1.0
    weights = pattern.get("platform_weight", {})
    return weights.get(platform, 0.5)


def _calculate_score(issues: list, cliche_matches: list | None = None) -> float:
    base = 0.0
    for issue in issues:
        if issue["type"] == "low_cttr":
            base += 0.2
        elif issue["type"] == "connector_overuse":
            base += 0.25
        elif issue["type"] == "cliche_detected":
            if cliche_matches:
                weighted_sum = sum(w for _, w in cliche_matches)
                base += min(0.15 + weighted_sum * 0.05, 0.35)
            else:
                base += 0.3
    return min(base, 1.0)
