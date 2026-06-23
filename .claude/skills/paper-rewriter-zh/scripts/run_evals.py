"""
评估运行器
用法：$PY run_evals.py [--eval-dir <评估目录>]
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from run_pipeline import run


def load_evals(eval_dir: Path = None) -> list:
    """加载评估用例。"""
    if eval_dir is None:
        eval_dir = Path(__file__).parent.parent / "evals"
    eval_file = eval_dir / "evals.json"
    if not eval_file.exists():
        print(f"错误: 评估文件不存在: {eval_file}")
        sys.exit(1)
    data = json.loads(eval_file.read_text(encoding="utf-8"))
    return data.get("evals", [])


def run_eval(eval_case: dict) -> dict:
    """运行单个评估用例。"""
    result = run(
        original=eval_case["original"],
        rewritten=eval_case["rewritten"],
        domain=eval_case.get("domain", "通用"),
        intensity=eval_case.get("intensity", "中度"),
    )

    expected = eval_case.get("expected", {})
    checks = []

    # 检查 verdict
    if "verdict" in expected:
        actual = result["evaluation"]["verdict"]
        ok = actual == expected["verdict"]
        checks.append({"check": "verdict", "expected": expected["verdict"], "actual": actual, "pass": ok})

    # 检查 needs_iteration
    if "needs_iteration" in expected:
        actual = result["needs_iteration"]
        ok = actual == expected["needs_iteration"]
        checks.append({"check": "needs_iteration", "expected": expected["needs_iteration"], "actual": actual, "pass": ok})

    # 检查热点句数
    if "hot_sentence_count_min" in expected:
        actual = len(result["hot_sentences"])
        ok = actual >= expected["hot_sentence_count_min"]
        checks.append({"check": "hot_sentence_count", "expected": f">={expected['hot_sentence_count_min']}", "actual": actual, "pass": ok})

    # 检查风险分
    if "risk_score_min" in expected:
        actual = result["risk_analysis"]["overall_risk"]
        ok = actual >= expected["risk_score_min"]
        checks.append({"check": "risk_score", "expected": f">={expected['risk_score_min']}", "actual": round(actual, 3), "pass": ok})

    # 检查连续匹配
    if "max_consecutive_max" in expected:
        actual = result["similarity"]["max_consecutive"]
        ok = actual <= expected["max_consecutive_max"]
        checks.append({"check": "max_consecutive", "expected": f"<={expected['max_consecutive_max']}", "actual": actual, "pass": ok})

    # 检查三元组重叠
    if "trigram_overlap_max" in expected:
        actual = result["similarity"]["trigram_overlap"]
        ok = actual <= expected["trigram_overlap_max"]
        checks.append({"check": "trigram_overlap", "expected": f"<={expected['trigram_overlap_max']}", "actual": round(actual, 3), "pass": ok})

    # 检查套话检测
    if "cliche_detected" in expected:
        issues = result["risk_analysis"]["paragraph_scores"][0]["issues"] if result["risk_analysis"]["paragraph_scores"] else []
        has_cliche = any(i["type"] == "cliche_detected" for i in issues)
        ok = has_cliche == expected["cliche_detected"]
        checks.append({"check": "cliche_detected", "expected": expected["cliche_detected"], "actual": has_cliche, "pass": ok})

    # 检查保留术语
    if "preserve_terms" in expected:
        found = result["preserve_terms"]
        missing = [t for t in expected["preserve_terms"] if t not in found]
        ok = len(missing) == 0
        checks.append({"check": "preserve_terms", "expected": expected["preserve_terms"], "actual": found, "pass": ok, "missing": missing})

    passed = sum(1 for c in checks if c["pass"])
    total = len(checks)

    return {
        "id": eval_case["id"],
        "name": eval_case["name"],
        "passed": passed,
        "total": total,
        "success": passed == total,
        "checks": checks,
    }


def main():
    args = sys.argv[1:]
    eval_dir = None
    if "--eval-dir" in args:
        idx = args.index("--eval-dir")
        if idx + 1 < len(args):
            eval_dir = Path(args[idx + 1])

    evals = load_evals(eval_dir)
    print(f"## 运行 {len(evals)} 个评估用例\n")

    results = []
    for eval_case in evals:
        result = run_eval(eval_case)
        results.append(result)
        status = "PASS" if result["success"] else "FAIL"
        print(f"  [{status}] {result['id']}: {result['name']} ({result['passed']}/{result['total']})")
        if not result["success"]:
            for check in result["checks"]:
                if not check["pass"]:
                    print(f"         FAIL: {check['check']} — expected {check['expected']}, got {check['actual']}")

    total_passed = sum(1 for r in results if r["success"])
    total_cases = len(results)
    print(f"\n## 结果: {total_passed}/{total_cases} 通过")

    # 输出 JSON
    json_output = {
        "total": total_cases,
        "passed": total_passed,
        "failed": total_cases - total_passed,
        "results": results,
    }
    print(f"\n[JSON] {json.dumps(json_output, ensure_ascii=False)}", file=sys.stderr)


if __name__ == "__main__":
    main()
