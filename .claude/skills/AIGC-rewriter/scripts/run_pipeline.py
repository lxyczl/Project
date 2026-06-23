"""
AIGC-rewriter Unified Pipeline Entry

Two modes:
  analyze  — analyze original text, output risk report + rewrite suggestions (for Claude to use)
  verify   — compare original vs rewritten, output similarity + risk change + feedback

Usage:
  python run_pipeline.py analyze <filepath> [--platform turnitin] [--threshold 0.3]
  python run_pipeline.py analyze --text "text content"
  python run_pipeline.py verify <original_file> <rewritten_file> [--section body] [--techniques cliche_replace]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ── Project paths ──────────────────────────────────────────
SKILL_DIR = Path(__file__).parent.parent  # project root
SCRIPTS_DIR = Path(__file__).parent       # scripts directory
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


# ── Subcommand: analyze ──────────────────────────────────
def cmd_analyze(args) -> dict:
    """Analyze original text, output risk report + rewrite suggestions."""
    # 1. Read text
    if args.text:
        original = args.text
    else:
        original = _read_file(args.file)

    if not original.strip():
        return {"error": "Input text is empty"}

    # 2. Risk analysis
    analysis = analyze_text(
        original,
        is_markdown=False,
        threshold=getattr(args, "threshold", None),
        patterns_dir=SKILL_DIR / "patterns",
        no_learn=False,
        platform=getattr(args, "platform", "turnitin"),
    )

    # 3. Reference document suggestions
    domains = load_domains()
    synonyms = load_synonyms()
    preserve_terms = get_domain_preserve_terms(original, domains)
    domain_replacements = get_domain_replacements(original, domains)
    synonym_suggestions = get_synonym_suggestions(original, synonyms)

    # 4. Feedback system suggestions
    fs = FeedbackSystem()
    suggestions = fs.get_rewrite_suggestions(
        section_type="body",
        intensity="medium",
    )

    # 5. Generate per-paragraph rewrite guides (merge with original text)
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
        # Mark protected terms found in this paragraph
        para_text = text_by_index.get(para["index"], "")
        guide["preserve_terms_in_para"] = [
            t for t in preserve_terms if t in para_text
        ]
        # Mark available replacements
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
        "platform": analysis.get("platform", "turnitin"),
    }


# ── Subcommand: verify ───────────────────────────────────
def cmd_verify(args) -> dict:
    """Compare original vs rewritten, output similarity + risk change + feedback."""
    original = _read_file(args.original)
    rewritten = _read_file(args.rewritten)

    if not original.strip() or not rewritten.strip():
        return {"error": "Input text is empty"}

    # 1. Similarity analysis
    sim_metrics = calculate_similarity(original, rewritten)
    sim_report = format_report(original, rewritten)
    consecutive = find_consecutive_matches(original, rewritten, CONSECUTIVE_WARNING)
    hotspots = find_sentence_level_matches(original, rewritten, threshold=0.5)

    # Suggest techniques for hotspot sentences
    for h in hotspots:
        h["suggested_techniques"] = suggest_techniques({
            "max_consecutive": h["max_consecutive"],
            "trigram_overlap": h["trigram_overlap"],
        })

    # 2. Risk score comparison
    patterns_dir = SKILL_DIR / "patterns"
    analysis_before = analyze_text(original, is_markdown=False, threshold=None, patterns_dir=patterns_dir)
    analysis_after = analyze_text(rewritten, is_markdown=False, threshold=None, patterns_dir=patterns_dir)
    risk_before = analysis_before.get("overall_risk", 0)
    risk_after = analysis_after.get("overall_risk", 0)

    # 3. Feedback recording
    section_type = getattr(args, "section", "body")
    techniques_used = getattr(args, "techniques", None)
    if isinstance(techniques_used, str):
        techniques_used = techniques_used.split()

    intensity = getattr(args, "intensity", "medium")

    # Collect issues
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

    # 4. Evaluation result
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


# ── Formatted output ───────────────────────────────────────
def format_analyze_output(result: dict) -> str:
    """Format analyze result as readable report."""
    lines = ["# AIGC Risk Analysis Report\n"]

    lines.append(f"**Overall Risk**: {result['overall_risk']:.2f}")
    lines.append(f"**Paragraphs**: {result['paragraph_count']}, of which {result['high_risk_count']} high-risk\n")

    # Protected terms
    if result.get("preserve_terms"):
        lines.append("## Protected Terms (cannot be replaced)")
        lines.append(", ".join(result["preserve_terms"]))
        lines.append("")

    # Per-paragraph
    lines.append("## Paragraph Analysis (sorted by priority)\n")
    sorted_paras = sorted(result["paragraphs"], key=lambda x: x["priority"], reverse=True)
    for p in sorted_paras:
        risk_icon = "🔴" if p["risk"] > 0.5 else "🟡" if p["risk"] > p["threshold"] else "🟢"
        lines.append(f"### Paragraph {p['index']} {risk_icon} Risk {p['risk']:.2f} (threshold {p['threshold']:.2f})")
        lines.append(f"- Section type: {p['section_type']}")

        if p["issues"]:
            lines.append("- Issues:")
            for issue in p["issues"]:
                lines.append(f"  - [{issue['type']}] {issue['detail']}")
        if p.get("suggestion"):
            lines.append(f"- Suggestion: {p['suggestion']}")
        if p.get("preserve_terms_in_para"):
            lines.append(f"- Protected terms in paragraph: {', '.join(p['preserve_terms_in_para'])}")
        if p.get("available_replacements"):
            lines.append("- Available replacements:")
            for src, targets in p["available_replacements"].items():
                lines.append(f"  - {src} → {', '.join(targets)}")
        lines.append("")

    # Feedback suggestions
    fb = result.get("feedback_suggestions", {})
    if fb.get("effective_techniques"):
        lines.append("## Historically Effective Techniques")
        for tech in fb["effective_techniques"]:
            lines.append(f"- {tech['technique']}: success rate {tech['success_rate']:.0%} ({tech.get('total', tech.get('count', 0))} times)")
        lines.append("")

    return "\n".join(lines)


def format_verify_output(result: dict) -> str:
    """Format verify result as readable report."""
    lines = ["# Rewrite Verification Report\n"]

    # Risk change
    lines.append("## Risk Score Change")
    lines.append(f"- Before: {result['risk_before']:.2f}")
    lines.append(f"- After: {result['risk_after']:.2f}")
    lines.append(f"- Reduction: {result['risk_reduction']:.2f}")

    verdict = result["verdict"]
    verdict_icon = {"excellent": "🏆", "success": "✅", "partial": "🟡", "marginal": "⚠️", "fail": "❌"}.get(verdict, "❓")
    lines.append(f"- Verdict: {verdict_icon} {verdict}")
    if result.get("failure_type"):
        lines.append(f"- Failure type: {result['failure_type']}")
    lines.append("")

    # Similarity report
    lines.append(result.get("similarity_report", ""))

    # Consecutive matches
    if result.get("consecutive_matches"):
        lines.append("\n## Long Consecutive Matches")
        for i, m in enumerate(result["consecutive_matches"], 1):
            lines.append(f"{i}. Position {m['start_orig']}: \"{m['text']}\" ({m['length']} words)")
        lines.append("")

    # Hotspot sentences
    if result.get("hotspot_sentences"):
        lines.append("\n## High-Similarity Sentence Hotspots")
        for h in result["hotspot_sentences"]:
            lines.append(f"- **Similarity {h['similarity_score']:.0%}** ({h['max_consecutive']} consecutive words)")
            lines.append(f"  - Original: {h['original_sentence'][:80]}...")
            lines.append(f"  - Rewritten: {h['rewritten_sentence'][:80]}...")
            if h.get("suggested_techniques"):
                lines.append(f"  - Suggested techniques: {', '.join(h['suggested_techniques'])}")
        lines.append("")

    return "\n".join(lines)


# ── Utility functions ──────────────────────────────────────
def _read_file(path_str: str) -> str:
    """Read file, supports .txt / .md / .docx / .pdf formats."""
    from utils.doc_parser import read_document
    text, _suffix = read_document(path_str)
    return text


# ── CLI entry ──────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AIGC-rewriter Pipeline: Analyze + Verify",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # analyze
    p_analyze = sub.add_parser("analyze", help="Analyze original text risk")
    p_analyze.add_argument("file", nargs="?", help="Input file path")
    p_analyze.add_argument("--text", help="Direct text input")
    p_analyze.add_argument("--platform", default="turnitin", help="Detection platform (turnitin/gptzero)")
    p_analyze.add_argument("--threshold", type=float, help="Risk threshold override")

    # verify
    p_verify = sub.add_parser("verify", help="Verify rewrite quality")
    p_verify.add_argument("original", help="Original file path")
    p_verify.add_argument("rewritten", help="Rewritten file path")
    p_verify.add_argument("--section", default="body", help="Section type")
    p_verify.add_argument("--techniques", nargs="*", help="Techniques used")
    p_verify.add_argument("--intensity", default="medium", help="Rewrite intensity")

    return parser


def main():
    # Windows terminal UTF-8 output
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
        print(f"[Error] {result['error']}", file=sys.stderr)
        sys.exit(1)

    # Formatted output to stdout
    if args.command == "analyze":
        print(format_analyze_output(result))
    else:
        print(format_verify_output(result))

    # JSON output to stderr (for programmatic consumption)
    json_result = {k: v for k, v in result.items() if k not in ("similarity_report",)}
    print(json.dumps(json_result, ensure_ascii=False, indent=2), file=sys.stderr)


if __name__ == "__main__":
    main()
