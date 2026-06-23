# paper-rewriter 全流程改进设计

**日期**: 2026-06-23
**范围**: 相似度计算升级 + 反馈学习深化 + 分析→改写闭环 + 分析器修复
**目标**: 提升改写质量评估精度、增强反馈学习深度、建立分析到改写的结构化闭环、修复分析器已知 bug

---

## 1. 背景与现状

### 1.1 当前架构

```
用户文本 → Claude 改写 → similarity_calculator.py 评估 → feedback_system.py 学习
                ↑                                              ↓
                └──────────── get_rewrite_suggestions() ────────┘
```

分析引擎独立运行：`analyze.py` → 7 维度风险评分（syntax/vocabulary/ai_traces/english/structure/paragraphs/patterns）

### 1.2 四个核心瓶颈

1. **相似度计算粒度粗**: `tokenize()` 用纯正则 `\b[a-z]+\b`，不处理连字符（"well-known" 切成两词）、数字（"3D" 被忽略）、缩写（"U.S." 被拆开）。句子级热点定位缺失，无法精确定位哪些句子需要重点改写。

2. **反馈学习信号弱**: 只依赖用户主观打分（1-5），无客观指标自动评估。失败时不区分原因（连续匹配过长 vs 句式太相似 vs 词汇太相似），不学习技巧组合的有效性。

3. **分析→改写断裂**: `analyze_rewrite()` 返回的结果没有句子级热点和迭代标记。Claude 看到报告后靠经验判断，没有结构化的"下一步建议"。SKILL.md 要求 Claude 内联执行 Python 代码（步骤 6），脆弱易错。

4. **分析器已知 bug**: 被动语态检测漏掉不规则被动（run/put/set）；TTR 阈值不考虑文本长度；名词化后缀匹配有重复（ment 出现两次）且误报率高；分句误切缩写（Dr. Smith）。

---

## 2. 改进设计

### 2.1 层面 1：相似度计算升级

**文件**: `scripts/similarity_calculator.py`

#### 2.1.1 分词策略

```python
def tokenize(text: str, mode: str = "word") -> list[str]:
    """将文本分词。优先 nltk，fallback 到正则。

    注意：此函数不过滤停用词——连续匹配检测需要保留所有单词
    （Turnitin 按所有单词计数）。停用词过滤仅在 calculate_similarity
    的 n-gram 重叠率计算中单独进行。
    """
    if mode == "word":
        try:
            from nltk import word_tokenize
            tokens = word_tokenize(text)
            return [t.lower() for t in tokens if t.isalpha() and len(t) > 1]
        except ImportError:
            pass  # fallback to regex mode
    return _regex_tokenize(text)


def _regex_tokenize(text: str) -> list[str]:
    """正则分词（原有逻辑，保留作为 fallback）"""
    return re.findall(r'\b[a-z]+\b', text.lower())


# 精简停用词表（学术英文高频虚词，约 60 个）
# 仅用于 n-gram 重叠率计算，不用于连续匹配检测
STOPWORDS = {
    "the", "a", "an", "of", "in", "to", "for", "with", "on", "at",
    "from", "by", "as", "is", "was", "are", "were", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "this", "that", "these",
    "those", "it", "its", "they", "their", "them", "he", "she", "his",
    "her", "we", "our", "you", "your", "not", "no", "but", "or", "and",
    "if", "then", "than", "so", "such", "which", "who", "whom", "what",
}
```

**设计决策**:
- 用 nltk.word_tokenize 而非 spaCy：轻量级，无模型下载需求
- nltk 未安装时自动降级到正则，打印 `UserWarning`
- 过滤掉单字符 token（如单独的 "a"、"I"），减少噪声
- **停用词不过滤**：`tokenize()` 返回完整 token 列表。停用词过滤仅在 `calculate_similarity` 的 n-gram 重叠率计算中单独进行（通过 `_filter_stopwords(tokens)` 辅助函数），确保 `find_consecutive_matches` 的连续匹配检测不受影响

