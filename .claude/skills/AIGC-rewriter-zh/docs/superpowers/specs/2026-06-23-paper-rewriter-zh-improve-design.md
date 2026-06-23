# paper-rewriter-zh 全流程改进设计

**日期**: 2026-06-23
**范围**: 相似度计算升级 + 反馈学习深化 + 分析→改写闭环
**目标**: 提升改写质量评估精度、增强反馈学习深度、建立分析到改写的结构化闭环

---

## 1. 背景与现状

### 1.1 当前架构

```
用户文本 → Claude 改写 → similarity_calculator.py 评估 → feedback_system.py 学习
                ↑                                              ↓
                └──────────── get_rewrite_suggestions() ────────┘
```

### 1.2 三个核心瓶颈

1. **相似度计算粒度粗**: `tokenize()` 用正则 `[一-鿿]|[0-9]+` 按单字切分，不识别词边界。"生态系统服务" 被切成 7 个独立字符，导致 n-gram 重叠率和连续匹配的计算不够精准。

2. **反馈学习信号弱**: `auto_learn` 只做二元判定（成功/失败），不区分失败的具体原因。同样是 `warning`，可能是"句式没变只是换了词"，也可能是"换了句式但专业术语周围太相似"。

3. **分析→改写断裂**: `analyze` 产出的报告（哪些句子匹配、哪些 n-gram 重叠高）没有反馈给改写决策。Claude 看到报告后靠经验判断，没有结构化的"下一步建议"。

---

## 2. 改进设计

### 2.1 层面 1：相似度计算升级

**文件**: `scripts/similarity_calculator.py`

#### 2.1.1 分词策略

```python
def tokenize(text: str, mode: str = "word") -> list[str]:
    """将文本分词。优先 jieba，fallback 到字符级。

    注意：此函数不过滤停用词——连续匹配检测需要保留所有字符
    （知网查重按所有字符计数）。停用词过滤仅在 calculate_similarity
    的 n-gram 重叠率计算中单独进行。
    """
    if mode == "word":
        try:
            import jieba
            tokens = jieba.lcut(text)
            return [t for t in tokens if t.strip()]
        except ImportError:
            pass  # fallback to char mode
    return _char_tokenize(text)


def _char_tokenize(text: str) -> list[str]:
    """字符级分词（原有逻辑）"""
    return re.findall(r'[一-鿿]|[0-9]+', text)


# 精简停用词表（学术中文高频虚词，约 50 个）
# 仅用于 n-gram 重叠率计算，不用于连续匹配检测
STOPWORDS = {
    "的", "了", "在", "是", "和", "与", "及", "等", "对", "中",
    "为", "上", "下", "个", "之", "而", "则", "但", "又", "也",
    "都", "就", "不", "有", "这", "那", "被", "把", "将", "从",
    "到", "所", "以", "于", "其", "或", "者", "一", "二", "三",
    "能", "可", "会", "要", "做", "着", "过", "地", "得", "很",
}
```

**设计决策**:
- 用 jieba 而非更复杂的分词器（THULAC/pkuseg）：精度够用，无外部依赖问题
- 内置停用词表而非加载外部文件：保持自包含，无路径依赖
- jieba 未安装时自动降级到字符级，打印 warning（不 break）
- **停用词不过滤**：`tokenize()` 返回完整 token 列表。停用词过滤仅在 `calculate_similarity` 的 n-gram 重叠率计算中单独进行（通过 `_filter_stopwords(tokens)` 辅助函数，输入 token 列表，返回过滤后的列表），确保 `find_longest_common_substring` 和 `find_consecutive_matches` 的连续匹配检测不受影响

#### 2.1.2 n-gram 计算适配

`ngrams()` 不需要改——它接收 token list，分词粒度变了自动适应。

**重要**：`max_consecutive`（最长连续匹配）始终按**字符级**计算，不随分词模式变化。原因：知网查重规则是"连续 13 **字**"相同算抄袭，这里的"字"指的是字符而非词。即使 tokenize 改为词级，`find_longest_common_substring` 仍使用 `_char_tokenize` 的结果。

`calculate_similarity()` 改动：
- 默认用词级 tokenization
- 输出新增 `token_mode: "word"` 或 `"char"` 字段
- 当 `token_mode="word"` 时，`unigram_overlap` / `bigram_overlap` / `trigram_overlap` 自动变为词级计算（不再需要单独的 `word_overlap` 字段——词级 unigram_overlap 本身就是词重叠率）
- 新增 `content_word_overlap` 指标：过滤停用词后的实词重叠率（衡量内容词的改写程度）

