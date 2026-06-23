# AIGC-rewriter-zh 架构级重构设计

日期：2026-06-23
状态：已批准
范围：`.claude/skills/AIGC-rewriter-zh/`

---

## 1. 背景与目标

AIGC-rewriter-zh 是一个中文论文降 AIGC 率 Skill，通过 5 维度分析（句法、词汇、AI 痕迹、中文特化、结构）检测高风险段落，指导 Claude 改写以降低 AIGC 检测率。

当前存在三类结构性问题：

- **检测准确率**：成语检测仅 8 个后缀硬编码、被字句正则误报多、段首检测过短、句长分析重复计算
- **执行效率**：反馈学习系统两套并存（`patterns/learned.json` + `feedback/strategies.json`）、每段改写需 4 次 subprocess
- **可用性**：不支持 .docx、SKILL.md 充斥内联代码、无学科术语保护

本次重构目标：合并学习系统、新增 Python 规则引擎、调优分析参数、精简 SKILL.md、支持 .docx。

---

## 2. 整体架构

### 2.1 目录结构

```
AIGC-rewriter-zh/
├── SKILL.md              ← 精简指令（~120 行，流程 + 约束 + 参考资料索引）
├── analyze.py            ← 分析 CLI 入口（保持不变）
├── rewrite_cli.py        ← 新增：分析 + 规则改写 CLI
├── feedback_cli.py       ← 简化：只操作 learned.json（suggest/changes/learn/report）
├── analyzer/             ← 分析引擎（调参优化，不改结构）
│   ├── syntax.py
│   ├── vocabulary.py
│   ├── ai_traces.py
│   ├── chinese.py
│   ├── structure.py
│   ├── paragraphs.py
│   ├── patterns.py       ← PatternLibrary（扩展 learned 管理）
│   └── scorer.py
├── rewriter/             ← 新增：规则改写引擎
│   ├── rules.py          ← 规则替换（套话、连接词、成语、被字句）
│   ├── style.py          ← 句式调整（了字、的字嵌套、句长变化）
│   └── verify.py         ← 准确性验证（扩展连续匹配检测）
├── patterns/             ← 模式库
│   ├── builtin.json
│   ├── user.json
│   ├── learned.json      ← 唯一学习存储（合并 strategies）
│   └── config.json       ← 新增：维度权重等可配置参数
├── references/           ← 新增：外置参考资料
│   ├── techniques.md     ← 改写技巧详情 + 示例
│   ├── issue_actions.md  ← issue type → 改写动作映射
│   ├── domains.md        ← 学科术语保护表
│   └── edge_cases.md     ← 边界情况处理
├── utils/
│   └── text.py
└── tests/
```

### 2.2 数据流

```
用户输入（文本 / .txt / .md / .docx）
  │
  ▼
feedback_cli.py suggest → 获取历史建议（推荐技巧、强度、术语保护）
  │
  ▼
rewrite_cli.py rewrite → Python 规则替换（套话/连接词/成语/被字句/段首去重）
  │                     → 内部调用 verify.py 做准确性检查
  │                     → 输出：规则改写文本 + remaining_issues + changes + 验证结果
  ▼
  ┌─ remaining_issues 为空 ──→ 直接进入学习
  │
  └─ remaining_issues 不为空 ──→ Claude 语义改写（句式重组/主被动/语气调整）
                                → 输出变更记录 JSON
  ▼
rewrite_cli.py analyze → 改写后风险分
  │
  ▼
feedback_cli.py changes → 记录变更到 session
feedback_cli.py learn   → 自动判定 success/fail → 更新 learned.json
  │
  ▼
下次改写时 suggest 可获取更新后的建议
```

注：`analyze.py` 保持独立（向后兼容），`rewrite_cli.py` 内部调用其 `analyze_text()` 函数，不重复实现分析逻辑。

### 2.3 删除的模块

| 文件/目录 | 原因 |
|-----------|------|
| `feedback_system.py` | 核心逻辑迁入 `PatternLibrary` |
| `feedback/learning/strategies.json` | 合并到 `patterns/learned.json` |
| `feedback/sessions/*.json`（旧文件） | 清空旧 session，新格式从零开始 |

保留 `feedback/sessions/` 目录结构，用于存储新格式的 session 记录。

---

## 3. CLI 设计

两个脚本，各司其职。

### 3.1 `rewrite_cli.py`（分析 + 规则改写）

```
rewrite_cli.py <command> [args]

子命令：
  analyze   <文件|--text "..."> [--threshold N] [--platform cnki]
  rewrite   <文件> [--platform cnki] [--intensity medium]
```

