"""
相似度计算脚本
评估改写前后文本的相似度，使用多种指标综合判断

指标体系:
  - LCS (Longest Common Subsequence): 捕捉词序，核心指标
  - N-gram precision (BLEU 风格): 衡量改写文本中有多少 n-gram 来自原文
  - N-gram recall: 衡量原文中有多少 n-gram 被保留在改写文本中
  - Consecutive match detection: 找出所有超长连续匹配（Turnitin 风格）
  - Composite score: 加权综合分，0-100，越低越好（低=改写充分）
"""
from pathlib import Path
import re


# ── 基础工具 ──────────────────────────────────────────────────────

import warnings


# 精简停用词表（学术英文高频虚词，约 60 个）
# 仅用于 n-gram 重叠率计算中的 content_word_overlap，不用于连续匹配检测
STOPWORDS = {
    "the", "a", "an", "of", "in", "to", "for", "with", "on", "at",
    "from", "by", "as", "is", "was", "are", "were", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "this", "that", "these",
    "those", "it", "its", "they", "their", "them", "he", "she", "his",
    "her", "we", "our", "you", "your", "not", "no", "but", "or", "and",
    "if", "then", "than", "so", "such", "which", "who", "whom", "what",
}


def _filter_stopwords(tokens: list[str]) -> list[str]:
    """过滤停用词，保留实词"""
    return [t for t in tokens if t not in STOPWORDS]


def tokenize(text: str, mode: str = "word") -> list[str]:
    """将文本分词。优先 nltk，fallback 到正则。

    Args:
        text: 输入文本
        mode: "word" 使用 nltk（fallback 正则），"regex" 强制使用正则

    Returns:
        分词结果列表
    """
    if mode == "word":
        try:
            from nltk import word_tokenize
            tokens = word_tokenize(text)
            return [t.lower() for t in tokens if t.isalpha() and len(t) > 1]
        except ImportError:
            warnings.warn(
                "nltk 未安装，降级到正则分词。安装 nltk 可获得更精准的分词: pip install nltk",
                UserWarning, stacklevel=2
            )
        # fallback 到正则时仍过滤单字符，保持 word 模式语义一致
        return [t for t in _regex_tokenize(text) if len(t) > 1]
    return _regex_tokenize(text)


def _regex_tokenize(text: str) -> list[str]:
    """正则分词（原有逻辑，保留作为 fallback）"""
    return re.findall(r'\b[a-z]+\b', text.lower())


def find_sentence_level_matches(
    original: str,
    rewritten: str,
    threshold: float = 0.5
) -> list[dict]:
    """
    逐句对比，返回相似度超过阈值的句子对。

    Args:
        original: 原文
        rewritten: 改写文本
        threshold: 相似度阈值（0-1）

    Returns:
        [{original_sentence, rewritten_sentence, similarity_score, max_consecutive, suggested_techniques}, ...]
    """
    # 导入分句函数
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from analyzer.syntax import split_sentences

    orig_sents = split_sentences(original)
    rew_sents = split_sentences(rewritten)

    if not orig_sents or not rew_sents:
        return []

    matches = []
    used_rew = set()

    for orig_sent in orig_sents:
        best_score = 0.0
        best_rew_idx = -1
        tok_orig = tokenize(orig_sent)

        for j, rew_sent in enumerate(rew_sents):
            if j in used_rew:
                continue
            tok_rew = tokenize(rew_sent)
            if not tok_orig or not tok_rew:
                continue

            # 计算句子级 composite score（归一化到 0-1）
            lcs = lcs_ratio(tok_orig, tok_rew)
            tg_prec = ngram_precision(tok_orig, tok_rew, 3)
            bg_prec = ngram_precision(tok_orig, tok_rew, 2)
            vocab_ovl = vocabulary_overlap(tok_orig, tok_rew)
            consec = find_consecutive_matches(tok_orig, tok_rew, min_length=3)
            max_consec = max((m["length"] for m in consec), default=0)

            score = (
                lcs * 25 +
                tg_prec * 30 +
                bg_prec * 20 +
                vocab_ovl * 15 +
                min(max_consec / 10, 1.0) * 10
            ) / 100.0

            if score > best_score:
                best_score = score
                best_rew_idx = j

        if best_score >= threshold and best_rew_idx >= 0:
            used_rew.add(best_rew_idx)
            tok_orig = tokenize(orig_sent)
            tok_rew = tokenize(rew_sents[best_rew_idx])
            consec = find_consecutive_matches(tok_orig, tok_rew, min_length=3)
            max_consec = max((m["length"] for m in consec), default=0)

            # 推荐技巧
            tg = ngram_precision(tok_orig, tok_rew, 3)
            if max_consec >= 8:
                techniques = ["voice_conversion", "clause_insertion", "word_order_change"]
            elif max_consec >= 5:
                techniques = ["voice_conversion", "synonym_replacement"]
            elif tg >= 0.30:
                techniques = ["synonym_replacement", "word_order_change"]
            else:
                techniques = ["synonym_replacement"]

            matches.append({
                "original_sentence": orig_sent,
                "rewritten_sentence": rew_sents[best_rew_idx],
                "similarity_score": round(best_score, 3),
                "max_consecutive": max_consec,
                "suggested_techniques": techniques,
            })

    return matches