#### 2.1.2 n-gram 计算适配

`ngrams()` 不需要改——它接收 token list，分词粒度变了自动适应。

**重要**：`max_consecutive`（最长连续匹配）始终按**单词级**计算。Turnitin 的规则是"连续 8 个以上相同单词"算抄袭，这里的"词"指的是分词后的 token。与中文版不同（中文版 max_consecutive 按字符级计算以匹配知网"连续 13 字"规则），英文版的 max_consecutive 随分词模式变化——当 `token_mode="word"` 时按词级计算，当 `token_mode="regex"` 时按正则分词结果计算。

`calculate_similarity()` 改动：
- 默认用词级 tokenization
- 输出新增 `token_mode: "word"` 或 `"regex"` 字段
- 当 `token_mode="word"` 时，`unigram_overlap` / `bigram_overlap` / `trigram_overlap` 自动变为词级计算
- 新增 `content_word_overlap` 指标：过滤停用词后的实词重叠率（衡量内容词的改写程度）

```python
def calculate_similarity(original: str, rewritten: str) -> dict:
    # 尝试词级分词（用于 n-gram 重叠率）
    orig_tokens = tokenize(original, mode="word")
    rewrite_tokens = tokenize(rewritten, mode="word")
    token_mode = "word"

    # 如果词级分词结果太少（<3 个 token），降级到正则
    if len(orig_tokens) < 3 or len(rewrite_tokens) < 3:
        orig_tokens = _regex_tokenize(original)
        rewrite_tokens = _regex_tokenize(rewritten)
        token_mode = "regex"

    # n-gram 重叠率：用 orig_tokens / rewrite_tokens（词级或正则）
    # 停用词过滤仅在此处：_filter_stopwords(orig_tokens) 用于 content_word_overlap
    ...

    # max_consecutive：用 tokenize 结果（词级或正则）
    max_consecutive = find_longest_consecutive_match(orig_tokens, rewrite_tokens)

    return {
        "composite_score": ...,               # 0-100
        "lcs_ratio": ...,
        "bigram_precision": ...,
        "bigram_recall": ...,
        "trigram_precision": ...,
        "trigram_recall": ...,
        "vocabulary_overlap": ...,
        "max_consecutive": max_consecutive,    # 词级
        "consecutive_matches": [...],
        "original_word_count": ...,
        "rewritten_word_count": ...,
        "token_mode": token_mode,             # 新增
        "content_word_overlap": ...,          # 新增：过滤停用词后的实词重叠率
    }
```

#### 2.1.3 句子级热点定位

新增函数：

```python
def find_sentence_level_matches(
    original: str,
    rewritten: str,
    threshold: float = 0.5
) -> list[dict]:
    """
    逐句对比，返回相似度超过阈值的句子对。

    返回:
        [
            {
                "original_sentence": "...",
                "rewritten_sentence": "...",
                "similarity_score": 0.85,
                "max_consecutive": 9,
                "suggested_techniques": ["voice_conversion", "clause_insertion"]
            },
            ...
        ]
    """
```

**分句规则**: 与 `analyzer/syntax.py` 一致——按 `.!?` + 空格 + 大写字母 分句，排除缩写（Dr./Mr./Mrs./Prof./etc./Fig./Tab.）。

**匹配策略**: 对每个原文句子，在改写文本中找到相似度最高的句子（贪心匹配）。边界情况：
- 多个原文句子匹配到同一个改写句子：保留相似度最高的那个，其余标记为"未匹配"
- 原文句子在改写文本中找不到相似句子（最高相似度 < threshold）：跳过，不纳入热点
- 改写后句子被拆分（一拆多）：取多个改写句子的拼接作为匹配结果

**`similarity_score` 定义**: 使用与 `calculate_similarity()` 相同的 composite score 公式（LCS * 25 + trigram * 30 + bigram * 20 + vocab * 15 + consecutive * 10），归一化到 0-1。