**`analyze` 子命令**：调用现有分析引擎，输出 JSON 风险报告。支持 .txt/.md/.docx。

**`rewrite` 子命令**：先调用 analyze 获取风险报告，再对高风险段落执行 Python 规则替换。`--intensity` 为用户指定的基础值（light/medium/heavy），实际执行强度会与学习系统 `intensity_adjustments` 的乘数叠加：`effective = base × multiplier`。

输出格式：

```json
{
  "analysis": { "overall_risk": 0.72, "paragraphs": [...] },
  "rewritten_text": "...",
  "changes": [
    {"type": "cliche_replace", "original": "综上所述", "rewritten": "从整体来看"},
    {"type": "connector_reduce", "original": "因此，", "rewritten": ""}
  ],
  "remaining_issues": [
    {"index": 0, "type": "low_burstiness", "detail": "..."},
    {"index": 1, "type": "no_personal_voice", "detail": "..."}
  ],
  "needs_claude_rewrite": true
}
```

`needs_claude_rewrite` 判断逻辑：

```python
SEMANTIC_ISSUES = {"low_burstiness", "no_personal_voice", "too_fluent",
                   "uniform_sentence_length", "deep_nesting", "excessive_parallelism"}
needs_claude = any(i["type"] in SEMANTIC_ISSUES for i in remaining_issues)
```

### 3.2 `feedback_cli.py`（学习系统）

```
feedback_cli.py <command> [args]

子命令：
  suggest   [--domain 学科] [--intensity medium]
  changes   <session_id> '<变更JSON>'
  learn     <session_id>
  report
```

**`suggest`**：返回推荐技巧、强度调整、词汇偏好、学科术语保护名单。

**`changes`**：将 Claude 语义改写的变更记录写入 session。

**`learn`**：读取 session，基于风险分变化自动判定，更新 `learned.json`。

**`report`**：输出学习策略报告（Markdown 格式）。

### 3.3 自动评估标准

基于 AIGC 风险分变化，替代用户打分：

| 判定 | 条件 | 动作 |
|------|------|------|
| `excellent` | 风险分降低 ≥ 0.3 | 记为成功，略微降低强度 |
| `success` | 风险分降低 0.1–0.3 | 记为成功 |
| `warning` | 风险分降低 < 0.1 | 记为失败，加强改写力度 |
| `fail` | 风险分不降反升 | 标记顽固 pattern，换策略 |

### 3.4 Session 记录结构

存储在 `feedback/sessions/<session_id>.json`：

```json
{
  "session_id": "2026-06-23-a1b2c3d4",
  "timestamp": "2026-06-23T16:00:00",
  "domain": "建筑能耗",
  "intensity": "medium",
  "original_text": "...(前200字)",
  "rewritten_text": "...(前200字)",
  "risk_before": 0.72,
  "risk_after": 0.35,
  "risk_reduction": 0.37,
  "auto_evaluation": {"verdict": "excellent", "score": 90, "reason": "风险分降低0.37"},
  "techniques_used": ["cliche_replace", "sentence_restructure"],
  "changes_made": [
    {"type": "cliche_replace", "original": "综上所述", "rewritten": "从整体来看"},
    {"type": "句式重组", "original": "...", "rewritten": "..."}
  ]
}
```

---

## 4. 分析引擎优化

在现有 5 维度架构上做参数调优，不改结构。

### 4.1 成语检测（`chinese.py`）

**现状**：8 个后缀硬编码，漏报严重。

**改进**：内置高频 AI 成语表（~50 个）+ 后缀兜底。

```python
AI_IDIOMS = {
    "举足轻重", "相辅相成", "不可或缺", "日益突出", "不可否认",
    "不容忽视", "息息相关", "层出不穷", "与时俱进", "实事求是",
    "有的放矢", "统筹兼顾", "因势利导", "推陈出新", "标本兼治",
    # ... 从 builtin.json idiom 类型 + 常见 AI 高频词提取，约 50 个
}

def detect_idioms(text: str) -> tuple[int, list[str]]:
    """查表检测 AI 高频成语，返回 (命中数, 命中列表)。"""
    found = [w for w in AI_IDIOMS if w in text]
    return len(found), found
```

阈值调整：密度 > 0.05（每 200 字 1 个）才报 issue。

### 4.2 "被…所…"检测（`chinese.py`）

**现状**：正则 `被[^。，！？]{0,20}所` 会误匹配"被认为是一种…所有"。

**改进**：排除干扰模式。

```python
BEI_SUO = re.findall(r'被[^。，！？]{0,20}所(?!有|在|谓|以)', text)
BEI_SUO = [m for m in BEI_SUO if '。' not in m and '，' not in m]
```

