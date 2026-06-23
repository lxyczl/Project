"""English-specific analysis dimension.

Replaces chinese.py from the Chinese version.
Detects: excessive passive voice, nominalization overuse, hedging overuse.
"""

import re

# Irregular past participles (common in academic writing)
_IRREGULAR_PAST_PARTICIPLES = {
    "shown", "given", "taken", "made", "known", "found", "considered", "used",
    "required", "determined", "observed", "reported", "proposed", "suggested",
    "demonstrated", "established", "applied", "analyzed", "presented", "described",
    "performed", "conducted", "obtained", "based", "related", "involved", "defined",
    "characterized", "recognized", "attributed", "assumed", "expected", "indicated",
    "revealed", "confirmed", "identified", "evaluated", "assessed", "measured",
    "calculated", "estimated", "compared", "combined", "derived", "formulated",
    "implemented", "utilized", "incorporated", "adapted", "modified", "adjusted",
    "transformed", "converted", "extracted", "detected", "isolated", "purified",
    "synthesized", "generated", "produced", "constructed", "assembled", "configured",
    "optimized", "validated", "verified", "tested", "examined", "investigated",
    "explored", "studied", "achieved", "acquired", "addressed", "adopted",
    "affected", "allowed", "approved", "associated", "attempted", "authorized",
    "claimed", "classified", "collected", "committed", "completed", "concluded",
    "connected", "consisted", "contained", "continued", "controlled", "corrected",
    "covered", "created", "decreased", "delivered", "denied", "derived",
    "designed", "destroyed", "developed", "directed", "discovered", "distributed",
    "documented", "dominated", "eliminated", "enabled", "encouraged", "enforced",
    "engaged", "ensured", "entered", "equipped", "established", "exceeded",
    "excluded", "exhibited", "expanded", "experienced", "explained", "expressed",
    "extended", "facilitated", "failed", "focused", "followed", "forbidden",
    "forced", "formed", "guaranteed", "handled", "illustrated", "included",
    "increased", "influenced", "informed", "inspired", "instructed", "intended",
    "introduced", "invented", "joined", "judged", "justified", "launched",
    "limited", "linked", "listed", "located", "maintained", "managed",
    "marked", "matched", "mentioned", "monitored", "moved", "needed",
    "noted", "obliged", "obtained", "offered", "opened", "operated",
    "ordered", "organized", "originated", "overcome", "owned", "perceived",
    "permitted", "placed", "planned", "pointed", "positioned", "predicted",
    "preferred", "prepared", "preserved", "prevented", "processed", "produced",
    "programmed", "promoted", "protected", "provided", "published", "pursued",
    "qualified", "raised", "reached", "received", "recognized", "recommended",
    "reduced", "referred", "refused", "regulated", "rejected", "released",
    "relied", "remained", "removed", "replaced", "represented", "requested",
    "required", "reserved", "resolved", "responded", "restored", "restricted",
    "retained", "revealed", "reviewed", "revised", "saved", "secured",
    "selected", "separated", "served", "settled", "shared", "shifted",
    "solved", "sought", "specified", "started", "stated", "stimulated",
    "strengthened", "structured", "submitted", "succeeded", "supported",
    "surrounded", "survived", "sustained", "targeted", "tended", "threatened",
    "tolerated", "tracked", "transferred", "transmitted", "treated",
    "triggered", "unified", "updated", "used", "viewed", "violated",
    "welcomed", "withdrawn", "withstood",
}

# Academic standard passive expressions (not counted as excessive passive)
_PASSIVE_EXCEPTIONS = [
    r"as\s+shown\s+in",
    r"as\s+illustrated\s+in",
    r"as\s+presented\s+in",
    r"as\s+demonstrated\s+by",
    r"is\s+given\s+by",
    r"is\s+defined\s+as",
    r"is\s+denoted\s+by",
    r"are\s+listed\s+in",
    r"is\s+summarized\s+in",
    r"is\s+defined\s+as\s+follows",
]

# Nominalization suffixes
_NOMINALIZATION_SUFFIXES = [
    "tion", "sion", "ment", "ness", "ity", "ance", "ence", "ism", "ist",
    "ive", "ize", "ify",
]

# Common exceptions that shouldn't count as nominalizations
_NOMINALIZATION_EXCEPTIONS = {
    "nation", "condition", "information", "education", "situation",
    "position", "production", "direction", "attention", "action",
    "decision", "section", "collection", "connection", "protection",
    "election", "function", "question", "position", "generation",
}

# Hedging markers
_HEDGING_MARKERS = [
    r"it\s+seems\s+that",
    r"\barguably\b",
    r"\bperhaps\b",
    r"it\s+is\s+possible\s+that",
    r"to\s+some\s+extent",
    r"one\s+might\s+argue",
    r"it\s+could\s+be\s+said",
    r"there\s+is\s+a\s+tendency\s+to",
    r"it\s+is\s+generally\s+accepted\s+that",
    r"it\s+is\s+widely\s+believed\s+that",
    r"more\s+or\s+less",
    r"in\s+a\s+sense",
    r"up\s+to\s+a\s+point",
    r"to\s+a\s+certain\s+degree",
]


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


