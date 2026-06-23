# paper-rewriter 全流程改进设计

**日期**: 2026-06-23
**范围**: 相似度计算升级 + 反馈学习深化 + 分析引擎优化 + SKILL.md 流程改进
**目标**: 提升改写质量评估精度、增强反馈学习深度、修复分析引擎误报、建立自动迭代闭环

---

## 1. 背景与现状

### 1.1 当前架构

```
用户文本 → Claude 改写 → similarity_calculator.py 评估 → feedback_system.py 学习
                ↑                                              ↓
                └──────────── get_rewrite_suggestions() ────────┘
```

分析引擎独立运行：`analyze.py` → 5 维度风险评分（syntax/vocabulary/ai_traces/english/structure）

### 1.2 四个核心瓶颈

1. **相似度计算粒度粗**: `tokenize()` 用纯正则 `\b[a-z]+\b`，不处理连字符（"well-known" 切成两词）、数字（"3D" 被忽略）、缩写（"U.S." 被拆开）。句子级热点定位缺失，无法精确定位哪些句子需要重点改写。

2. **反馈学习信号弱**: 只依赖用户主观打分（1-5），无客观指标自动评估。失败时不区分原因（连续匹配过长 vs 句式太相似 vs 词汇太相似），不学习技巧组合的有效性。

3. **分析引擎误报**: 被动语态检测漏掉不规则被动（run/put/set）；TTR 阈值不考虑文本长度；名词化后缀匹配误报率高（nation 匹配 -tion）；分句误切缩写（Dr. Smith）。

4. **SKILL.md 流程断裂**: 改写后没有自动迭代循环（相似度仍高时无后续动作）；步骤 6 要求 Claude 内联执行 Python 代码，脆弱易错；缺少章节差异化阈值。

---

## 2. 改进设计

### 2.1 层面 1：相似度计算升级

**文件**: `scripts/similarity_calculator.py`

#### 2.1.1 分词策略

```python
def tokenize(text: str, mode: str = "word") -> list[str]:
    """将文本分词。优先 nltk，fallback 到正则。"""
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
```

**设计决策**:
- 用 nltk.word_tokenize 而非 spaCy：轻量级，无模型下载需求
- nltk 未安装时自动降级到正则，打印 `UserWarning`
- 过滤掉单字符 token（如单独的 "a"、"I"），减少噪声

#### 2.1.2 句子级热点定位

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

**匹配策略**: 贪心匹配——对每个原文句子，在改写文本中找相似度最高的句子（避免一对多）。如果两个原文句子匹配到同一个改写句子，保留相似度更高的那个，另一个找次优匹配。

**`similarity_score` 定义**: 使用与 `calculate_similarity()` 相同的 composite score 公式（LCS * 25 + trigram * 30 + bigram * 20 + vocab * 15 + consecutive * 10），归一化到 0-1。

**技巧推荐**: 根据句子级指标自动推荐：
- `max_consecutive >= 5`: voice_conversion, clause_insertion, word_order_change
- `trigram_precision >= 0.3`: synonym_replacement, word_order_change
- 其他: synonym_replacement

#### 2.1.3 连续匹配检测优化

当前 O(n²) 复杂度，改用 hash-based n-gram index：

```python
def find_consecutive_matches(tokens_orig, tokens_rew, min_length=4):
    """
    用 hash map 加速连续匹配检测。

    算法:
    1. 对原文建 bigram → [positions] 的 index
       orig_index = {(tokens_orig[i], tokens_orig[i+1]): i for i in range(n-1)}
    2. 改写文本滑动窗口，对每个位置 i 查 orig_index 找匹配起点
       key = (tokens_rew[i], tokens_rew[i+1])
       if key in orig_index:
           for j in orig_index[key]:  # 原文中所有匹配位置
               # 从 (j, i) 开始向前延伸
               length = 2  # bigram 已匹配
               while (j + length < len(tokens_orig) and
                      i + length < len(tokens_rew) and
                      tokens_orig[j + length] == tokens_rew[i + length]):
                   length += 1
               if length >= min_length:
                   matches.append({start_orig: j, start_rewrite: i, length, text})
    3. 去重：移除被更长匹配完全包含的短匹配（与现有 _remove_subsumed 逻辑一致）
    4. 跳过已匹配部分：在改写文本中跳过已匹配的 token，避免重叠报告

    复杂度: O(n + m + k) 其中 n=原文长度, m=改写长度, k=匹配数量
    """
```

