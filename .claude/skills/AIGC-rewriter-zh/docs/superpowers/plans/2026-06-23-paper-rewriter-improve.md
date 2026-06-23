# paper-rewriter 全流程改进实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 提升英文版 paper-rewriter 的改写质量评估精度、增强反馈学习深度、建立分析到改写的结构化闭环、修复分析器已知 bug。

**Architecture:** 4 层改进——(1) 相似度计算升级（nltk 分词 + 句子级热点 + 停用词过滤），(2) 反馈学习深化（自动评估 + 失败分类 + 技巧组合 + 自适应学习率），(3) 分析→改写闭环（analyze_rewrite 扩展 + CLI analyze + SKILL.md 流程），(4) 分析器修复（被动语态 + CTTR + 名词化 + 分句）。

**Tech Stack:** Python 3.10+, pytest, nltk (optional, regex fallback), pathlib

## Global Constraints

- Python 路径：所有 Bash 中的 Python 调用必须用环境变量 `$PY`
- 注释和输出使用中文，变量/函数命名英文
- 路径处理必须用 `pathlib.Path`
- 向后兼容：所有已有接口不能 break，新增参数必须有默认值
- nltk 为可选依赖：未安装时自动降级到正则，打印 `UserWarning`
- Turnitin 阈值：连续匹配 ≥8 词 = fail，≥5 词 = warning；三元组精度 ≥0.30 = warning
- 测试目录：`E:\WorkSpace\Claude Code\.claude\skills\paper-rewriter\tests\`
- 脚本目录：`E:\WorkSpace\Claude Code\.claude\skills\paper-rewriter\scripts\`
- 分析器目录：`E:\WorkSpace\Claude Code\.claude\skills\paper-rewriter\analyzer\`

---

## 文件结构

```
paper-rewriter/
├── scripts/
│   ├── similarity_calculator.py   # 修改：tokenize 升级 + 句子级热点 + 停用词
│   ├── feedback_system.py         # 修改：auto_evaluate + classify_failure + 组合 + 自适应
│   └── rewrite_with_feedback.py   # 修改：返回值扩展 + CLI analyze
├── analyzer/
│   ├── syntax.py                  # 修改：被动语态增强 + 分句改进
│   ├── vocabulary.py              # 修改：CTTR 校正
│   ├── english.py                 # 修改：名词化修复
│   └── ai_traces.py               # 修改：导入 syntax.split_sentences
├── SKILL.md                       # 修改：流程更新（迭代闭环 + 章节阈值）
└── tests/
    ├── test_analyzer.py           # 修改：新增分析器测试
    ├── test_similarity.py         # 新建：相似度计算测试
    └── test_feedback_system.py    # 修改：新增反馈系统测试
```

---

### Task 1: Analyzer — 被动语态检测增强 + CTTR 校正

**Files:**
- Modify: `analyzer/syntax.py:40-49` — 被动语态检测逻辑
- Modify: `analyzer/vocabulary.py:47-55` — TTR → CTTR
- Modify: `tests/test_analyzer.py` — 新增测试

**Interfaces:**
- Produces: `split_sentences()` 行为不变（分句改进在 Task 3）；被动语态检测覆盖不规则动词；CTTR 替代 TTR

- [ ] **Step 1: 写被动语态增强的失败测试**

在 `tests/test_analyzer.py` 的 `TestSyntaxAnalyzer` 类末尾添加：

```python
def test_passive_irregular(self):
    """不规则被动语态应被检测到"""
    text = (
        "The data was run through the model. "
        "The results were put into the table. "
        "The values were set by the algorithm. "
        "The samples were cut into pieces."
    )
    result = analyze_syntax(text)
    types = {i["type"] for i in result["issues"]}
    assert "excessive_passive" in types
```

- [ ] **Step 2: 运行测试确认失败**

Run: `$PY -m pytest tests/test_analyzer.py::TestSyntaxAnalyzer::test_passive_irregular -v`
Expected: FAIL — 被动语态计数不足，未检测到 excessive_passive

- [ ] **Step 3: 实现被动语态增强**

修改 `analyzer/syntax.py`，将第 40-49 行替换为：

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `$PY -m pytest tests/test_analyzer.py::TestSyntaxAnalyzer::test_passive_irregular -v`
Expected: PASS

- [ ] **Step 5: 写 CTTR 的失败测试**

在 `tests/test_analyzer.py` 的 `TestVocabularyAnalyzer` 类末尾添加：

```python
def test_cttr_short_text_no_false_positive(self):
    """短文本不应因 TTR 低而误报"""
    text = "The method is effective. The approach works well."
    result = analyze_vocabulary(text, [])
    types = {i["type"] for i in result["issues"]}
    assert "low_ttr" not in types
```

- [ ] **Step 6: 运行测试确认失败**

Run: `$PY -m pytest tests/test_analyzer.py::TestVocabularyAnalyzer::test_cttr_short_text_no_false_positive -v`
Expected: 可能 PASS（取决于文本长度），继续实现 CTTR

- [ ] **Step 7: 实现 CTTR 校正**

修改 `analyzer/vocabulary.py`，将第 47-55 行替换为：

```python
    # 1. CTTR (Corrected Type-Token Ratio) — 对文本长度不敏感的词汇丰富度
    words = tokenize(text)
    if len(words) > 10:
        cttr = len(set(words)) / (2 * len(words)) ** 0.5
        if cttr < 0.5:
            issues.append({
                "type": "low_ttr",
                "detail": f"Vocabulary richness CTTR={cttr:.2f}, too low"
            })
