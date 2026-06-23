# English Academic Paper Rewriter

Claude Code skill for rewriting English academic papers to reduce similarity scores (Turnitin, iThenticate, etc.).

## Features

- **Risk analysis engine**: 4-dimension analysis (syntax, vocabulary, AI traces, English-specific) with 17 risk types
- **Pattern library**: 50+ built-in rules for cliche phrases, connectors, verbose expressions
- **15 rewriting techniques** across 3 tiers (see SKILL.md for details)
- **3 intensity levels**: Light (词汇替换), Medium (词汇+结构), Heavy (完全重组)
- **20 academic domains** with domain-specific terminology protection
- **Similarity calculator**: LCS + N-gram + consecutive match detection
- **Turnitin report parsing**: Auto-detect high-priority sections
- **Feedback learning system**: Learns from user feedback to improve over time

## Quick Start

**直接发文本：**
```
帮我改写这段英文论文：[粘贴文本]
```

**给文件：**
```
帮我改写这个论文的摘要：E:\Desktop\paper.docx
```

**指定选项：**
```
请用中等强度改写这段生态水文领域的论文摘要：[粘贴文本]
```

## File Structure

```
paper-rewriter/
├── SKILL.md                    # 核心技能指令（Claude 读取）
├── README.md                   # 本文件
├── analyze.py                  # 分析引擎 CLI 入口
├── analyzer/                   # 分析引擎
│   ├── syntax.py               # 句法分析（句长、被动语态、嵌套）
│   ├── vocabulary.py           # 词汇分析（TTR、连接词、套话）
│   ├── ai_traces.py            # AI 痕迹检测（流畅度、突发性、个人表达）
│   ├── english.py              # 英文特征（冠词、模糊限定、名词化）
│   ├── structure.py            # 结构分析（段落长度、段首模式）
│   ├── paragraphs.py           # 段落切分与章节识别
│   ├── patterns.py             # 模式库加载器
│   └── scorer.py               # 综合评分与优先级排序
├── patterns/                   # 模式库
│   ├── builtin.json            # 内置规则（50+ 条）
│   ├── user.json               # 用户自定义（可选）
│   └── learned.json            # 自动积累（可选）
├── references/                 # 参考资料
│   ├── domains.md              # 20个学科的专业词汇表
│   ├── examples.md             # 改写示例
│   ├── techniques.md           # 改写技巧详解
│   ├── synonyms.md             # 同义词替换表
│   ├── edge_cases.md           # 边界情况处理
│   └── advanced.md             # 高级功能说明
├── scripts/                    # 辅助脚本
│   ├── document_parser.py      # 文档解析（docx/pdf）
│   ├── similarity_calculator.py # 相似度计算
│   ├── rewrite_with_feedback.py # 反馈入口
│   ├── feedback_system.py      # 反馈记录 & 学习
│   └── turnitin_parser.py      # Turnitin 报告解析
├── feedback/                   # 反馈数据
│   ├── sessions/               # 改写会话记录
│   └── learning/               # 学习到的策略
└── tests/                      # 测试
    ├── test_basic.py           # 单元测试
    ├── test_analyzer.py        # 分析引擎测试
    ├── test_real_paper.py      # 真实论文测试
    ├── test_feedback_system.py # 反馈系统测试
    ├── test_real_feedback.py   # 反馈集成测试
    └── test_complete_workflow.py # 完整工作流测试
```

## Intensity Levels

| 级别 | 做法 | 适用场景 |
|------|------|---------|
| 🟢 Light | 主要同义词替换，不改结构 | 低相似度 (<25%) |
| 🟡 Medium | 同义词+结构调整 | 中等相似度 (25-50%) |
| 🔴 Heavy | 完全重组，使用所有技巧 | 高相似度 (>50%) |

## Supported Domains

生态水文 | 土木水利 | 绿色建筑 | 建筑节能 | 水利工程 | 土木工程 | BIPV | 光伏 | 生态安全格局 | SHAP分析 | 地下水脆弱性 | 生态系统服务 | 半干旱区耦合 | InVEST模型 | 改进DRASTIC | 电路理论 | OWA算法 | 生态源地 | 生态廊道 | 生态阻力面

完整词汇表见 `references/domains.md`。

## Running Tests

```bash
$PY -m pytest tests/ -v
```

## More Info

- 改写技巧和示例 → `references/techniques.md`, `references/examples.md`
- 高级功能（Turnitin 解析、反馈学习） → `references/advanced.md`
- 边界情况处理 → `references/edge_cases.md`
- 同义词表 → `references/synonyms.md`