def analyze_english(text: str, section_type: str = "body") -> dict:
    """Analyze English-specific AIGC features, return risk score and issues."""
    issues = []

    words = _tokenize(text)
    word_count = len(words)
    if word_count < 20:
        return {"score": 0.0, "issues": []}

    sentences = _split_sentences(text)
    sentence_count = max(len(sentences), 1)

    # 1. Excessive passive voice
    passive_count = _count_passive_voice(text, words)
    passive_ratio = passive_count / sentence_count if sentence_count > 0 else 0

    # Dynamic threshold by section
    passive_threshold = {
        "method": 0.50,
        "results": 0.40,
    }.get(section_type, 0.30)

    if passive_ratio > passive_threshold:
        issues.append({
            "type": "excessive_passive",
            "detail": f"Passive voice ratio {passive_ratio:.0%} ({passive_count}/{sentence_count}), exceeds {passive_threshold:.0%} threshold"
        })

    # 2. Nominalization overuse
    nominal_count = _count_nominalizations(words)
    nominal_ratio = nominal_count / word_count if word_count > 0 else 0
    if nominal_ratio > 0.15:
        issues.append({
            "type": "nominalization_overuse",
            "detail": f"Nominalization ratio {nominal_ratio:.1%} ({nominal_count}/{word_count}), too high"
        })

    # 3. Hedging overuse
    hedging_count = sum(len(re.findall(m, text, re.IGNORECASE)) for m in _HEDGING_MARKERS)
    hedging_ratio = hedging_count / sentence_count if sentence_count > 0 else 0
    if hedging_ratio > 0.3:
        issues.append({
            "type": "hedging_overuse",
            "detail": f"Hedging marker ratio {hedging_ratio:.1%} ({hedging_count}/{sentence_count}), too high"
        })

    score = _calculate_score(issues)
    return {"score": score, "issues": issues}


def _count_passive_voice(text: str, words: list[str]) -> int:
    """Count passive voice constructions.

    Detection: is/are/was/were/be/been/being + past participle (VBN)
    Also: get/got + past participle
    """
    # Use nltk pos_tag if available for accurate VBN detection
    try:
        import nltk
        # Ensure required nltk data is available
        try:
            nltk.data.find('taggers/averaged_perceptron_tagger_eng')
        except LookupError:
            try:
                nltk.download('averaged_perceptron_tagger_eng', quiet=True)
            except Exception:
                nltk.download('averaged_perceptron_tagger', quiet=True)
        tagged = nltk.pos_tag(words)
        passive_count = 0
        be_forms = {"is", "are", "was", "were", "be", "been", "being"}
        get_forms = {"get", "gets", "got", "getting"}

        for i in range(1, len(tagged)):
            word_lower = tagged[i][0].lower()
            prev_lower = tagged[i-1][0].lower()
            pos = tagged[i][1]

            # be + VBN
            if prev_lower in be_forms and pos == "VBN":
                # Check exceptions using wider context window (up to 5 words back)
                context_start = max(0, i - 4)
                context = " ".join(t[0].lower() for t in tagged[context_start:i+1])
                if not any(re.search(exc, context) for exc in _PASSIVE_EXCEPTIONS):
                    passive_count += 1
            # get/got + VBN
            elif prev_lower in get_forms and pos == "VBN":
                passive_count += 1

        return passive_count
    except ImportError:
        # Fallback: heuristic detection
        be_pattern = r'\b(?:is|are|was|were|be|been|being)\s+(\w+(?:ed|en|wn|nt|pt|lt|ft))\b'
        matches = re.findall(be_pattern, text, re.IGNORECASE)
        passive_count = sum(1 for m in matches if m.lower() in _IRREGULAR_PAST_PARTICIPLES or m.endswith("ed"))
        # Filter exceptions
        for exc in _PASSIVE_EXCEPTIONS:
            passive_count -= len(re.findall(exc, text, re.IGNORECASE))
        return max(passive_count, 0)


def _count_nominalizations(words: list[str]) -> int:
    """Count nominalization suffixes, excluding common exceptions."""
    count = 0
    for word in words:
        word_lower = word.lower()
        if word_lower in _NOMINALIZATION_EXCEPTIONS:
            continue
        for suffix in _NOMINALIZATION_SUFFIXES:
            if word_lower.endswith(suffix) and len(word_lower) > len(suffix) + 2:
                count += 1
                break
    return count


def _calculate_score(issues: list) -> float:
    base = 0.0
    for issue in issues:
        if issue["type"] == "excessive_passive":
            base += 0.2
        elif issue["type"] == "nominalization_overuse":
            base += 0.2
        elif issue["type"] == "hedging_overuse":
            base += 0.15
    return min(base, 1.0)