```python
def calculate_similarity(original: str, rewritten: str) -> dict:
    # 尝试词级分词（用于 n-gram 重叠率）
    orig_tokens = tokenize(original, mode="word")
    rewrite_tokens = tokenize(rewritten, mode="word")
    token_mode = "word"

    # 如果词级分词结果太少（<3 个 token），降级到字符级
    if len(orig_tokens) < 3 or len(rewrite_tokens) < 3:
        orig_tokens = _char_tokenize(original)
        rewrite_tokens = _char_tokenize(rewritten)
        token_mode = "char"

    # n-gram 重叠率：用 orig_tokens / rewrite_tokens（词级或字符级）
    # 停用词过滤仅在此处：_filter_stopwords(orig_tokens) 用于 content_word_overlap
    ...

    # max_consecutive：始终用字符级（匹配知网"连续13字"规则）
    max_consecutive = find_longest_common_substring(original, rewritten)
    # 内部实现：find_longest_common_substring 使用 _char_tokenize，不随 tokenize 的 mode 变化

    return {
        "unigram_overlap": ...,           # 词级（token_mode="word"）或字符级重叠率
        "bigram_overlap": ...,
        "trigram_overlap": ...,
        "max_consecutive": max_consecutive,  # 始终字符级
        "vocabulary_diversity": ...,
        "original_char_count": ...,
        "rewritten_char_count": ...,
        "token_mode": token_mode,         # 新增
        "content_word_overlap": ...,      # 新增：过滤停用词后的实词重叠率
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
                "max_consecutive": 9
            },
            ...
        ]
    """
```

**分句规则**: 按 `。；？！\n` 分句，引号内的内容保持完整。

**匹配策略**: 对每个原文句子，在改写文本中找到相似度最高的句子（贪心匹配）。边界情况：
- 多个原文句子匹配到同一个改写句子：保留相似度最高的那个，其余标记为"未匹配"
- 原文句子在改写文本中找不到相似句子（最高相似度 < threshold）：跳过，不纳入热点
- 改写后句子被拆分（一拆多）：取多个改写句子的拼接作为匹配结果

#### 2.1.4 向后兼容

- `tokenize()` 新增 `mode` 参数，带默认值 `"word"`，已有调用 `tokenize(text)` 仍然兼容
- jieba 未安装时自动降级到字符级，打印 `UserWarning`
- **测试适配**：现有依赖字符级分词的测试（如 `test_chinese_chars`）需显式传入 `mode="char"` 或改用字符成员检查。jieba 未安装时现有测试自动通过（行为不变）

---

### 2.2 层面 2：反馈学习深化

**文件**: `scripts/feedback_system.py`

#### 2.2.1 失败原因分类

新增函数，**复用 `evaluate_rewrite_quality` 的判定结果**，不重复检查阈值：

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
        return "consecutive_too_long"      # mc >= 13，有未改写的长片段
    elif verdict == "warning":
        if mc >= 10 and tri >= 0.25:
            return "structure_too_similar"  # 句式和用词都没变
        elif mc >= 10:
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
    "max_consecutive": 15,
    "trigram_overlap": 0.3,
    "timestamp": "..."
}
```

#### 2.2.2 技巧组合学习

strategies.json 新增字段：

```json
{
    "technique_combinations": {
        "句式重组+同义词替换": {"success": 0, "total": 0},
        "拆分长句+引用位置移动": {"success": 0, "total": 0}
    }
}
```

`auto_learn` 逻辑：
1. 从 `changes_made` 提取本次使用的技巧集合（去重）
2. 生成所有两两组合，按 Unicode 编码排序（`sorted()` 默认行为），用 `+` 连接，如 "句式重组+同义词替换"
3. 根据 `is_success` 更新 `technique_combinations` 计数

`get_rewrite_suggestions()` 新增返回：
```python
{
    "effective_combinations": [
        {"combination": "句式重组+同义词替换", "success_rate": 0.85}
    ]
}
```

#### 2.2.3 问题模式→建议映射

`get_rewrite_suggestions()` 新增 `targeted_advice` 字段：

```python
def get_rewrite_suggestions(self, domain, intensity, current_metrics=None):
    suggestions = { ... 原有字段 ... }
    suggestions["targeted_advice"] = []

    # 基于历史问题模式生成建议（使用 failure_type 而非字符串匹配）
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

    # 基于当前文本指标生成建议（见层面 3 的 3.2）
    if current_metrics:
        ... 见层面 3 ...

    return suggestions
```

#### 2.2.4 学习率自适应

strategies.json 新增计数器：

```json
{
    "intensity_adjustments": {
        "中度": {
            "multiplier": 1.0,
            "consecutive_failures": 0,
            "consecutive_successes": 0
        }
    }
}
```

强度调整逻辑改为：

```python
if not is_success:
    count = adjustment["consecutive_failures"]
    step = min(0.10, 0.05 + count * 0.01)  # 0.05, 0.06, 0.07, ..., 上界 0.10
    adjustment["multiplier"] = min(1.5, adjustment["multiplier"] + step)
    adjustment["consecutive_failures"] = count + 1
    adjustment["consecutive_successes"] = 0
elif evaluation["verdict"] == "excellent":
    count = adjustment["consecutive_successes"]
    step = max(0.01, 0.02 - count * 0.003)  # 0.02, 0.017, 0.014..., 下界 0.01
    adjustment["multiplier"] = max(0.5, adjustment["multiplier"] - step)
    adjustment["consecutive_successes"] = count + 1
    adjustment["consecutive_failures"] = 0