```

- [ ] **Step 8: 运行全部分析器测试确认无回归**

Run: `$PY -m pytest tests/test_analyzer.py -v`
Expected: 全部 PASS（含新增测试 + 原有测试）

- [ ] **Step 9: Commit**

```bash
git add analyzer/syntax.py analyzer/vocabulary.py tests/test_analyzer.py
git commit -m "fix: 被动语态检测增强（不规则动词）+ CTTR 长度校正"
```

---

### Task 2: Analyzer — 名词化修复 + 分句改进

**Files:**
- Modify: `analyzer/english.py:33-39` — 名词化 regex 修复
- Modify: `analyzer/syntax.py:7-13` — 分句改进（缩写排除）
- Modify: `analyzer/ai_traces.py:60-63` — 消除重复代码
- Modify: `tests/test_analyzer.py` — 新增测试

**Interfaces:**
- Produces: `split_sentences()` 现在正确处理缩写；`analyze_english()` 不再误报 "nation" 等词

- [ ] **Step 1: 写名词化修复的失败测试**

在 `tests/test_analyzer.py` 的 `TestEnglishAnalyzer` 类末尾添加：

```python
def test_nominalization_exceptions(self):
    """常见非名词化词不应被标记"""
    text = (
        "The nation faces a critical condition regarding its education system. "
        "The government's protection policy requires attention and direction. "
        "The situation at the station called for immediate action."
    )
    result = analyze_english(text)
    types = {i["type"] for i in result["issues"]}
    assert "excessive_nominalization" not in types
```

- [ ] **Step 2: 运行测试确认失败**

Run: `$PY -m pytest tests/test_analyzer.py::TestEnglishAnalyzer::test_nominalization_exceptions -v`
Expected: FAIL — "nation", "condition", "education" 等被误报为名词化

- [ ] **Step 3: 实现名词化修复**

修改 `analyzer/english.py`，将第 33-39 行替换为：

```python
    # 3. 名词化过度 — -tion/-ment/-ness/-ity 后缀密度
    nominalizations = re.findall(r'\b\w{3,}(?:tion|ment|ness|ity|ence|ance)s?\b', text_lower)
    NOM_EXCEPTIONS = {
        "nation", "attention", "mention", "condition", "position",
        "question", "section", "action", "relation", "information",
        "station", "situation", "direction", "collection", "connection",
        "election", "protection", "production", "reduction", "education",
        "government", "environment", "development", "management", "movement",
        "statement", "agreement", "requirement", "treatment", "assessment"
    }
    nominalizations = [w for w in nominalizations if w not in NOM_EXCEPTIONS]
    nom_ratio = len(nominalizations) / word_count
    if nom_ratio > 0.08:
        issues.append({
            "type": "excessive_nominalization",
            "detail": f"Nominalization ratio={nom_ratio:.1%}, text is overly nominal"
        })
```

- [ ] **Step 4: 运行名词化测试确认通过**

Run: `$PY -m pytest tests/test_analyzer.py::TestEnglishAnalyzer::test_nominalization_exceptions -v`
Expected: PASS

- [ ] **Step 5: 写分句改进的失败测试**

在 `tests/test_analyzer.py` 的 `TestSyntaxAnalyzer` 类末尾添加：

```python
def test_split_sentences_abbreviations(self):
    """缩写不应导致误切"""
    text = "Dr. Smith conducted the experiment. The results were promising. Prof. Johnson reviewed the paper."
    sentences = split_sentences(text)
    # "Dr. Smith conducted the experiment" 应为一句，不应被切开
    assert any("Dr. Smith" in s for s in sentences)
    assert any("Prof. Johnson" in s for s in sentences)
```

- [ ] **Step 6: 运行测试确认失败**

Run: `$PY -m pytest tests/test_analyzer.py::TestSyntaxAnalyzer::test_split_sentences_abbreviations -v`
Expected: FAIL — "Dr. Smith" 被切开

- [ ] **Step 7: 实现分句改进**

修改 `analyzer/syntax.py`，将第 7-13 行替换为：

```python
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
```

- [ ] **Step 8: 修改 ai_traces.py 消除重复代码**

修改 `analyzer/ai_traces.py`：
1. 在文件顶部添加导入：`from analyzer.syntax import split_sentences`
2. 删除第 60-63 行的 `_split_sentences` 函数
3. 将第 10 行的 `sentences = _split_sentences(text)` 改为 `sentences = split_sentences(text)`

注意：如果导入路径有问题（循环依赖等），保留 `_split_sentences` 但改为调用 `split_sentences`：

```python
# 替代方案：直接导入
from analyzer.syntax import split_sentences

# 在 analyze_ai_traces 中：
sentences = split_sentences(text)  # 替代 _split_sentences(text)

# 删除 _split_sentences 函数
```

- [ ] **Step 9: 运行全部分析器测试确认无回归**

Run: `$PY -m pytest tests/test_analyzer.py -v`
Expected: 全部 PASS

- [ ] **Step 10: Commit**

```bash
git add analyzer/english.py analyzer/syntax.py analyzer/ai_traces.py tests/test_analyzer.py
git commit -m "fix: 名词化误报修复（排除词表）+ 分句缩写排除 + 消除重复代码"
```

---

### Task 3: 相似度计算 — tokenize 升级 + 停用词

**Files:**
- Modify: `scripts/similarity_calculator.py:18-20` — tokenize 升级
- Create: `tests/test_similarity.py` — 新测试文件

**Interfaces:**
- Consumes: 无
- Produces: `tokenize(text, mode="word")` — 新签名，向后兼容；`STOPWORDS` 集合；`_filter_stopwords(tokens)` 函数

- [ ] **Step 1: 写 tokenize 升级的测试**

创建 `tests/test_similarity.py`：

```python
"""
相似度计算测试
"""
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestTokenize:
    """测试分词策略"""

    def test_tokenize_word_mode(self):
        """词级分词应返回词列表"""
        from similarity_calculator import tokenize
        result = tokenize("The results show that the method is effective", mode="word")
        assert len(result) > 0
        assert "the" in result
        assert "results" in result

    def test_tokenize_regex_mode(self):
        """正则分词应使用原有逻辑"""
        from similarity_calculator import tokenize
        result = tokenize("Hello, world! This is a test.", mode="regex")
        assert result == ["hello", "world", "this", "is", "a", "test"]

    def test_tokenize_default_is_word(self):
        """默认模式应为 word"""
        from similarity_calculator import tokenize
        result = tokenize("The method is effective")
        assert len(result) > 0

    def test_tokenize_backward_compat(self):
        """向后兼容：tokenize(text) 行为不变"""
        from similarity_calculator import tokenize
        result = tokenize("The results show that the method is effective")
        assert len(result) > 0
        assert "the" in result

    def test_tokenize_single_char_filtered(self):
        """单字符 token 应被过滤（word 模式）"""
        from similarity_calculator import tokenize
        result = tokenize("I am a student", mode="word")
        # "I" 和 "a" 是单字符，应被过滤
        assert "i" not in result or "a" not in result

    def test_tokenize_fallback_no_nltk(self):
        """nltk 不可用时应降级到正则"""
        from similarity_calculator import tokenize
        # 如果 nltk 未安装，word 模式应降级到正则
        result = tokenize("The method is effective", mode="word")
        assert len(result) > 0


