"""
Turnitin 报告解析脚本
解析 Turnitin 颜色编码，识别高重复率段落
"""
from pathlib import Path
import re
from typing import Optional


def parse_turnitin_report(report_text: str) -> dict:
    """
    解析 Turnitin 报告

    参数:
        report_text: Turnitin 报告文本（支持纯文本或 HTML）

    返回:
        解析结果，包含各颜色段落
    """
    # 颜色编码定义
    color_codes = {
        "red": {"range": "25-49%", "priority": "HIGH", "description": "重度抄袭"},
        "orange": {"range": "50-74%", "priority": "MEDIUM", "description": "中度抄袭"},
        "yellow": {"range": "1-24%", "priority": "LOW", "description": "轻度抄袭"},
        "green": {"range": "citation", "priority": "CITATION", "description": "引用"},
        "blue": {"range": "0%", "priority": "NONE", "description": "无抄袭"}
    }

    # 初始化结果
    result = {
        "summary": {
            "total_sentences": 0,
            "red_count": 0,
            "orange_count": 0,
            "yellow_count": 0,
            "green_count": 0,
            "blue_count": 0
        },
        "paragraphs": {
            "red": [],
            "orange": [],
            "yellow": [],
            "green": [],
            "blue": []
        },
        "priority_report": []
    }

    # 按段落分割
    paragraphs = re.split(r'\n\s*\n', report_text)
    result["summary"]["total_paragraphs"] = len(paragraphs)

    for i, paragraph in enumerate(paragraphs):
        if not paragraph.strip():
            continue

        # 检测颜色标记
        color = detect_color(paragraph)
        if color:
            result["paragraphs"][color].append({
                "index": i + 1,
                "text": paragraph.strip(),
                "color": color,
                "priority": color_codes[color]["priority"]
            })
            result["summary"][f"{color}_count"] += 1

    # 生成优先级报告
    result["priority_report"] = generate_priority_report(result)

    return result


def detect_color(text: str) -> Optional[str]:
    """
    检测文本中的颜色标记（支持多种 Turnitin 报告格式）

    参数:
        text: 文本内容

    返回:
        颜色名称或 None
    """
    # ── 1. Turnitin HTML 格式（真实报告）──
    # CSS class: highlight-red, highlight__red, match-red, similarity-red 等
    class_patterns = {
        "red": r'class="[^"]*(?:highlight|match|similarity)[_-]?red[^"]*"',
        "orange": r'class="[^"]*(?:highlight|match|similarity)[_-]?orange[^"]*"',
        "yellow": r'class="[^"]*(?:highlight|match|similarity)[_-]?yellow[^"]*"',
        "green": r'class="[^"]*(?:highlight|match|similarity)[_-]?green[^"]*"',
        "blue": r'class="[^"]*(?:highlight|match|similarity)[_-]?blue[^"]*"',
    }
    for color, pattern in class_patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            return color

    # ── 2. 内联样式：background-color / color ──
    # 支持 hex (#ff0000, #f00), 命名色, rgb()
    inline_patterns = {
        "red": r'(?:background-)?color:\s*(?:red|#ff0000|#f00(?:000)?|rgb\s*\(\s*255)',
        "orange": r'(?:background-)?color:\s*(?:orange|#ffa500|#ff[89a][0-9a-f]{3})',
        "yellow": r'(?:background-)?color:\s*(?:yellow|#ffff00|#ff0|#ffee00)',
        "green": r'(?:background-)?color:\s*(?:green|#00[89a-f]000|#0f0)',
        "blue": r'(?:background-)?color:\s*(?:blue|#0000ff|#00f)',
    }
    for color, pattern in inline_patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            return color

    # ── 3. Turnitin 数字编号（1-6 对应不同颜色）──
    # 有些 Turnitin 导出用 data-color="1" 等
    num_match = re.search(r'data-color="(\d)"', text)
    if num_match:
        num_color_map = {"1": "red", "2": "orange", "3": "yellow", "4": "green", "5": "blue", "6": "blue"}
        return num_color_map.get(num_match.group(1))

    # ── 4. 纯文本标记 [RED], [ORANGE] 等 ──
    text_patterns = {
        "red": r'\[RED\]|\[红色\]',
        "orange": r'\[ORANGE\]|\[橙色\]',
        "yellow": r'\[YELLOW\]|\[黄色\]',
        "green": r'\[GREEN\]|\[绿色\]',
        "blue": r'\[BLUE\]|\[蓝色\]',
    }
    for color, pattern in text_patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            return color

    # ── 5. 基于相似度百分比推断 ──
    similarity_match = re.search(r'(\d+)%\s*(?:similarity|match|plagiarism)', text, re.IGNORECASE)
    if similarity_match:
        similarity = int(similarity_match.group(1))
        if 25 <= similarity <= 49:
            return "red"
        elif 50 <= similarity <= 74:
            return "orange"
        elif 1 <= similarity <= 24:
            return "yellow"
        elif similarity == 0:
            return "blue"

    return None


