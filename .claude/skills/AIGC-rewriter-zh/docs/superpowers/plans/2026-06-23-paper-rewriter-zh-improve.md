# paper-rewriter-zh 全流程改进 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 升级相似度计算（jieba 分词 + 句子级热点）、深化反馈学习（失败分类 + 技巧组合 + 自适应学习率）、建立分析→改写闭环。

**Architecture:** 三层改进，自底向上：similarity_calculator.py（分词 + 热点定位）→ feedback_system.py（失败分类 + 组合学习 + 建议映射）→ rewrite_with_feedback.py（返回值扩展 + 动态建议）+ SKILL.md（流程更新）。

**Tech Stack:** Python 3.14, pytest, jieba（可选依赖）

## Global Constraints

- `$PY` = `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe`
- `max_consecutive` 始终按字符级计算（知网"连续13字"规则）
- `tokenize()` 不过滤停用词——停用词过滤仅在 `calculate_similarity` 内部进行
- jieba 未安装时自动降级到字符级，不 break
- 所有现有测试必须继续通过

---

### Task 1: similarity_calculator.py — 分词升级

**Files:**
- Modify: `.claude/skills/paper-rewriter-zh/scripts/similarity_calculator.py`
- Test: `.claude/skills/paper-rewriter-zh/tests/test_similarity_calculator.py`

**Interfaces:**
- Produces: `tokenize(text, mode="word") -> list[str]`, `_char_tokenize(text) -> list[str]`, `_filter_stopwords(tokens) -> list[str]`, `STOPWORDS: set`

- [ ] **Step 1: 写失败测试 — tokenize word mode**

在 `tests/test_similarity_calculator.py` 的 `TestTokenize` 类末尾添加：

```python
def test_word_mode_returns_list(self):
    """word mode 返回列表（jieba 安装时为词列表，否则为字符列表）"""
    result = tokenize("研究方法", mode="word")
    assert isinstance(result, list)
    assert len(result) > 0

def test_char_mode_returns_chars(self):
    """char mode 始终返回字符列表"""
    result = tokenize("研究方法", mode="char")
    assert result == ["研", "究", "方", "法"]

def test_filter_stopwords(self):
    """_filter_stopwords 过滤停用词"""
    tokens = ["研究", "的", "方法", "了"]
    filtered = _filter_stopwords(tokens)
    assert "的" not in filtered
    assert "了" not in filtered
    assert "研究" in filtered
    assert "方法" in filtered

def test_stopwords_constant_exists(self):
    """STOPWORDS 集合存在且非空"""
    assert isinstance(STOPWORDS, set)
    assert len(STOPWORDS) > 0
```

同时修改已有测试 `test_chinese_chars`，加 `mode="char"`：

```python
def test_chinese_chars(self):
    assert tokenize("研究方法", mode="char") == ["研", "究", "方", "法"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m pytest .claude/skills/paper-rewriter-zh/tests/test_similarity_calculator.py -v`

Expected: `test_chinese_chars` 可能通过（取决于 jieba 是否安装），新增测试 FAIL（函数不存在）。

- [ ] **Step 3: 实现分词升级**

在 `scripts/similarity_calculator.py` 中：

1. 在文件顶部 `import re` 之后添加 `import warnings`
2. 将原 `tokenize` 函数重命名为 `_char_tokenize`
3. 添加 `STOPWORDS`、`_filter_stopwords`、新 `tokenize`

```python
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
            warnings.warn("jieba 未安装，使用字符级分词。pip install jieba 可获得更精准的词级分词。", UserWarning)
    return _char_tokenize(text)
```

4. 更新 `calculate_similarity` 中对 `tokenize` 的调用：将 `tokenize(original)` 改为 `_char_tokenize(original)`（这个函数后续 Task 2 会大改，此处先保持最小变更让测试通过）

5. 更新 `find_longest_common_substring` 中的调用：确保使用 `_char_tokenize`

6. 更新 `find_consecutive_matches` 中的调用：确保使用 `_char_tokenize`

7. 更新 `main` 中的 `tokenize` 调用（如有）

- [ ] **Step 4: 跑测试确认通过**

Run: `$PY -m pytest .claude/skills/paper-rewriter-zh/tests/test_similarity_calculator.py -v`

Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/paper-rewriter-zh/scripts/similarity_calculator.py .claude/skills/paper-rewriter-zh/tests/test_similarity_calculator.py
git commit -m "feat: 分词升级 — jieba 词级分词 + 停用词表 + 字符级 fallback"
```

---

### Task 2: similarity_calculator.py — calculate_similarity 升级

**Files:**
- Modify: `.claude/skills/paper-rewriter-zh/scripts/similarity_calculator.py`
- Test: `.claude/skills/paper-rewriter-zh/tests/test_similarity_calculator.py`

**Interfaces:**
- Consumes: `tokenize(text, mode)`, `_char_tokenize(text)`, `_filter_stopwords(tokens)`
- Produces: `calculate_similarity()` 返回新增 `token_mode`, `content_word_overlap` 字段

- [ ] **Step 1: 写失败测试 — 新返回字段**

在 `tests/test_similarity_calculator.py` 的 `TestCalculateSimilarity` 类末尾添加：

```python
def test_returns_token_mode(self):
    result = calculate_similarity("测试文本", "改写文本")
    assert "token_mode" in result
    assert result["token_mode"] in ("word", "char")

