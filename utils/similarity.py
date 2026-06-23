"""
中文相似度计算模块
用于评估改写前后文本的相似度，支持句子级热点检测

从 paper-rewriter-zh 移植，适配 AIGC-rewriter-zh 架构
"""
import re
import warnings
from pathlib import Path

# 阈值常量（知网查重规则：连续13字相同算抄袭）
CONSECUTIVE_WARNING = 13   # 连续匹配警告阈值
CONSECUTIVE_CAUTION = 10   # 连续匹配注意阈值
TRIGRAM_CAUTION = 0.3      # 三元组重叠率注意阈值
UNIGRAM_CAUTION = 0.7      # 字重叠率注意阈值

# 精简停用词表（学术中文高频虚词）
# 仅用于 n-gram 重叠率计算，不用于连续匹配检测
STOPWORDS = {
    "的", "了", "在", "是", "和", "与", "及", "等", "对", "中",
    "为", "上", "下", "个", "之", "而", "则", "但", "又", "也",
    "都", "就", "不", "有", "这", "那", "被", "把", "将", "从",
    "到", "所", "以", "于", "其", "或", "者", "一", "二", "三",
    "能", "可", "会", "要", "做", "着", "过", "地", "得", "很",
}


def _filter_stopwords(tokens: list[str]) -> list[str]:
    """过滤停用词（仅用于 n-gram 重叠率计算）"""
    return [t for t in tokens if t not in STOPWORDS]


def _char_tokenize(text: str) -> list[str]:
    """将文本分词为汉字列表（按字分割）"""
    return re.findall(r'[一-鿿]|[0-9]+', text)


def tokenize(text: str, mode: str = "word") -> list[str]:
    """将文本分词。优先 jieba，fallback 到字符级。

    注意：此函数不过滤停用词——连续匹配检测需要保留所有字符。
    """
    if mode == "word":
        try:
            import jieba
            tokens = jieba.lcut(text)
            return [t for t in tokens if t.strip()]
        except ImportError:
            warnings.warn(
                "jieba 未安装，使用字符级分词。pip install jieba 可获得更精准的词级分词。",
                UserWarning,
            )
    return _char_tokenize(text)


def ngrams(tokens: list[str], n: int) -> list[tuple]:
    """生成 n-gram"""
    return [tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]


def find_longest_common_substring(original: str, rewritten: str) -> int:
    """使用动态规划计算最长公共子串长度（按 token 级别）"""
    orig_tokens = _char_tokenize(original)
    rewrite_tokens = _char_tokenize(rewritten)

    if not orig_tokens or not rewrite_tokens:
        return 0

    m, n = len(orig_tokens), len(rewrite_tokens)
    prev = [0] * (n + 1)
    max_len = 0

    for i in range(1, m + 1):
        curr = [0] * (n + 1)
        for j in range(1, n + 1):
            if orig_tokens[i - 1] == rewrite_tokens[j - 1]:
                curr[j] = prev[j - 1] + 1
                max_len = max(max_len, curr[j])
        prev = curr

    return max_len


def calculate_similarity(original: str, rewritten: str) -> dict:
    """
    计算两段文本的相似度

    返回:
        - unigram_overlap: 字/词级别的重叠率
        - bigram_overlap: 二元组重叠率
        - trigram_overlap: 三元组重叠率
        - max_consecutive: 最长连续匹配字数（始终字符级）
        - vocabulary_diversity: 词汇多样性分数
        - token_mode: 实际使用的分词模式 ("word" / "char")
        - content_word_overlap: 过滤停用词后的实词重叠率
    """
    orig_tokens = tokenize(original, mode="word")
    rewrite_tokens = tokenize(rewritten, mode="word")
    token_mode = "word"

    if len(orig_tokens) < 3 or len(rewrite_tokens) < 3:
        orig_tokens = _char_tokenize(original)
        rewrite_tokens = _char_tokenize(rewritten)
        token_mode = "char"

    orig_set = set(orig_tokens)
    rewrite_set = set(rewrite_tokens)
    unigram_overlap = len(orig_set & rewrite_set) / len(orig_set) if orig_set else 0

    orig_bigrams = set(ngrams(orig_tokens, 2))
    rewrite_bigrams = set(ngrams(rewrite_tokens, 2))
    bigram_overlap = len(orig_bigrams & rewrite_bigrams) / len(orig_bigrams) if orig_bigrams else 0

    orig_trigrams = set(ngrams(orig_tokens, 3))
    rewrite_trigrams = set(ngrams(rewrite_tokens, 3))
    trigram_overlap = len(orig_trigrams & rewrite_trigrams) / len(orig_trigrams) if orig_trigrams else 0

    max_consecutive = find_longest_common_substring(original, rewritten)

    vocabulary_diversity = len(rewrite_set) / len(rewrite_tokens) if rewrite_tokens else 0

    orig_content = _filter_stopwords(orig_tokens)
    rewrite_content = _filter_stopwords(rewrite_tokens)
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
        "original_char_count": len(_char_tokenize(original)),
        "rewritten_char_count": len(_char_tokenize(rewritten)),
        "token_mode": token_mode,
        "content_word_overlap": round(content_word_overlap, 3),
    }


