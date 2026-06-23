"""句法特征分析维度（英文学术写作）。"""

import re
import statistics


ABBREVIATIONS = {
    'dr', 'mr', 'mrs', 'ms', 'prof', 'sr', 'jr', 'vs', 'etc',
    'fig', 'tab', 'eq', 'ref', 'vol', 'no', 'pp', 'ed', 'est',
    'approx', 'dept', 'univ', 'inc', 'ltd', 'corp', 'govt',
    'u.s', 'u.k', 'e.g', 'i.e', 'al'
}


def _ends_with_abbreviation(text: str) -> bool:
    """检查文本是否以缩写结尾"""
    last_word = text.strip().split()[-1].rstrip('.').lower()
    return last_word in ABBREVIATIONS


def split_sentences(text: str) -> list[str]:
    """按句号/问号/感叹号分句（英文），排除缩写误切。"""
    raw = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    merged = []
    for sent in raw:
        if merged and _ends_with_abbreviation(merged[-1]):
            merged[-1] = merged[-1] + ' ' + sent
        else:
            merged.append(sent)
    return [s.strip() for s in merged if s.strip() and len(s.strip()) > 10]


def analyze_syntax(text: str) -> dict:
    """分析句法特征，返回风险分和问题列表。"""
    sentences = split_sentences(text)
    if len(sentences) < 2:
        return {"score": 0.0, "issues": []}

    issues = []

    # 1. 句长方差 — 过于均匀 = 高风险
    lengths = [len(s.split()) for s in sentences]
    if len(lengths) >= 3:
        mean_len = statistics.mean(lengths)
        if mean_len > 0:
            try:
                cv = statistics.stdev(lengths) / mean_len
            except statistics.StatisticsError:
                cv = 0
            if cv < 0.25:
                issues.append({
                    "type": "uniform_sentence_length",
                    "detail": f"Sentence length CV={cv:.2f}, too uniform"
                })

    # 2. 被动语态频率 — 过高 = AI 倾向
    IRREGULAR_PAST_PARTICIPLES = {
        "run", "put", "set", "cut", "make", "take", "come", "go",
        "give", "get", "show", "know", "think", "find", "say",
        "tell", "become", "leave", "bring", "build", "buy", "catch",
        "choose", "draw", "drive", "eat", "fall", "feel", "fight",
        "fly", "forget", "grow", "hang", "hear", "hide", "hold",
        "keep", "lead", "lend", "lose", "meet", "pay", "read",
        "ride", "ring", "rise", "send", "shake", "shoot", "shut",
        "sing", "sit", "sleep", "speak", "spend", "stand", "steal",
        "strike", "swim", "teach", "throw", "wake", "wear", "win", "write"
    }

    passive_patterns = [
        r'\b(?:is|are|was|were|been|being)\s+\w+(?:ed|en|t|wn)\b',
        r'\bget(?:s|ting)?\s+\w+ed\b',
    ]

    def _is_passive(match_text: str) -> bool:
        words = match_text.lower().split()
        if len(words) < 2:
            return False
        verb = words[-1]
        if re.search(r'(?:ed|en|t|wn)$', verb):
            return True
        if verb in IRREGULAR_PAST_PARTICIPLES:
            return True
        return False

    passive_count = 0
    for p in passive_patterns:
        for m in re.finditer(p, text):
            if _is_passive(m.group()):
                passive_count += 1

    if len(sentences) > 3 and passive_count / len(sentences) > 0.6:
        issues.append({
            "type": "excessive_passive",
            "detail": f"Passive voice ratio {passive_count}/{len(sentences)}={passive_count/len(sentences):.0%}, too high"
        })

    # 3. 并列结构频率 — AI 喜欢大量并列
    parallel_markers = len(re.findall(r',\s*\w+\s*,\s*\w+\s*,\s*\w+', text))
    if parallel_markers > len(sentences) * 0.4:
        issues.append({
            "type": "excessive_parallelism",
            "detail": f"Excessive parallel structures: {parallel_markers} instances"
        })

    # 4. 从句嵌套深度 — 过深 = 不自然
    # 检测连续多个从句标记
    deep_nested = len(re.findall(
        r'\b(?:which|that|who|whom|whose|where|when)\b[^.]{0,40}\b(?:which|that|who|whom|whose|where|when)\b',
        text
    ))
    if deep_nested > 0:
        issues.append({
            "type": "deep_nesting",
            "detail": f"Detected {deep_nested} deeply nested clauses"
        })

    score = _calculate_score(issues)
    return {"score": score, "issues": issues}


def _calculate_score(issues: list) -> float:
    base = 0.0
    for issue in issues:
        if issue["type"] == "uniform_sentence_length":
            base += 0.25
        elif issue["type"] == "excessive_passive":
            base += 0.2
        elif issue["type"] == "excessive_parallelism":
            base += 0.2
        elif issue["type"] == "deep_nesting":
            base += 0.15
    return min(base, 1.0)
