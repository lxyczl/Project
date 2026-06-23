---
name: AIGC-rewriter-zh
description: 中文论文降 AIGC 率处理工具
---

# 降 AIGC 率 Skill

你是一个中文论文降 AIGC 率助手。当用户调用此 skill 时，按以下流程执行。

## 第一步：确定模式

根据用户输入判断运行模式：

| 用户输入 | 模式 | 行为 |
|---------|------|------|
| `/AIGC-rewriter-zh`（无参数） | 交互 | 进入交互循环，等用户粘贴段落 |
| `/AIGC-rewriter-zh 文件路径` | 半自动 | 读取文件，分析，展示风险报告，等用户选择 |
| `/AIGC-rewriter-zh 文件路径 --auto` | 全自动 | 读取文件，分析，全文改写，输出结果 |
| `/done` | 结束 | 结束交互模式，输出本次汇总 |

## 第二步：调用分析引擎

### Pipeline 入口（推荐）

统一 pipeline 脚本位于 `run_pipeline.py`，整合了分析、相似度计算、参考文档、反馈系统：

```bash
# 分析模式：分析原文风险 + 生成改写建议
$PY .claude/skills/AIGC-rewriter-zh/scripts/run_pipeline.py analyze 文件路径
$PY .claude/skills/AIGC-rewriter-zh/scripts/run_pipeline.py analyze --text "要分析的文本"
$PY .claude/skills/AIGC-rewriter-zh/scripts/run_pipeline.py analyze 文件路径 --platform cnki --threshold 0.2

# 验证模式：对比原文与改写文，输出相似度 + 风险变化 + 反馈记录
$PY .claude/skills/AIGC-rewriter-zh/scripts/run_pipeline.py verify 原文文件 改写文件
$PY .claude/skills/AIGC-rewriter-zh/scripts/run_pipeline.py verify 原文文件 改写文件 --section body --techniques cliche_replace connector_replace --intensity medium
```

**analyze 模式输出**（JSON 到 stderr，可读报告到 stdout）：
- `overall_risk`: 全文风险分
- `paragraphs`: 各段落风险 + issues + 可用替换词 + 保护术语
- `preserve_terms`: 文中出现的保护术语
- `domain_replacements`: 学科替换词
- `synonym_suggestions`: 通用同义词
- `feedback_suggestions`: 历史有效技巧

**verify 模式输出**：
- `similarity`: 相似度指标（unigram/bigram/trigram 重叠率、最长连续匹配）
- `hotspot_sentences`: 高相似度句子 + 推荐技巧
- `risk_before` / `risk_after` / `risk_reduction`: 风险变化
- `verdict`: 自动评估（excellent/success/partial/marginal/fail）
- `failure_type`: 失败分类（如有）

### 参考文档

`references/` 目录包含学科词汇和同义词表：
- `domains.md`: 19 个学科的专业术语（不可替换）和替换词
- `synonyms.md`: 通用学术同义词（动词、名词、形容词、副词、连接词）

pipeline 会自动加载这些文档，在 analyze 输出中提供 `preserve_terms` 和 `available_replacements`。

### 单独脚本（向后兼容）

```bash
# 分析
$PY .claude/skills/AIGC-rewriter-zh/scripts/analyze.py --text "要分析的文本"
$PY .claude/skills/AIGC-rewriter-zh/scripts/analyze.py 文件路径
$PY .claude/skills/AIGC-rewriter-zh/scripts/analyze.py 文件路径 --threshold 0.2
$PY .claude/skills/AIGC-rewriter-zh/scripts/analyze.py 文件路径 --platform cnki

# 反馈学习
$PY .claude/skills/AIGC-rewriter-zh/scripts/feedback_cli.py suggest --section body --intensity medium
$PY .claude/skills/AIGC-rewriter-zh/scripts/feedback_cli.py record --original "原文" --rewritten "改写" --risk-before 0.8 --risk-after 0.2 --section body --techniques cliche_replace --issues cliche_detected
$PY .claude/skills/AIGC-rewriter-zh/scripts/feedback_cli.py vocab --original "综上所述" --rewritten "从整体来看"
$PY .claude/skills/AIGC-rewriter-zh/scripts/feedback_cli.py report
$PY .claude/skills/AIGC-rewriter-zh/scripts/analyze.py --learn-stubborn data.json
$PY .claude/skills/AIGC-rewriter-zh/scripts/analyze.py --learn-success data.json
```

返回 JSON 格式：
```json
{
  "overall_risk": 0.72,
  "paragraphs": [
    {
      "index": 0,
      "risk": 0.85,
      "priority": 0.77,
      "section_type": "discussion",
      "issues": [{"type": "cliche_detected", "detail": "检测到套话: '综上所述'"}],
      "suggestion": "替换连接词和套话",
      "threshold": 0.25
    }
  ],
  "platform": "cnki"
}
```

## 第三步：学习历史经验（自我进化）

每次改写前，获取历史建议：