def format_report(original: str, rewritten: str) -> str:
    """生成格式化的相似度报告"""
    metrics = calculate_similarity(original, rewritten)

    unigram_desc = "词级别的相似度" if metrics["token_mode"] == "word" else "字级别的相似度"

    if metrics["max_consecutive"] >= CONSECUTIVE_WARNING:
        assessment = "⚠️ **警告**: 存在超过13个连续字匹配，需要进一步改写"
    elif metrics["max_consecutive"] >= CONSECUTIVE_CAUTION:
        assessment = "⚠️ **注意**: 存在超过10个连续字匹配，建议调整"
    elif metrics["trigram_overlap"] > TRIGRAM_CAUTION:
        assessment = "⚠️ **注意**: 三元组重叠率较高，建议调整句子结构"
    elif metrics["unigram_overlap"] > UNIGRAM_CAUTION:
        assessment = "⚠️ **注意**: 字/词重叠率较高，建议增加同义词替换"
    else:
        assessment = "✅ **通过**: 相似度在可接受范围内"

    report = f"""
## 相似度分析报告

### 基本信息
- 原文字数: {metrics['original_char_count']}
- 改写字数: {metrics['rewritten_char_count']}
- 分词模式: {metrics['token_mode']}

### 相似度指标
| 指标 | 值 | 说明 |
|------|-----|------|
| 字/词重叠率 | {metrics['unigram_overlap']:.1%} | {unigram_desc} |
| 二元组重叠率 | {metrics['bigram_overlap']:.1%} | 连续两个 token 的相似度 |
| 三元组重叠率 | {metrics['trigram_overlap']:.1%} | 连续三个 token 的相似度 |
| 最长连续匹配 | {metrics['max_consecutive']} 字 | 改写后最多连续几个字与原文相同 |
| 词汇多样性 | {metrics['vocabulary_diversity']:.1%} | 独特 token 占比 |
| 实词重叠率 | {metrics['content_word_overlap']:.1%} | 过滤停用词后的重叠率 |

### 评估结果
{assessment}
"""
    return report


def _split_sentences(text: str) -> list[str]:
    """按句号/分号/问号/感叹号/换行分句，过滤空句。"""
    if not text or not text.strip():
        return []
    sentences = re.split(r'(?<=[。；？！\n])', text)
    return [s.strip() for s in sentences if s.strip()]


def find_sentence_level_matches(
    original: str,
    rewritten: str,
    threshold: float = 0.5,
) -> list[dict]:
    """
    逐句对比，返回相似度超过阈值的句子对。

    每个原句只匹配一个最相似的改写句（贪心匹配，避免重复）。
    返回按 similarity_score 降序排列。
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
    """找出所有超过指定长度的连续匹配"""
    orig_tokens = _char_tokenize(original)
    rewrite_tokens = _char_tokenize(rewritten)

    matches = []
    i = 0
    while i < len(orig_tokens):
        j = 0
        while j < len(rewrite_tokens):
            if orig_tokens[i] == rewrite_tokens[j]:
                length = 0
                while (i + length < len(orig_tokens) and
                       j + length < len(rewrite_tokens) and
                       orig_tokens[i + length] == rewrite_tokens[j + length]):
                    length += 1

                if length >= min_length:
                    matches.append({
                        "start_orig": i,
                        "start_rewrite": j,
                        "length": length,
                        "text": "".join(orig_tokens[i:i+length])
                    })
                j += length
            else:
                j += 1
        i += 1

    return matches


def suggest_techniques(metrics: dict) -> list[str]:
    """根据相似度指标推荐改写技巧（中文名称，与 SKILL.md 对齐）"""
    techniques = []
    mc = metrics.get("max_consecutive", 0)
    tri = metrics.get("trigram_overlap", 0)

    if mc >= 13:
        techniques.extend(["句式重构", "长句拆分", "主被动互换"])
    elif mc >= 10:
        techniques.extend(["句式重构", "同义词替换"])
    elif tri >= 0.25:
        techniques.extend(["同义词替换", "因果倒置", "条件重构"])
    else:
        techniques.extend(["同义词替换", "调整语序"])

    return techniques


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("用法: python similarity.py <原文文件> <改写文件>")
        sys.exit(1)

    original_file = Path(sys.argv[1])
    rewritten_file = Path(sys.argv[2])

    for f in (original_file, rewritten_file):
        if not f.exists():
            print(f"错误: 找不到文件 {f}")
            sys.exit(1)

    try:
        original = original_file.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        original = original_file.read_text(encoding='gbk')
    try:
        rewritten = rewritten_file.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        rewritten = rewritten_file.read_text(encoding='gbk')

    print(format_report(original, rewritten))

    matches = find_consecutive_matches(original, rewritten, min_length=CONSECUTIVE_WARNING)
    if matches:
        print("\n### 超过13个字的连续匹配")
        for i, match in enumerate(matches, 1):
            print(f"{i}. 位置 {match['start_orig']}: \"{match['text']}\" ({match['length']} 字)")