**技巧推荐**: 根据句子级指标自动推荐：
- `max_consecutive >= 8`: voice_conversion, clause_insertion, word_order_change
- `trigram_precision >= 0.30`: synonym_replacement, word_order_change
- 其他: synonym_replacement

#### 2.1.4 向后兼容

- `tokenize()` 新增 `mode` 参数，带默认值 `"word"`，已有调用 `tokenize(text)` 仍然兼容
- nltk 未安装时自动降级到正则，打印 `UserWarning`
- `calculate_similarity()` 返回值新增 `token_mode` 和 `content_word_overlap` 字段，不破坏现有消费方
- **测试适配**：现有依赖正则分词的测试需显式传入 `mode="regex"` 或适配新的返回字段。nltk 未安装时现有测试自动通过（行为不变）

---

### 2.2 层面 2：反馈学习深化

**文件**: `scripts/feedback_system.py`

#### 2.2.1 自动评估（客观指标）

新增基于客观指标的自动评估，对齐中文版 `evaluate_rewrite_quality()`：

```python
def auto_evaluate(metrics: dict) -> dict:
    """基于客观指标自动判定成功/失败。Turnitin 比知网更敏感，阈值更严格。"""
    mc = metrics.get("max_consecutive", 0)
    tri = metrics.get("trigram_precision", 0)

    if mc >= 8:
        verdict = "fail"          # Turnitin 必定标红
    elif mc >= 5 or tri >= 0.30:
        verdict = "warning"       # 有风险
    elif tri < 0.15 and mc < 4:
        verdict = "excellent"     # 改写充分
    else:
        verdict = "success"       # 可接受

    return {
        "verdict": verdict,
        "is_success": verdict in ("success", "excellent"),
        "max_consecutive": mc,
        "trigram_precision": tri,
        "reason": _verdict_reason(verdict, mc, tri),
    }


def _verdict_reason(verdict: str, mc: int, tri: float) -> str:
    if verdict == "fail":
        return f"连续匹配 {mc} 词，超过 Turnitin 阈值（8 词）"
    elif verdict == "warning":
        if mc >= 5:
            return f"连续匹配 {mc} 词，接近阈值"
        return f"三元组精度 {tri:.1%}，句式相似度偏高"
    elif verdict == "excellent":
        return "改写充分，相似度低"
    return "可接受"
```

#### 2.2.2 失败原因分类

新增函数，**复用 `auto_evaluate` 的判定结果**，不重复检查阈值：

```python
def classify_failure(metrics: dict, verdict: str) -> str:
    """根据指标和已有 verdict 细分失败原因。

    verdict 由 auto_evaluate 产生，此处不再重复阈值判断，
    而是基于 verdict + 指标细节做更细粒度的分类。
    """
    if verdict == "excellent":
        return "none"

    mc = metrics.get("max_consecutive", 0)
    tri = metrics.get("trigram_precision", 0)

    if verdict == "fail":
        return "consecutive_too_long"      # mc >= 8，有未改写的长片段
    elif verdict == "warning":
        if mc >= 5 and tri >= 0.25:
            return "structure_too_similar"  # 句式和用词都没变
        elif mc >= 5:
            return "consecutive_risk"       # 连续匹配接近阈值
        elif tri >= 0.20:
            return "trigram_risk"           # 三元组重叠率高
        else:
            return "mixed_risk"             # 混合问题
    else:  # success
        return "none"                       # 成功无需分类
```

在 `auto_learn` 中，`failure_type` 存入 `problem_patterns`：

```python
problem_patterns 条目结构:
{
    "issue": "...",
    "failure_type": "consecutive_too_long",  # 新增
    "domain": "...",
    "intensity": "...",
    "max_consecutive": 10,
    "trigram_precision": 0.35,
    "timestamp": "..."
}
```

#### 2.2.3 技巧组合学习

strategies.json 新增字段：

```json
{
    "technique_combinations": {
        "voice_conversion+synonym_replacement": {"success": 0, "total": 0},
        "clause_insertion+word_order_change": {"success": 0, "total": 0}
    }
}
```

