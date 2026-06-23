"""
English similarity calculation module
Evaluates text similarity before/after rewriting, with sentence-level hotspot detection.

Adapted from AIGC-rewriter-zh for English (Turnitin/GPTZero rules).
"""
import re
import warnings
from pathlib import Path

# Threshold constants (Turnitin rule: 8 consecutive words = plagiarism)
CONSECUTIVE_WARNING = 8    # consecutive match warning threshold (words)
CONSECUTIVE_CAUTION = 5    # consecutive match caution threshold (words)
TRIGRAM_CAUTION = 0.3      # trigram overlap caution threshold
UNIGRAM_CAUTION = 0.7      # unigram overlap caution threshold

# Stopwords (English academic high-frequency function words)
# Only used for content_word_overlap, not for consecutive match detection
STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "must", "need", "dare",
    "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
    "from", "as", "into", "through", "during", "before", "after", "above",
    "below", "between", "out", "off", "over", "under", "again", "further",
    "then", "once",
}


def _filter_stopwords(tokens: list[str]) -> list[str]:
    """Filter stopwords (only for n-gram overlap calculation)."""
    return [t for t in tokens if t.lower() not in STOPWORDS]


def _word_tokenize(text: str) -> list[str]:
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
        warnings.warn(
            "nltk not installed, using regex tokenizer. pip install nltk for better tokenization.",
            UserWarning,
        )
        return re.findall(r"[a-zA-Z]+(?:'[a-z]+)?|\d+\.?\d*%?", text)


def ngrams(tokens: list[str], n: int) -> list[tuple]:
    """Generate n-grams."""
    return [tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]


def find_longest_common_substring(original: str, rewritten: str) -> int:
    """Find longest common substring length using DP (word level)."""
    orig_tokens = _word_tokenize(original)
    rewrite_tokens = _word_tokenize(rewritten)

    if not orig_tokens or not rewrite_tokens:
        return 0

    m, n = len(orig_tokens), len(rewrite_tokens)
    prev = [0] * (n + 1)
    max_len = 0

    for i in range(1, m + 1):
        curr = [0] * (n + 1)
        for j in range(1, n + 1):
            if orig_tokens[i - 1].lower() == rewrite_tokens[j - 1].lower():
                curr[j] = prev[j - 1] + 1
                max_len = max(max_len, curr[j])
        prev = curr

    return max_len


def calculate_similarity(original: str, rewritten: str) -> dict:
    """Calculate similarity metrics between two texts.

    Returns:
        - unigram_overlap: word-level overlap ratio
        - bigram_overlap: bigram overlap ratio
        - trigram_overlap: trigram overlap ratio
        - max_consecutive: longest consecutive match (words)
        - vocabulary_diversity: unique token ratio
        - token_mode: actual tokenization mode ("word" / "regex")
        - content_word_overlap: overlap ratio after filtering stopwords
    """
    orig_tokens = _word_tokenize(original)
    rewrite_tokens = _word_tokenize(rewritten)
    token_mode = "word"

    if len(orig_tokens) < 3 or len(rewrite_tokens) < 3:
        orig_tokens = re.findall(r"[a-zA-Z]+(?:'[a-z]+)?|\d+\.?\d*%?", original)
        rewrite_tokens = re.findall(r"[a-zA-Z]+(?:'[a-z]+)?|\d+\.?\d*%?", rewritten)
        token_mode = "regex"

    orig_set = set(t.lower() for t in orig_tokens)
    rewrite_set = set(t.lower() for t in rewrite_tokens)
    unigram_overlap = len(orig_set & rewrite_set) / len(orig_set) if orig_set else 0

    orig_bigrams = set(ngrams([t.lower() for t in orig_tokens], 2))
    rewrite_bigrams = set(ngrams([t.lower() for t in rewrite_tokens], 2))
    bigram_overlap = len(orig_bigrams & rewrite_bigrams) / len(orig_bigrams) if orig_bigrams else 0

    orig_trigrams = set(ngrams([t.lower() for t in orig_tokens], 3))
    rewrite_trigrams = set(ngrams([t.lower() for t in rewrite_tokens], 3))
    trigram_overlap = len(orig_trigrams & rewrite_trigrams) / len(orig_trigrams) if orig_trigrams else 0

    max_consecutive = find_longest_common_substring(original, rewritten)

    vocabulary_diversity = len(rewrite_set) / len(rewrite_tokens) if rewrite_tokens else 0

    orig_content = _filter_stopwords([t.lower() for t in orig_tokens])
    rewrite_content = _filter_stopwords([t.lower() for t in rewrite_tokens])
    orig_content_set = set(orig_content)
    rewrite_content_set = set(rewrite_content)
    content_word_overlap = (
        len(orig_content_set & rewrite_content_set) / len(orig_content_set)
        if orig_content_set else 0
    )

    return {
        "unigram_overlap": round(unigram_overlap, 3),
        "bigram_overlap": round(bigram_overlap, 3),
        "trigram_overlap": round(trigram_overlap, 3),
        "max_consecutive": max_consecutive,
        "vocabulary_diversity": round(vocabulary_diversity, 3),
        "original_word_count": len(orig_tokens),
        "rewritten_word_count": len(rewrite_tokens),
        "token_mode": token_mode,
        "content_word_overlap": round(content_word_overlap, 3),
    }


