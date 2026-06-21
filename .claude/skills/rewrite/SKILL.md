---
name: rewrite
description: 中文论文降 AIGC 率处理工具
---

# 降 AIGC 率 Skill

降低中文学术论文的 AIGC 检测率。核心思路：Python 做检测仪，Claude 做手术刀，模式库做参考手册。

## 调用方式

分析引擎脚本位于 `.claude/skills/rewrite/analyze.py`，通过 Bash 工具调用：

```bash
$PY .claude/skills/rewrite/analyze.py <文件路径>                    # 文件分析
$PY .claude/skills/rewrite/analyze.py --text "文本内容"             # 直接传入文本
$PY .claude/skills/rewrite/analyze.py <文件路径> --output result.json  # 输出到文件
$PY .claude/skills/rewrite/analyze.py <文件路径> --threshold 0.2     # 自定义阈值
```

返回 JSON 格式的分析结果，Claude 根据结果决定改写策略。

## 运行模式

### 交互模式（默认）

当用户调用 `/rewrite` 且未指定 `--file` 时进入。

1. 提示用户粘贴需要处理的段落
2. 调用 `$PY analyze.py --text "用户粘贴的文本"` 分析风险
3. 根据风险分选择改写策略，执行改写
4. 输出改写结果 + 风险分变化
5. 等待下一段落或指令

**交互指令：**
- `重来` / `再来一次`：对上一段重新改写
- `太激进了` / `保守点`：切换为轻度改写
- `再大胆些`：切换为深度改写
- `换风格 xxx`：切换风格（academic/narrative/technical）
- `/done`：结束会话，输出汇总

### 半自动模式

当用户指定 `--file` 但未指定 `--mode auto` 时进入。

1. 读取文件，调用分析引擎生成风险报告
2. 输出高风险段落列表（按优先级排序）
3. 用户选择要处理的段落
4. 逐段改写并输出结果

### 全自动模式

当用户指定 `--file` 和 `--mode auto` 时进入。

1. 读取文件
2. 预检：提取专业术语，展示保护名单供用户确认
3. 调用分析引擎生成风险报告
4. 按优先级逐段改写（每段独立迭代至阈值以下）
5. 准确性验证，标记可疑项
6. 用户确认后写入 `<原文件名>_rewritten.md`
7. 生成 `<原文件名>_diff.md` 和 `<原文件名>_analysis.json`

## 改写约束

1. **术语保护**：`patterns/user.json` 和 `patterns/builtin.json` 中的 `protected_terms` 不可替换
2. **含义保真**：语义不得偏离原文，允许表述方式变化，不允许内容增删
3. **学术语气**：从"AI 标准体"变成"真人学术体"，不是口语化
4. **公式/表格/引用**：跳过，只处理正文文字
5. **每段独立迭代**：各段独立判断是否达到阈值

## 改写策略

根据风险分选择策略：
- 0.3–0.5（轻度）：替换连接词、调整语序、打破并列结构
- 0.5–0.7（中度）：长短句拆合、主被动互换、插入过渡句
- 0.7+（深度）：段落重组、增加主观标记、引入非典型论证节奏

## 改写风格

- `academic`（默认）：正式学术语气
- `narrative`：叙述性风格，适合建筑学交叉方向
- `technical`：紧凑技术风格，适合 CS/AI 方向

## 章节阈值

| 章节 | 默认阈值 |
|------|---------|
| 摘要 | 0.25 |
| 引言 | 0.3 |
| 方法 | 0.35 |
| 结果 | 0.3 |
| 讨论 | 0.25 |
| 结论 | 0.3 |
| 相关工作 | 0.4 |

## 错误处理

- 单段处理失败不阻塞全文
- 改写后风险分不降反升 → 回退原文，换策略重试一次
- 分析引擎失败 → 降级为纯 prompt 改写
- 迭代 3 轮未达阈值 → 标记为"需人工处理"

## 使用方式

```
/rewrite                          # 交互模式
/rewrite --file paper.md          # 半自动模式
/rewrite --file paper.md --mode auto  # 全自动模式
/rewrite --style technical        # 指定风格
/rewrite --threshold 0.2          # 自定义阈值
/done                             # 结束交互模式
```