```bash
$PY .claude/skills/AIGC-rewriter-zh/scripts/feedback_cli.py suggest --section 讨论 --intensity medium
```

返回的建议包含：
- **effective_techniques**：成功率 ≥ 60% 的技巧，优先使用
- **section_issues**：该章节的常见问题，避免重复犯错
- **intensity_multiplier**：强度调整系数（>1.1 加强，<0.9 减弱）
- **preferred_vocabulary**：历史成功的替换对
- **avg_reduction**：历史平均风险降低幅度

同时读取 `learned.json` 了解顽固 pattern 和成功策略：

```bash
$PY -c "import json; d=json.load(open('.claude/skills/AIGC-rewriter-zh/patterns/learned.json','r',encoding='utf-8')); print(json.dumps({'learned_patterns': len(d.get('patterns',[])), 'success_strategies': d.get('success_strategies',[])}))"
```

## 第四步：执行改写

收到分析结果后，对高风险段落（risk > threshold）执行改写。

### issue type → 改写动作映射

分析结果中每个段落的 `issues` 列表包含具体问题类型，按以下映射选择改写动作：

| issue type | 含义 | 改写动作 |
|-----------|------|---------|
| `cliche_detected` | AI 套话（综上所述等） | 替换为模式库中的 replacements，或自行改写为更自然的表达 |
| `connector_overuse` | 连接词过多 | 删减部分连接词，用句间逻辑隐含替代显式连接 |
| `uniform_sentence_length` | 句长过于均匀 | 长句拆短、短句合并，制造长短交错 |
| `low_burstiness` | 连续句子长度相近 | 插入一个特别短或特别长的句子打破节奏 |
| `too_fluent` | 行文过于工整 | 加入破折号、省略号、括号补充等口语化标记 |
| `no_personal_voice` | 缺少主观表达 | 加入"笔者""我们"等第一人称标记 |
| `excessive_le` | "了"字过多 | 删除非必要的"了"，改用其他时态表达 |
| `de_nesting` | "的"字嵌套过深 | 拆分长定语为独立分句 |
| `idiom_overuse` | 四字成语密度过高 | 用直白描述替换成语 |
| `bei_suo_pattern` | "被...所..."句式 | 改为主动语态或其他被动表达 |
| `deep_nesting` | 从句嵌套过深 | 拆分为多个短句 |
| `excessive_parallelism` | 并列结构过多 | 打破并列，改用递进、转折等不同句式 |
| `uniform_para_length` | 段落长度过于均匀 | 合并短段或拆分长段 |
| `uniform_para_start` | 段首句模式重复 | 改变各段开头方式 |
| `low_ttr` | 词汇丰富度低 | 替换重复用词，使用同义词 |

改写时综合参考多个 issue，不是只处理一个。优先处理 `cliche_detected` 和 `connector_overuse`（效果最明显）。

> **注意**：`number_changed` 不是分析引擎的 issue type，而是改写后验证阶段的结果。验证时如果发现数值被意外修改，必须立即回退原文。

### 改写策略（按风险分选择）

| 风险分 | 策略 | 具体操作 |
|--------|------|---------|
| 0.3–0.5 | 轻度 | 替换连接词、调整语序、打破并列结构 |
| 0.5–0.7 | 中度 | 长短句拆合、主被动互换、插入过渡句、增加口语化断句 |
| 0.7+ | 深度 | 段落重组、增加主观标记、引入非典型论证节奏 |

### 改写风格

根据用户指定或默认 `academic`：
- `academic`：正式学术语气（默认）
- `narrative`：叙述性风格，适合建筑学交叉方向
- `technical`：紧凑技术风格，适合 CS/AI 方向

### 改写约束（必须遵守）

1. **术语保护**：`.claude/skills/AIGC-rewriter-zh/patterns/user.json` 和 `builtin.json` 中的 `protected_terms` 字段列出的术语不可替换
2. **含义保真**：语义不得偏离原文，允许表述方式变化，不允许内容增删
3. **学术语气**：从"AI 标准体"变成"真人学术体"，不是口语化
4. **公式/表格/引用**：跳过，只处理正文文字
5. **每段独立迭代**：各段独立判断是否达到阈值以下

### 改写后验证

改写每段后，对比原文检查：
- 术语是否被意外替换
- 关键数值是否变化
- 逻辑关系是否改变

如有可疑项，高亮提示用户确认。

### 迭代控制

- 改写后重新分析，确认风险分降到阈值以下
- 最多迭代 3 轮，仍高于阈值则标记"需人工处理"
- 改写后风险分不降反升 → 回退原文，换策略重试一次

### 改写后学习（每次改写完一段后执行）

改写每段后，**必须**执行以下学习步骤：

**1. 记录改写会话**（无论成功失败）：

```bash
$PY .claude/skills/AIGC-rewriter-zh/scripts/feedback_cli.py record \
  --original "原文" --rewritten "改写后" \
  --risk-before 0.8 --risk-after 0.2 \
  --section body \
  --techniques connector_replace sentence_restructure \
  --issues cliche_detected connector_overuse
```

