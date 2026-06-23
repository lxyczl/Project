"""AIGC 风险分析引擎 CLI 入口（英文版）。"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyzer.paragraphs import split_paragraphs
from analyzer.scorer import score_paragraphs, compute_overall_risk, get_threshold
from analyzer.patterns import PatternLibrary


def analyze_text(
    text: str,
    threshold: float | None,
    patterns_dir: Path | None,
) -> dict:
    """执行完整的分析流程。"""
    # 加载模式库
    if patterns_dir:
        lib = PatternLibrary.load(patterns_dir)
    else:
        lib = PatternLibrary()

    # 段落切分
    paragraphs = split_paragraphs(text)
    if not paragraphs:
        return {"overall_risk": 0.0, "paragraphs": []}

    # 风险评分
    scored = score_paragraphs(paragraphs, lib.get_patterns())
    overall = compute_overall_risk(scored)

    # 附加阈值信息
    for para in scored:
        para["threshold"] = get_threshold(para["section_type"], threshold)

    return {
        "overall_risk": overall,
        "paragraphs": scored,
    }


def learn_stubborn_patterns(
    original: str,
    rewritten: str,
    patterns_dir: Path,
) -> dict:
    """对比原文与改写后文本，将改写后仍高风险的 pattern 记录到 learned.json。"""
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
    """记录一次成功的改写策略到 learned.json。"""
    lib = PatternLibrary.load(patterns_dir)

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
    parser = argparse.ArgumentParser(description="Analyze text for AIGC detection risk")
    parser.add_argument("input", nargs="?", help="Input file path (.txt)")
    parser.add_argument("--text", "-T", help="Direct text input")
    parser.add_argument("--output", "-o", help="Output JSON file path")
    parser.add_argument("--threshold", "-t", type=float, default=None, help="Risk threshold")
    parser.add_argument("--patterns", "-p", help="Pattern library directory path")
    parser.add_argument("--learn-stubborn", metavar="JSON_FILE",
                        help="Learn stubborn patterns from JSON file")
    parser.add_argument("--learn-success", metavar="JSON_FILE",
                        help="Learn success strategies from JSON file")
    args = parser.parse_args()

    # 默认模式库路径
    default_patterns = Path(__file__).resolve().parent / "patterns"
    patterns_dir = Path(args.patterns) if args.patterns else default_patterns

    # --learn-success 模式
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
            result = {"error": f"Missing field: {e}", "recorded": False}
        except Exception as e:
            result = {"error": str(e), "recorded": False}
        if args.output:
            Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
        else:
            print(json.dumps(result, indent=2))
        return

    # --learn-stubborn 模式
    if args.learn_stubborn:
        stub_path = Path(args.learn_stubborn)
        if not stub_path.exists():
            print(f"[Error] File not found: {stub_path}", file=sys.stderr)
            sys.exit(1)
        try:
            stub_data = json.loads(stub_path.read_text(encoding="utf-8"))
            result = learn_stubborn_patterns(
                stub_data["original"], stub_data["rewritten"], patterns_dir
            )
        except KeyError as e:
            result = {"error": f"Missing field: {e}", "learned_count": 0, "stubborn_patterns": []}
        except Exception as e:
            result = {"error": str(e), "learned_count": 0, "stubborn_patterns": []}
        if args.output:
            Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
        else:
            print(json.dumps(result, indent=2))
        return

    # 分析模式
    if args.text:
        text = args.text
    elif args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"[Error] File not found: {input_path}", file=sys.stderr)
            sys.exit(1)
        text = input_path.read_text(encoding="utf-8")
    else:
        print("[Error] Provide input file path or --text argument", file=sys.stderr)
        sys.exit(1)

    if not text.strip():
        print("[Error] Input is empty", file=sys.stderr)
        sys.exit(1)

    try:
        result = analyze_text(text, args.threshold, patterns_dir)
    except Exception as e:
        result = {"error": str(e), "overall_risk": None, "paragraphs": []}

    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