def format_report(original: str, rewritten: str) -> str:
    """Generate formatted similarity report."""
    metrics = calculate_similarity(original, rewritten)

    unigram_desc = "word-level similarity"

    if metrics["max_consecutive"] >= CONSECUTIVE_WARNING:
        assessment = "⚠️ **Warning**: Over 8 consecutive word matches found, further rewrite needed"
    elif metrics["max_consecutive"] >= CONSECUTIVE_CAUTION:
        assessment = "⚠️ **Caution**: Over 5 consecutive word matches found, adjustment recommended"
    elif metrics["trigram_overlap"] > TRIGRAM_CAUTION:
        assessment = "⚠️ **Caution**: High trigram overlap, sentence restructuring recommended"
    elif metrics["unigram_overlap"] > UNIGRAM_CAUTION:
        assessment = "⚠️ **Caution**: High word overlap, more synonym replacement recommended"
    else:
        assessment = "✅ **Pass**: Similarity within acceptable range"

    report = f"""
## Similarity Analysis Report

### Basic Info
- Original word count: {metrics['original_word_count']}
- Rewritten word count: {metrics['rewritten_word_count']}
- Tokenization mode: {metrics['token_mode']}

### Similarity Metrics
| Metric | Value | Description |
|--------|-------|-------------|
| Word overlap | {metrics['unigram_overlap']:.1%} | {unigram_desc} |
| Bigram overlap | {metrics['bigram_overlap']:.1%} | Consecutive two-token similarity |
| Trigram overlap | {metrics['trigram_overlap']:.1%} | Consecutive three-token similarity |
| Longest consecutive match | {metrics['max_consecutive']} words | Max consecutive words matching original |
| Vocabulary diversity | {metrics['vocabulary_diversity']:.1%} | Unique token ratio |
| Content word overlap | {metrics['content_word_overlap']:.1%} | Overlap after filtering stopwords |

### Assessment
{assessment}
"""
    return report


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences by English punctuation."""
    if not text or not text.strip():
        return []
    sentences = re.split(r'(?<=[.!?;\n])', text)
    return [s.strip() for s in sentences if s.strip()]


def find_sentence_level_matches(
    original: str,
    rewritten: str,
    threshold: float = 0.5,
) -> list[dict]:
    """Compare sentence by sentence, return pairs exceeding similarity threshold.

    Each original sentence matches at most one best rewritten sentence (greedy matching).
    Returns sorted by similarity_score descending.
    """
    orig_sentences = _split_sentences(original)
    rew_sentences = _split_sentences(rewritten)

    if not orig_sentences or not rew_sentences:
        return []

    matches = []
    used_rew = set()

    for orig_sent in orig_sentences:
        best_score = 0.0
        best_idx = -1
        best_metrics = None

        for j, rew_sent in enumerate(rew_sentences):
            if j in used_rew:
                continue
            metrics = calculate_similarity(orig_sent, rew_sent)
            score = metrics["unigram_overlap"]

            if score > best_score:
                best_score = score
                best_idx = j
                best_metrics = metrics

        if best_idx >= 0 and best_score >= threshold:
            used_rew.add(best_idx)
            matches.append({
                "original_sentence": orig_sent,
                "rewritten_sentence": rew_sentences[best_idx],
                "similarity_score": round(best_score, 3),
                "max_consecutive": best_metrics["max_consecutive"],
                "trigram_overlap": best_metrics["trigram_overlap"],
            })

    matches.sort(key=lambda x: x["similarity_score"], reverse=True)
    return matches


def find_consecutive_matches(
    original: str,
    rewritten: str,
    min_length: int = CONSECUTIVE_WARNING,
) -> list[dict]:
    """Find all consecutive matches exceeding specified length (word level)."""
    orig_tokens = _word_tokenize(original)
    rewrite_tokens = _word_tokenize(rewritten)

    matches = []
    i = 0
    while i < len(orig_tokens):
        j = 0
        while j < len(rewrite_tokens):
            if orig_tokens[i].lower() == rewrite_tokens[j].lower():
                length = 0
                while (i + length < len(orig_tokens) and
                       j + length < len(rewrite_tokens) and
                       orig_tokens[i + length].lower() == rewrite_tokens[j + length].lower()):
                    length += 1

                if length >= min_length:
                    matches.append({
                        "start_orig": i,
                        "start_rewrite": j,
                        "length": length,
                        "text": " ".join(orig_tokens[i:i+length])
                    })
                j += length
            else:
                j += 1
        i += 1

    return matches


def suggest_techniques(metrics: dict) -> list[str]:
    """Suggest rewrite techniques based on similarity metrics."""
    techniques = []
    mc = metrics.get("max_consecutive", 0)
    tri = metrics.get("trigram_overlap", 0)

    if mc >= 8:
        techniques.extend(["Restructure sentence", "Split long sentence", "Active/passive swap"])
    elif mc >= 5:
        techniques.extend(["Restructure sentence", "Synonym replacement"])
    elif tri >= 0.25:
        techniques.extend(["Synonym replacement", "Causal inversion", "Condition restructuring"])
    else:
        techniques.extend(["Synonym replacement", "Adjust word order"])

    return techniques


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python similarity.py <original_file> <rewritten_file>")
        sys.exit(1)

    original_file = Path(sys.argv[1])
    rewritten_file = Path(sys.argv[2])

    # Add parent directory to path for imports
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from utils.doc_parser import read_document

    try:
        original, _ = read_document(str(original_file))
        rewritten, _ = read_document(str(rewritten_file))
    except (FileNotFoundError, ValueError, ImportError) as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(format_report(original, rewritten))

    matches = find_consecutive_matches(original, rewritten, min_length=CONSECUTIVE_WARNING)
    if matches:
        print("\n### Consecutive matches over 8 words")
        for i, match in enumerate(matches, 1):
            print(f"{i}. Position {match['start_orig']}: \"{match['text']}\" ({match['length']} words)")