### 4.3 段首检测（`structure.py`）

**现状**：只看前 5 字，误报多。

**改进**：前 10 字 + 排除常见学术开头。

```python
COMMON_STARTS = {"本文", "研究", "通过", "基于", "在", "随着", "为了"}
prefixes = [s[:10] for s in first_sentences if len(s) >= 10
            and s[:4] not in COMMON_STARTS]
```

### 4.4 句长分析去重

**现状**：`syntax.py`（变异系数）和 `ai_traces.py`（连续相似）都分析句长。

**改进**：句长相关分析统一到 `syntax.py`，`ai_traces.py` 只保留 `too_fluent` 和 `no_personal_voice`。

### 4.5 权重配置外置（`patterns/config.json`）

```json
{
  "dimension_weights": {
    "syntax": 0.2,
    "vocabulary": 0.3,
    "ai_traces": 0.25,
    "chinese": 0.25
  },
  "structure_cap": 0.15,
  "section_thresholds": {
    "abstract": 0.25,
    "introduction": 0.3,
    "method": 0.35,
    "results": 0.3,
    "discussion": 0.25,
    "conclusion": 0.3,
    "related_work": 0.4,
    "body": 0.3
  }
}
```

`scorer.py` 读取此文件，有默认值兜底。

---

## 5. Python 规则改写引擎

新增 `rewriter/` 目录，处理可规则化的替换任务。

### 5.1 职责划分

| 层 | 负责 | 具体操作 |
|---|------|---------|
| Python 规则 | 确定性替换 | 套话替换、连接词削减、成语直白化、被字句改写、段首去重、了字减少、的字拆分 |
| Claude 语义 | 需要理解语境 | 句式重组、长短句调整、主被动互换、语气调整、段落重组、突发性制造 |

### 5.2 模块设计

**`rules.py`**：接收文本 + issues，按 issue type 执行替换。

```python
def apply_rules(text: str, issues: list, patterns: list, platform: str = None) -> tuple[str, list]:
    """执行规则替换，返回 (改写后文本, 变更记录)。"""
    changes = []
    result = text
    for issue in issues:
        match issue["type"]:
            case "cliche_detected":
                result, c = replace_cliches(result, patterns, platform)
                changes.extend(c)
            case "connector_overuse":
                result, c = reduce_connectors(result)
                changes.extend(c)
            case "idiom_overuse":
                result, c = simplify_idioms(result, patterns)
                changes.extend(c)
            case "bei_suo_pattern":
                result, c = rewrite_bei_suo(result)
                changes.extend(c)
            case "uniform_para_start":
                result, c = diversify_starts(result)
                changes.extend(c)
    return result, changes
```

**`style.py`**：句式层面的轻量调整。

```python
def adjust_style(text: str, issues: list, intensity: str = "medium") -> tuple[str, list]:
    """句式风格调整，返回 (改写后文本, 变更记录)。"""
    changes = []
    result = text
    for issue in issues:
        match issue["type"]:
            case "excessive_le":
                result, c = reduce_le_particles(result)
                changes.extend(c)
            case "de_nesting":
                result, c = break_de_nesting(result)
                changes.extend(c)
            case "uniform_sentence_length":
                result, c = vary_sentence_length(result, intensity)
                changes.extend(c)
    return result, changes
```

**`verify.py`**：保留现有 `verify_accuracy()`，增加连续匹配检测。

```python
def check_consecutive_match(original: str, rewritten: str, max_len: int = 13) -> list:
    """检查改写后是否有连续 max_len 字与原文相同。"""
```

### 5.3 套话替换逻辑

从 `builtin.json` 的 `replacements` 中选择替换词。优先使用 `learned.json` 中 `vocabulary_preferences` 成功率高的替换对。

---

## 6. 学习系统合并

### 6.1 合并方案

**删除**：`feedback_system.py`、`feedback/learning/` 目录

**扩展 `patterns/learned.json`** 为唯一学习存储：

```json
{
  "patterns": [],
  "protected_terms": [],
  "success_strategies": [],
  "technique_effectiveness": {
    "cliche_replace": {"success": 0, "total": 0},
    "connector_reduce": {"success": 0, "total": 0},
    "sentence_restructure": {"success": 0, "total": 0}
  },
  "vocabulary_preferences": {
    "综上所述→从整体来看": {"success": 3}
  },
  "intensity_adjustments": {
    "light": {"multiplier": 1.0},
    "medium": {"multiplier": 1.0},
    "heavy": {"multiplier": 1.0}
  },
  "domain_stats": {},
  "session_count": 0,
  "total_risk_reduction": 0.0,
  "last_updated": ""
}
```

### 6.2 `PatternLibrary` 扩展