def ngrams(tokens: list[str], n: int) -> list[tuple]:
    """生成 n-gram"""
    return [tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]


# ── LCS（最长公共子序列）──────────────────────────────────────────

def lcs_length(a: list[str], b: list[str]) -> int:
    """计算两个 token 序列的最长公共子序列长度（空间优化版）"""
    if not a or not b:
        return 0
    m, n = len(a), len(b)
    # 只保留两行，节省内存
    prev = [0] * (n + 1)
    curr = [0] * (n + 1)
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i-1] == b[j-1]:
                curr[j] = prev[j-1] + 1
            else:
                curr[j] = max(prev[j], curr[j-1])
        prev, curr = curr, [0] * (n + 1)
    return prev[n]


def lcs_ratio(a: list[str], b: list[str]) -> float:
    """LCS 长度 / 较短序列长度，0-1"""
    if not a or not b:
        return 0.0
    return lcs_length(a, b) / min(len(a), len(b))


# ── N-gram 精度 & 召回 ────────────────────────────────────────────

def ngram_precision(tokens_orig: list[str], tokens_rew: list[str], n: int) -> float:
    """改写文本中有多少 n-gram 也出现在原文中（精度）"""
    ng_rew = ngrams(tokens_rew, n)
    if not ng_rew:
        return 0.0
    ng_orig = set(ngrams(tokens_orig, n))
    hits = sum(1 for ng in ng_rew if ng in ng_orig)
    return hits / len(ng_rew)


def ngram_recall(tokens_orig: list[str], tokens_rew: list[str], n: int) -> float:
    """原文中有多少 n-gram 被保留在改写文本中（召回）"""
    ng_orig = ngrams(tokens_orig, n)
    if not ng_orig:
        return 0.0
    ng_rew = set(ngrams(tokens_rew, n))
    hits = sum(1 for ng in ng_orig if ng in ng_rew)
    return hits / len(ng_orig)


# ── 连续匹配检测 ──────────────────────────────────────────────────