class TestStopwords:
    """测试停用词过滤"""

    def test_filter_stopwords(self):
        """停用词应被过滤"""
        from similarity_calculator import _filter_stopwords
        tokens = ["the", "method", "is", "effective", "for", "this", "problem"]
        filtered = _filter_stopwords(tokens)
        assert "the" not in filtered
        assert "is" not in filtered
        assert "method" in filtered
        assert "effective" in filtered

    def test_filter_stopwords_empty(self):
        """空列表应返回空列表"""
        from similarity_calculator import _filter_stopwords
        assert _filter_stopwords([]) == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `$PY -m pytest tests/test_similarity.py -v`
Expected: FAIL — `tokenize` 不接受 `mode` 参数，`_filter_stopwords` 不存在

- [ ] **Step 3: 实现 tokenize 升级 + 停用词**

修改 `scripts/similarity_calculator.py`，将第 18-20 行替换为：

```python
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
    return _regex_tokenize(text)


def _regex_tokenize(text: str) -> list[str]:
    """正则分词（原有逻辑，保留作为 fallback）"""
    return re.findall(r'\b[a-z]+\b', text.lower())
```

- [ ] **Step 4: 运行测试确认通过**

Run: `$PY -m pytest tests/test_similarity.py -v`
Expected: PASS

- [ ] **Step 5: 运行原有测试确认无回归**

Run: `$PY -m pytest tests/test_basic.py::TestSimilarityCalculator -v`
Expected: PASS — 原有测试仍使用 `tokenize(text)` 签名，向后兼容

- [ ] **Step 6: Commit**

```bash
git add scripts/similarity_calculator.py tests/test_similarity.py
git commit -m "feat: tokenize 升级（nltk + fallback）+ 停用词过滤"
```

---

### Task 4: 相似度计算 — 句子级热点定位 + content_word_overlap

**Files:**
- Modify: `scripts/similarity_calculator.py` — 新增 `find_sentence_level_matches()` + `calculate_similarity()` 更新
- Modify: `tests/test_similarity.py` — 新增测试

**Interfaces:**
- Consumes: `tokenize()`, `_filter_stopwords()`, `split_sentences()` (from analyzer.syntax)
- Produces: `find_sentence_level_matches(original, rewritten, threshold=0.5) -> list[dict]`；`calculate_similarity()` 返回值新增 `token_mode`, `content_word_overlap`

- [ ] **Step 1: 写句子级热点的测试**

在 `tests/test_similarity.py` 末尾添加：

```python
class TestSentenceLevelMatches:
    """测试句子级热点定位"""

    def test_sentence_level_matches(self):
        """相似句子应被定位"""
        from similarity_calculator import find_sentence_level_matches
        orig = "The method is effective. The results show improvement. We analyzed the data."
        rew = "The approach is effective. The findings demonstrate improvement. The data was analyzed."
        matches = find_sentence_level_matches(orig, rew, threshold=0.3)
        assert len(matches) > 0
        assert "original_sentence" in matches[0]
        assert "rewritten_sentence" in matches[0]
        assert "similarity_score" in matches[0]

    def test_sentence_level_no_match(self):
        """完全不同的句子应返回空"""
        from similarity_calculator import find_sentence_level_matches
        orig = "The method is effective."
        rew = "An entirely different approach was utilized for this investigation."
        matches = find_sentence_level_matches(orig, rew, threshold=0.8)
        assert len(matches) == 0

    def test_sentence_level_suggested_techniques(self):
        """热点句子应推荐技巧"""
        from similarity_calculator import find_sentence_level_matches
        orig = "The results show that the method is effective for this problem"
        rew = "The results show that the method is effective for this issue"
        matches = find_sentence_level_matches(orig, rew, threshold=0.3)
        if matches:
            assert "suggested_techniques" in matches[0]


class TestContentWordOverlap:
    """测试实词重叠率"""

    def test_content_word_overlap(self):
        """停用词过滤后的实词重叠率应低于总重叠率"""
        from similarity_calculator import calculate_similarity
        orig = "The method is effective for this problem"
        rew = "The approach is useful for this issue"
        result = calculate_similarity(orig, rew)
        assert "content_word_overlap" in result
        assert "token_mode" in result
        assert result["content_word_overlap"] <= result["vocabulary_overlap"]

    def test_token_mode_field(self):
        """返回值应包含 token_mode"""
        from similarity_calculator import calculate_similarity
        result = calculate_similarity("The method is effective", "The approach works well")
        assert result["token_mode"] in ("word", "regex")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `$PY -m pytest tests/test_similarity.py::TestSentenceLevelMatches -v`
Expected: FAIL — `find_sentence_level_matches` 不存在

- [ ] **Step 3: 实现句子级热点定位**

在 `scripts/similarity_calculator.py` 的 `_filter_stopwords` 函数之后、`ngrams` 函数之前添加：

```python
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
```

- [ ] **Step 4: 更新 calculate_similarity() 返回值**

修改 `scripts/similarity_calculator.py` 的 `calculate_similarity` 函数：

1. 将第 180-181 行的分词逻辑替换为：

```python
    # 尝试词级分词
    tok_orig = tokenize(original, mode="word")
    tok_rew = tokenize(rewritten, mode="word")
    token_mode = "word"

    # 如果词级分词结果太少（<3 个 token），降级到正则
    if len(tok_orig) < 3 or len(tok_rew) < 3:
        tok_orig = _regex_tokenize(original)
        tok_rew = _regex_tokenize(rewritten)
        token_mode = "regex"
