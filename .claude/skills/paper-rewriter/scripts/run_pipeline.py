"""
One-click analysis pipeline: original + rewritten → similarity → hotspot → auto-evaluate → iteration hint

Usage:
  $PY run_pipeline.py <original_file> <rewritten_file> [domain] [intensity] [--project <dir>]
  $PY run_pipeline.py --stdin [domain] [intensity]  (read JSON from stdin: {"original": "...", "rewritten": "..."})

Supported formats: .txt, .docx, .pdf
"""
import sys
import json
from pathlib import Path

# Add scripts/ and skill root to path
_skill_root = Path(__file__).resolve().parent.parent
_scripts_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_scripts_dir))
sys.path.insert(0, str(_skill_root))


def _read_file(path: Path) -> str:
    """Read text from .txt, .docx, or .pdf files."""
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return path.read_text(encoding="utf-8")
    elif suffix in (".docx", ".pdf"):
        from document_parser import parse_document, get_text_for_rewrite
        result = parse_document(str(path))
        if "error" in result:
            print(f"Error parsing {path.name}: {result['error']}", file=sys.stderr)
            sys.exit(1)
        return get_text_for_rewrite(result)
    else:
        print(f"Error: unsupported file format: {suffix}", file=sys.stderr)
        sys.exit(1)

from similarity_calculator import calculate_similarity, format_report, find_sentence_level_matches
from feedback_system import FeedbackSystem, auto_evaluate, classify_failure


# ── Analyzer integration ───────────────────────────────────────────

def run_analyzer(text: str) -> dict:
    """Run all analyzer modules on the rewritten text."""
    from analyzer.syntax import analyze_syntax
    from analyzer.vocabulary import analyze_vocabulary
    from analyzer.english import analyze_english
    from analyzer.ai_traces import analyze_ai_traces
    from analyzer.patterns import PatternLibrary

    lib = PatternLibrary()
    patterns = lib.get_patterns()

    syntax = analyze_syntax(text)
    vocab = analyze_vocabulary(text, patterns)
    english = analyze_english(text)
    ai = analyze_ai_traces(text)

    # Collect all issues
    all_issues = []
    for module_name, result in [("syntax", syntax), ("vocabulary", vocab),
                                 ("english", english), ("ai_traces", ai)]:
        for issue in result.get("issues", []):
            issue["module"] = module_name
            all_issues.append(issue)

    # Overall analyzer score (average of module scores)
    scores = [syntax["score"], vocab["score"], english["score"], ai["score"]]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 100.0

    return {
        "overall_score": avg_score,
        "syntax": syntax,
        "vocabulary": vocab,
        "english": english,
        "ai_traces": ai,
        "all_issues": all_issues,
    }


# ── Technique suggestion ───────────────────────────────────────────

def _suggest_techniques(sentence_metrics: dict) -> list[str]:
    """Suggest rewrite techniques based on sentence-level metrics."""
    mc = sentence_metrics.get("max_consecutive", 0)
    tri = sentence_metrics.get("trigram_overlap", 0)

    if mc >= 8:
        return ["voice_conversion", "clause_insertion", "word_order_change"]
    elif mc >= 5:
        return ["voice_conversion", "synonym_replacement"]
    elif tri >= 0.25:
        return ["synonym_replacement", "word_order_change", "clause_insertion"]
    else:
        return ["synonym_replacement", "word_order_change"]


# ── Core pipeline ──────────────────────────────────────────────────

def run(original: str, rewritten: str, domain: str = "general",
        intensity: str = "medium", project_dir: Path = None) -> dict:
    """Core pipeline: input original + rewritten, return full analysis result."""

    # 1. Similarity analysis
    similarity = calculate_similarity(original, rewritten)

    # 2. Analyzer on rewritten text
    analyzer_result = run_analyzer(rewritten)

    # 3. Auto evaluation
    evaluation = auto_evaluate(similarity)

    # 4. Failure classification
    failure_type = classify_failure(similarity, evaluation["verdict"])

    # 5. Sentence-level hotspots
    hot_sentences = find_sentence_level_matches(original, rewritten, threshold=0.5)
    for sent in hot_sentences:
        sent["suggested_techniques"] = _suggest_techniques(sent)

    # 6. Feedback system (store in project dir if specified)
    if project_dir:
        feedback_dir = project_dir / ".paper-rewriter"
        feedback_dir.mkdir(parents=True, exist_ok=True)
        fs = FeedbackSystem(feedback_dir)
    else:
        fs = FeedbackSystem()

    session = fs.record_rewrite_session(
        original_text=original,
        rewritten_text=rewritten,
        domain=domain,
        intensity=intensity,
    )

    # 7. Get historical suggestions
    suggestions = fs.get_rewrite_suggestions(domain, intensity, current_metrics=similarity)

    # 8. Determine if iteration is needed
    needs_iteration = (
        evaluation["verdict"] == "fail" or
        (evaluation["verdict"] == "warning" and len(hot_sentences) > 0)
    )

    # 9. Section-specific threshold check
    section_thresholds = {
        "abstract": 50, "introduction": 60, "methods": 70,
        "results": 70, "discussion": 60, "default": 65,
    }
    threshold = section_thresholds.get(domain, section_thresholds["default"])
    over_threshold = similarity["composite_score"] > threshold

    report_text = format_report(original, rewritten)

    return {
        "session_id": session["session_id"],
        "similarity": similarity,
        "analyzer": analyzer_result,
        "evaluation": evaluation,
        "failure_type": failure_type,
        "hot_sentences": hot_sentences,
        "needs_iteration": needs_iteration,
        "over_threshold": over_threshold,
        "threshold": threshold,
        "suggestions": suggestions,
        "report": report_text,
    }


