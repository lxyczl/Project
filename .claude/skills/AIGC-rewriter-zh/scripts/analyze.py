"""AIGC 风险分析引擎 CLI 入口。"""

import argparse
import json
import re
import sys
from pathlib import Path

# 确保从任意目录调用时都能找到 analyzer 包
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
    """执行完整的分析流程。"""
    # 加载模式库
    if patterns_dir:
        lib = PatternLibrary.load(patterns_dir)
    else:
        lib = PatternLibrary()

    # 段落切分
    paragraphs = split_paragraphs(text, is_markdown)
    if not paragraphs:
        return {"overall_risk": 0.0, "paragraphs": []}

    # 风险评分
    scored = score_paragraphs(paragraphs, lib.get_patterns(), platform)
    overall = compute_overall_risk(scored)

    # 附加阈值信息（供调用方决策）
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
    """对比原文与改写后文本，将改写后仍高风险的 pattern 记录到 learned.json。

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
            orig_hit = bool(re.search(match_str, original))
            rewritten_hit = bool(re.search(match_str, rewritten))
        except re.error:
            orig_hit = match_str in original
            rewritten_hit = match_str in rewritten

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
    """记录一次成功的改写策略到 learned.json。

    分析哪些 pattern 被成功消除，记录对应的替换策略。
    """
    lib = PatternLibrary.load(patterns_dir)

    # 找出原文有但改写后消失的 pattern → 成功消除
    eliminated = []
    for p in lib.get_patterns():
        match_str = p.get("match", "")
        if not match_str:
            continue
        try:
            orig_hit = bool(re.search(match_str, original))
            rewritten_hit = bool(re.search(match_str, rewritten))
        except re.error:
            orig_hit = match_str in original
            rewritten_hit = match_str in rewritten

        if orig_hit and not rewritten_hit:
            eliminated.append(p)

    # 记录成功策略
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
    parser = argparse.ArgumentParser(description="分析文本的 AIGC 风险")
    parser.add_argument("input", nargs="?", help="输入文件路径 (.txt / .md / .docx / .pdf)")
    parser.add_argument("--text", "-T", help="直接传入文本（交互模式用）")
    parser.add_argument("--output", "-o", help="输出 JSON 文件路径")
    parser.add_argument("--threshold", "-t", type=float, default=None, help="风险阈值")
    parser.add_argument("--patterns", "-p", help="模式库目录路径")
    parser.add_argument("--no-learn", action="store_true", default=False, help="跳过模式学习")
    parser.add_argument("--platform", choices=["cnki", "vip", "wanfang", "paperpass"],
                        default=None, help="目标检测平台（影响套话权重）")
    parser.add_argument("--learn-stubborn", metavar="JSON_FILE",
                        help="传入 JSON 文件路径（含 original 和 rewritten 字段），将顽固 pattern 写入 learned.json")
    parser.add_argument("--learn-success", metavar="JSON_FILE",
                        help="传入 JSON 文件路径（含 original、rewritten、risk_before、risk_after），记录成功改写策略")
    args = parser.parse_args()

    # 默认模式库路径
    default_patterns = Path(__file__).resolve().parent.parent / "patterns"
    patterns_dir = Path(args.patterns) if args.patterns else default_patterns

    # --learn-success 模式：记录成功改写策略
    if args.learn_success:
        succ_path = Path(args.learn_success)
        if not succ_path.exists():
            print(f"[错误] 文件不存在: {succ_path}", file=sys.stderr)
            sys.exit(1)
        try:
            succ_data = json.loads(succ_path.read_text(encoding="utf-8"))
            result = learn_success(
                succ_data["original"], succ_data["rewritten"],
                succ_data["risk_before"], succ_data["risk_after"],
                patterns_dir,
            )
        except KeyError as e:
            result = {"error": f"JSON 缺少必要字段: {e}", "recorded": False}
        except Exception as e:
            result = {"error": f"学习过程出错: {e}", "recorded": False}
        if args.output:
            Path(args.output).write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # --learn-stubborn 模式：学习顽固 pattern
    if args.learn_stubborn:
        stub_path = Path(args.learn_stubborn)
        if not stub_path.exists():
            print(f"[错误] 文件不存在: {stub_path}", file=sys.stderr)
            sys.exit(1)
        try:
            stub_data = json.loads(stub_path.read_text(encoding="utf-8"))
            original = stub_data["original"]
            rewritten = stub_data["rewritten"]
            result = learn_stubborn_patterns(original, rewritten, patterns_dir)
        except KeyError as e:
            result = {"error": f"JSON 缺少必要字段: {e}（需要 original 和 rewritten）", "learned_count": 0, "stubborn_patterns": []}
        except Exception as e:
            result = {"error": f"学习过程出错: {e}", "learned_count": 0, "stubborn_patterns": []}
        if args.output:
            Path(args.output).write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # 分析模式
    if args.text:
        text = args.text
        is_markdown = False
    elif args.input:
        from utils.doc_parser import read_document
        try:
            text, suffix = read_document(args.input)
        except (FileNotFoundError, ValueError, ImportError) as e:
            print(f"[错误] {e}", file=sys.stderr)
            sys.exit(1)
        is_markdown = suffix == ".md"
    else:
        print("[错误] 请提供输入文件路径或 --text 参数", file=sys.stderr)
        sys.exit(1)

    if not text.strip():
        print("[错误] 输入内容为空", file=sys.stderr)
        sys.exit(1)

    try:
        result = analyze_text(text, is_markdown, args.threshold, patterns_dir,
                              no_learn=args.no_learn, platform=args.platform)
    except Exception as e:
        result = {"error": f"分析过程出错: {e}", "overall_risk": None, "paragraphs": []}

    if args.output:
        Path(args.output).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
