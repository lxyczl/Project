"""AI trace detection dimension."""

import re


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences by English punctuation."""
    pattern = r'[^.!?;]+[.!?;]?'
    sentences = re.findall(pattern, text)
    return [s.strip() for s in sentences if s.strip()]


def analyze_ai_traces(text: str, section_type: str = "body") -> dict:
    """Detect AI generation traces, return risk score and issues."""
    issues = []
    sentences = _split_sentences(text)

    # 1. Too fluent — lack of informal markers
    # AI text tends to be perfectly formed, missing ellipses, em dashes, etc.
    informal_markers = len(re.findall(r'[—–()…:;]', text))
    if len(sentences) > 5 and informal_markers / len(sentences) < 0.1:
        issues.append({"type": "too_fluent", "detail": f"Very few informal markers ({informal_markers}/{len(sentences)}), writing too polished"})

    # 2. Low burstiness — sentence length variation
    if len(sentences) >= 5:
        # Word-level sentence lengths
        lengths = [len(re.findall(r"[a-zA-Z]+(?:'[a-z]+)?|\d+\.?\d*%?", s)) for s in sentences]
        consecutive_similar = 0
        max_consecutive = 0
        for i in range(1, len(lengths)):
            if abs(lengths[i] - lengths[i-1]) < 5:
                consecutive_similar += 1
                max_consecutive = max(max_consecutive, consecutive_similar)
            else:
                consecutive_similar = 0

        if max_consecutive >= 3:
            issues.append({"type": "low_burstiness", "detail": f"{max_consecutive + 1} consecutive sentences with similar length, lacking variation"})

    # 3. No personal voice — lack of subjective markers
    # English personal markers
    personal_patterns = [
        r'\bI\s+(?:argue|contend|believe|suggest|maintain|assert)\b',
        r'\b[Ww]e\s+(?:found|observed|noted|discovered|showed)\b',
        r'\b[Ii]n\s+our\s+view\b',
        r'\b[Ff]rom\s+my\s+perspective\b',
        r'\b[Nn]otably\b',
        r'\b[Ii]nterestingly\b',
        r'\b[Ss]urprisingly\b',
        r'\b[Ii]t\s+is\s+worth\s+noting\s+that\b',
    ]
    personal_count = sum(len(re.findall(p, text)) for p in personal_patterns)

    # Discipline-aware: STEM fields traditionally avoid first person
    # STEM sections require 12+ sentences with zero markers to trigger
    # Non-STEM sections require 8+ sentences with zero markers
    stem_sections = {"method", "results"}
    threshold_sentences = 12 if section_type in stem_sections else 8
    if len(sentences) > threshold_sentences and personal_count == 0:
        issues.append({"type": "no_personal_voice", "detail": "Lack of personal expression markers"})

    score = _calculate_score(issues)
    return {"score": score, "issues": issues}


def _calculate_score(issues: list) -> float:
    base = 0.0
    for issue in issues:
        if issue["type"] == "too_fluent":
            base += 0.2
        elif issue["type"] == "low_burstiness":
            base += 0.25
        elif issue["type"] == "no_personal_voice":
            base += 0.1
    return min(base, 1.0)
