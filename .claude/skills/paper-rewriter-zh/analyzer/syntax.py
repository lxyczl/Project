"""句法特征分析维度（中文学术写作）。"""
import re
import statistics


def split_sentences(text: str) -> list[str]:
    """中文分句：按句号/问号/感叹号/分号切分。"""
    raw = re.split(r'[。！？；\n]', text)
    return [s.strip() for s in raw if s.strip() and len(s.strip()) > 5]


def analyze_syntax(text: str) -> dict:
    """分析句法特征，返回风险分和问题列表。"""
    sentences = split_sentences(text)
    if len(sentences) < 2:
        return {"score": 0.0, "issues": []}

    issues = []

    # 1. 句长方差 — 过于均匀 = 高风险（用字数）
    lengths = [len(s) for s in sentences]
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
                    "detail": f"句长变异系数 CV={cv:.2f}，过于均匀"
                })

    # 2. 被动语态频率 — 中文被动标记：被/受/遭/为...所/由...来
    passive_patterns = [
        r'被\S{1,6}(?:了|过|着)?',
        r'受到\S{1,6}(?:的)?',
        r'遭到\S{1,6}(?:的)?',
        r'为\S{1,4}所\S{1,4}',
        r'由\S{1,6}(?:来|进行|完成|实现)',
    ]
    passive_count = sum(len(re.findall(p, text)) for p in passive_patterns)
    if len(sentences) > 3 and passive_count / len(sentences) > 0.6:
        issues.append({
            "type": "excessive_passive",
            "detail": f"被动语态比例 {passive_count}/{len(sentences)}={passive_count/len(sentences):.0%}，偏高"
        })

    # 3. 并列结构频率 — AI 喜欢大量顿号并列
    parallel_markers = len(re.findall(r'[一-鿿]、[一-鿿]、[一-鿿]', text))
    if parallel_markers > len(sentences) * 0.4:
        issues.append({
            "type": "excessive_parallelism",
            "detail": f"并列结构过多：{parallel_markers} 处"
        })

    # 4. 的字嵌套深度 — 连续多个"的"字修饰
    deep_nested = len(re.findall(r'[一-鿿]{2,}的[一-鿿]{2,}的[一-鿿]{2,}', text))
    if deep_nested > 0:
        issues.append({
            "type": "deep_nesting",
            "detail": f"检测到 {deep_nested} 处深层'的'字嵌套"
        })

    score = _calculate_score(issues)
    return {"score": score, "issues": issues}


def _calculate_score(issues: list) -> float:
    base = 0.0
    for issue in issues:
        t = issue["type"]
        if t == "uniform_sentence_length":
            base += 0.25
        elif t == "excessive_passive":
            base += 0.2
        elif t == "excessive_parallelism":
            base += 0.2
        elif t == "deep_nesting":
            base += 0.15
    return min(base, 1.0)