`auto_learn` 逻辑：
1. 从 `changes_made` 提取本次使用的技巧集合（去重）
2. 生成所有两两组合，按字母排序，用 `+` 连接，如 "voice_conversion+synonym_replacement"
3. 根据 `is_success` 更新 `technique_combinations` 计数

`get_rewrite_suggestions()` 新增返回：
```python
{
    "effective_combinations": [
        {"combination": "voice_conversion+synonym_replacement", "success_rate": 0.85}
    ]
}
```

#### 2.2.4 问题模式→建议映射

`get_rewrite_suggestions()` 新增 `targeted_advice` 和 `priority_techniques` 字段：

```python
def get_rewrite_suggestions(self, domain, intensity, current_metrics=None):
    suggestions = { ... 原有字段 ... }
    suggestions["targeted_advice"] = []
    suggestions["priority_techniques"] = []

    # 基于历史问题模式生成建议（使用 failure_type 而非字符串匹配）
    recent_problems = [
        p for p in self.strategies["problem_patterns"]
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

    # 基于当前文本指标生成建议（见层面 3 的 3.2）
    if current_metrics:
        ... 见层面 3 ...

    return suggestions
```

#### 2.2.5 学习率自适应

strategies.json 新增计数器：

```json
{
    "intensity_adjustments": {
        "medium": {
            "multiplier": 1.0,
            "consecutive_failures": 0,
            "consecutive_successes": 0
        }
    }
}
```

强度调整逻辑改为（`is_success` 由 `auto_evaluate` 的 verdict 决定）：

```python
if not is_success:
    count = adjustment["consecutive_failures"]
    step = min(0.10, 0.05 + count * 0.01)  # 0.05, 0.06, 0.07, ..., 上界 0.10
    adjustment["multiplier"] = min(1.5, adjustment["multiplier"] + step)
    adjustment["consecutive_failures"] = count + 1
    adjustment["consecutive_successes"] = 0
elif verdict == "excellent":
    count = adjustment["consecutive_successes"]
    step = max(0.01, 0.02 - count * 0.003)  # 0.02, 0.017, 0.014..., 下界 0.01
    adjustment["multiplier"] = max(0.5, adjustment["multiplier"] - step)
    adjustment["consecutive_successes"] = count + 1
    adjustment["consecutive_failures"] = 0
# verdict == "success" 时：multiplier 保持不变，两个计数器归零
```

注意：`step` 有上界 0.10（失败时）和下界 0.01（成功时），防止步长过大/过小。`multiplier` 有硬边界 [0.5, 1.5]。`verdict == "success"` 时不做调整，但重置连续计数器。

---

### 2.3 层面 3：分析→改写闭环

**文件**: `scripts/rewrite_with_feedback.py`, `SKILL.md`

#### 2.3.1 analyze_rewrite 返回值扩展

```python
def analyze_rewrite(self, original, rewritten, domain, intensity, section_type, changes_made):
    # ... 原有逻辑 ...

    # 新增：自动评估
    auto_evaluation = auto_evaluate(similarity)

    # 新增：句子级热点
    hot_sentences = find_sentence_level_matches(original, rewritten, threshold=0.5)

    # 为每个热点句子推荐技巧
    for sent in hot_sentences:
        sent["suggested_techniques"] = _suggest_techniques_for_sentence(sent)

    # 新增：迭代判断
    needs_iteration = auto_evaluation["verdict"] == "fail" or \
                     (auto_evaluation["verdict"] == "warning" and len(hot_sentences) > 0)

    return {
        "session_id": ...,
        "similarity": ...,
        "auto_evaluation": auto_evaluation,     # 新增
        "suggestions": ...,
        "report": ...,
        "hot_sentences": hot_sentences,         # 新增
        "needs_iteration": needs_iteration,     # 新增
    }


def _suggest_techniques_for_sentence(sentence_metrics: dict) -> list[str]:
    """根据句子级指标推荐技巧"""
    mc = sentence_metrics.get("max_consecutive", 0)
    tri = sentence_metrics.get("trigram_precision", 0)

    if mc >= 8:
        return ["voice_conversion", "clause_insertion", "word_order_change"]
    elif mc >= 5:
        return ["voice_conversion", "synonym_replacement"]
    elif tri >= 0.30:
        return ["synonym_replacement", "word_order_change"]
    else:
        return ["synonym_replacement"]
```

