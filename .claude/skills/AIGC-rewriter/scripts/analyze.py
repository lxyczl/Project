"""AIGC risk analysis engine CLI entry point."""

import argparse
import json
import re
import sys
from pathlib import Path

# Ensure analyzer package is findable from any directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyzer.paragraphs import split_paragraphs
from analyzer.scorer import score_paragraphs, compute_overall_risk, get_threshold
from analyzer.patterns import PatternLibrary


def analyze_text(
    text: str,
    is_markdown: bool,
    threshold: float | None,
    patterns_dir: Path | None,
    no_learn: bool = False,
    platform: str | None = None,
) -> dict:
    """Execute full analysis pipeline."""
    # Load pattern library
    if patterns_dir:
        lib = PatternLibrary.load(patterns_dir)
    else:
        lib = PatternLibrary()

    # Split paragraphs
    paragraphs = split_paragraphs(text, is_markdown)
    if not paragraphs:
        return {"overall_risk": 0.0, "paragraphs": []}

    # Risk scoring
    scored = score_paragraphs(paragraphs, lib.get_patterns(), platform)
    overall = compute_overall_risk(scored)

    # Attach threshold info (for caller decision-making)
    for para in scored:
        para["threshold"] = get_threshold(para["section_type"], threshold)

    return {
        "overall_risk": overall,
        "paragraphs": scored,
        "no_learn": no_learn,
        "platform": platform,
    }


def learn_stubborn_patterns(
    original: str,
    rewritten: str,
    patterns_dir: Path,
) -> dict:
    """Compare original vs rewritten, record stubborn patterns to learned.json.

    Returns:
        dict: {"learned_count": int, "stubborn_patterns": list}
    """
    lib = PatternLibrary.load(patterns_dir)
    stubborn = []

    for p in lib.get_patterns():
        match_str = p.get("match", "")
        if not match_str:
            continue
        try:
            orig_hit = bool(re.search(match_str, original, re.IGNORECASE))
            rewritten_hit = bool(re.search(match_str, rewritten, re.IGNORECASE))
        except re.error:
            orig_hit = match_str.lower() in original.lower()
            rewritten_hit = match_str.lower() in rewritten.lower()

        if orig_hit and rewritten_hit:
            stubborn.append(p)

    learned_count = 0
    for p in stubborn:
        learned_p = {
            "id": f"learned_{p['id']}",
            "type": p.get("type", "cliche"),
            "match": p["match"],
            "replacements": p.get("replacements", []),
            "platform_weight": p.get("platform_weight", {}),
            "source": "learned",
            "original_id": p["id"],
            "stubborn_count": 1,
        }
        lib.add_learned_pattern(learned_p)
        learned_count += 1

    if learned_count > 0:
        lib.save_learned()

    return {
        "learned_count": learned_count,
        "stubborn_patterns": [p["match"] for p in stubborn],
    }


