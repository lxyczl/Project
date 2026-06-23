# AIGC-rewriter-zh

中文论文降 AIGC 率处理工具。针对知网、维普等平台的 AIGC 检测，通过五维度风险分析识别 AI 生成痕迹，并提供针对性改写建议。

## 目录结构

```
AIGC-rewriter-zh/
├── SKILL.md                    # 核心流程（Claude 读取的入口）
├── README.md                   # 本文件
│
├── scripts/                    # 核心脚本（6个）
│   ├── run_pipeline.py         #   统一 Pipeline 入口（analyze + verify）
│   ├── run_evals.py            #   评估运行器
│   ├── analyze.py              #   风险分析 CLI
│   ├── feedback_cli.py         #   反馈系统 CLI
│   ├── feedback_system.py      #   反馈学习核心
│   └── edge_cases.py           #   边界情况检测
│
├── analyzer/                   # 五维度风险分析引擎（8模块）
│   ├── scorer.py
│   ├── syntax.py
│   ├── vocabulary.py
│   ├── ai_traces.py
│   ├── chinese.py
│   ├── structure.py
│   ├── paragraphs.py
│   └── patterns.py
│
├── rewriter/                   # 改写辅助
│   ├── context.py
│   ├── diff.py
│   └── verify.py
│
├── utils/                      # 工具模块
│   ├── similarity.py           #   相似度计算
│   ├── reference_loader.py     #   参考文档加载器
│   └── text.py
│
├── references/                 # 参考文档（5个）
│   ├── domains.md              #   19 学科词汇
│   ├── synonyms.md             #   140 同义词
│   ├── techniques.md           #   15 种改写技巧
│   ├── chinese-specific.md     #   10 种中文技巧
│   └── edge_cases.md           #   边界规则
│
├── patterns/                   # 模式库
│   ├── builtin.json
│   ├── user.json
│   └── learned.json
│
├── feedback/                   # 反馈数据
│   ├── learning/strategies.json
│   └── sessions/
│
├── evals/                      # 评估用例
│   └── evals.json              #   6 个评估基准（6/6 通过）
│
└── tests/                      # 单元测试（181 个）
    └── ...（14 个测试文件）
```

## 快速使用

支持输入格式：`.txt` / `.md` / `.docx` / `.pdf`（文字型）。输出仍为 `.txt` 或 `.md`。

### 分析模式

分析原文风险，输出改写建议：

```bash
$PY scripts/run_pipeline.py analyze --text "综上所述，本研究通过深入分析..."
$PY scripts/run_pipeline.py analyze 论文.docx
$PY scripts/run_pipeline.py analyze 论文.pdf --platform cnki --threshold 0.2
```

### 验证模式

对比原文与改写文，输出相似度 + 风险变化：

```bash
$PY scripts/run_pipeline.py verify 原文.txt 改写.txt
$PY scripts/run_pipeline.py verify 原文.txt 改写.txt --techniques cliche_replace connector_replace
```

### 评估

运行评估基准：

```bash
$PY scripts/run_evals.py
```

### 单独模块

```bash
# 风险分析
$PY scripts/analyze.py --text "文本内容"
$PY scripts/analyze.py 文件路径

# 相似度计算
$PY utils/similarity.py 原文.txt 改写.txt

# 反馈系统
$PY scripts/feedback_cli.py suggest --section body --intensity medium
$PY scripts/feedback_cli.py record --original "原文" --rewritten "改写" --risk-before 0.8 --risk-after 0.2
$PY scripts/feedback_cli.py report
```

## 五维度风险分析

| 维度 | 权重 | 检测内容 |
|------|------|---------|
| 词汇 | 0.30 | 套话、连接词过密、TTR 低 |
| AI 痕迹 | 0.25 | 过度流畅、缺少主观表达 |
| 中文特化 | 0.25 | "了"字过多、"的"字嵌套、"被...所..."句式 |
| 句法 | 0.20 | 句长均匀、并列过多、嵌套过深 |
| 结构 | +0.15 | 段落长度均匀、段首句模式重复 |

## 反馈系统

- **自动评估**：5 级判定（fail/marginal/partial/success/excellent）
- **失败分类**：7 种失败类型，针对性建议
- **技巧组合**：跟踪 2 元素技巧组合的成功率
- **自适应学习率**：连续失败加大步长，连续成功减小步长
- **针对性建议**：根据 failure_type 和历史 pattern 生成

## 参考文档

- `domains.md`：19 个学科（CS/AI、机器学习、三维重建、建筑能耗、生态水文等）的专业术语和替换词
- `synonyms.md`：140 条通用学术同义词，按动词/名词/形容词/副词/连接词分类
- `techniques.md`：15 种改写技巧，含示例和组合技
- `chinese-specific.md`：10 种中文独特技巧（四字词语、文言成分、量词替换等）
- `edge_cases.md`：边界情况处理规则（短文本、非学术、公式引用等）
