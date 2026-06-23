"""Syntax feature analysis dimension."""

import re
import statistics


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences by English punctuation."""
    pattern = r'[^.!?;]+[.!?;]?'
    sentences = re.findall(pattern, text)
    return [s.strip() for s in sentences if s.strip()]


def _tokenize(text: str) -> list[str]:
    """Tokenize English text."""
    try:
        import nltk
        return [w for w in nltk.word_tokenize(text) if w.strip()]
    except ImportError:
        return re.findall(r"[a-zA-Z]+(?:'[a-z]+)?|\d+\.?\d*%?", text)


def analyze_syntax(text: str) -> dict:
    """Analyze syntax features, return risk score and issues."""
    sentences = _split_sentences(text)
    if len(sentences) < 2:
        return {"score": 0.0, "issues": []}

    issues = []

    # 1. Sentence length variance — too uniform = high risk
    # Use word count per sentence
    lengths = [len(_tokenize(s)) for s in sentences]
    if len(lengths) >= 3:
        try:
            mean_len = statistics.mean(lengths)
            cv = statistics.stdev(lengths) / mean_len if mean_len > 0 else 0
        except statistics.StatisticsError:
            cv = 0
        # CV < 0.3 means sentence lengths too uniform
        if cv < 0.3:
            issues.append({"type": "uniform_sentence_length", "detail": f"Sentence length CV={cv:.2f}, too uniform"})

    # 2. Excessive parallelism — X, Y, and Z patterns
    parallel_markers = len(re.findall(r',\s*\w+(?:\s+\w+)*\s*,\s*(?:and|or)\s+', text, re.IGNORECASE))
    if parallel_markers > len(sentences) * 0.5:
        issues.append({"type": "excessive_parallelism", "detail": f"Excessive parallel structures: {parallel_markers} instances"})

    # 3. Deep nesting — that/which/who/whom clause nesting 3+ levels
    # Count occurrences of relative pronouns in the same sentence
    pronouns = r'\b(?:that|which|who|whom)\b'
    for sent in sentences:
        pronoun_count = len(re.findall(pronouns, sent, re.IGNORECASE))
        if pronoun_count >= 3:
            issues.append({"type": "deep_nesting", "detail": f"Detected clause with {pronoun_count} relative pronouns, likely deep nesting"})
            break  # One instance is enough

    score = _calculate_score(issues)
    return {"score": score, "issues": issues}


def _calculate_score(issues: list) -> float:
    base = 0.0
    for issue in issues:
        if issue["type"] == "uniform_sentence_length":
            base += 0.3
        elif issue["type"] == "excessive_parallelism":
            base += 0.2
        elif issue["type"] == "deep_nesting":
            base += 0.15
    return min(base, 1.0)