#### 2.3.2 get_rewrite_suggestions 动态建议

```python
def get_rewrite_suggestions(self, domain="General", intensity="medium", current_metrics=None):
    suggestions = { ... 原有字段 + 层面 2 新增字段 ... }

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

    return suggestions
```

#### 2.3.3 CLI analyze 命令

给 `rewrite_with_feedback.py` 新增 `analyze` CLI 命令：

```bash
$PY scripts/rewrite_with_feedback.py analyze <原文文件> <改写文件> <学科> <强度>
```

输出 JSON 包含：session_id, composite_score, auto_evaluation, hot_sentences, needs_iteration, report。

Claude 不再需要写内联 Python 代码，只调 CLI。

#### 2.3.4 SKILL.md 流程更新

场景 1（用户发文本）流程改为：

```
1. 获取建议（带学科和强度）
2. 按规则改写
3. 分析结果（含句子级热点和 needs_iteration 标记）
4. 如果 needs_iteration 为 true：
   a. 查看 hot_sentences，定位需要重点改写的句子
   b. 使用 suggested_techniques 针对性改写这些句子
   c. 再次分析验证（最多 3 轮）
   d. 如果 3 轮后仍有 fail/warning：返回当前最佳结果，附带 warning 提示"以下句子仍需手动调整"并列出未解决的热点句子
5. 返回最终结果
6. 询问满意度
7. 记录反馈（自动学习）
```

场景 2（用户给文件）流程改为：

```
1. 获取建议
2. 分段改写（每段 ≤500 词）
3. 分析每段结果
4. 对 needs_iteration 的段落自动迭代改写（最多 3 轮）
5. 合并结果 + 报告
6. 询问满意度
7. 记录反馈
```

#### 2.3.5 章节差异化阈值

| 章节 | composite_score 阈值 | 理由 |
|------|---------------------|------|
| Abstract | 50 | 摘要是查重重灾区 |
| Introduction | 60 | 引言容易与文献综述重复 |
| Methods | 70 | 方法描述常用固定表达 |
| Results | 60 | 结果描述相对客观 |
| Discussion | 50 | 讨论容易与已有研究重复 |
| Conclusion | 60 | 结论常用套话 |

#### 2.3.6 report 命令升级

`format_report()` 新增部分：

```markdown
### 改写建议
- 优先使用技巧：voice_conversion, clause_insertion
- 需要重点改写的句子（3 句）：
  1. "The method is effective for..."（连续匹配 9 词）
  2. "We used the model to..."（三元组重叠 35%）
  3. ...
```

---

### 2.4 层面 4：分析器修复

#### 2.4.1 被动语态检测增强 (`analyzer/syntax.py`)

当前只匹配 `is/are/was/were/been/being + ed/en`，漏掉不规则被动。

改进：

```python
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

PASSIVE_PATTERNS = [
    r'\b(?:is|are|was|were|been|being)\s+\w+(?:ed|en|t|wn)\b',  # 扩展后缀
    r'\bget(?:s|ting)?\s+\w+ed\b',  # get 被动
]

def _is_passive(match_text: str) -> bool:
    """验证被动语态匹配：先用正则匹配候选，再验证动词形式。"""
    words = match_text.lower().split()
    if len(words) < 2:
        return False
    verb = words[-1]
    # 动词以 ed/en/t/wn 结尾 → 确认为被动
    if re.search(r'(?:ed|en|t|wn)$', verb):
        return True
    # 动词在不规则动词表中 → 确认为被动
    if verb in IRREGULAR_PAST_PARTICIPLES:
        return True
    return False
```