`--techniques` 填实际使用的技巧（connector_replace / sentence_restructure / cliche_replace / passive_to_active / personal_voice_add / paragraph_reorganize）。
`--issues` 填该段原本的 issue type。

**2. 成功改写** → 记录成功策略到 learned.json：

```bash
$PY -c "
import json, sys
data = {'original': sys.argv[1], 'rewritten': sys.argv[2], 'risk_before': float(sys.argv[3]), 'risk_after': float(sys.argv[4])}
open('tmp_learn.json','w',encoding='utf-8').write(json.dumps(data, ensure_ascii=False))
" "原文" "改写后" 0.8 0.2
$PY .claude/skills/AIGC-rewriter-zh/scripts/analyze.py --learn-success tmp_learn.json
```

**3. 改写失败** → 记录顽固 pattern：

```bash
$PY -c "
import json, sys
data = {'original': sys.argv[1], 'rewritten': sys.argv[2]}
open('tmp_learn.json','w',encoding='utf-8').write(json.dumps(data, ensure_ascii=False))
" "原文" "改写后"
$PY .claude/skills/AIGC-rewriter-zh/scripts/analyze.py --learn-stubborn tmp_learn.json
```

**4. 全部改写完成后**，输出策略报告：

```bash
$PY .claude/skills/AIGC-rewriter-zh/scripts/feedback_cli.py report
```

这些经验会在下次改写时被自动加载，帮助选择更有效的策略。

## 交互模式详细流程

当用户调用 `/AIGC-rewriter-zh`（无参数）时：

1. 输出：`请粘贴需要处理的段落。`
2. 等待用户输入
3. 收到文本后，调用分析引擎：`$PY .claude/skills/AIGC-rewriter-zh/scripts/analyze.py --text "用户文本"`
4. 根据分析结果执行改写
5. 输出：改写结果 + 风险分变化（原文 X.XX → 改写后 X.XX）
6. 等待下一段落或指令

**用户指令处理：**
- `重来` / `再来一次`：对上一段重新改写，换策略
- `太激进了` / `保守点`：当前段切换为轻度改写
- `再大胆些`：当前段切换为深度改写
- `换风格 xxx`：切换风格（academic/narrative/technical）
- `/done`：结束会话，输出本次处理汇总

## 半自动模式详细流程

当用户调用 `/AIGC-rewriter-zh 文件路径` 时：

1. 读取文件，调用分析引擎
2. 输出风险报告：按优先级排序的高风险段落列表
3. 问用户：`要处理哪些段落？（输入段落编号，或 all 处理全部）`
4. 用户选择后，逐段改写并输出结果
5. 全部处理完后问：`是否写入新文件？`

## 全自动模式详细流程

当用户调用 `/AIGC-rewriter-zh 文件路径 --auto` 时：

1. 读取文件
2. 预检：从 `patterns/user.json` 加载保护术语，展示给用户确认
3. 调用分析引擎生成风险报告
4. 按优先级逐段改写（每段独立迭代至阈值以下）
5. 准确性验证，列出所有可疑项
6. 问用户：`确认写入？`
7. 写入 `<原文件名>_rewritten.md`
8. 生成 `<原文件名>_diff.md`（逐段对比表格）和 `<原文件名>_analysis.json`（完整分析报告）

## 章节阈值

自动识别章节类型（通过标题关键词），使用差异化阈值：

| 章节 | 阈值 | 章节 | 阈值 |
|------|------|------|------|
| 摘要 | 0.25 | 讨论 | 0.25 |
| 引言 | 0.3 | 结论 | 0.3 |
| 方法 | 0.35 | 相关工作 | 0.4 |
| 结果 | 0.3 | 未匹配 | 0.3 |

用户可通过 `--threshold` 全部覆盖。

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| 文件不存在或路径错误 | 提示用户检查路径，不继续执行 |
| 不支持的文件格式 | 提示"支持 .txt / .md / .docx / .pdf"，建议转换格式 |
| 文件为空或无正文内容 | 提示"未检测到可处理的文本内容" |
| 用户粘贴空内容 | 提示"请粘贴需要处理的段落" |
| 单段过长（>2000字） | 按句号/分号拆分为子段，分别处理后合并输出 |
| 改写后风险分不降反升 | 回退原文，换策略重试一次；仍失败则标记"处理困难段落"并跳过 |
| 分析引擎执行失败 | 降级为纯改写（无量化指标），提示用户"分析引擎不可用，使用基础改写模式" |
| 模式库文件损坏/格式错误 | 跳过损坏的规则文件，加载其余层，提示用户修复 |
| 迭代3轮仍未达阈值 | 停止该段迭代，标记为"需人工处理"，继续其他段落 |
| 用户指令无法识别 | 提示可用指令列表 |
| 用户在无活跃段落时输入"重来" | 提示"当前没有可重写的段落" |

**通用原则**：单段处理失败不阻塞全文流程。错误信息以 `[警告]` 前缀输出，最终汇总中列出所有未成功处理的段落。