def find_consecutive_matches(
    tokens_orig: list[str],
    tokens_rew: list[str],
    min_length: int = 4
) -> list[dict]:
    """
    找出改写文本中所有与原文连续匹配 ≥ min_length 词的片段。
    使用滑动窗口在改写文本上扫描，对每个起点尝试在原文中找到对应位置。

    返回: [{start_orig, start_rewrite, length, text}, ...]
    """
    matches = []
    # 对改写文本的每个位置，尝试匹配原文中相同位置的子串
    # 更全面的做法：对原文每个起点 × 改写每个起点，但 O(n²) 太慢
    # 折中：用 set 快速过滤，再精确匹配
    orig_set = set(tokens_orig)

    i = 0
    while i < len(tokens_rew):
        # 只在改写文本的 token 也出现在原文中时才尝试匹配
        if tokens_rew[i] not in orig_set:
            i += 1
            continue

        # 在原文中找所有可能的起点
        for j in range(len(tokens_orig)):
            if tokens_orig[j] != tokens_rew[i]:
                continue
            # 从 (j, i) 开始延伸
            length = 0
            while (j + length < len(tokens_orig) and
                   i + length < len(tokens_rew) and
                   tokens_orig[j + length] == tokens_rew[i + length]):
                length += 1

            if length >= min_length:
                matches.append({
                    "start_orig": j,
                    "start_rewrite": i,
                    "length": length,
                    "text": " ".join(tokens_orig[j:j+length])
                })
                # 跳过已匹配的部分，避免重复报告
                i += length - 1
                break
        i += 1

    # 去重：如果一个匹配被另一个完全包含，只保留较长的
    matches = _remove_subsumed(matches)
    return sorted(matches, key=lambda m: m["length"], reverse=True)


def _remove_subsumed(matches: list[dict]) -> list[dict]:
    """移除被更长匹配包含的短匹配"""
    if not matches:
        return matches
    # 按长度降序
    matches.sort(key=lambda m: m["length"], reverse=True)
    kept = []
    for m in matches:
        # 检查是否被已有匹配包含
        subsumed = False
        for k in kept:
            if (k["start_orig"] <= m["start_orig"] and
                k["start_orig"] + k["length"] >= m["start_orig"] + m["length"] and
                k["start_rewrite"] <= m["start_rewrite"] and
                k["start_rewrite"] + k["length"] >= m["start_rewrite"] + m["length"]):
                subsumed = True
                break
        if not subsumed:
            kept.append(m)
    return kept


# ── 词汇重叠（Jaccard，保留用于快速筛选）──────────────────────────

def vocabulary_overlap(tokens_orig: list[str], tokens_rew: list[str]) -> float:
    """词汇级别的 Jaccard 重叠率"""
    set_orig = set(tokens_orig)
    set_rew = set(tokens_rew)
    if not set_orig or not set_rew:
        return 0.0
    return len(set_orig & set_rew) / len(set_orig | set_rew)


# ── 综合评分 ──────────────────────────────────────────────────────

def calculate_similarity(original: str, rewritten: str) -> dict:
    """
    计算两段文本的综合相似度。

    返回:
        composite_score: 0-100 综合分，越低 = 改写越充分
        lcs_ratio: LCS 相似度 (0-1)
        bigram_precision / bigram_recall: 二元组精度/召回
        trigram_precision / trigram_recall: 三元组精度/召回
        vocabulary_overlap: 词汇 Jaccard 重叠 (0-1)
        max_consecutive: 最长连续匹配词数
        consecutive_matches: 所有超长连续匹配详情
        original_word_count / rewritten_word_count: 词数
    """
    # 尝试词级分词
    tok_orig = tokenize(original, mode="word")
    tok_rew = tokenize(rewritten, mode="word")
    token_mode = "word"

    # 如果词级分词结果太少（<3 个 token），降级到正则
    if len(tok_orig) < 3 or len(tok_rew) < 3:
        tok_orig = _regex_tokenize(original)
        tok_rew = _regex_tokenize(rewritten)
        token_mode = "regex"

    # LCS
    lcs = lcs_ratio(tok_orig, tok_rew)

    # N-gram precision & recall
    bg_prec = ngram_precision(tok_orig, tok_rew, 2)
    bg_rec = ngram_recall(tok_orig, tok_rew, 2)
    tg_prec = ngram_precision(tok_orig, tok_rew, 3)
    tg_rec = ngram_recall(tok_orig, tok_rew, 3)

    # 词汇重叠
    vocab_ovl = vocabulary_overlap(tok_orig, tok_rew)

    # 实词重叠（过滤停用词后）
    content_orig = _filter_stopwords(tok_orig)
    content_rew = _filter_stopwords(tok_rew)
    content_ovl = vocabulary_overlap(content_orig, content_rew) if content_orig and content_rew else 0.0

    # 连续匹配
    consec = find_consecutive_matches(tok_orig, tok_rew, min_length=4)
    max_consec = max((m["length"] for m in consec), default=0)

    # 综合评分（加权）
    # 权重设计：LCS 和 trigram precision 是最能反映 Turnitin 检测结果的指标
    composite = (
        lcs * 25 +                   # 词序保留程度
        tg_prec * 30 +               # 三元组精度（Turnitin 核心）
        bg_prec * 20 +               # 二元组精度
        vocab_ovl * 15 +             # 词汇重叠
        min(max_consec / 10, 1.0) * 10  # 连续匹配惩罚（10 词封顶）
    )
    composite = round(min(100, composite), 1)

    return {
        "composite_score": composite,
        "lcs_ratio": round(lcs, 3),
        "bigram_precision": round(bg_prec, 3),
        "bigram_recall": round(bg_rec, 3),
        "trigram_precision": round(tg_prec, 3),
        "trigram_recall": round(tg_rec, 3),
        "vocabulary_overlap": round(vocab_ovl, 3),
        "max_consecutive": max_consec,
        "consecutive_matches": consec,
        "original_word_count": len(tok_orig),
        "rewritten_word_count": len(tok_rew),
        "token_mode": token_mode,
        "content_word_overlap": round(content_ovl, 3),
    }


