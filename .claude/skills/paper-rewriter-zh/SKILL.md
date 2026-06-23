---
name: paper-rewriter-zh
description: |
  改写中文学术论文以降低查重率。当用户想要：
  - 改写/降重中文学术文本
  - 降低论文查重率
  - 降低AIGC检测率
  - "降重", "改写", "中文论文降重", "论文降重"
  本技能应用系统化的改写技巧，包括句式重组、同义词替换、语态转换等。
---

# 中文学术论文降重

## 快速流程

```bash
# 标准：原文 + 改写文对比
$PY scripts/run_pipeline.py <原文> <改写文> [学科] [强度]

# 知网报告：解析查重报告 + 改写文对比
$PY scripts/run_pipeline.py --cnki <知网报告.html> <改写文> [学科] [强度]

# 文档解析：Word/PDF 提取纯文本
$PY scripts/run_pipeline.py --doc <论文.docx>

# 独立风险分析（不改写）
$PY scripts/analyze.py <文本文件>
```

pipeline 自动完成：相似度分析 → 风险分析 → 句级热点定位 → 自动评估 → 迭代判断。

### 操作步骤

1. **获取文本**：文件路径、粘贴、Word/PDF（`--doc`）、知网报告（`--cnki`）
2. **运行 pipeline**，获取评估结果
3. **如果 `needs_iteration` 为 true**：对 hot_sentences 逐句改写，再次运行（最多 3 轮）
4. **如果达标**：输出最终报告

### pipeline 输出

- `verdict`: excellent / success / warning / fail
- `hot_sentences`: 需重点改写的句子 + 推荐技巧
- `needs_iteration`: true 时必须继续改写
- `risk_analysis`: 三维度风险（句法25% / 词汇35% / AI痕迹40%）
- `preserve_terms`: 从 `references/domains.md` 提取的术语
- `synonym_suggestions`: 从 `references/synonyms.md` 提取的替换建议

### 知网规则

- 连续 13 字相同 = 抄袭（必须打破）
- 三元组重叠率 ≥ 20% = 风险

## 改写技巧

pipeline 会根据指标自动推荐，从以下技巧中选择：

- **句式重组** / **主被动转换** / **拆分长句** / **合并短句**
- **同义词替换** / **调整语序** / **增加修饰语** / **删除冗余**
- **因果倒置** / **条件重组**
- **四字词语重组** / **文言成分替换** / **把被字句转换**

## 核心约束

- 保留学术含义，不编造内容
- 专业术语必须保留（`references/domains.md`）
- 语句通顺，符合学术规范，不用口语

## 项目级数据存储

反馈数据存在项目目录 `.paper-rewriter/` 下，用 `--project <目录>` 指定项目根目录。

## 文档解析依赖

- Word: `uv pip install python-docx`
- PDF: `uv pip install PyMuPDF`

## 进阶（可选）

```bash
$PY scripts/rewrite_with_feedback.py suggest <学科> <强度>  # 获取建议
$PY scripts/similarity_calculator.py <原文> <改写文>          # 仅分析相似度
$PY scripts/rewrite_with_feedback.py report                   # 策略报告
```

## 自我学习机制

每次改写后，系统自动记录会话并学习有效策略。

### 改写前：获取历史建议

```bash
$PY scripts/rewrite_with_feedback.py suggest <学科> <强度>
```

返回的建议包含：
- **effective_techniques**：成功率 ≥ 60% 的技巧，优先使用
- **section_issues**：该章节的常见问题，避免重复犯错
- **preferred_vocabulary**：历史成功的替换对

### 改写后：记录会话

pipeline 自动调用 `record_rewrite_session`，记录：
- 原文 / 改写文 / 相似度指标
- 使用的技巧 / 学科 / 强度
- 自动评估结果（auto_evaluate）

### 自动评估

`auto_evaluate` 基于知网规则判定：
- `excellent`：连续匹配 < 8 字，三元组 < 10%
- `success`：连续匹配 < 13 字，三元组 < 20%
- `warning`：接近阈值但未超过
- `fail`：连续 ≥ 13 字或三元组 ≥ 20%

### 失败分类

`classify_failure` 细分失败原因：
- `consecutive_too_long`：连续匹配过长
- `structure_too_similar`：句式结构过于相似
- `trigram_risk`：三元组重叠率过高
- `mixed_risk`：多项指标接近阈值

### 策略报告

```bash
$PY scripts/rewrite_with_feedback.py report
```

查看历史改写的成功率、有效技巧、常见问题。