```

2. 在词汇重叠计算之后添加 content_word_overlap：

```python
    # 实词重叠（过滤停用词后）
    content_orig = _filter_stopwords(tok_orig)
    content_rew = _filter_stopwords(tok_rew)
    content_ovl = vocabulary_overlap(content_orig, content_rew) if content_orig and content_rew else 0.0
```

3. 在返回值字典中添加新字段：

```python
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
        "token_mode": token_mode,              # 新增
        "content_word_overlap": round(content_ovl, 3),  # 新增
    }
```

- [ ] **Step 5: 运行全部相似度测试**

Run: `$PY -m pytest tests/test_similarity.py tests/test_basic.py::TestSimilarityCalculator -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/similarity_calculator.py tests/test_similarity.py
git commit -m "feat: 句子级热点定位 + content_word_overlap 指标"
```

---

### Task 5: 反馈系统 — 自动评估 + 失败分类

**Files:**
- Modify: `scripts/feedback_system.py` — 新增 `auto_evaluate()`, `classify_failure()`, `_verdict_reason()`
- Modify: `tests/test_feedback_system.py` — 新增测试

**Interfaces:**
- Produces: `auto_evaluate(metrics) -> dict` 含 verdict/is_success/reason；`classify_failure(metrics, verdict) -> str`

- [ ] **Step 1: 写自动评估的测试**

在 `tests/test_feedback_system.py` 末尾添加：

```python
class TestAutoEvaluate:
    """测试自动评估"""

    def test_auto_evaluate_excellent(self):
        from feedback_system import auto_evaluate
        metrics = {"max_consecutive": 2, "trigram_precision": 0.05}
        result = auto_evaluate(metrics)
        assert result["verdict"] == "excellent"
        assert result["is_success"] is True

    def test_auto_evaluate_fail(self):
        from feedback_system import auto_evaluate
        metrics = {"max_consecutive": 10, "trigram_precision": 0.1}
        result = auto_evaluate(metrics)
        assert result["verdict"] == "fail"
        assert result["is_success"] is False

    def test_auto_evaluate_warning_mc(self):
        from feedback_system import auto_evaluate
        metrics = {"max_consecutive": 6, "trigram_precision": 0.1}
        result = auto_evaluate(metrics)
        assert result["verdict"] == "warning"

    def test_auto_evaluate_warning_tri(self):
        from feedback_system import auto_evaluate
        metrics = {"max_consecutive": 3, "trigram_precision": 0.35}
        result = auto_evaluate(metrics)
        assert result["verdict"] == "warning"

    def test_auto_evaluate_success(self):
        from feedback_system import auto_evaluate
        metrics = {"max_consecutive": 4, "trigram_precision": 0.20}
        result = auto_evaluate(metrics)
        assert result["verdict"] == "success"
        assert result["is_success"] is True


class TestClassifyFailure:
    """测试失败分类"""

    def test_classify_failure_consecutive(self):
        from feedback_system import classify_failure
        assert classify_failure({"max_consecutive": 10}, "fail") == "consecutive_too_long"

    def test_classify_failure_structure(self):
        from feedback_system import classify_failure
        assert classify_failure({"max_consecutive": 6, "trigram_precision": 0.28}, "warning") == "structure_too_similar"

    def test_classify_failure_consecutive_risk(self):
        from feedback_system import classify_failure
        assert classify_failure({"max_consecutive": 6, "trigram_precision": 0.1}, "warning") == "consecutive_risk"

    def test_classify_failure_trigram_risk(self):
        from feedback_system import classify_failure
        assert classify_failure({"max_consecutive": 3, "trigram_precision": 0.25}, "warning") == "trigram_risk"

    def test_classify_failure_none(self):
        from feedback_system import classify_failure
        assert classify_failure({}, "excellent") == "none"
        assert classify_failure({}, "success") == "none"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `$PY -m pytest tests/test_feedback_system.py::TestAutoEvaluate tests/test_feedback_system.py::TestClassifyFailure -v`
Expected: FAIL — `auto_evaluate` 和 `classify_failure` 不存在

- [ ] **Step 3: 实现自动评估 + 失败分类**

在 `scripts/feedback_system.py` 的 `class FeedbackSystem` 之前添加：

```python
def auto_evaluate(metrics: dict) -> dict:
    """基于客观指标自动判定成功/失败。Turnitin 比知网更敏感，阈值更严格。"""
    mc = metrics.get("max_consecutive", 0)
    tri = metrics.get("trigram_precision", 0)

    if mc >= 8:
        verdict = "fail"
    elif mc >= 5 or tri >= 0.30:
        verdict = "warning"
    elif tri < 0.15 and mc < 4:
        verdict = "excellent"
    else:
        verdict = "success"

    return {
        "verdict": verdict,
        "is_success": verdict in ("success", "excellent"),
        "max_consecutive": mc,
        "trigram_precision": tri,
        "reason": _verdict_reason(verdict, mc, tri),
    }


def _verdict_reason(verdict: str, mc: int, tri: float) -> str:
    """生成判定原因说明"""
    if verdict == "fail":
        return f"连续匹配 {mc} 词，超过 Turnitin 阈值（8 词）"
    elif verdict == "warning":
        if mc >= 5:
            return f"连续匹配 {mc} 词，接近阈值"
        return f"三元组精度 {tri:.1%}，句式相似度偏高"
    elif verdict == "excellent":
        return "改写充分，相似度低"
    return "可接受"


def classify_failure(metrics: dict, verdict: str) -> str:
    """根据指标和已有 verdict 细分失败原因。"""
    if verdict in ("excellent", "success"):
        return "none"

    mc = metrics.get("max_consecutive", 0)
    tri = metrics.get("trigram_precision", 0)

    if verdict == "fail":
        return "consecutive_too_long"
    elif verdict == "warning":
        if mc >= 5 and tri >= 0.25:
            return "structure_too_similar"
        elif mc >= 5:
            return "consecutive_risk"
        elif tri >= 0.20:
            return "trigram_risk"
        else:
            return "mixed_risk"
    return "none"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `$PY -m pytest tests/test_feedback_system.py::TestAutoEvaluate tests/test_feedback_system.py::TestClassifyFailure -v`
Expected: PASS

- [ ] **Step 5: 运行原有反馈测试确认无回归**

Run: `$PY -m pytest tests/test_feedback_system.py -v`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/feedback_system.py tests/test_feedback_system.py
git commit -m "feat: 自动评估 auto_evaluate + 失败分类 classify_failure"
```