def generate_priority_report(result: dict) -> list:
    """
    生成优先级报告

    参数:
        result: 解析结果

    返回:
        优先级报告列表
    """
    report = []

    # 高优先级（红色）
    if result["paragraphs"]["red"]:
        report.append({
            "priority": "HIGH",
            "color": "red",
            "count": len(result["paragraphs"]["red"]),
            "description": "重度抄袭 - 必须彻底改写",
            "paragraphs": result["paragraphs"]["red"]
        })

    # 中优先级（橙色）
    if result["paragraphs"]["orange"]:
        report.append({
            "priority": "MEDIUM",
            "color": "orange",
            "count": len(result["paragraphs"]["orange"]),
            "description": "中度抄袭 - 需要改写",
            "paragraphs": result["paragraphs"]["orange"]
        })

    # 低优先级（黄色）
    if result["paragraphs"]["yellow"]:
        report.append({
            "priority": "LOW",
            "color": "yellow",
            "count": len(result["paragraphs"]["yellow"]),
            "description": "轻度抄袭 - 可选择性改写",
            "paragraphs": result["paragraphs"]["yellow"]
        })

    # 引用（绿色）
    if result["paragraphs"]["green"]:
        report.append({
            "priority": "CITATION",
            "color": "green",
            "count": len(result["paragraphs"]["green"]),
            "description": "引用 - 可保留不改",
            "paragraphs": result["paragraphs"]["green"]
        })

    # 无抄袭（蓝色）
    if result["paragraphs"]["blue"]:
        report.append({
            "priority": "NONE",
            "color": "blue",
            "count": len(result["paragraphs"]["blue"]),
            "description": "无抄袭 - 无需改写",
            "paragraphs": result["paragraphs"]["blue"]
        })

    return report


def format_turnitin_report(result: dict) -> str:
    """
    格式化 Turnitin 报告

    参数:
        result: 解析结果

    返回:
        格式化的报告文本
    """
    report = """
## Turnitin 报告分析

### 摘要
- 总段落数: {total_paragraphs}
- 🔴 高重复率 (25-49%): {red_count} 段
- 🟠 中重复率 (50-74%): {orange_count} 段
- 🟡 低重复率 (1-24%): {yellow_count} 段
- 🟢 引用: {green_count} 段
- 🔵 无抄袭: {blue_count} 段

### 优先级处理建议

{priority_sections}

### 处理顺序建议
1. 首先处理 🔴 高重复率段落（使用重度改写）
2. 然后处理 🟠 中重复率段落（使用中度改写）
3. 最后处理 🟡 低重复率段落（使用轻度改写）
4. 🟢 引用段落可保留不改
5. 🔵 无抄袭段落无需处理
"""

    # 生成优先级部分
    priority_sections = ""
    for item in result["priority_report"]:
        priority_sections += f"#### {item['priority']} - {item['description']}\n"
        priority_sections += f"- 段落数量: {item['count']}\n"
        priority_sections += "- 段落列表:\n"
        for para in item["paragraphs"][:5]:  # 最多显示5个
            text_preview = para["text"][:100] + "..." if len(para["text"]) > 100 else para["text"]
            priority_sections += f"  - 段落 {para['index']}: {text_preview}\n"
        if len(item["paragraphs"]) > 5:
            priority_sections += f"  - ... 还有 {len(item['paragraphs']) - 5} 个段落\n"
        priority_sections += "\n"

    return report.format(
        total_paragraphs=result["summary"]["total_paragraphs"],
        red_count=result["summary"]["red_count"],
        orange_count=result["summary"]["orange_count"],
        yellow_count=result["summary"]["yellow_count"],
        green_count=result["summary"]["green_count"],
        blue_count=result["summary"]["blue_count"],
        priority_sections=priority_sections
    )


def get_intensity_for_color(color: str) -> str:
    """
    根据颜色获取改写强度

    参数:
        color: 颜色名称

    返回:
        改写强度
    """
    intensity_map = {
        "red": "heavy",
        "orange": "medium",
        "yellow": "light",
        "green": "none",
        "blue": "none"
    }
    return intensity_map.get(color, "medium")