#### 2.4.2 TTR 长度校正 (`analyzer/vocabulary.py`)

当前 TTR < 0.4 就报警，但短文本天然 TTR 高，长文本天然 TTR 低。

改用 Carroll's Corrected TTR (CTTR)：

```python
# CTTR = |unique tokens| / sqrt(2 * |total tokens|)
# 对文本长度不敏感
cttr = len(set(words)) / (2 * len(words)) ** 0.5
if cttr < 0.5:  # 阈值需通过 Turnitin 实际结果做经验验证
    issues.append(...)
```

#### 2.4.3 名词化检测修复 (`analyzer/english.py`)

修复重复的 `ment`，并排除常见非名词化词：

```python
# 修复前：r'\b\w+(?:tion|ment|ness|ity|ence|ance|ment)s?\b'  (ment 重复)
# 修复后：
nominalizations = re.findall(r'\b\w{3,}(?:tion|ment|ness|ity|ence|ance)s?\b', text_lower)

# 排除常见的非名词化词（单词长度 ≥ 6 且后缀前至少有 3 个字母）
NOM_EXCEPTIONS = {
    "nation", "attention", "mention", "condition", "position",
    "question", "section", "action", "relation", "information",
    "station", "situation", "direction", "collection", "connection",
    "election", "protection", "production", "reduction", "education",
    "government", "environment", "development", "management", "movement",
    "statement", "agreement", "requirement", "treatment", "assessment"
}
nominalizations = [w for w in nominalizations if w not in NOM_EXCEPTIONS]
```

#### 2.4.4 分句改进 (`analyzer/syntax.py`, `analyzer/ai_traces.py`)

当前 `re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)` 会误切缩写。

改进：加缩写排除列表和合并逻辑，同时消除 `ai_traces.py` 中的重复代码：

```python
# 在 analyzer/syntax.py 中定义，ai_traces.py 改为导入
ABBREVIATIONS = {
    'dr', 'mr', 'mrs', 'ms', 'prof', 'sr', 'jr', 'vs', 'etc',
    'fig', 'tab', 'eq', 'ref', 'vol', 'no', 'pp', 'ed', 'est',
    'approx', 'dept', 'univ', 'inc', 'ltd', 'corp', 'govt',
    'u.s', 'u.k', 'e.g', 'i.e', 'al', 'approx'
}

def split_sentences(text: str) -> list[str]:
    raw = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    merged = []
    for sent in raw:
        if merged and _ends_with_abbreviation(merged[-1]):
            merged[-1] = merged[-1] + ' ' + sent
        else:
            merged.append(sent)
    return [s.strip() for s in merged if s.strip() and len(s.strip()) > 10]


def _ends_with_abbreviation(text: str) -> bool:
    last_word = text.strip().split()[-1].rstrip('.').lower()
    return last_word in ABBREVIATIONS
```

`ai_traces.py` 改为：
```python
from syntax import split_sentences  # 替代 _split_sentences
```

---

## 3. 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `scripts/similarity_calculator.py` | 修改 | nltk 分词、词级 n-gram、句子级热点定位、停用词过滤 |
| `scripts/feedback_system.py` | 修改 | 自动评估、失败分类、技巧组合学习、建议映射、自适应学习率 |
| `scripts/rewrite_with_feedback.py` | 修改 | 新增 analyze CLI 命令、返回值扩展、迭代改写支持 |
| `SKILL.md` | 修改 | 流程更新（迭代验证闭环 + 章节阈值） |
| `analyzer/syntax.py` | 修改 | 被动语态增强、分句改进（缩写排除） |
| `analyzer/vocabulary.py` | 修改 | CTTR 校正 |
| `analyzer/english.py` | 修改 | 名词化修复（去重 + 排除词表） |
| `analyzer/ai_traces.py` | 修改 | 导入 syntax.split_sentences 替代重复代码 |
| `tests/test_similarity_calculator.py` | 修改 | 适配新 tokenize、新增句子级测试 |
| `tests/test_feedback_system.py` | 修改 | 新增自动评估、失败分类、技巧组合、自适应学习率测试 |
| `tests/test_analyzer.py` | 修改 | 新增被动语态、CTTR、名词化、分句测试 |