---

### Task 6: 反馈系统 — 技巧组合学习 + 自适应学习率 + 建议映射

**Files:**
- Modify: `scripts/feedback_system.py` — 更新 `_load_strategies`, `_learn_from_feedback`, `get_rewrite_suggestions`
- Modify: `tests/test_feedback_system.py` — 新增测试

**Interfaces:**
- Produces: `get_rewrite_suggestions()` 新增 `targeted_advice`, `priority_techniques`, `effective_combinations` 字段
- strategies.json 新增 `technique_combinations` 字段

- [ ] **Step 1: 写技巧组合 + 自适应学习率 + 建议映射的测试**

在 `tests/test_feedback_system.py` 末尾添加：

```python
class TestTechniqueCombinations:
    """测试技巧组合学习"""

    def test_technique_combinations_recorded(self, tmp_path):
        """技巧组合应被记录"""
        system = FeedbackSystem(tmp_path)
        session = system.record_rewrite_session(
            original_text="The method is effective",
            rewritten_text="The approach demonstrates efficacy",
            domain="test",
            intensity="medium",
            changes_made=[
                {"type": "voice_conversion", "original": "We analyzed", "rewritten": "Analysis was performed"},
                {"type": "synonym_replacement", "original": "effective", "rewritten": "efficacious"},
            ]
        )
        system.collect_feedback(session["session_id"], overall_score=5)
        combos = system.strategies.get("technique_combinations", {})
        assert len(combos) > 0

    def test_effective_combinations_in_suggestions(self, tmp_path):
        """建议中应包含有效组合"""
        system = FeedbackSystem(tmp_path)
        # 模拟多次成功的组合
        system.strategies["technique_combinations"] = {
            "voice_conversion+synonym_replacement": {"success": 5, "total": 5}
        }
        suggestions = system.get_rewrite_suggestions("test", "medium")
        assert "effective_combinations" in suggestions
        assert len(suggestions["effective_combinations"]) > 0


class TestAdaptiveLearningRate:
    """测试自适应学习率"""

    def test_consecutive_failures_increase_step(self, tmp_path):
        """连续失败时步长应递增"""
        system = FeedbackSystem(tmp_path)
        adj = system.strategies["intensity_adjustments"]["medium"]
        # 模拟连续失败
        adj["consecutive_failures"] = 3
        adj["multiplier"] = 1.0
        system._save_strategies()

        # 触发学习
        session = system.record_rewrite_session("orig", "rew", "test", "medium")
        system.collect_feedback(session["session_id"], overall_score=1)

        new_adj = system.strategies["intensity_adjustments"]["medium"]
        # 步长应为 min(0.10, 0.05 + 3 * 0.01) = 0.08
        assert new_adj["multiplier"] > 1.0

    def test_success_resets_counters(self, tmp_path):
        """success 应重置连续计数器"""
        system = FeedbackSystem(tmp_path)
        adj = system.strategies["intensity_adjustments"]["medium"]
        adj["consecutive_failures"] = 3
        adj["consecutive_successes"] = 0
        adj["multiplier"] = 1.2
        system._save_strategies()

        session = system.record_rewrite_session("orig", "rew", "test", "medium")
        system.collect_feedback(session["session_id"], overall_score=4)  # avg=4 → success

        new_adj = system.strategies["intensity_adjustments"]["medium"]
        assert new_adj["consecutive_failures"] == 0
        assert new_adj["multiplier"] == 1.2  # 不变


class TestTargetedAdvice:
    """测试针对性建议"""

    def test_targeted_advice_high_mc(self, tmp_path):
        """高连续匹配应生成句式重组建议"""
        system = FeedbackSystem(tmp_path)
        suggestions = system.get_rewrite_suggestions("test", "medium", current_metrics={
            "max_consecutive": 10,
            "trigram_precision": 0.15
        })
        assert "targeted_advice" in suggestions
        assert "priority_techniques" in suggestions
        assert len(suggestions["targeted_advice"]) > 0
        assert len(suggestions["priority_techniques"]) > 0

    def test_targeted_advice_high_tri(self, tmp_path):
        """高三元组精度应生成结构调整建议"""
        system = FeedbackSystem(tmp_path)
        suggestions = system.get_rewrite_suggestions("test", "medium", current_metrics={
            "max_consecutive": 3,
            "trigram_precision": 0.25
        })
        assert len(suggestions["targeted_advice"]) > 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `$PY -m pytest tests/test_feedback_system.py::TestTechniqueCombinations tests/test_feedback_system.py::TestAdaptiveLearningRate tests/test_feedback_system.py::TestTargetedAdvice -v`
Expected: FAIL — `effective_combinations`, `targeted_advice` 等字段不存在

- [ ] **Step 3: 更新 _load_strategies 默认结构**

修改 `scripts/feedback_system.py` 的 `_load_strategies` 方法，在默认策略字典中添加：

```python
            "technique_combinations": {},  # 新增
```

并在 `intensity_adjustments` 的每个级别中添加计数器：

```python
            "intensity_adjustments": {
                "light": {"multiplier": 1.0, "consecutive_failures": 0, "consecutive_successes": 0},
                "medium": {"multiplier": 1.0, "consecutive_failures": 0, "consecutive_successes": 0},
                "heavy": {"multiplier": 1.0, "consecutive_failures": 0, "consecutive_successes": 0}
            },
```

- [ ] **Step 4: 更新 _learn_from_feedback — 技巧组合 + 自适应学习率**

修改 `_learn_from_feedback` 方法：

1. 在方法开头导入 auto_evaluate 和 classify_failure（已经在同一文件中，直接调用）
2. 在学习技术有效性（第 219-224 行）之后添加技巧组合学习：

```python
        # 3b. 学习技巧组合
        techniques_used = list(set(
            c.get("type", "synonym_replacement")
            for c in session.get("changes_made", [])
        ))
        if len(techniques_used) >= 2:
            from itertools import combinations
            for t1, t2 in combinations(sorted(techniques_used), 2):
                combo_key = f"{t1}+{t2}"
                if combo_key not in self.strategies["technique_combinations"]:
                    self.strategies["technique_combinations"][combo_key] = {"success": 0, "total": 0}
                self.strategies["technique_combinations"][combo_key]["total"] += 1
                if is_success:
                    self.strategies["technique_combinations"][combo_key]["success"] += 1