def learn_success(
    original: str,
    rewritten: str,
    risk_before: float,
    risk_after: float,
    patterns_dir: Path,
) -> dict:
    """Record a successful rewrite strategy to learned.json.

    Analyzes which patterns were successfully eliminated.
    """
    lib = PatternLibrary.load(patterns_dir)

    # Find patterns present in original but gone in rewritten = successfully eliminated
    eliminated = []
    for p in lib.get_patterns():
        match_str = p.get("match", "")
        if not match_str:
            continue
        try:
            orig_hit = bool(re.search(match_str, original, re.IGNORECASE))
            rewritten_hit = bool(re.search(match_str, rewritten, re.IGNORECASE))
        except re.error:
            orig_hit = match_str.lower() in original.lower()
            rewritten_hit = match_str.lower() in rewritten.lower()

        if orig_hit and not rewritten_hit:
            eliminated.append(p)

    # Record success strategy
    success_entry = {
        "eliminated_patterns": [p["match"] for p in eliminated],
        "risk_before": risk_before,
        "risk_after": risk_after,
        "reduction": round(risk_before - risk_after, 3),
    }

    lib.add_success_strategy(success_entry)
    lib.save_learned()

    return {
        "recorded": True,
        "eliminated_count": len(eliminated),
        "eliminated_patterns": [p["match"] for p in eliminated],
        "risk_reduction": success_entry["reduction"],
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze text for AIGC risk")
    parser.add_argument("input", nargs="?", help="Input file path (.txt / .md / .docx / .pdf)")
    parser.add_argument("--text", "-T", help="Direct text input (for interactive mode)")
    parser.add_argument("--output", "-o", help="Output JSON file path")
    parser.add_argument("--threshold", "-t", type=float, default=None, help="Risk threshold override")
    parser.add_argument("--patterns", "-p", help="Pattern library directory path")
    parser.add_argument("--no-learn", action="store_true", default=False, help="Skip pattern learning")
    parser.add_argument("--platform", choices=["turnitin", "gptzero"],
                        default=None, help="Target detection platform (affects cliche weighting)")
    parser.add_argument("--learn-stubborn", metavar="JSON_FILE",
                        help="Pass JSON file path (with original and rewritten fields), write stubborn patterns to learned.json")
    parser.add_argument("--learn-success", metavar="JSON_FILE",
                        help="Pass JSON file path (with original, rewritten, risk_before, risk_after), record successful rewrite strategy")
    args = parser.parse_args()

    # Default pattern library path
    default_patterns = Path(__file__).resolve().parent.parent / "patterns"
    patterns_dir = Path(args.patterns) if args.patterns else default_patterns

    # --learn-success mode
    if args.learn_success:
        succ_path = Path(args.learn_success)
        if not succ_path.exists():
            print(f"[Error] File not found: {succ_path}", file=sys.stderr)
            sys.exit(1)
        try:
            succ_data = json.loads(succ_path.read_text(encoding="utf-8"))
            result = learn_success(
                succ_data["original"], succ_data["rewritten"],
                succ_data["risk_before"], succ_data["risk_after"],
                patterns_dir,
            )
        except KeyError as e:
            result = {"error": f"JSON missing required field: {e}", "recorded": False}
        except Exception as e:
            result = {"error": f"Learning process error: {e}", "recorded": False}
        if args.output:
            Path(args.output).write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # --learn-stubborn mode
    if args.learn_stubborn:
        stub_path = Path(args.learn_stubborn)
        if not stub_path.exists():
            print(f"[Error] File not found: {stub_path}", file=sys.stderr)
            sys.exit(1)
        try:
            stub_data = json.loads(stub_path.read_text(encoding="utf-8"))
            original = stub_data["original"]
            rewritten = stub_data["rewritten"]
            result = learn_stubborn_patterns(original, rewritten, patterns_dir)
        except KeyError as e:
            result = {"error": f"JSON missing required field: {e} (need original and rewritten)", "learned_count": 0, "stubborn_patterns": []}
        except Exception as e:
            result = {"error": f"Learning process error: {e}", "learned_count": 0, "stubborn_patterns": []}
        if args.output:
            Path(args.output).write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # Analysis mode
    if args.text:
        text = args.text
        is_markdown = False
    elif args.input:
        from utils.doc_parser import read_document
        try:
            text, suffix = read_document(args.input)
        except (FileNotFoundError, ValueError, ImportError) as e:
            print(f"[Error] {e}", file=sys.stderr)
            sys.exit(1)
        is_markdown = suffix == ".md"
    else:
        print("[Error] Please provide input file path or --text parameter", file=sys.stderr)
        sys.exit(1)

    if not text.strip():
        print("[Error] Input content is empty", file=sys.stderr)
        sys.exit(1)

    try:
        result = analyze_text(text, is_markdown, args.threshold, patterns_dir,
                              no_learn=args.no_learn, platform=args.platform)
    except Exception as e:
        result = {"error": f"Analysis process error: {e}", "overall_risk": None, "paragraphs": []}

    if args.output:
        Path(args.output).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