#### 2.1.4 向后兼容

- `tokenize()` 接口签名不变，默认 `mode="word"`
- nltk 未安装时自动降级，打印 `UserWarning`
- `calculate_similarity()` 返回值新增 `token_mode` 和 `sentence_matches` 字段，不破坏现有消费方
- 现有测试自动适配

---

### 2.2 层面 2：反馈学习深化

**文件**: `scripts/feedback_system.py`

#### 2.2.1 自动评估（客观指标）

新增基于客观指标的自动评估，与中文版 `AIGC-rewriter-zh` 对齐：

```python
def auto_evaluate(self, metrics: dict) -> dict:
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

    return {"verdict": verdict, "max_consecutive": mc, "trigram_precision": tri}
```

#### 2.2.2 失败原因分类

```python
def classify_failure(metrics: dict) -> str:
    """根据指标细分失败原因"""
    mc = metrics.get("max_consecutive", 0)
    tri = metrics.get("trigram_precision", 0)

    if mc >= 8:
        return "consecutive_too_long"      # 有未改写的长片段
    elif tri >= 0.30:
        return "structure_too_similar"     # 句式没变
    elif metrics.get("vocabulary_overlap", 0) >= 0.6:
        return "vocabulary_too_similar"    # 换了词但不够多
    else:
        return "minor_issues"              # 轻微问题
```

失败类型存入 `problem_patterns`，用于生成针对性建议。

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

`record_rewrite_session` 后自动提取本次使用的技巧集合，生成所有两两组合，根据 `auto_evaluate` 结果更新计数。

`get_rewrite_suggestions()` 新增返回：
```python
{
    "effective_combinations": [
        {"combination": "voice_conversion+synonym_replacement", "success_rate": 0.85}
    ]
}
```

#### 2.2.4 问题模式→建议映射

`get_rewrite_suggestions()` 新增 `targeted_advice` 和 `priority_techniques`：

```python
if current_metrics:
    mc = current_metrics.get("max_consecutive", 0)
    tri = current_metrics.get("trigram_precision", 0)

    if mc >= 8:
        suggestions["priority_techniques"] = ["voice_conversion", "clause_insertion", "word_order_change"]
        suggestions["targeted_advice"].append(
            f"存在 {mc} 词连续匹配（超过 Turnitin 阈值），必须使用句式重组"
        )
    elif mc >= 5:
        suggestions["priority_techniques"] = ["voice_conversion", "synonym_replacement"]
        suggestions["targeted_advice"].append(
            f"连续匹配 {mc} 词，接近阈值，建议使用句式重组+同义词替换"
        )
    elif tri >= 0.30:
        suggestions["priority_techniques"] = ["synonym_replacement", "word_order_change"]
        suggestions["targeted_advice"].append(
            f"三元组精度 {tri:.1%}，需要改变句子结构和用词"
        )
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

强度调整逻辑改为（`is_success` 由 `auto_evaluate` 的 verdict 决定：`is_success = verdict in ("success", "excellent")`）：

```python
if not is_success:
    count = adjustment["consecutive_failures"]
    step = 0.05 + count * 0.01  # 0.05, 0.06, 0.07...
    adjustment["multiplier"] = min(1.5, adjustment["multiplier"] + step)
    adjustment["consecutive_failures"] = count + 1
    adjustment["consecutive_successes"] = 0
elif verdict == "excellent":
    count = adjustment["consecutive_successes"]
    step = max(0.01, 0.02 - count * 0.003)  # 0.02, 0.017, 0.014...
    adjustment["multiplier"] = max(0.5, adjustment["multiplier"] - step)
    adjustment["consecutive_successes"] = count + 1
    adjustment["consecutive_failures"] = 0
```

---

### 2.3 层面 3：分析引擎优化

#### 2.3.1 被动语态检测增强 (`analyzer/syntax.py`)

当前只匹配 `is/are/was/were/been/being + ed/en`，漏掉不规则被动。

改进：

```python
passive_patterns = [
    r'\b(?:is|are|was|were|been|being)\s+\w+(?:ed|en|t|wn)\b',  # 扩展后缀
    r'\bget(?:s|ting)?\s+\w+ed\b',  # get 被动
    r'\bhas\s+been\s+\w+ing\b',  # 完成进行被动
]