---

## 4. 测试策略

### 4.1 新增测试用例

**similarity_calculator.py**:
- `test_tokenize_word_mode`: nltk 分词结果为词列表
- `test_tokenize_fallback`: nltk 不可用时降级到正则
- `test_word_overlap`: 词级重叠率计算
- `test_content_word_overlap`: 过滤停用词后的实词重叠率
- `test_sentence_level_matches`: 句子级热点定位
- `test_sentence_level_no_match`: 完全不同的句子返回空
- `test_sentence_level_suggested_techniques`: 热点句子推荐技巧

**feedback_system.py**:
- `test_auto_evaluate_excellent`: max_consecutive=2, trigram=0.05 → excellent
- `test_auto_evaluate_fail`: max_consecutive=10 → fail
- `test_auto_evaluate_success`: verdict=success 时 multiplier 不变
- `test_classify_failure_consecutive`: mc=10 → consecutive_too_long
- `test_classify_failure_structure`: tri=0.35 → structure_too_similar
- `test_technique_combinations`: 组合计数正确
- `test_targeted_advice`: 高 mc 生成句式重组建议
- `test_adaptive_learning_rate`: 连续失败时 step 递增
- `test_adaptive_learning_rate_success_reset`: success 重置计数器

**analyzer/**:
- `test_passive_irregular`: "The data was run through" 检测到
- `test_cttr_length_correction`: 短文本不误报
- `test_nominalization_exceptions`: "nation" 不被标记
- `test_nominalization_no_duplicate_ment`: 正则无重复 ment
- `test_split_sentences_abbreviations`: "Dr. Smith went." 不误切

### 4.2 回归测试

- 所有现有测试必须继续通过（72 个测试）
- tokenize 接口向后兼容验证
- 综合评分范围验证（0-100）
- ai_traces 导入 syntax.split_sentences 后行为不变

---

## 5. 依赖与风险

### 5.1 nltk 依赖

- **风险**: 用户环境未安装 nltk
- **缓解**: 自动降级到正则，打印 warning；在 README 中说明 `pip install nltk` 可获得更精准的分词

### 5.2 性能

- **风险**: nltk.word_tokenize 首次调用需加载 tokenizer（约 0.5 秒）
- **缓解**: 后续调用很快；对于短文本（<50 词），正则可能更快，可在 tokenize 中加阈值判断

### 5.3 CTTR 阈值

- **风险**: 0.5 是估算值，可能需要调整
- **缓解**: 初始值保守设置，通过 Turnitin 实际结果做经验验证后调整

### 5.4 自动评估阈值

- **风险**: Turnitin 检测算法可能更新，阈值需要调整
- **缓解**: 阈值集中在 `auto_evaluate` 函数中，易于修改

### 5.5 数据清理

- **风险**: `strategies.json` 和 session 文件包含中文数据，与英文 skill 不匹配
- **缓解**: 实施时清理现有中文数据，重置为英文模板

---

## 6. 实施顺序

1. **analyzer/ 四个模块修复** — 被动语态、CTTR、名词化、分句（独立，不影响其他模块）
2. **tests/test_analyzer.py** — 新测试 + 回归验证
3. **scripts/similarity_calculator.py** — 分词升级 + 句子级热点 + 停用词过滤
4. **tests/test_similarity_calculator.py** — 新测试 + 回归验证
5. **scripts/feedback_system.py** — 自动评估 + 失败分类 + 技巧组合 + 建议映射 + 自适应学习率
6. **tests/test_feedback_system.py** — 新测试 + 回归验证
7. **scripts/rewrite_with_feedback.py** — 新 CLI 命令 + 返回值扩展
8. **SKILL.md** — 流程更新（迭代验证闭环 + 章节阈值）
9. **集成验证** — 端到端测试（全量 72+ 测试通过）
