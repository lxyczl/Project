"""
评估运行器
用法：$PY run_evals.py [--eval-dir <评估目录>]
"""
import sys
import json
from pathlib import Path

# 确保从任意目录调用时都能找到模块
_SCRIPTS_DIR = Path(__file__).resolve().parent
_SKILL_DIR = _SCRIPTS_DIR.parent
sys.path.insert(0, str(_SKILL_DIR))
sys.path.insert(0, str(_SCRIPTS_DIR))

from analyze import analyze_text
from utils.reference_loader import load_domains, get_domain_preserve_terms


def load_evals(eval_dir: Path = None) -> list:
    """加载评估用例。"""
    if eval_dir is None:
        eval_dir = _SKILL_DIR / "evals"
    eval_file = eval_dir / "evals.json"
    if not eval_file.exists():
        print(f"错误: 评估文件不存在: {eval_file}")
        sys.exit(1)
    data = json.loads(eval_file.read_text(encoding="utf-8"))
    return data.get("evals", [])


def run_eval(eval_case: dict) -> dict:
    """运行单个评估用例。"""
    original = eval_case["original"]
    patterns_dir = _SKILL_DIR / "patterns"

    # 分析
    result = analyze_text(
        original,
        is_markdown=False,
        threshold=None,
        patterns_dir=patterns_dir,
        no_learn=True,
    )

    expected = eval_case.get("expected", {})
    checks = []

    # 检查风险分下限
    if "risk_min" in expected:
        actual = result["overall_risk"]
        ok = actual >= expected["risk_min"]
        checks.append({
            "check": "risk_min",
            "expected": f">={expected['risk_min']}",
            "actual": round(actual, 3),
            "pass": ok,
        })

    # 检查风险分上限
    if "risk_max" in expected:
        actual = result["overall_risk"]
        ok = actual <= expected["risk_max"]
        checks.append({
            "check": "risk_max",
            "expected": f"<={expected['risk_max']}",
            "actual": round(actual, 3),
            "pass": ok,
        })

    # 检查套话检测
    if "cliche_detected" in expected:
        all_issues = []
        for p in result.get("paragraphs", []):
            all_issues.extend(p.get("issues", []))
        has_cliche = any(i["type"] == "cliche_detected" for i in all_issues)
        ok = has_cliche == expected["cliche_detected"]
        checks.append({
            "check": "cliche_detected",
            "expected": expected["cliche_detected"],
            "actual": has_cliche,
            "pass": ok,
        })

    # 检查连接词过密
    if "connector_overuse" in expected:
        all_issues = []
        for p in result.get("paragraphs", []):
            all_issues.extend(p.get("issues", []))
        has_connector = any(i["type"] == "connector_overuse" for i in all_issues)
        ok = has_connector == expected["connector_overuse"]
        checks.append({
            "check": "connector_overuse",
            "expected": expected["connector_overuse"],
            "actual": has_connector,
            "pass": ok,
        })

    # 检查句长均匀
    if "uniform_sentence" in expected:
        all_issues = []
        for p in result.get("paragraphs", []):
            all_issues.extend(p.get("issues", []))
        has_uniform = any(i["type"] == "uniform_sentence_length" for i in all_issues)
        ok = has_uniform == expected["uniform_sentence"]
        checks.append({
            "check": "uniform_sentence",
            "expected": expected["uniform_sentence"],
            "actual": has_uniform,
            "pass": ok,
        })

    # 检查 issue 数量下限
    if "issue_count_min" in expected:
        total_issues = sum(len(p.get("issues", [])) for p in result.get("paragraphs", []))
        ok = total_issues >= expected["issue_count_min"]
        checks.append({
            "check": "issue_count_min",
            "expected": f">={expected['issue_count_min']}",
            "actual": total_issues,
            "pass": ok,
        })

    # 检查保护术语
    if "preserve_terms" in expected:
        domains = load_domains()
        found = get_domain_preserve_terms(original, domains)
        missing = [t for t in expected["preserve_terms"] if t not in found]
        ok = len(missing) == 0
        checks.append({
            "check": "preserve_terms",
            "expected": expected["preserve_terms"],
            "actual": found,
            "pass": ok,
            "missing": missing,
        })

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
    import io
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

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