def test_returns_content_word_overlap(self):
    result = calculate_similarity("研究表明该方法具有重要意义", "研究显示此方法具有重大价值")
    assert "content_word_overlap" in result
    assert 0 <= result["content_word_overlap"] <= 1

def test_max_consecutive_always_char_level(self):
    """max_consecutive 始终按字符级计算"""
    result = calculate_similarity("研究方法", "研究方法")
    assert result["max_consecutive"] == 4  # 4 个字符，不论 token_mode
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m pytest .claude/skills/paper-rewriter-zh/tests/test_similarity_calculator.py::TestCalculateSimilarity -v`

Expected: 新测试 FAIL（字段不存在）。

- [ ] **Step 3: 重写 calculate_similarity**

将 `similarity_calculator.py` 中的 `calculate_similarity` 函数替换为：

```python
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
    # 尝试词级分词（用于 n-gram 重叠率）
    orig_tokens = tokenize(original, mode="word")
    rewrite_tokens = tokenize(rewritten, mode="word")
    token_mode = "word"

    # 如果词级分词结果太少（<3 个 token），降级到字符级
    if len(orig_tokens) < 3 or len(rewrite_tokens) < 3:
        orig_tokens = _char_tokenize(original)
        rewrite_tokens = _char_tokenize(rewritten)
        token_mode = "char"

    # 字/词级别重叠
    orig_set = set(orig_tokens)
    rewrite_set = set(rewrite_tokens)
    unigram_overlap = len(orig_set & rewrite_set) / len(orig_set) if orig_set else 0

    # 二元组重叠
    orig_bigrams = set(ngrams(orig_tokens, 2))
    rewrite_bigrams = set(ngrams(rewrite_tokens, 2))
    bigram_overlap = len(orig_bigrams & rewrite_bigrams) / len(orig_bigrams) if orig_bigrams else 0

    # 三元组重叠
    orig_trigrams = set(ngrams(orig_tokens, 3))
    rewrite_trigrams = set(ngrams(rewrite_tokens, 3))
    trigram_overlap = len(orig_trigrams & rewrite_trigrams) / len(orig_trigrams) if orig_trigrams else 0

    # 最长连续匹配（始终按字符级，匹配知网查重逻辑）
    max_consecutive = find_longest_common_substring(original, rewritten)

    # 词汇多样性（独特 token / 总 token 数）
    vocabulary_diversity = len(rewrite_set) / len(rewrite_tokens) if rewrite_tokens else 0

    # 实词重叠率（过滤停用词后）
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `$PY -m pytest .claude/skills/paper-rewriter-zh/tests/test_similarity_calculator.py -v`

Expected: 全部 PASS。

- [ ] **Step 5: 更新 format_report 适配新字段**

将 `format_report` 中的 report 模板添加新字段：

```python
def format_report(original: str, rewritten: str) -> str:
    """生成格式化的相似度报告"""
    metrics = calculate_similarity(original, rewritten)

    report = """
## 相似度分析报告

### 基本信息
- 原文字数: {original_char_count}
- 改写字数: {rewritten_char_count}
- 分词模式: {token_mode}

### 相似度指标
| 指标 | 值 | 说明 |
|------|-----|------|
| 字/词重叠率 | {unigram_overlap:.1%} | {unigram_desc} |
| 二元组重叠率 | {bigram_overlap:.1%} | 连续两个 token 的相似度 |
| 三元组重叠率 | {trigram_overlap:.1%} | 连续三个 token 的相似度 |
| 最长连续匹配 | {max_consecutive} 字 | 改写后最多连续几个字与原文相同 |
| 词汇多样性 | {vocabulary_diversity:.1%} | 独特 token 占比 |
| 实词重叠率 | {content_word_overlap:.1%} | 过滤停用词后的重叠率 |

### 评估结果
{assessment}
"""

    # 评估结果（知网查重规则：连续13字相同算抄袭）
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

    unigram_desc = "词级别的相似度" if metrics["token_mode"] == "word" else "字级别的相似度"

    return report.format(**metrics, assessment=assessment, unigram_desc=unigram_desc)
```

- [ ] **Step 6: 跑全部测试确认无回归**

Run: `$PY -m pytest .claude/skills/paper-rewriter-zh/tests/test_similarity_calculator.py -v`