# ── 报告格式化 ────────────────────────────────────────────────────

def format_report(original: str, rewritten: str) -> str:
    """生成格式化的相似度报告"""
    m = calculate_similarity(original, rewritten)

    # 评估结果
    if m["max_consecutive"] >= 8:
        assessment = "⚠️ **警告**: 存在 ≥8 词连续匹配，Turnitin 几乎必定标红，必须改写"
    elif m["max_consecutive"] >= 5:
        assessment = "⚠️ **注意**: 存在 ≥5 词连续匹配，有被标红风险"
    elif m["trigram_precision"] > 0.3:
        assessment = "⚠️ **注意**: 三元组精度偏高，建议调整句子结构"
    elif m["composite_score"] > 60:
        assessment = "⚠️ **注意**: 综合相似度偏高，建议进一步改写"
    else:
        assessment = "✅ **通过**: 相似度在可接受范围内"

    # 连续匹配详情
    consec_section = ""
    if m["consecutive_matches"]:
        consec_section = "\n### 超长连续匹配（≥4 词）\n\n"
        for i, match in enumerate(m["consecutive_matches"], 1):
            consec_section += (
                f"{i}. 原文位置 {match['start_orig']}, "
                f"改写位置 {match['start_rewrite']}: "
                f"\"{match['text']}\"（{match['length']} 词）\n"
            )
    else:
        consec_section = "\n✅ 无超长连续匹配\n"

    return f"""## 相似度分析报告

### 基本信息
- 原文词数: {m['original_word_count']}
- 改写词数: {m['rewritten_word_count']}

### 综合评分
| 指标 | 值 | 说明 |
|------|-----|------|
| **综合分** | **{m['composite_score']}** | 0-100，越低改写越充分 |
| LCS 比率 | {m['lcs_ratio']:.1%} | 词序保留程度 |
| 二元组精度 | {m['bigram_precision']:.1%} | 改写文本中来自原文的 bigram 比例 |
| 二元组召回 | {m['bigram_recall']:.1%} | 原文中被保留的 bigram 比例 |
| 三元组精度 | {m['trigram_precision']:.1%} | 改写文本中来自原文的 trigram 比例 |
| 三元组召回 | {m['trigram_recall']:.1%} | 原文中被保留的 trigram 比例 |
| 词汇重叠 | {m['vocabulary_overlap']:.1%} | Jaccard 重叠率 |
| 最长连续匹配 | {m['max_consecutive']} 词 | 超过 4 词即有标红风险 |

### 评估结果
{assessment}
{consec_section}"""