```

3. 替换强度调整逻辑（第 248-259 行）为自适应版本：

```python
        # 4. 自适应学习率
        adjustment = self.strategies["intensity_adjustments"][intensity]
        if "consecutive_failures" not in adjustment:
            adjustment["consecutive_failures"] = 0
        if "consecutive_successes" not in adjustment:
            adjustment["consecutive_successes"] = 0

        verdict = "success"  # 默认
        if session.get("metrics"):
            eval_result = auto_evaluate(session["metrics"])
            verdict = eval_result["verdict"]
            is_success = eval_result["is_success"]

        if not is_success:
            count = adjustment["consecutive_failures"]
            step = min(0.10, 0.05 + count * 0.01)
            adjustment["multiplier"] = min(1.5, adjustment["multiplier"] + step)
            adjustment["consecutive_failures"] = count + 1
            adjustment["consecutive_successes"] = 0
        elif verdict == "excellent":
            count = adjustment["consecutive_successes"]
            step = max(0.01, 0.02 - count * 0.003)
            adjustment["multiplier"] = max(0.5, adjustment["multiplier"] - step)
            adjustment["consecutive_successes"] = count + 1
            adjustment["consecutive_failures"] = 0
        else:  # success
            adjustment["consecutive_failures"] = 0
            adjustment["consecutive_successes"] = 0
```

4. 在记录问题模式时添加 failure_type：

```python
        # 5. 记录问题模式
        if avg_score < 3:
            failure_type = "none"
            if session.get("metrics"):
                eval_result = auto_evaluate(session["metrics"])
                failure_type = classify_failure(session["metrics"], eval_result["verdict"])
            self.strategies["problem_patterns"].append({
                "issue": feedback.get("improved", ""),
                "failure_type": failure_type,
                "domain": domain,
                "intensity": intensity,
                "max_consecutive": session.get("metrics", {}).get("max_consecutive", 0),
                "trigram_precision": session.get("metrics", {}).get("trigram_precision", 0),
                "timestamp": session.get("timestamp")
            })
```

- [ ] **Step 5: 更新 get_rewrite_suggestions — 建议映射 + 组合**

修改 `get_rewrite_suggestions` 方法：

1. 添加 `current_metrics` 参数：

```python
    def get_rewrite_suggestions(
        self,
        domain: str = "general",
        intensity: str = "medium",
        current_metrics: dict = None
    ) -> dict:
```

2. 在 suggestions 字典中添加新字段：

```python
        suggestions = {
            "preferred_vocabulary": [],
            "effective_techniques": [],
            "intensity_multiplier": 1.0,
            "domain_issues": [],
            "new_terms_to_preserve": [],
            "targeted_advice": [],          # 新增
            "priority_techniques": [],      # 新增
            "effective_combinations": [],   # 新增
        }
```

3. 在获取新术语之后添加建议映射逻辑：

```python
        # 6. 有效技巧组合
        for combo_key, data in self.strategies.get("technique_combinations", {}).items():
            if data["total"] >= 2:
                success_rate = data["success"] / data["total"]
                if success_rate >= 0.7:
                    suggestions["effective_combinations"].append({
                        "combination": combo_key,
                        "success_rate": round(success_rate, 2)
                    })

        # 7. 基于历史问题模式生成建议
        recent_problems = [
            p for p in self.strategies.get("problem_patterns", [])
            if p.get("domain") == domain
        ][-5:]

        failure_type_advice = {
            "consecutive_too_long": "该学科历史改写中多次出现超长连续匹配，建议优先使用 voice_conversion + clause_insertion",
            "structure_too_similar": "该学科历史改写中句式相似度偏高，建议加强结构调整",
            "consecutive_risk": "该学科历史改写中连续匹配接近阈值，建议增加句式变化",
            "trigram_risk": "该学科历史改写中三元组重叠率偏高，建议加强结构调整",
        }
        seen_types = set()
        for problem in recent_problems:
            ft = problem.get("failure_type", "")
            if ft in failure_type_advice and ft not in seen_types:
                suggestions["targeted_advice"].append(failure_type_advice[ft])
                seen_types.add(ft)

        # 8. 基于当前文本指标生成建议
        if current_metrics:
            mc = current_metrics.get("max_consecutive", 0)
            tri = current_metrics.get("trigram_precision", 0)

            if mc >= 8:
                suggestions["priority_techniques"] = ["voice_conversion", "clause_insertion", "word_order_change"]
                suggestions["targeted_advice"].append(
                    f"存在 {mc} 词连续匹配（超过 Turnitin 阈值），必须使用句式重组打破结构"
                )
            elif mc >= 5:
                suggestions["priority_techniques"] = ["voice_conversion", "synonym_replacement", "word_order_change"]
                suggestions["targeted_advice"].append(
                    f"连续匹配 {mc} 词，接近阈值，建议使用句式重组+同义词替换"
                )
            elif tri >= 0.20:
                suggestions["priority_techniques"] = ["synonym_replacement", "word_order_change"]
                suggestions["targeted_advice"].append(
                    f"三元组精度 {tri:.1%}，需要改变句子结构和用词"
                )