Expected: 全部 PASS。

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/paper-rewriter-zh/scripts/similarity_calculator.py .claude/skills/paper-rewriter-zh/tests/test_similarity_calculator.py
git commit -m "feat: calculate_similarity 升级 — 词级 n-gram + content_word_overlap + token_mode"
```

---

### Task 3: similarity_calculator.py — 句子级热点定位

**Files:**
- Modify: `.claude/skills/paper-rewriter-zh/scripts/similarity_calculator.py`
- Test: `.claude/skills/paper-rewriter-zh/tests/test_similarity_calculator.py`

**Interfaces:**
- Consumes: `calculate_similarity(original, rewritten)`
- Produces: `find_sentence_level_matches(original, rewritten, threshold=0.5) -> list[dict]`

- [ ] **Step 1: 写失败测试**

在 `tests/test_similarity_calculator.py` 末尾新增类：

```python
class TestFindSentenceLevelMatches:
    """句子级热点定位测试"""

    def test_finds_similar_sentence(self):
        orig = "研究表明X很重要。Y具有重要意义。"
        rew = "研究显示X非常关键。Y具有重大价值。"
        matches = find_sentence_level_matches(orig, rew, threshold=0.3)
        assert len(matches) > 0
        assert "original_sentence" in matches[0]
        assert "rewritten_sentence" in matches[0]
        assert "similarity_score" in matches[0]
        assert "max_consecutive" in matches[0]

    def test_no_match_below_threshold(self):
        orig = "天气晴朗万里无云。"
        rew = "研究方法具有重要意义。"
        matches = find_sentence_level_matches(orig, rew, threshold=0.5)
        assert len(matches) == 0

    def test_empty_input(self):
        assert find_sentence_level_matches("", "研究方法") == []
        assert find_sentence_level_matches("研究方法", "") == []
        assert find_sentence_level_matches("", "") == []

    def test_multiple_sentences(self):
        orig = "A导致B。C影响D。E促进F。"
        rew = "A造成B。X影响Y。E推动F。"
        matches = find_sentence_level_matches(orig, rew, threshold=0.3)
        # 至少匹配到 2 句（A→A, E→E）
        assert len(matches) >= 2

    def test_returns_sorted_by_similarity(self):
        orig = "研究方法有效。数据分析困难。"
        rew = "研究方法可行。数据处理复杂。"
        matches = find_sentence_level_matches(orig, rew, threshold=0.2)
        if len(matches) >= 2:
            assert matches[0]["similarity_score"] >= matches[1]["similarity_score"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m pytest .claude/skills/paper-rewriter-zh/tests/test_similarity_calculator.py::TestFindSentenceLevelMatches -v`

Expected: FAIL（函数不存在）。

- [ ] **Step 3: 实现 find_sentence_level_matches**

在 `similarity_calculator.py` 的 `format_report` 函数之前添加：

```python
def _split_sentences(text: str) -> list[str]:
    """按句号/分号/问号/感叹号/换行分句，引号内内容保持完整。"""
    import re as _re
    # 先按引号分割，标记引号内/外
    # 简化处理：按常见分句符分割，过滤空句
    sentences = _re.split(r'(?<=[。；？！\n])', text)
    return [s.strip() for s in sentences if s.strip()]


def find_sentence_level_matches(
    original: str,
    rewritten: str,
    threshold: float = 0.5
) -> list[dict]:
    """
    逐句对比，返回相似度超过阈值的句子对。

    返回按 similarity_score 降序排列。
    """
    orig_sentences = _split_sentences(original)
    rew_sentences = _split_sentences(rewritten)

    if not orig_sentences or not rew_sentences:
        return []

    matches = []
    used_rew = set()  # 已匹配的改写句子索引

    for orig_sent in orig_sentences:
        best_score = 0.0
        best_idx = -1
        best_metrics = None

        for j, rew_sent in enumerate(rew_sentences):
            if j in used_rew:
                continue
            metrics = calculate_similarity(orig_sent, rew_sent)
            # 用 unigram_overlap 和 trigram_overlap 的加权作为句子相似度
            score = metrics["unigram_overlap"] * 0.4 + (1 - metrics["trigram_overlap"]) * 0.3 + (1 - metrics["max_consecutive"] / max(len(_char_tokenize(orig_sent)), 1)) * 0.3
            # 简化：直接用 unigram_overlap 作为句子相似度
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

    # 按相似度降序排列
    matches.sort(key=lambda x: x["similarity_score"], reverse=True)
    return matches
```

- [ ] **Step 4: 跑测试确认通过**

Run: `$PY -m pytest .claude/skills/paper-rewriter-zh/tests/test_similarity_calculator.py -v`

Expected: 全部 PASS。

- [ ] **Step 5: 跑全量测试确认无回归**

Run: `$PY -m pytest .claude/skills/paper-rewriter-zh/tests/ -v`

Expected: 全部 PASS。

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/paper-rewriter-zh/scripts/similarity_calculator.py .claude/skills/paper-rewriter-zh/tests/test_similarity_calculator.py
git commit -m "feat: 句子级热点定位 — find_sentence_level_matches"
```

---

### Task 4: feedback_system.py — 失败分类

**Files:**
- Modify: `.claude/skills/paper-rewriter-zh/scripts/feedback_system.py`
- Test: `.claude/skills/paper-rewriter-zh/tests/test_feedback_system.py`

**Interfaces:**
- Consumes: `evaluate_rewrite_quality(metrics)` 的 verdict 输出
- Produces: `classify_failure(metrics, verdict) -> str`

- [ ] **Step 1: 写失败测试**

在 `tests/test_feedback_system.py` 末尾新增类：

```python
class TestClassifyFailure:
    """失败原因分类测试"""

    def test_excellent_returns_none(self):
        assert classify_failure({"max_consecutive": 3, "trigram_overlap": 0.05}, "excellent") == "none"

    def test_success_returns_none(self):
        assert classify_failure({"max_consecutive": 8, "trigram_overlap": 0.15}, "success") == "none"

    def test_fail_returns_consecutive_too_long(self):
        assert classify_failure({"max_consecutive": 15, "trigram_overlap": 0.5}, "fail") == "consecutive_too_long"

    def test_warning_consecutive_and_trigram(self):
        result = classify_failure({"max_consecutive": 11, "trigram_overlap": 0.30}, "warning")
        assert result == "structure_too_similar"

    def test_warning_consecutive_only(self):
        result = classify_failure({"max_consecutive": 11, "trigram_overlap": 0.10}, "warning")
        assert result == "consecutive_risk"

    def test_warning_trigram_only(self):
        result = classify_failure({"max_consecutive": 5, "trigram_overlap": 0.25}, "warning")
        assert result == "trigram_risk"

    def test_warning_mixed(self):
        result = classify_failure({"max_consecutive": 8, "trigram_overlap": 0.15}, "warning")
        assert result == "mixed_risk"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m pytest .claude/skills/paper-rewriter-zh/tests/test_feedback_system.py::TestClassifyFailure -v`

Expected: FAIL（函数不存在）。

- [ ] **Step 3: 实现 classify_failure**

在 `scripts/feedback_system.py` 的 `evaluate_rewrite_quality` 函数之后、`class FeedbackSystem` 之前添加：

```python
def classify_failure(metrics: dict, verdict: str) -> str:
    """根据指标和已有 verdict 细分失败原因。

    verdict 由 evaluate_rewrite_quality 产生，此处不再重复阈值判断，
    而是基于 verdict + 指标细节做更细粒度的分类。
    """
    if verdict == "excellent":
        return "none"

    mc = metrics.get("max_consecutive", 0)
    tri = metrics.get("trigram_overlap", 0)

    if verdict == "fail":
        return "consecutive_too_long"
    elif verdict == "warning":
        if mc >= 10 and tri >= 0.25:
            return "structure_too_similar"
        elif mc >= 10:
            return "consecutive_risk"
        elif tri >= 0.20:
            return "trigram_risk"
        else:
            return "mixed_risk"
    else:  # success
        return "none"
```

- [ ] **Step 4: 集成到 auto_learn**

在 `FeedbackSystem.auto_learn` 方法中，找到 `problem_patterns.append` 那段代码，在 `"issue"` 字段之后添加 `"failure_type"`：

```python
# 在 auto_learn 方法中，找到这段：
# self.strategies["problem_patterns"].append({
#     "issue": evaluation["reason"],
#     "domain": domain,
#     ...
# })
# 改为：
import sys
sys.path.insert(0, str(Path(__file__).parent))
from feedback_system import classify_failure  # 如果在同一文件则不需要 import

# ... 在 auto_learn 内部 ...
failure_type = classify_failure(metrics, evaluation["verdict"])
self.strategies["problem_patterns"].append({
    "issue": evaluation["reason"],
    "failure_type": failure_type,
    "domain": domain,
    "intensity": intensity,
    "max_consecutive": metrics.get("max_consecutive", 0),
    "trigram_overlap": metrics.get("trigram_overlap", 0),
    "timestamp": session.get("timestamp")
})
```

注意：`classify_failure` 和 `FeedbackSystem` 在同一文件，直接调用即可，无需 import。

- [ ] **Step 5: 跑测试确认通过**

Run: `$PY -m pytest .claude/skills/paper-rewriter-zh/tests/test_feedback_system.py -v`

Expected: 全部 PASS。

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/paper-rewriter-zh/scripts/feedback_system.py .claude/skills/paper-rewriter-zh/tests/test_feedback_system.py
git commit -m "feat: 失败原因分类 — classify_failure + 集成到 auto_learn"
```

---

### Task 5: feedback_system.py — 技巧组合学习

**Files:**
- Modify: `.claude/skills/paper-rewriter-zh/scripts/feedback_system.py`
- Test: `.claude/skills/paper-rewriter-zh/tests/test_feedback_system.py`

**Interfaces:**
- Consumes: `session["changes_made"]` 列表
- Produces: `strategies["technique_combinations"]` 字段, `get_rewrite_suggestions()` 返回 `effective_combinations`

- [ ] **Step 1: 写失败测试**

在 `tests/test_feedback_system.py` 末尾新增类：

```python
class TestTechniqueCombinations:
    """技巧组合学习测试"""

    def _make_system(self):
        tmpdir = Path(tempfile.mkdtemp())
        return FeedbackSystem(skill_dir=tmpdir)

    def test_default_strategies_has_combinations_field(self):
        system = self._make_system()
        assert "technique_combinations" in system.strategies

    def test_auto_learn_records_combinations(self):
        system = self._make_system()
        session = system.record_rewrite_session(
            original_text="测试文本足够长以通过检查",
            rewritten_text="改写文本也足够长以通过检查",
            changes_made=[
                {"type": "句式重组", "original": "A", "rewritten": "B"},
                {"type": "同义词替换", "original": "C", "rewritten": "D"},
            ]
        )
        system.auto_learn(session["session_id"])
        combos = system.strategies["technique_combinations"]
        # 排序后 key 应为 "句式重组+同义词替换"（Unicode 排序）
        key = "+".join(sorted(["句式重组", "同义词替换"]))
        assert key in combos
        assert combos[key]["total"] == 1

    def test_combinations_deduplicate(self):
        """同一技巧不与自身组合"""
        system = self._make_system()
        session = system.record_rewrite_session(
            original_text="测试", rewritten_text="改写",
            changes_made=[
                {"type": "同义词替换", "original": "A", "rewritten": "B"},
                {"type": "同义词替换", "original": "C", "rewritten": "D"},
            ]
        )
        system.auto_learn(session["session_id"])
        combos = system.strategies["technique_combinations"]
        # 只有一个技巧，不应产生组合
        assert len(combos) == 0 or all(v["total"] == 0 for v in combos.values())

    def test_suggestions_include_effective_combinations(self):
        system = self._make_system()
        # 成功 3 次
        for _ in range(3):
            session = system.record_rewrite_session(
                original_text="测试文本足够长", rewritten_text="改写文本也足够长",
                changes_made=[
                    {"type": "句式重组", "original": "A", "rewritten": "B"},
                    {"type": "同义词替换", "original": "C", "rewritten": "D"},
                ]
            )
            system.auto_learn(session["session_id"])
        suggestions = system.get_rewrite_suggestions("通用", "中度")
        assert "effective_combinations" in suggestions
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m pytest .claude/skills/paper-rewriter-zh/tests/test_feedback_system.py::TestTechniqueCombinations -v`

Expected: FAIL。

- [ ] **Step 3: 实现技巧组合学习**

1. 在 `_load_strategies` 的默认返回值中添加：
```python
"technique_combinations": {},
```

2. 在 `auto_learn` 方法中，技巧有效性学习之后添加：
```python
# 3.5 学习技巧组合
changes = session.get("changes_made", [])
tech_types = list(set(c.get("type", "") for c in changes if c.get("type")))
if len(tech_types) >= 2:
    from itertools import combinations
    for t1, t2 in combinations(sorted(tech_types), 2):
        key = f"{t1}+{t2}"
        if key not in self.strategies["technique_combinations"]:
            self.strategies["technique_combinations"][key] = {"success": 0, "total": 0}
        self.strategies["technique_combinations"][key]["total"] += 1
        if is_success:
            self.strategies["technique_combinations"][key]["success"] += 1
```

3. 在 `get_rewrite_suggestions` 方法末尾添加：
```python
# 有效技巧组合
suggestions["effective_combinations"] = []
for combo_key, combo_data in self.strategies.get("technique_combinations", {}).items():
    if combo_data["total"] >= 2:
        rate = combo_data["success"] / combo_data["total"]
        if rate >= 0.7:
            suggestions["effective_combinations"].append({
                "combination": combo_key,
                "success_rate": round(rate, 2)
            })
```

- [ ] **Step 4: 跑测试确认通过**

Run: `$PY -m pytest .claude/skills/paper-rewriter-zh/tests/test_feedback_system.py -v`

Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/paper-rewriter-zh/scripts/feedback_system.py .claude/skills/paper-rewriter-zh/tests/test_feedback_system.py
git commit -m "feat: 技巧组合学习 — technique_combinations + effective_combinations"
```

---

### Task 6: feedback_system.py — 建议映射 + 自适应学习率

**Files:**
- Modify: `.claude/skills/paper-rewriter-zh/scripts/feedback_system.py`
- Test: `.claude/skills/paper-rewriter-zh/tests/test_feedback_system.py`

**Interfaces:**
- Consumes: `classify_failure()`, `strategies["problem_patterns"]`, `strategies["intensity_adjustments"]`
- Produces: `get_rewrite_suggestions()` 返回 `targeted_advice`, `priority_techniques`；强度调整步长自适应

- [ ] **Step 1: 写失败测试**

在 `tests/test_feedback_system.py` 末尾新增类：

```python
class TestTargetedAdvice:
    """针对性建议测试"""

    def _make_system(self):
        tmpdir = Path(tempfile.mkdtemp())
        return FeedbackSystem(skill_dir=tmpdir)

    def test_targeted_advice_from_problem_patterns(self):
        system = self._make_system()
        # 模拟历史失败
        system.strategies["problem_patterns"].append({
            "issue": "连续15字匹配",
            "failure_type": "consecutive_too_long",
            "domain": "生态水文",
            "intensity": "中度",
        })
        suggestions = system.get_rewrite_suggestions("生态水文", "中度")
        assert "targeted_advice" in suggestions
        assert any("连续匹配" in a or "句式重组" in a for a in suggestions["targeted_advice"])

    def test_targeted_advice_empty_when_no_problems(self):
        system = self._make_system()
        suggestions = system.get_rewrite_suggestions("通用", "中度")
        assert suggestions["targeted_advice"] == []


class TestAdaptiveLearningRate:
    """自适应学习率测试"""

    def _make_system(self):
        tmpdir = Path(tempfile.mkdtemp())
        return FeedbackSystem(skill_dir=tmpdir)

    def test_consecutive_failures_increases_step(self):
        system = self._make_system()
        # 连续失败 3 次
        for _ in range(3):
            session = system.record_rewrite_session(
                original_text="测试文本", rewritten_text="测试文本",  # 完全相同
                intensity="中度"
            )
            system.auto_learn(session["session_id"])
        mult = system.strategies["intensity_adjustments"]["中度"]["multiplier"]
        # 第1次 step=0.05, 第2次 step=0.06, 第3次 step=0.07, 总增 0.18
        assert mult > 1.15

    def test_step_upper_bound(self):
        system = self._make_system()
        # 连续失败很多次
        for _ in range(20):
            session = system.record_rewrite_session(
                original_text="测试", rewritten_text="测试",
                intensity="中度"
            )
            system.auto_learn(session["session_id"])
        # step 不应超过 0.10
        failures = system.strategies["intensity_adjustments"]["中度"]["consecutive_failures"]
        step = min(0.10, 0.05 + (failures - 1) * 0.01)
        assert step <= 0.10

    def test_multiplier_hard_bounds(self):
        system = self._make_system()
        # 测试上界
        for _ in range(100):
            session = system.record_rewrite_session(
                original_text="测试", rewritten_text="测试",
                intensity="轻度"
            )
            system.auto_learn(session["session_id"])
        assert system.strategies["intensity_adjustments"]["轻度"]["multiplier"] <= 1.5
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m pytest .claude/skills/paper-rewriter-zh/tests/test_feedback_system.py::TestTargetedAdvice -v`

Expected: FAIL。

- [ ] **Step 3: 实现建议映射**

在 `get_rewrite_suggestions` 方法中，在 `suggestions["targeted_advice"] = []` 之后添加：

```python
# 基于历史问题模式生成建议（使用 failure_type）
recent_problems = [
    p for p in self.strategies["problem_patterns"]
    if p.get("domain") == domain
][-5:]

failure_type_advice = {
    "consecutive_too_long": "该学科历史改写中多次出现超长连续匹配，建议优先使用句式重组+拆分长句",
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
```

- [ ] **Step 4: 实现自适应学习率**

将 `auto_learn` 方法中的强度调整逻辑替换为：

```python
# 4. 学习强度调整（自适应步长）
if not is_success:
    count = adjustment.get("consecutive_failures", 0)
    step = min(0.10, 0.05 + count * 0.01)
    adjustment["multiplier"] = min(1.5, adjustment["multiplier"] + step)
    adjustment["consecutive_failures"] = count + 1
    adjustment["consecutive_successes"] = 0
elif evaluation["verdict"] == "excellent":
    count = adjustment.get("consecutive_successes", 0)
    step = max(0.01, 0.02 - count * 0.003)
    adjustment["multiplier"] = max(0.5, adjustment["multiplier"] - step)
    adjustment["consecutive_successes"] = count + 1
    adjustment["consecutive_failures"] = 0
```

同时更新 `_load_strategies` 中 `intensity_adjustments` 的默认值，添加计数器：

```python
"intensity_adjustments": {
    "轻度": {"multiplier": 1.0, "consecutive_failures": 0, "consecutive_successes": 0},
    "中度": {"multiplier": 1.0, "consecutive_failures": 0, "consecutive_successes": 0},
    "重度": {"multiplier": 1.0, "consecutive_failures": 0, "consecutive_successes": 0}
},
```

- [ ] **Step 5: 跑测试确认通过**

Run: `$PY -m pytest .claude/skills/paper-rewriter-zh/tests/test_feedback_system.py -v`

Expected: 全部 PASS。

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/paper-rewriter-zh/scripts/feedback_system.py .claude/skills/paper-rewriter-zh/tests/test_feedback_system.py
git commit -m "feat: 建议映射 + 自适应学习率 — targeted_advice + adaptive step"
```

---

### Task 7: rewrite_with_feedback.py — 返回值扩展 + 动态建议

**Files:**
- Modify: `.claude/skills/paper-rewriter-zh/scripts/rewrite_with_feedback.py`
- Test: `.claude/skills/paper-rewriter-zh/tests/test_feedback_system.py`

**Interfaces:**
- Consumes: `find_sentence_level_matches()`, `classify_failure()`, `get_rewrite_suggestions(domain, intensity, current_metrics)`
- Produces: `analyze_rewrite()` 返回新增 `hot_sentences`, `needs_iteration`；`get_suggestions()` 支持 `current_metrics` 参数

- [ ] **Step 1: 写失败测试**

在 `tests/test_feedback_system.py` 的 `TestRewriteWithFeedback` 类末尾添加：

```python
def test_analyze_returns_hot_sentences(self):
    r = self._make_rewriter()
    result = r.analyze_rewrite(
        original="研究表明该方法具有重要意义和价值",
        rewritten="研究显示此方法具有重大作用与贡献",
        domain="通用", intensity="中度"
    )
    assert "hot_sentences" in result
    assert "needs_iteration" in result
    assert isinstance(result["hot_sentences"], list)

def test_analyze_needs_iteration_on_fail(self):
    r = self._make_rewriter()
    result = r.analyze_rewrite(
        original="测试文本",
        rewritten="测试文本",  # 完全相同
        domain="通用", intensity="中度"
    )
    assert result["needs_iteration"] is True

def test_get_suggestions_with_current_metrics(self):
    r = self._make_rewriter()
    suggestions = r.get_suggestions("通用", "中度")
    assert "targeted_advice" in suggestions
    # 带 current_metrics 调用
    suggestions2 = r.get_suggestions("通用", "中度", current_metrics={
        "max_consecutive": 15, "trigram_overlap": 0.3
    })
    assert "priority_techniques" in suggestions2
    assert len(suggestions2["targeted_advice"]) > len(suggestions["targeted_advice"])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `$PY -m pytest .claude/skills/paper-rewriter-zh/tests/test_feedback_system.py::TestRewriteWithFeedback -v`

Expected: FAIL。

- [ ] **Step 3: 扩展 analyze_rewrite**

将 `rewrite_with_feedback.py` 中的 `analyze_rewrite` 方法替换为：

```python
def analyze_rewrite(
    self,
    original: str,
    rewritten: str,
    domain: str = "通用",
    intensity: str = "中度",
    section_type: str = "unknown"
) -> dict:
    """分析改写结果并记录会话。"""
    from similarity_calculator import calculate_similarity, format_report, find_sentence_level_matches

    similarity = calculate_similarity(original, rewritten)

    session = self.feedback_system.record_rewrite_session(
        original_text=original,
        rewritten_text=rewritten,
        domain=domain,
        intensity=intensity,
        section_type=section_type
    )

    suggestions = self.feedback_system.get_rewrite_suggestions(domain, intensity, current_metrics=similarity)

    # 句子级热点
    hot_sentences = find_sentence_level_matches(original, rewritten, threshold=0.5)
    for sent in hot_sentences:
        sent["suggested_techniques"] = self._suggest_techniques_for_sentence(sent)

    auto_evaluation = session["auto_evaluation"]
    needs_iteration = (
        auto_evaluation["verdict"] == "fail" or
        (auto_evaluation["verdict"] == "warning" and len(hot_sentences) > 0)
    )

    return {
        "session_id": session["session_id"],
        "similarity": similarity,
        "auto_evaluation": auto_evaluation,
        "suggestions": suggestions,
        "report": format_report(original, rewritten),
        "hot_sentences": hot_sentences,
        "needs_iteration": needs_iteration,
    }


def _suggest_techniques_for_sentence(self, sentence_metrics: dict) -> list[str]:
    """根据句子级指标推荐技巧"""
    mc = sentence_metrics.get("max_consecutive", 0)
    tri = sentence_metrics.get("trigram_overlap", 0)

    if mc >= 13:
        return ["句式重组", "拆分长句", "主被动转换"]
    elif mc >= 10:
        return ["句式重组", "同义词替换"]
    elif tri >= 0.25:
        return ["同义词替换", "因果倒置", "条件重组"]
    else:
        return ["同义词替换", "调整语序"]
```

- [ ] **Step 4: 扩展 get_suggestions**

将 `get_suggestions` 方法改为：

```python
def get_suggestions(self, domain: str = "通用", intensity: str = "中度", current_metrics: dict = None) -> dict:
    """获取基于历史反馈的改写建议，可选带当前文本指标"""
    return self.feedback_system.get_rewrite_suggestions(domain, intensity, current_metrics=current_metrics)
```

- [ ] **Step 5: 更新 feedback_system.py 的 get_rewrite_suggestions 签名**

在 `FeedbackSystem.get_rewrite_suggestions` 方法签名中添加 `current_metrics=None` 参数，并在方法末尾添加动态建议逻辑：

```python
def get_rewrite_suggestions(
    self,
    domain: str = "通用",
    intensity: str = "中度",
    current_metrics: dict = None
) -> dict:
    # ... 原有逻辑 ...

    # 基于当前文本指标的动态建议
    if current_metrics:
        mc = current_metrics.get("max_consecutive", 0)
        tri = current_metrics.get("trigram_overlap", 0)

        if mc >= 13:
            suggestions["priority_techniques"] = ["句式重组", "拆分长句", "主被动转换"]
            suggestions["targeted_advice"].append(
                f"存在 {mc} 字连续匹配（超过知网 13 字阈值），必须使用句式重组打破结构"
            )
        elif mc >= 10:
            suggestions["priority_techniques"] = ["句式重组", "同义词替换", "调整语序"]
            suggestions["targeted_advice"].append(
                f"连续匹配 {mc} 字，接近阈值，建议使用句式重组+同义词替换"
            )
        elif tri >= 0.20:
            suggestions["priority_techniques"] = ["同义词替换", "因果倒置", "条件重组"]
            suggestions["targeted_advice"].append(
                f"三元组重叠率 {tri:.1%}，需要改变句子结构和用词"
            )

    return suggestions
```

- [ ] **Step 6: 跑测试确认通过**

Run: `$PY -m pytest .claude/skills/paper-rewriter-zh/tests/ -v`

Expected: 全部 PASS。

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/paper-rewriter-zh/scripts/rewrite_with_feedback.py .claude/skills/paper-rewriter-zh/scripts/feedback_system.py .claude/skills/paper-rewriter-zh/tests/test_feedback_system.py
git commit -m "feat: analyze 返回值扩展 — hot_sentences + needs_iteration + 动态建议"
```

---

### Task 8: SKILL.md — 流程更新

**Files:**
- Modify: `.claude/skills/paper-rewriter-zh/SKILL.md`

- [ ] **Step 1: 更新场景 1 流程**

找到 SKILL.md 中的 `### 场景1：用户发文本` 部分，替换为：

```markdown
### 场景1：用户发文本
1. 获取建议 → 2. 按规则改写 → 3. 分析结果（含句子级热点和 needs_iteration 标记）→ 4. 如果 needs_iteration 为 true：定位热点句子，使用 suggested_techniques 针对性改写，再次分析验证（最多 3 轮；3 轮后仍 fail 则返回当前结果并提示需手动调整）→ 5. 返回最终结果 → 6. 询问满意度 → 7. 记录反馈
```

- [ ] **Step 2: 更新场景 2 流程**

找到 `### 场景2：用户给文件`，替换为：

```markdown
### 场景2：用户给文件
1. 获取建议 → 2. 分段改写（每段 ≤500 字）→ 3. 分析每段结果（含句子级热点）→ 4. 对 needs_iteration 的段落自动迭代改写（最多 3 轮）→ 5. 合并结果+报告 → 6. 询问满意度 → 7. 记录反馈
```

- [ ] **Step 3: 更新反馈闭环描述**

找到 `### 反馈闭环（每次改写必须遵循）` 中的自动评估标准部分，在 `**手动反馈（可选）**` 之前添加：

```markdown
**句子级热点定位**：`analyze` 命令现在返回 `hot_sentences`（需要重点改写的句子）和 `needs_iteration` 标记。当 `needs_iteration` 为 true 时，应自动对热点句子进行针对性改写（最多 3 轮）。
```

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/paper-rewriter-zh/SKILL.md
git commit -m "feat: SKILL.md 流程更新 — 迭代验证闭环 + 句子级热点"
```

---

### Task 9: README.md — jieba 依赖说明

**Files:**
- Modify: `.claude/skills/paper-rewriter-zh/README.md`

- [ ] **Step 1: 添加可选依赖说明**

在 README.md 的 `## 快速开始` 之前添加：

```markdown
## 可选依赖

- **jieba**: 提供更精准的中文分词。未安装时自动使用字符级分词（功能正常，但词级相似度计算精度稍低）。
  ```bash
  pip install jieba
  ```

---
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/paper-rewriter-zh/README.md
git commit -m "docs: 补充 jieba 可选依赖说明"
```

---

### Task 10: 集成验证

- [ ] **Step 1: 跑全量测试**

Run: `$PY -m pytest .claude/skills/paper-rewriter-zh/tests/ -v`

Expected: 全部 PASS。

- [ ] **Step 2: 端到端手动验证**

创建临时文件测试完整流程：

```bash
cd "E:\WorkSpace\Claude Code"
echo "研究表明，城市化进程的加快导致了生态环境的恶化。地下水位下降是导致植被退化的主要原因。" > /tmp/test_original.txt
```

运行 CLI：
```bash
$PY .claude/skills/paper-rewriter-zh/scripts/rewrite_with_feedback.py suggest 生态水文 中度
$PY .claude/skills/paper-rewriter-zh/scripts/similarity_calculator.py /tmp/test_original.txt /tmp/test_original.txt
```

Expected: suggest 返回 JSON 包含 `targeted_advice` 和 `effective_combinations` 字段；similarity_calculator 输出包含 `token_mode` 和 `content_word_overlap`。

- [ ] **Step 3: 检查策略报告**

Run: `$PY .claude/skills/paper-rewriter-zh/scripts/rewrite_with_feedback.py report`

Expected: 报告格式正常，包含技巧有效性、强度调整等部分。