在现有 `patterns.py` 中增加方法：

- `record_session(session: dict)` — 记录会话并自动学习
- `get_suggestions(domain, intensity)` — 获取改写建议
- `get_strategy_report()` — 生成策略报告

### 6.3 冷启动

`learned.json` 初始模板预置空结构。`suggest` 在无数据时返回默认策略 + 提示信息。

---

## 7. SKILL.md 重构

### 7.1 目标

从 ~270 行压缩到 ~120 行。外置参考资料到 `references/`。

### 7.2 新结构

```
SKILL.md
├── 流程骨架（6 步，含分支）
├── 模式（交互/半自动/全自动）
├── 约束（5 条）
├── 错误处理表
└── 参考资料索引表

references/
├── techniques.md       ← 改写技巧 + 示例
├── issue_actions.md    ← issue type → 改写动作映射
├── domains.md          ← 学科术语保护表
└── edge_cases.md       ← 边界情况
```

### 7.3 流程分支

```
Python 规则替换
  ├── remaining_issues 为空 → 直接验证
  └── remaining_issues 不为空 → Claude 语义改写 → 验证
```

### 7.4 Claude 语义改写变更记录

SKILL.md 中要求 Claude 在语义改写后输出变更记录 JSON，通过 `feedback_cli.py changes` 写入 session。

### 7.5 错误处理表（SKILL.md 内容）

| 场景 | 处理 |
|------|------|
| 文件不存在或路径错误 | 提示用户检查路径，不继续执行 |
| 不支持的文件格式 | 提示"支持 .txt/.md/.docx"，建议转换 |
| python-docx 未安装 | 提示安装命令，降级为纯文本提取 |
| 分析引擎执行失败 | 降级为纯改写（无量化指标），提示用户 |
| 改写后风险分不降反升 | 回退原文，换策略重试一次 |
| 迭代 3 轮仍未达标 | 标记"需人工处理"，继续其他段落 |
| 用户指令无法识别 | 提示可用指令列表 |

### 7.6 `analyze.py` CLI 变更

删除 `--learn-stubborn` 和 `--learn-success` 参数，学习功能统一由 `feedback_cli.py learn` 完成。删除后 `main()` 中增加提示：

```python
if args.learn_stubborn or args.learn_success:
    print("[提示] 学习功能已迁移到 feedback_cli.py，请使用:", file=sys.stderr)
    print("  $PY feedback_cli.py learn <session_id>", file=sys.stderr)
    sys.exit(1)
```

---

## 8. .docx 支持

### 8.1 依赖

`python-docx`，加到 `pyproject.toml`。

### 8.2 输入处理

```python
if path.suffix == ".docx":
    from docx import Document
    doc = Document(path)
    text = "\n".join(p.text for p in doc.paragraphs)
elif path.suffix in (".txt", ".md"):
    text = path.read_text(encoding="utf-8")
```

### 8.3 输出处理（全自动模式）

保留原格式，替换段落文本，输出 `<原文件名>_rewritten.docx`。

### 8.4 降级

`python-docx` 未安装时，提示用户安装，降级为纯文本提取。

---

## 9. 测试策略

| 模块 | 现有测试 | 需新增 |
|------|---------|--------|
| analyzer/ | 7 个测试文件 | 调参后的阈值测试 |
| rewriter/ | 无 | `test_rules.py`、`test_style.py` |
| rewriter/verify | `test_rewriter.py` | 连续匹配检测测试 |
| feedback_cli.py | `test_feedback.py` | 需重写：测试 PatternLibrary 新方法 + CLI 子命令（suggest/changes/learn/report） |
| rewrite_cli.py | 无 | 集成测试：analyze → rewrite 完整流程 |
| .docx | 无 | 读取 → 分析 → 输出测试 |

---

## 10. 迁移计划

分 5 步，每步可独立验证。

| 步骤 | 内容 | 验证 |
|------|------|------|
| Step 1 | 合并学习系统：扩展 learned.json，迁移 feedback_system.py 逻辑到 PatternLibrary，更新 feedback_cli.py，删除 analyze.py 的 --learn-* 参数，清空旧 feedback/sessions/ | 现有测试通过 |
| Step 2 | 新增规则引擎：创建 rewriter/rules.py + style.py，创建 rewrite_cli.py | 新测试通过 |
| Step 3 | 分析引擎调参：成语检测、被字句、段首、句长去重、权重外置 | 阈值测试通过 |
| Step 4 | SKILL.md 重构 + references/：外置参考资料，重写 SKILL.md | 端到端走通 |
| Step 5 | .docx 支持：输入读取 + 输出写入 | .docx 输入输出测试 |