```

- [ ] **Step 6: 运行全部反馈测试**

Run: `$PY -m pytest tests/test_feedback_system.py -v`
Expected: 全部 PASS

- [ ] **Step 7: Commit**

```bash
git add scripts/feedback_system.py tests/test_feedback_system.py
git commit -m "feat: 技巧组合学习 + 自适应学习率 + 问题→建议映射"
```

---

### Task 7: rewrite_with_feedback — 返回值扩展 + CLI analyze

**Files:**
- Modify: `scripts/rewrite_with_feedback.py` — `analyze_rewrite()` 扩展 + CLI `analyze` 命令
- Modify: `tests/test_similarity.py` 或新建测试 — 集成测试

**Interfaces:**
- Consumes: `auto_evaluate()`, `classify_failure()`, `find_sentence_level_matches()` from earlier tasks
- Produces: `analyze_rewrite()` 返回值新增 `auto_evaluation`, `hot_sentences`, `needs_iteration`

- [ ] **Step 1: 写 analyze_rewrite 扩展的测试**

在 `tests/test_similarity.py` 末尾添加集成测试：

```python
class TestRewriteWithFeedbackIntegration:
    """测试改写分析集成"""

    def test_analyze_rewrite_extended_fields(self, tmp_path):
        """analyze_rewrite 应返回新增字段"""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from rewrite_with_feedback import RewriteWithFeedback

        r = RewriteWithFeedback(tmp_path)
        result = r.analyze_rewrite(
            original="The method is effective for this problem. The results show improvement.",
            rewritten="The approach is effective for this issue. The findings demonstrate improvement.",
            domain="test",
            intensity="medium"
        )
        assert "auto_evaluation" in result
        assert "hot_sentences" in result
        assert "needs_iteration" in result
        assert "verdict" in result["auto_evaluation"]

    def test_analyze_rewrite_needs_iteration_on_fail(self, tmp_path):
        """高相似度应触发迭代"""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from rewrite_with_feedback import RewriteWithFeedback

        r = RewriteWithFeedback(tmp_path)
        # 几乎相同的文本
        text = "The method is effective for this problem and shows good results"
        result = r.analyze_rewrite(
            original=text,
            rewritten=text,
            domain="test",
            intensity="medium"
        )
        assert result["needs_iteration"] is True
```

- [ ] **Step 2: 运行测试确认失败**

Run: `$PY -m pytest tests/test_similarity.py::TestRewriteWithFeedbackIntegration -v`
Expected: FAIL — `auto_evaluation` 等字段不存在

- [ ] **Step 3: 实现 analyze_rewrite 扩展**

修改 `scripts/rewrite_with_feedback.py`：

1. 更新导入（第 11 行）：

```python
from feedback_system import FeedbackSystem, auto_evaluate
from similarity_calculator import calculate_similarity, format_report, find_sentence_level_matches
```

2. 替换 `analyze_rewrite` 方法（第 23-60 行）：

```python
    def analyze_rewrite(
        self,
        original: str,
        rewritten: str,
        domain: str = "general",
        intensity: str = "medium",
        section_type: str = "unknown",
        changes_made: list = None
    ) -> dict:
        """
        分析改写结果并记录会话。

        返回:
            session_id, similarity, suggestions, composite_score, report,
            auto_evaluation, hot_sentences, needs_iteration
        """
        similarity = calculate_similarity(original, rewritten)

        session = self.feedback_system.record_rewrite_session(
            original_text=original,
            rewritten_text=rewritten,
            domain=domain,
            intensity=intensity,
            section_type=section_type,
            changes_made=changes_made
        )

        # 自动评估
        auto_evaluation = auto_evaluate(similarity)

        # 句子级热点
        hot_sentences = find_sentence_level_matches(original, rewritten, threshold=0.5)

        # 为每个热点句子推荐技巧
        for sent in hot_sentences:
            sent["suggested_techniques"] = self._suggest_techniques_for_sentence(sent)

        # 迭代判断
        needs_iteration = (
            auto_evaluation["verdict"] == "fail" or
            (auto_evaluation["verdict"] == "warning" and len(hot_sentences) > 0)
        )

        suggestions = self.feedback_system.get_rewrite_suggestions(
            domain, intensity, current_metrics=similarity
        )

        return {
            "session_id": session["session_id"],
            "similarity": similarity,
            "auto_evaluation": auto_evaluation,
            "suggestions": suggestions,
            "composite_score": similarity["composite_score"],
            "report": format_report(original, rewritten),
            "hot_sentences": hot_sentences,
            "needs_iteration": needs_iteration,
        }

    def _suggest_techniques_for_sentence(self, sentence_metrics: dict) -> list[str]:
        """根据句子级指标推荐技巧"""
        mc = sentence_metrics.get("max_consecutive", 0)
        tri = 0.0
        # 从 similarity_score 推算 trigram（简化处理）
        score = sentence_metrics.get("similarity_score", 0)

        if mc >= 8:
            return ["voice_conversion", "clause_insertion", "word_order_change"]
        elif mc >= 5:
            return ["voice_conversion", "synonym_replacement"]
        elif score >= 0.7:
            return ["synonym_replacement", "word_order_change"]
        else:
            return ["synonym_replacement"]
```

- [ ] **Step 4: 添加 CLI analyze 命令**

修改 `scripts/rewrite_with_feedback.py` 的 `__main__` 部分：

1. 更新 `_usage` 函数：

```python
    def _usage():
        print("用法:")
        print("  $PY rewrite_with_feedback.py analyze <原文文件> <改写文件> [domain] [intensity]")
        print("  $PY rewrite_with_feedback.py suggest [domain] [intensity]")
        print("  $PY rewrite_with_feedback.py feedback <session_id> <v> <s> <t> <o>")
        print("  $PY rewrite_with_feedback.py report")
        sys.exit(1)
```

2. 在 `cmd = sys.argv[1]` 之后、`if cmd == "suggest":` 之前添加 analyze 分支：

```python
    if cmd == "analyze":
        if len(sys.argv) < 4:
            _usage()
        orig_file = Path(sys.argv[2])
        rew_file = Path(sys.argv[3])
        domain = sys.argv[4] if len(sys.argv) > 4 else "general"
        intensity = sys.argv[5] if len(sys.argv) > 5 else "medium"

        original = orig_file.read_text(encoding="utf-8")
        rewritten = rew_file.read_text(encoding="utf-8")

        result = r.analyze_rewrite(original, rewritten, domain, intensity)
        print(json.dumps({
            "session_id": result["session_id"],
            "composite_score": result["composite_score"],
            "auto_evaluation": result["auto_evaluation"],
            "hot_sentences": result["hot_sentences"],
            "needs_iteration": result["needs_iteration"],
            "report": result["report"],
        }, ensure_ascii=False, indent=2))