# ── Output formatting ──────────────────────────────────────────────

def format_output(result: dict) -> str:
    """Format a concise report for Claude to read."""
    ev = result["evaluation"]
    sim = result["similarity"]
    hot = result["hot_sentences"]
    sug = result["suggestions"]
    ana = result["analyzer"]

    lines = []

    # Evaluation verdict
    lines.append(f"## Evaluation: {ev['verdict'].upper()} ({sim['composite_score']}/100)")
    lines.append(f"   {ev['reason']}")
    if result["failure_type"] != "none":
        lines.append(f"   Failure type: {result['failure_type']}")
    lines.append("")

    # Key metrics
    lines.append("## Key Metrics")
    lines.append(f"   Consecutive match: {sim['max_consecutive']} words (threshold: 8)")
    lines.append(f"   Trigram precision: {sim['trigram_precision']:.1%} (warning: ≥30%)")
    if sim.get("content_word_overlap") is not None:
        lines.append(f"   Content word overlap: {sim['content_word_overlap']:.1%}")
    lines.append(f"   Token mode: {sim.get('token_mode', 'word')}")
    lines.append(f"   Section threshold: {result['threshold']} (score: {sim['composite_score']})")
    lines.append("")

    # Analyzer issues (only if there are notable issues)
    ana_issues = [i for i in ana["all_issues"] if i.get("severity") in ("high", "medium")]
    if ana_issues:
        lines.append(f"## Analyzer Issues ({len(ana_issues)} notable)")
        for issue in ana_issues[:6]:
            lines.append(f"   [{issue['module']}] {issue['type']}: {issue.get('detail', '')}")
        lines.append("")

    # Hot sentences
    if hot:
        lines.append(f"## Hot Sentences ({len(hot)} need rework)")
        for i, s in enumerate(hot[:5], 1):
            techniques = ", ".join(s.get("suggested_techniques", []))
            orig = s['original_sentence'][:60]
            lines.append(f"   {i}. {orig}...")
            lines.append(f"      Similarity: {s['similarity_score']:.1%}, consecutive: {s['max_consecutive']}w")
            lines.append(f"      Suggested: {techniques}")
        lines.append("")

    # Historical suggestions
    if sug.get("effective_techniques"):
        lines.append("## Effective Techniques (from history)")
        for t in sug["effective_techniques"][:5]:
            lines.append(f"   - {t['technique']} ({t['success_rate']:.0%})")
        lines.append("")

    if sug.get("targeted_advice"):
        lines.append("## Targeted Advice")
        for a in sug["targeted_advice"]:
            lines.append(f"   - {a}")
        lines.append("")

    if sug.get("effective_combinations"):
        lines.append("## Effective Combinations")
        for c in sug["effective_combinations"][:3]:
            lines.append(f"   - {c['combination']} ({c['success_rate']:.0%})")
        lines.append("")

    # Iteration hint
    if result["needs_iteration"]:
        lines.append(">>> NEEDS ITERATION: rework hot sentences and re-analyze <<<")
    else:
        lines.append(">>> PASSED: no iteration needed <<<")

    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    # Parse --project
    project_dir = None
    if "--project" in args:
        idx = args.index("--project")
        if idx + 1 < len(args):
            project_dir = Path(args[idx + 1])
            args = args[:idx] + args[idx + 2:]
        else:
            print("Error: --project requires a directory argument")
            sys.exit(1)

    domain = "general"
    intensity = "medium"

    if args[0] == "--stdin":
        data = json.loads(sys.stdin.read())
        original = data["original"]
        rewritten = data["rewritten"]
        if len(args) > 1:
            domain = args[1]
        if len(args) > 2:
            intensity = args[2]
    else:
        if len(args) < 2:
            print("Error: need original and rewritten file paths")
            sys.exit(1)
        orig_file, rew_file = Path(args[0]), Path(args[1])
        for fpath, label in [(orig_file, "original"), (rew_file, "rewritten")]:
            if not fpath.exists():
                print(f"Error: {label} file not found: {fpath}")
                sys.exit(1)
        original = _read_file(orig_file)
        rewritten = _read_file(rew_file)
        if len(args) > 2:
            domain = args[2]
        if len(args) > 3:
            intensity = args[3]

    result = run(original, rewritten, domain, intensity, project_dir)

    # Print concise report to stdout
    print(format_output(result))

    # Print JSON summary to stderr for programmatic use
    json_output = {
        "session_id": result["session_id"],
        "verdict": result["evaluation"]["verdict"],
        "composite_score": result["similarity"]["composite_score"],
        "max_consecutive": result["similarity"]["max_consecutive"],
        "trigram_precision": result["similarity"]["trigram_precision"],
        "needs_iteration": result["needs_iteration"],
        "failure_type": result["failure_type"],
        "hot_count": len(result["hot_sentences"]),
        "analyzer_score": result["analyzer"]["overall_score"],
    }
    print(f"\n[JSON] {json.dumps(json_output)}", file=sys.stderr)