# 使用方式：先用正则匹配候选被动句，再用 IRREGULAR_PAST_PARTICIPLES 验证：
# 1. 对每个匹配，提取动词部分
# 2. 如果动词以 ed/en/t/wn 结尾 → 确认为被动
# 3. 如果动词在 IRREGULAR_PAST_PARTICIPLES 中 → 确认为被动
# 4. 否则 → 不是被动，跳过
# 这样 "The data was processed" 能匹配（processed 以 ed 结尾），
# "The experiment was run" 也能匹配（run 在不规则动词表中），
# "The study was important" 不会误匹配（important 不在表中且不以 ed/en/t/wn 结尾）

# 不规则动词过去分词表
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
```

#### 2.3.2 TTR 长度校正 (`analyzer/vocabulary.py`)

当前 TTR < 0.4 就报警，但短文本天然 TTR 高，长文本天然 TTR 低。

改用 Carroll's Corrected TTR (CTTR)：

```python
# CTTR = |unique tokens| / sqrt(2 * |total tokens|)
# 对文本长度不敏感
cttr = len(set(words)) / (2 * len(words)) ** 0.5
if cttr < 0.5:  # 阈值需通过 Turnitin 实际结果做经验验证
    issues.append(...)
```

#### 2.3.3 名词化检测误报修复 (`analyzer/english.py`)

只匹配真正的名词化后缀（单词长度 ≥ 6 且后缀前至少有 3 个字母）：

```python
nominalizations = re.findall(r'\b\w{3,}(?:tion|ment|ness|ity|ence|ance)s?\b', text_lower)
# 排除常见的非名词化词
NOM_EXCEPTIONS = {
    "nation", "attention", "mention", "condition", "position",
    "question", "section", "action", "relation", "information",
    "station", "situation", "direction", "collection", "connection",
    "election", "protection", "production", "reduction", "education"
}
nominalizations = [w for w in nominalizations if w not in NOM_EXCEPTIONS]
```

#### 2.3.4 分句改进 (`analyzer/syntax.py`, `analyzer/ai_traces.py`)

当前 `re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)` 会误切缩写。

改进：加缩写排除列表和合并逻辑：

```python
ABBREVIATIONS = {
    'dr', 'mr', 'mrs', 'ms', 'prof', 'sr', 'jr', 'vs', 'etc',
    'fig', 'tab', 'eq', 'ref', 'vol', 'no', 'pp', 'ed', 'est',
    'approx', 'dept', 'univ', 'inc', 'ltd', 'corp', 'govt'
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

---

### 2.4 层面 4：SKILL.md 流程优化

**文件**: `SKILL.md`, `scripts/rewrite_with_feedback.py`

#### 2.4.1 改写后自动迭代

`analyze_rewrite()` 返回值新增：

```python
{
    "needs_iteration": auto_evaluation["verdict"] in ("fail", "warning"),
    "hot_sentences": [...],  # 句子级热点
    "iteration_round": 1
}
```

SKILL.md 流程改为：

```
1. 获取建议
2. 改写
3. 分析结果（含句子级热点和 needs_iteration 标记）
4. 如果 needs_iteration 为 true：
   a. 查看 hot_sentences，定位需要重点改写的句子
   b. 使用 suggested_techniques 针对性改写这些句子
   c. 再次分析验证（最多 3 轮）
   d. 用户可随时中断迭代（输入"停"）
5. 返回最终结果
6. 询问满意度
7. 记录反馈
```

#### 2.4.2 章节差异化阈值

| 章节 | 阈值 | 理由 |
|------|------|------|
| Abstract | 0.25 | 摘要是查重重灾区 |
| Introduction | 0.30 | 引言容易与文献综述重复 |
| Methods | 0.35 | 方法描述常用固定表达 |
| Results | 0.30 | 结果描述相对客观 |
| Discussion | 0.25 | 讨论容易与已有研究重复 |
| Conclusion | 0.30 | 结论常用套话 |

#### 2.4.3 分析入口统一

给 `rewrite_with_feedback.py` 新增 `analyze` CLI 命令：

```bash
$PY scripts/rewrite_with_feedback.py analyze <原文文件> <改写文件> <学科> <强度>
```

输出 JSON 包含：session_id, composite_score, auto_evaluation, hot_sentences, needs_iteration, report。

Claude 不再需要写内联 Python 代码，只调 CLI。

#### 2.4.4 Diff 报告

新增 `diff` CLI 命令：

```bash
$PY scripts/rewrite_with_feedback.py diff <原文文件> <改写文件>
```

输出 markdown 格式的逐句对比表格：

```markdown
## 改写对比报告

| # | 原文 | 改写 | 技巧 | 相似度 |
|---|------|------|------|--------|
| 1 | The method is effective... | The approach demonstrates... | voice_conversion | 0.35 |
| 2 | ... | ... | ... | ... |
```

---

## 3. 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `scripts/similarity_calculator.py` | 修改 | nltk 分词、句子级热点、连续匹配优化 |
| `scripts/feedback_system.py` | 修改 | 自动评估、失败分类、技巧组合、自适应学习率 |
| `scripts/rewrite_with_feedback.py` | 修改 | 新增 analyze/diff CLI 命令、返回值扩展 |
| `SKILL.md` | 修改 | 自动迭代、章节阈值、CLI 统一 |
| `analyzer/syntax.py` | 修改 | 被动语态增强、分句改进（缩写排除） |
| `analyzer/vocabulary.py` | 修改 | CTTR 校正 |
| `analyzer/ai_traces.py` | 修改 | 分句改进（缩写排除） |
| `analyzer/english.py` | 修改 | 名词化排除词表 |
| `tests/test_similarity_calculator.py` | 新建 | 相似度计算测试 |
| `tests/test_feedback_system.py` | 修改 | 新增自动评估、失败分类、技巧组合测试 |
| `tests/test_analyzer.py` | 修改 | 新增被动语态、CTTR、名词化、分句测试 |

---

## 4. 测试策略

### 4.1 新增测试用例

**tests/test_similarity_calculator.py**（新建）:
- `test_tokenize_word_mode`: nltk 分词结果为词列表
- `test_tokenize_fallback`: nltk 不可用时降级到正则
- `test_sentence_level_matches`: 句子级热点定位
- `test_sentence_level_no_match`: 完全不同的句子返回空
- `test_consecutive_matches_performance`: 1000 词文本 < 1 秒

**tests/test_feedback_system.py**（扩展）:
- `test_auto_evaluate_excellent`: max_consecutive=2, trigram=0.05 → excellent
- `test_auto_evaluate_fail`: max_consecutive=10 → fail
- `test_classify_failure_consecutive`: mc=10 → consecutive_too_long
- `test_classify_failure_structure`: tri=0.35 → structure_too_similar
- `test_technique_combinations`: 组合计数正确
- `test_adaptive_learning_rate`: 连续失败时 step 递增
- `test_targeted_advice`: 高 mc 生成句式重组建议

**tests/test_analyzer.py**（扩展）:
- `test_passive_irregular`: "The data was run through" 检测到
- `test_cttr_length_correction`: 短文本不误报
- `test_nominalization_exceptions`: "nation" 不被标记
- `test_split_sentences_abbreviations`: "Dr. Smith went." 不误切

### 4.2 回归测试

- 所有现有测试必须继续通过
- tokenize 接口向后兼容验证
- 综合评分范围验证（0-100）

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
- **缓解**: 阈值集中在 `_calculate_score` 函数中，易于修改

---

## 6. 实施顺序

1. **analyzer/ 四个模块修复** — 被动语态、CTTR、名词化、分句（独立，不影响其他模块）
2. **scripts/similarity_calculator.py** — 分词升级 + 句子级热点 + 连续匹配优化
3. **scripts/feedback_system.py** — 自动评估 + 失败分类 + 技巧组合 + 自适应学习率
4. **scripts/rewrite_with_feedback.py** — 新 CLI 命令（analyze/diff）+ 返回值扩展
5. **SKILL.md** — 流程更新（自动迭代 + 章节阈值）
6. **全部测试 + 集成验证** — 端到端测试
