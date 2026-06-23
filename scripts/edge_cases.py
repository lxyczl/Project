"""
边界情况检测
在 pipeline 中提前识别边界情况并给出建议
"""
import re


def detect_edge_cases(text: str) -> list[dict]:
    """检测文本的边界情况，返回 [{type, message, severity, skip_rewrite}]"""
    issues = []
    text_stripped = text.strip()
    char_count = len(text_stripped)

    # 1. 短文本（少于50字）
    if char_count < 50:
        issues.append({
            "type": "short_text",
            "message": f"文本过短（{char_count}字），改写效果有限，建议提供至少50字的段落",
            "severity": "warning",
            "skip_rewrite": False,
        })

    # 2. 纯英文文本
    chinese_chars = len(re.findall(r"[一-鿿]", text_stripped))
    if chinese_chars == 0 and char_count > 0:
        issues.append({
            "type": "pure_english",
            "message": "纯英文文本，本技能仅支持中文学术文本",
            "severity": "error",
            "skip_rewrite": True,
        })

    # 3. 非学术文本
    colloquial = ["我觉得", "我认为", "其实", "反正", "yyds", "绝绝子", "666", "太好用了"]
    found_colloquial = [w for w in colloquial if w in text_stripped]
    if found_colloquial:
        issues.append({
            "type": "non_academic",
            "message": f"检测到非学术表达（{', '.join(found_colloquial[:3])}），本技能专为学术论文设计",
            "severity": "warning",
            "skip_rewrite": False,
        })

    # 4. 超长文本（超过1000字）
    if char_count > 1000:
        issues.append({
            "type": "long_text",
            "message": f"文本较长（{char_count}字），建议分段改写以保证质量",
            "severity": "info",
            "skip_rewrite": False,
        })

    # 5. 大量公式/引用
    formula_count = len(re.findall(r"\$.*?\$", text_stripped))
    citation_count = len(re.findall(r"\[\d+\]", text_stripped))
    if formula_count + citation_count > 5:
        issues.append({
            "type": "formulas_citations",
            "message": f"文本包含{formula_count}个公式和{citation_count}个引用，改写空间有限",
            "severity": "info",
            "skip_rewrite": False,
        })

    # 6. 术语密集（英文术语占比高）
    english_terms = len(re.findall(r"[A-Za-z]{3,}", text_stripped))
    if english_terms > 10 and chinese_chars > 0:
        ratio = english_terms / (english_terms + chinese_chars)
        if ratio > 0.3:
            issues.append({
                "type": "term_dense",
                "message": f"术语密集（{english_terms}个英文术语），改写空间有限",
                "severity": "info",
                "skip_rewrite": False,
            })

    # 7. 直接引语
    quotes = re.findall(r'[""「」].*?[""「」]', text_stripped)
    if len(quotes) > 2:
        issues.append({
            "type": "direct_quotes",
            "message": f"文本包含{len(quotes)}处直接引语，引语部分不能改写",
            "severity": "info",
            "skip_rewrite": False,
        })

    return issues


def should_skip_rewrite(issues: list[dict]) -> bool:
    """根据边界情况判断是否应该跳过改写"""
    return any(issue.get("skip_rewrite") for issue in issues)


def format_edge_case_report(issues: list[dict]) -> str:
    """格式化边界情况报告"""
    if not issues:
        return ""

    severity_icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}
    lines = ["## 边界情况检测"]
    for issue in issues:
        icon = severity_icon.get(issue["severity"], "")
        lines.append(f"   {icon} [{issue['type']}] {issue['message']}")
    return "\n".join(lines)
