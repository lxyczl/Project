"""词汇分布分析维度（中文学术写作）。"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

# 中文 AI 高频连接词
AI_CONNECTORS = [
    "此外", "另外", "与此同时", "因此", "从而", "进而", "然而", "尽管如此",
    "不仅如此", "更重要的是", "值得注意的是", "综上所述", "总而言之",
    "换言之", "具体而言", "事实上", "实际上", "显然", "毫无疑问",
    "众所周知", "不难发现", "由此可知", "由此可见",
]

# 中文 AI 高频填充短语
FILLER_PHRASES = [
    "近年来", "随着", "在此基础上", "在此背景下", "在此过程中",
    "越来越多的研究表明", "大量研究表明", "相关研究表明",
    "具有重要意义", "发挥着重要作用", "扮演着重要角色",
    "取得了显著成效", "引起了广泛关注", "受到了越来越多的关注",
    "具有重要的理论意义和实践价值", "为提供了新的思路",
    "在方面具有重要意义", "对具有重要影响",
    "是当前研究的热点问题", "成为了研究热点",
]


def _tokenize_chinese(text: str) -> list[str]:
    """中文分词：优先 jieba，fallback 字符级。"""
    try:
        import jieba
        return [w for w in jieba.cut(text) if len(w.strip()) > 0 and not re.match(r'^[\s\W]+$', w)]
    except ImportError:
        return [c for c in text if '一' <= c <= '鿿']


def analyze_vocabulary(text: str, patterns: list = None) -> dict:
    """分析词汇分布，返回风险分和问题列表。"""
    if patterns is None:
        patterns = []
    issues = []

    # 1. CTTR — 词汇丰富度
    words = _tokenize_chinese(text)
    if len(words) > 10:
        cttr = len(set(words)) / (2 * len(words)) ** 0.5
        if cttr < 0.5:
            issues.append({
                "type": "low_ttr",
                "detail": f"词汇丰富度 CTTR={cttr:.2f}，偏低"
            })

    # 2. 连接词频率
    conn_count = sum(text.count(c) for c in AI_CONNECTORS)
    sentence_count = max(1, len(re.split(r'[。！？]', text)) - 1)
    if sentence_count > 0 and conn_count / sentence_count > 0.4:
        issues.append({
            "type": "connector_overuse",
            "detail": f"连接词频率 {conn_count}/{sentence_count}={conn_count/sentence_count:.1f}，偏高"
        })

    # 3. 套话检测
    cliche_matches = []
    for phrase in FILLER_PHRASES:
        if phrase in text:
            cliche_matches.append(phrase)

    # 模式库规则
    for pattern in patterns:
        if pattern.get("type") in ("cliche", "formal", "connector", "sentence_pattern"):
            match_str = pattern["match"]
            try:
                if re.search(match_str, text):
                    cliche_matches.append(match_str)
            except re.error:
                if match_str in text:
                    cliche_matches.append(match_str)

    if cliche_matches:
        unique = list(dict.fromkeys(cliche_matches))[:5]
        issues.append({
            "type": "cliche_detected",
            "detail": f"检测到套话：{', '.join(unique)}"
        })

    score = _calculate_score(issues, len(cliche_matches))
    return {"score": score, "issues": issues}


def _calculate_score(issues: list, cliche_count: int = 0) -> float:
    base = 0.0
    for issue in issues:
        t = issue["type"]
        if t == "low_ttr":
            base += 0.2
        elif t == "connector_overuse":
            base += 0.2
        elif t == "cliche_detected":
            base += min(0.1 + cliche_count * 0.05, 0.35)
    return min(base, 1.0)
