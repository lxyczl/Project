"""Evaluation runner for AIGC-rewriter.

Runs evaluation benchmarks from evals/evals.json against the analysis engine.
"""

import json
import sys
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from analyze import analyze_text


def load_evals(evals_path: Path) -> list[dict]:
    """Load evaluation benchmarks."""
    if not evals_path.exists():
        print(f"[Error] Eval file not found: {evals_path}", file=sys.stderr)
        sys.exit(1)
    try:
        return json.loads(evals_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"[Error] Failed to parse eval file: {e}", file=sys.stderr)
        sys.exit(1)


def run_eval(eval_case: dict, patterns_dir: Path) -> dict:
    """Run a single evaluation case.

    Returns:
        dict with eval_id, passed (bool), details (str), assertions_checked (int), assertions_passed (int)
    """
    eval_id = eval_case.get("id", "unknown")
    description = eval_case.get("description", "")
    text = eval_case.get("input", "")
    assertions = eval_case.get("assertions", {})

    if not text:
        return {
            "eval_id": eval_id,
            "passed": False,
            "details": "No input text provided",
            "assertions_checked": 0,
            "assertions_passed": 0,
        }

    # Run analysis
    try:
        result = analyze_text(
            text,
            is_markdown=False,
            threshold=None,
            patterns_dir=patterns_dir,
            platform="turnitin",
        )
    except Exception as e:
        return {
            "eval_id": eval_id,
            "passed": False,
            "details": f"Analysis failed: {e}",
            "assertions_checked": 0,
            "assertions_passed": 0,
        }

    # Check assertions
    checked = 0
    passed = 0
    failures = []

    overall_risk = result.get("overall_risk", 0)
    paragraphs = result.get("paragraphs", [])

    # Collect all issues across paragraphs
    all_issues = []
    for p in paragraphs:
        all_issues.extend(p.get("issues", []))
    issue_types = {i["type"] for i in all_issues}

    # risk_min assertion
    if "risk_min" in assertions:
        checked += 1
        if overall_risk >= assertions["risk_min"]:
            passed += 1
        else:
            failures.append(f"risk_min: expected >= {assertions['risk_min']}, got {overall_risk}")

    # risk_max assertion
    if "risk_max" in assertions:
        checked += 1
        if overall_risk <= assertions["risk_max"]:
            passed += 1
        else:
            failures.append(f"risk_max: expected <= {assertions['risk_max']}, got {overall_risk}")

    # cliche_detected assertion
    if "cliche_detected" in assertions:
        checked += 1
        has_cliche = "cliche_detected" in issue_types
        if has_cliche == assertions["cliche_detected"]:
            passed += 1
        else:
            failures.append(f"cliche_detected: expected {assertions['cliche_detected']}, got {has_cliche}")

    # connector_overuse assertion
    if "connector_overuse" in assertions:
        checked += 1
        has_connector = "connector_overuse" in issue_types
        if has_connector == assertions["connector_overuse"]:
            passed += 1
        else:
            failures.append(f"connector_overuse: expected {assertions['connector_overuse']}, got {has_connector}")

    # uniform_sentence assertion
    if "uniform_sentence" in assertions:
        checked += 1
        has_uniform = "uniform_sentence_length" in issue_types
        if has_uniform == assertions["uniform_sentence"]:
            passed += 1
        else:
            failures.append(f"uniform_sentence: expected {assertions['uniform_sentence']}, got {has_uniform}")

    # issue_count_min assertion
    if "issue_count_min" in assertions:
        checked += 1
        issue_count = len(all_issues)
        if issue_count >= assertions["issue_count_min"]:
            passed += 1
        else:
            failures.append(f"issue_count_min: expected >= {assertions['issue_count_min']}, got {issue_count}")

    # preserve_terms assertion
    if "preserve_terms" in assertions:
        checked += 1
        expected_terms = set(assertions["preserve_terms"])
        # Check if terms would be found by the pattern library
        from analyzer.patterns import PatternLibrary
        lib = PatternLibrary.load(patterns_dir)
        protected = lib.get_protected_terms()
        found_terms = {t for t in expected_terms if t.lower() in text.lower()}
        if found_terms == expected_terms:
            passed += 1
        else:
            missing = expected_terms - found_terms
            failures.append(f"preserve_terms: missing terms in text: {missing}")

    all_passed = passed == checked

    return {
        "eval_id": eval_id,
        "description": description,
        "passed": all_passed,
        "details": "; ".join(failures) if failures else "All assertions passed",
        "assertions_checked": checked,
        "assertions_passed": passed,
    }


def run_all_evals(evals_path: Path, patterns_dir: Path) -> list[dict]:
    """Run all evaluation cases."""
    evals = load_evals(evals_path)
    results = []
    for eval_case in evals:
        result = run_eval(eval_case, patterns_dir)
        results.append(result)
    return results


def format_results(results: list[dict]) -> str:
    """Format evaluation results as readable report."""
    lines = ["# Evaluation Results\n"]

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    lines.append(f"**Total**: {total}  |  **Passed**: {passed}  |  **Failed**: {failed}")
    lines.append("")

    for r in results:
        icon = "✅" if r["passed"] else "❌"
        lines.append(f"{icon} **{r['eval_id']}**: {r.get('description', '')}")
        lines.append(f"   Assertions: {r['assertions_passed']}/{r['assertions_checked']} passed")
        if not r["passed"]:
            lines.append(f"   Details: {r['details']}")
        lines.append("")

    return "\n".join(lines)


def main():
    import argparse
    import io

    # Windows terminal UTF-8 output
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Run AIGC-rewriter evaluations")
    parser.add_argument("--evals", default=None, help="Path to evals.json")
    parser.add_argument("--patterns", default=None, help="Path to patterns directory")
    parser.add_argument("--output", "-o", help="Output JSON file path")
    parser.add_argument("--json", action="store_true", help="Output JSON to stdout")
    args = parser.parse_args()

    # Default paths
    skill_dir = Path(__file__).parent.parent
    evals_path = Path(args.evals) if args.evals else skill_dir / "evals" / "evals.json"
    patterns_dir = Path(args.patterns) if args.patterns else skill_dir / "patterns"

    results = run_all_evals(evals_path, patterns_dir)

    if args.output:
        Path(args.output).write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(format_results(results))

    # Exit with failure code if any eval failed
    if any(not r["passed"] for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
