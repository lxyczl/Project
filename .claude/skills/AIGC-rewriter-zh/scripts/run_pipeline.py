"""
AIGC-rewriter-zh 统一 Pipeline 入口

两种模式：
  analyze  — 分析原文，输出风险报告 + 改写建议（供 Claude 改写用）
  verify   — 对比原文与改写文，输出相似度 + 风险变化 + 反馈记录

用法:
  python run_pipeline.py analyze <文件路径> [--platform cnki] [--threshold 0.3]
  python run_pipeline.py analyze --text "文本内容"
  python run_pipeline.py verify <原文文件> <改写文件> [--section body] [--techniques cliche_replace]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ── 项目路径 ──────────────────────────────────────────────
SKILL_DIR = Path(__file__).parent.parent  # 项目根目录
SCRIPTS_DIR = Path(__file__).parent       # scripts 目录
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from analyze import analyze_text
from utils.similarity import (
    calculate_similarity,
    find_consecutive_matches,
    find_sentence_level_matches,
    format_report,
    suggest_techniques,
    CONSECUTIVE_WARNING,
)
from utils.reference_loader import (
    get_domain_preserve_terms,
    get_domain_replacements,
    get_synonym_suggestions,
    load_domains,
    load_synonyms,
)
from feedback_system import FeedbackSystem


# ── 子命令：analyze ──────────────────────────────────────
def cmd_analyze(args) -> dict:
    """分析原文，输出风险报告 + 改写建议。"""
    # 1. 读取文本
    if args.text:
        original = args.text
    else:
        original = _read_file(args.file)

    if not original.strip():
        return {"error": "输入文本为空"}

    # 2. 风险分析
    analysis = analyze_text(
        original,
        is_markdown=False,
        threshold=getattr(args, "threshold", None),
        patterns_dir=SKILL_DIR / "patterns",
        no_learn=False,
        platform=getattr(args, "platform", "cnki"),
    )

    # 3. 参考文档建议
    domains = load_domains()
    synonyms = load_synonyms()
    preserve_terms = get_domain_preserve_terms(original, domains)
    domain_replacements = get_domain_replacements(original, domains)
    synonym_suggestions = get_synonym_suggestions(original, synonyms)

    # 4. 反馈系统建议
    fs = FeedbackSystem()
    suggestions = fs.get_rewrite_suggestions(
        section_type="body",
        intensity="medium",
    )

    # 5. 按段落生成改写建议（合并段落原文）
    from analyzer.paragraphs import split_paragraphs
    raw_paragraphs = split_paragraphs(original, is_markdown=False)
    text_by_index = {p["index"]: p["text"] for p in raw_paragraphs}

    paragraph_guides = []
    for para in analysis.get("paragraphs", []):
        guide = {
            "index": para["index"],
            "risk": para["risk"],
            "priority": para["priority"],
            "section_type": para.get("section_type", "body"),
            "issues": para["issues"],
            "suggestion": para.get("suggestion", ""),
            "threshold": para.get("threshold", 0.3),
        }
        # 为每个段落标注涉及的保护术语
        para_text = text_by_index.get(para["index"], "")
        guide["preserve_terms_in_para"] = [
            t for t in preserve_terms if t in para_text
        ]
        # 标注可用的替换词
        guide["available_replacements"] = {
            k: v for k, v in {**domain_replacements, **synonym_suggestions}.items()
            if k in para_text
        }
        paragraph_guides.append(guide)

    return {
        "mode": "analyze",
        "overall_risk": analysis.get("overall_risk", 0),
        "paragraph_count": len(analysis.get("paragraphs", [])),
        "high_risk_count": sum(
            1 for p in analysis.get("paragraphs", [])
            if p["risk"] > p.get("threshold", 0.3)
        ),
        "paragraphs": paragraph_guides,
        "preserve_terms": preserve_terms,
        "domain_replacements": domain_replacements,
        "synonym_suggestions": synonym_suggestions,
        "feedback_suggestions": suggestions,
        "platform": analysis.get("platform", "cnki"),
    }


# ── 子命令：verify ───────────────────────────────────────
def cmd_verify(args) -> dict:
    """对比原文与改写文，输出相似度 + 风险变化 + 反馈记录。"""
    original = _read_file(args.original)
    rewritten = _read_file(args.rewritten)

    if not original.strip() or not rewritten.strip():
        return {"error": "输入文本为空"}

    # 1. 相似度分析
    sim_metrics = calculate_similarity(original, rewritten)
    sim_report = format_report(original, rewritten)
    consecutive = find_consecutive_matches(original, rewritten, CONSECUTIVE_WARNING)
    hotspots = find_sentence_level_matches(original, rewritten, threshold=0.5)

    # 为热点句子推荐技巧
    for h in hotspots:
        h["suggested_techniques"] = suggest_techniques({
            "max_consecutive": h["max_consecutive"],
            "trigram_overlap": h["trigram_overlap"],
        })

    # 2. 风险分对比
    patterns_dir = SKILL_DIR / "patterns"
    analysis_before = analyze_text(original, is_markdown=False, threshold=None, patterns_dir=patterns_dir)
    analysis_after = analyze_text(rewritten, is_markdown=False, threshold=None, patterns_dir=patterns_dir)
    risk_before = analysis_before.get("overall_risk", 0)
    risk_after = analysis_after.get("overall_risk", 0)

    # 3. 反馈记录
    section_type = getattr(args, "section", "body")
    techniques_used = getattr(args, "techniques", None)
    if isinstance(techniques_used, str):
        techniques_used = techniques_used.split()

    intensity = getattr(args, "intensity", "medium")

    # 收集 issues
    issues_before = []
    issues_after = []
    for p in analysis_before.get("paragraphs", []):
        issues_before.extend(i["type"] for i in p.get("issues", []))
    for p in analysis_after.get("paragraphs", []):
        issues_after.extend(i["type"] for i in p.get("issues", []))

    fs = FeedbackSystem()
    session = fs.record_session(
        original_text=original,
        rewritten_text=rewritten,
        risk_before=risk_before,
        risk_after=risk_after,
        section_type=section_type,
        techniques_used=techniques_used,
        issues_before=issues_before,
        issues_after=issues_after,
        intensity=intensity,
    )

    # 4. 评估结果
    auto_eval = session.get("auto_evaluation", {})
    failure_type = session.get("failure_type")

    return {
        "mode": "verify",
        "similarity": sim_metrics,
        "similarity_report": sim_report,
        "consecutive_matches": consecutive,
        "hotspot_sentences": hotspots,
        "risk_before": round(risk_before, 3),
        "risk_after": round(risk_after, 3),
        "risk_reduction": round(risk_before - risk_after, 3),
        "verdict": auto_eval.get("verdict", "unknown"),
        "is_success": auto_eval.get("is_success", False),
        "failure_type": failure_type,
        "session_id": session.get("session_id"),
        "issues_before": issues_before,
        "issues_after": issues_after,
    }


# ── 格式化输出 ───────────────────────────────────────────
def format_analyze_output(result: dict) -> str:
    """将 analyze 结果格式化为可读报告。"""
    lines = ["# AIGC 风险分析报告\n"]

    lines.append(f"**总体风险分**: {result['overall_risk']:.2f}")
    lines.append(f"**段落数**: {result['paragraph_count']}，其中高风险 {result['high_risk_count']} 段\n")

    # 保护术语
    if result.get("preserve_terms"):
        lines.append("## 保护术语（不可替换）")
        lines.append("、".join(result["preserve_terms"]))
        lines.append("")

    # 按段落
    lines.append("## 段落分析（按优先级排序）\n")
    sorted_paras = sorted(result["paragraphs"], key=lambda x: x["priority"], reverse=True)
    for p in sorted_paras:
        risk_icon = "🔴" if p["risk"] > 0.5 else "🟡" if p["risk"] > p["threshold"] else "🟢"
        lines.append(f"### 段落 {p['index']} {risk_icon} 风险 {p['risk']:.2f} (阈值 {p['threshold']:.2f})")
        lines.append(f"- 章节类型: {p['section_type']}")

        if p["issues"]:
            lines.append("- 问题:")
            for issue in p["issues"]:
                lines.append(f"  - [{issue['type']}] {issue['detail']}")
        if p.get("suggestion"):
            lines.append(f"- 建议: {p['suggestion']}")
        if p.get("preserve_terms_in_para"):
            lines.append(f"- 涉及保护术语: {'、'.join(p['preserve_terms_in_para'])}")
        if p.get("available_replacements"):
            lines.append("- 可用替换:")
            for src, targets in p["available_replacements"].items():
                lines.append(f"  - {src} → {'、'.join(targets)}")
        lines.append("")

    # 反馈建议
    fb = result.get("feedback_suggestions", {})
    if fb.get("effective_techniques"):
        lines.append("## 历史有效技巧")
        for tech in fb["effective_techniques"]:
            lines.append(f"- {tech['technique']}: 成功率 {tech['success_rate']:.0%} ({tech.get('total', tech.get('count', 0))}次)")
        lines.append("")

    return "\n".join(lines)


def format_verify_output(result: dict) -> str:
    """将 verify 结果格式化为可读报告。"""
    lines = ["# 改写验证报告\n"]

    # 风险变化
    lines.append("## 风险分变化")
    lines.append(f"- 改写前: {result['risk_before']:.2f}")
    lines.append(f"- 改写后: {result['risk_after']:.2f}")
    lines.append(f"- 降低幅度: {result['risk_reduction']:.2f}")

    verdict = result["verdict"]
    verdict_icon = {"excellent": "🏆", "success": "✅", "partial": "🟡", "marginal": "⚠️", "fail": "❌"}.get(verdict, "❓")
    lines.append(f"- 评估结果: {verdict_icon} {verdict}")
    if result.get("failure_type"):
        lines.append(f"- 失败类型: {result['failure_type']}")
    lines.append("")

    # 相似度报告
    lines.append(result.get("similarity_report", ""))

    # 连续匹配
    if result.get("consecutive_matches"):
        lines.append("\n## 超长连续匹配")
        for i, m in enumerate(result["consecutive_matches"], 1):
            lines.append(f"{i}. 位置 {m['start_orig']}: \"{m['text']}\" ({m['length']} 字)")
        lines.append("")

    # 热点句子
    if result.get("hotspot_sentences"):
        lines.append("\n## 高相似度句子热点")
        for h in result["hotspot_sentences"]:
            lines.append(f"- **相似度 {h['similarity_score']:.0%}** (连续 {h['max_consecutive']} 字)")
            lines.append(f"  - 原文: {h['original_sentence'][:80]}...")
            lines.append(f"  - 改写: {h['rewritten_sentence'][:80]}...")
            if h.get("suggested_techniques"):
                lines.append(f"  - 推荐技巧: {'、'.join(h['suggested_techniques'])}")
        lines.append("")

    return "\n".join(lines)


# ── 工具函数 ─────────────────────────────────────────────
def _read_file(path_str: str) -> str:
    """读取文件，支持 .txt / .md / .docx / .pdf 格式。"""
    from utils.doc_parser import read_document
    text, _suffix = read_document(path_str)
    return text


# ── CLI 入口 ─────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AIGC-rewriter-zh Pipeline: 分析 + 验证",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # analyze
    p_analyze = sub.add_parser("analyze", help="分析原文风险")
    p_analyze.add_argument("file", nargs="?", help="输入文件路径")
    p_analyze.add_argument("--text", help="直接传入文本")
    p_analyze.add_argument("--platform", default="cnki", help="检测平台 (cnki/weipu)")
    p_analyze.add_argument("--threshold", type=float, help="风险阈值覆盖")

    # verify
    p_verify = sub.add_parser("verify", help="验证改写质量")
    p_verify.add_argument("original", help="原文文件路径")
    p_verify.add_argument("rewritten", help="改写文件路径")
    p_verify.add_argument("--section", default="body", help="章节类型")
    p_verify.add_argument("--techniques", nargs="*", help="使用的技巧列表")
    p_verify.add_argument("--intensity", default="medium", help="改写强度")

    return parser


def main():
    # Windows 终端 UTF-8 输出
    import io
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    parser = build_parser()
    args = parser.parse_args()

    if args.command == "analyze":
        result = cmd_analyze(args)
    elif args.command == "verify":
        result = cmd_verify(args)
    else:
        parser.print_help()
        sys.exit(1)

    if "error" in result:
        print(f"[错误] {result['error']}", file=sys.stderr)
        sys.exit(1)

    # 格式化输出到 stdout
    if args.command == "analyze":
        print(format_analyze_output(result))
    else:
        print(format_verify_output(result))

    # JSON 输出到 stderr（供程序化消费）
    json_result = {k: v for k, v in result.items() if k not in ("similarity_report",)}
    print(json.dumps(json_result, ensure_ascii=False, indent=2), file=sys.stderr)


if __name__ == "__main__":
    main()
