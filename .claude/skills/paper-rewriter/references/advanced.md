# Advanced Features Reference

This document describes the advanced features of the Paper Rewriter skill.

## Table of Contents

1. [Risk Analysis Engine](#risk-analysis-engine)
2. [Turnitin Report Parsing](#turnitin-report-parsing)
3. [Feedback Collection and Learning](#feedback-collection-and-learning)
4. [Batch Processing](#batch-processing)

---

## Risk Analysis Engine

Analyze text for AIGC detection risk before rewriting. The engine evaluates 4 dimensions and produces actionable risk scores.

### Architecture

```
analyze.py (CLI)
    analyzer/
    ├── syntax.py        # 句长方差、被动语态、并列结构、从句嵌套
    ├── vocabulary.py    # TTR、连接词频率、套话检测（50+ 规则）
    ├── ai_traces.py     # 流畅度、突发性、个人表达、句首模式
    ├── english.py       # 冠词过度、模糊限定、名词化、冗长短语
    ├── structure.py     # 段落长度方差、段首模式（全文级）
    ├── paragraphs.py    # 段落切分、章节识别
    ├── patterns.py      # 模式库加载器（builtin/user/learned）
    └── scorer.py        # 四维度加权评分 + 章节优先级
```

### 4 Dimensions

| 维度 | 权重 | 检测内容 |
|------|------|----------|
| Syntax | 0.20 | 句长方差、被动语态、并列结构、从句嵌套 |
| Vocabulary | 0.30 | TTR、连接词、套话/模板化表达 |
| AI Traces | 0.25 | 流畅度、突发性、个人表达、句首模式 |
| English | 0.25 | 冠词过度、模糊限定、名词化、冗长短语 |

### 17 Risk Types

Syntax: `uniform_sentence_length`, `excessive_passive`, `excessive_parallelism`, `deep_nesting`
Vocabulary: `low_ttr`, `connector_overuse`, `cliche_detected`
AI Traces: `too_fluent`, `low_burstiness`, `no_personal_voice`, `monotonous_openings`
English: `excessive_the`, `excessive_hedging`, `excessive_nominalization`, `verbose_phrases`
Structure: `uniform_para_length`, `uniform_para_start`

### Usage

```bash
# 分析文本
$PY analyze.py --text "Your text here"

# 分析文件
$PY analyze.py input.txt

# 输出到文件
$PY analyze.py input.txt -o result.json

# 学习顽固 pattern（改写后仍存在的）
$PY analyze.py --learn-stubborn comparison.json

# 记录成功改写策略
$PY analyze.py --learn-success comparison.json
```

### Output Format

```json
{
  "overall_risk": 0.45,
  "paragraphs": [
    {
      "index": 0,
      "risk": 0.52,
      "priority": 0.57,
      "section_type": "introduction",
      "issues": [
        {"type": "cliche_detected", "detail": "Cliche phrases detected: in recent years"},
        {"type": "connector_overuse", "detail": "Connector frequency 5/8=0.6, too high"}
      ],
      "suggestion": "Replace connectors and cliche phrases; Enrich vocabulary"
    }
  ]
}
```

### Pattern Library

模式库存储在 `patterns/` 目录：
- `builtin.json` — 内置规则（50+ 条），包含套话、连接词、冗长短语、句式模板
- `user.json` — 用户自定义规则（可选）
- `learned.json` — 自动积累的顽固 pattern 和成功策略（可选）

每条规则格式：
```json
{"id": "cliche_001", "type": "cliche", "match": "in recent years", "replacements": ["recently", "over the past decade"]}
```

---

## Turnitin Report Parsing

Parse Turnitin reports to identify high-priority sections. The skill automatically parses Turnitin reports when provided.

### Supported Formats

- HTML reports with CSS class or inline style color coding
- Text reports with `[RED]`, `[ORANGE]` etc. markers
- Percentage-based similarity indicators

### Color Codes

| Color | Similarity | Priority | Action |
|-------|------------|----------|--------|
| 🔴 Red | 25-49% | HIGH | Must rewrite thoroughly |
| 🟠 Orange | 50-74% | MEDIUM | Rewrite as needed |
| 🟡 Yellow | 1-24% | LOW | Minor adjustments |
| 🟢 Green | Citation | CITATION | Keep as-is |
| 🔵 Blue | 0% | NONE | No changes needed |

### Intensity Mapping

- Red sections → Heavy intensity
- Orange sections → Medium intensity
- Yellow sections → Light intensity

### Usage

```bash
# 从文件解析
$PY scripts/turnitin_parser.py <report_file>

# Python API
from turnitin_parser import parse_turnitin_report
result = parse_turnitin_report(report_html)
```

---

## Feedback Collection and Learning

Collect user feedback to improve rewriting quality over time.

### How It Works

1. Each rewrite session is recorded with metrics (LCS, n-gram, consecutive matches)
2. User provides feedback (vocabulary, structure, terminology, overall scores)
3. System learns from feedback and updates strategies
4. Next rewrite applies learned suggestions

### Feedback Dimensions

- **Vocabulary score** (1-5): Quality of word replacements
- **Structure score** (1-5): Sentence restructuring quality
- **Terminology score** (1-5): Professional term preservation
- **Overall score** (1-5): General satisfaction

### What Gets Learned

- `preferred_vocabulary`: Word replacement pairs that received high scores
- `effective_techniques`: Rewriting techniques with ≥70% success rate
- `intensity_multiplier`: Adjustment factor based on feedback trends
- `new_terms_to_preserve`: Domain terms reported by users
- `domain_patterns`: Common issues per academic domain

### Usage

```bash
# 获取建议（改写前）
$PY scripts/rewrite_with_feedback.py suggest [domain] [intensity]

# 分析改写结果（改写后）
$PY scripts/rewrite_with_feedback.py analyze <original_file> <rewritten_file> [domain] [intensity]

# 提交反馈
$PY scripts/rewrite_with_feedback.py feedback <session_id> <vocab> <structure> <terminology> <overall>

# 查看策略报告
$PY scripts/rewrite_with_feedback.py report
```

### Feedback Storage

```
feedback/
├── sessions/              # 改写会话记录（每个会话一个 JSON 文件）
│   └── 2026-06-20-<id>.json
└── learning/
    └── strategies.json    # 学习到的策略（自动更新）
```

---

## Batch Processing

Process multiple paragraphs or complete sections.

### Workflow

1. **Extract text** from document: `$PY scripts/document_parser.py <file> [section]`
2. **Get suggestions** for the domain: `$PY scripts/rewrite_with_feedback.py suggest <domain>`
3. **Rewrite each paragraph** applying suggestions
4. **Analyze each rewrite**: `$PY scripts/rewrite_with_feedback.py analyze ...`
5. **Collect feedback** after reviewing results

### Tips

- Process sections (Abstract, Introduction, Methods, etc.) separately
- Maintain terminology consistency across paragraphs
- Use the same intensity level within a section
- Review the similarity report before moving to the next section