```

注意：`step` 有上界 0.10（失败时）和下界 0.01（成功时），防止步长过大/过小。`multiplier` 有硬边界 [0.5, 1.5]。

---

### 2.3 层面 3：分析→改写闭环

**文件**: `scripts/rewrite_with_feedback.py`, `SKILL.md`

#### 2.3.1 analyze_rewrite 返回值扩展

```python
def analyze_rewrite(self, original, rewritten, domain, intensity, section_type):
    # ... 原有逻辑 ...

    # 新增：句子级热点
    from similarity_calculator import find_sentence_level_matches
    hot_sentences = find_sentence_level_matches(original, rewritten, threshold=0.5)

    # 为每个热点句子推荐技巧
    for sent in hot_sentences:
        sent["suggested_techniques"] = self._suggest_techniques_for_sentence(sent)

    return {
        "session_id": ...,
        "similarity": ...,
        "auto_evaluation": ...,
        "suggestions": ...,
        "report": ...,
        "hot_sentences": hot_sentences,           # 新增
        "needs_iteration": auto_evaluation["verdict"] == "fail" or
                          (auto_evaluation["verdict"] == "warning" and len(hot_sentences) > 0),  # 新增
    }


def _suggest_techniques_for_sentence(self, sentence_metrics: dict) -> list[str]:
    """根据句子级指标推荐技巧（同时考虑连续匹配和三元组重叠）"""
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

#### 2.3.2 get_rewrite_suggestions 动态建议

```python
def get_rewrite_suggestions(self, domain="通用", intensity="中度", current_metrics=None):
    suggestions = { ... 原有字段 + 层面 2 新增字段 ... }

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

#### 2.3.3 SKILL.md 流程更新

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
2. 分段改写（每段 ≤500 字）
3. 分析每段结果
4. 对 needs_iteration 的段落自动迭代改写（最多 3 轮）
5. 合并结果 + 报告
6. 询问满意度
7. 记录反馈
```

#### 2.3.4 report 命令升级

`format_report()` 新增部分：

```markdown
### 改写建议
- 优先使用技巧：句式重组、拆分长句
- 需要重点改写的句子（3 句）：
  1. "该地区的生态系统服务功能显著下降"（连续匹配 9 字）
  2. "研究者采用 InVEST 模型进行评估"（三元组重叠 35%）
  3. ...
```

---

## 3. 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `scripts/similarity_calculator.py` | 修改 | jieba 分词、词级 n-gram、句子级热点定位 |
| `scripts/feedback_system.py` | 修改 | 失败分类、技巧组合学习、建议映射、自适应学习率 |
| `scripts/rewrite_with_feedback.py` | 修改 | 返回值扩展、动态建议、迭代改写支持 |
| `SKILL.md` | 修改 | 流程更新（迭代验证闭环） |
| `tests/test_similarity_calculator.py` | 修改 | 适配新 tokenize、新增句子级测试 |
| `tests/test_feedback_system.py` | 修改 | 新增失败分类、技巧组合、自适应学习率测试 |
| `README.md` | 修改 | 补充 jieba 可选依赖说明（`pip install jieba` 获得更精准分词） |

---

## 4. 测试策略

### 4.1 新增测试用例

**similarity_calculator.py**:
- `test_tokenize_word_mode`: 验证 jieba 分词结果为词列表
- `test_tokenize_fallback`: jieba 不可用时降级到字符级
- `test_word_overlap`: 词级重叠率计算
- `test_sentence_level_matches`: 句子级热点定位
- `test_sentence_level_no_match`: 完全不同的句子

**feedback_system.py**:
- `test_classify_failure_consecutive`: 连续匹配过长
- `test_classify_failure_structure`: 句式相似
- `test_classify_failure_vocabulary`: 词汇相似
- `test_technique_combinations`: 技巧组合学习
- `test_targeted_advice`: 针对性建议生成
- `test_adaptive_learning_rate`: 连续失败时步长递增

### 4.2 回归测试

- 所有现有测试必须继续通过
- tokenize 接口向后兼容验证

---

## 5. 依赖与风险

### 5.1 jieba 依赖

- **风险**: 用户环境未安装 jieba
- **缓解**: 自动降级到字符级，打印 warning；在 README 中说明 `pip install jieba` 可获得更精准的分词

### 5.2 性能

- **风险**: jieba 首次加载较慢（约 1-2 秒）
- **缓解**: jieba 支持缓存字典，首次加载后后续调用很快；对于短文本（<100 字），字符级可能更快，可在 tokenize 中加阈值判断

### 5.3 分词一致性

- **风险**: jieba 分词结果可能因版本不同而有差异
- **缓解**: 不依赖分词结果做精确匹配，只用于相似度估算；差异在可接受范围内

---

## 6. 实施顺序

1. **similarity_calculator.py** — 分词升级 + 句子级热点
2. **tests/test_similarity_calculator.py** — 新测试 + 回归验证
3. **feedback_system.py** — 失败分类 + 技巧组合 + 建议映射 + 自适应学习率
4. **tests/test_feedback_system.py** — 新测试 + 回归验证
5. **rewrite_with_feedback.py** — 返回值扩展 + 动态建议
6. **SKILL.md** — 流程更新
7. **集成验证** — 端到端测试