```

- [ ] **Step 5: 运行测试**

Run: `$PY -m pytest tests/test_similarity.py::TestRewriteWithFeedbackIntegration tests/test_basic.py tests/test_feedback_system.py -v`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/rewrite_with_feedback.py tests/test_similarity.py
git commit -m "feat: analyze_rewrite 扩展（auto_evaluation + hot_sentences + needs_iteration）+ CLI analyze"
```

---

### Task 8: SKILL.md — 流程更新

**Files:**
- Modify: `SKILL.md` — 场景 1/2 流程更新 + 章节阈值 + report 升级

**Interfaces:**
- Consumes: `analyze` CLI 命令（Task 7），`needs_iteration` / `hot_sentences` 返回值

- [ ] **Step 1: 更新场景 1 流程（用户发文本）**

将 SKILL.md 第 14-37 行（场景 1）替换为：

```markdown
### 场景1：用户发文本
1. **分析风险**：运行 `$PY analyze.py --text "<原文>"` 获取风险评分和问题列表
   - 关注 `overall_risk`（0-1）和各段落的 `issues`（具体问题）
   - `suggestion` 字段给出改写建议
2. **获取历史建议**：运行 `$PY scripts/rewrite_with_feedback.py suggest <domain> <intensity>` 获取反馈学习建议
3. 扫描学科关键词 → 读取 `references/domains.md` 对应词汇
4. **针对性改写**：
   - 优先解决分析引擎指出的高风险问题（`priority` 最高的段落）
   - 应用反馈建议：优先使用 `effective_techniques`，保护 `new_terms_to_preserve`
   - 针对具体 issue 类型改写（见下方"风险类型与改写策略"）
5. **记录改动**：改写完成后，将每处改动记录为 `changes_made`（格式：`{"type": "技巧类型", "original": "原文片段", "rewritten": "改写片段"}`）
6. **分析结果**：运行以下 CLI 命令分析并记录会话：
   ```bash
   $PY scripts/rewrite_with_feedback.py analyze <原文文件> <改写文件> <学科> <强度>
   ```
   输出 JSON 包含：session_id, composite_score, auto_evaluation, hot_sentences, needs_iteration, report
7. **迭代验证**（自动）：
   - 如果 `needs_iteration` 为 true：
     a. 查看 `hot_sentences`，定位需要重点改写的句子
     b. 使用 `suggested_techniques` 针对性改写这些句子
     c. 再次运行 analyze 验证（最多 3 轮）
     d. 如果 3 轮后仍有 fail/warning：返回当前最佳结果，附带 warning 提示"以下句子仍需手动调整"并列出未解决的热点句子
8. 改写后主动询问满意度，收集反馈
```

- [ ] **Step 2: 更新场景 2 流程（用户给文件）**

将 SKILL.md 第 39-47 行（场景 2）替换为：

```markdown
### 场景2：用户给文件
1. 运行 `$PY scripts/document_parser.py <file> [section]` 提取文本
2. **分析风险**（同场景1步骤1）
3. **获取历史建议**（同场景1步骤2）
4. **针对性改写**（同场景1步骤4）— 每段 ≤500 词
5. **记录改动**（同场景1步骤5）
6. **分析每段结果**（同场景1步骤6）
7. **迭代验证**：对 `needs_iteration` 的段落自动迭代改写（最多 3 轮）
8. 合并结果 + 报告，返回最终结果
9. 改写后主动询问满意度，收集反馈
```

- [ ] **Step 3: 添加章节阈值说明**

在 SKILL.md 的 "关键规则" 部分之后添加：

```markdown
### 章节差异化阈值

不同章节的 composite_score 阈值不同：

| 章节 | 阈值 | 理由 |
|------|------|------|
| Abstract | 50 | 摘要是查重重灾区 |
| Introduction | 60 | 引言容易与文献综述重复 |
| Methods | 70 | 方法描述常用固定表达 |
| Results | 60 | 结果描述相对客观 |
| Discussion | 50 | 讨论容易与已有研究重复 |
| Conclusion | 60 | 结论常用套话 |

超过阈值时应继续迭代改写。
```

- [ ] **Step 4: 更新检查清单**

将 SKILL.md 的检查清单（第 206-216 行）更新为：

```markdown
## 检查清单

返回前必须检查：
- [ ] 连续词：有没有连续8个词和原文相同？（Turnitin 阈值）
- [ ] 术语：专业术语是否保留？
- [ ] 引用：引用格式是否完整？
- [ ] 公式：公式是否原样保留？
- [ ] 原意：是否改变了原意？
- [ ] 语法：语法是否正确？
- [ ] 流畅：读起来是否通顺？
- [ ] 学术：是否保持学术正式语体？
- [ ] 迭代：needs_iteration 是否已处理？
```

- [ ] **Step 5: Commit**

```bash
git add SKILL.md
git commit -m "feat: SKILL.md 流程更新（迭代验证闭环 + 章节阈值 + CLI analyze）"
```

---

### Task 9: 集成验证 — 全量测试

**Files:**
- 无新文件修改

- [ ] **Step 1: 运行全量测试**

Run: `$PY -m pytest tests/ -v`
Expected: 全部 PASS（原有 72 测试 + 新增测试）

- [ ] **Step 2: 验证向后兼容**

```bash
# 验证 tokenize 向后兼容
$PY -c "from scripts.similarity_calculator import tokenize; print(tokenize('The method is effective'))"

# 验证 calculate_similarity 返回值包含新字段
$PY -c "from scripts.similarity_calculator import calculate_similarity; r = calculate_similarity('The method is effective', 'The approach works well'); print('token_mode:', r.get('token_mode')); print('content_word_overlap:', r.get('content_word_overlap'))"

# 验证 auto_evaluate
$PY -c "from scripts.feedback_system import auto_evaluate; print(auto_evaluate({'max_consecutive': 10, 'trigram_precision': 0.1}))"
```

- [ ] **Step 3: 最终 Commit**

```bash
git add -A
git commit -m "chore: 集成验证 — 全量测试通过"
```
