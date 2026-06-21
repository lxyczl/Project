"""AIGC 风险分析引擎 CLI 入口。"""

import argparse
import json
import sys
from pathlib import Path

from analyzer.paragraphs import split_paragraphs
from analyzer.scorer import score_paragraphs, compute_overall_risk, get_threshold
from analyzer.patterns import PatternLibrary


def analyze_text(
    text: str,
    is_markdown: bool,
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
    paragraphs = split_paragraphs(text, is_markdown)
    if not paragraphs:
        return {"overall_risk": 0.0, "paragraphs": []}

    # 风险评分
    scored = score_paragraphs(paragraphs, lib.get_patterns())
    overall = compute_overall_risk(scored)

    # 附加阈值信息（供调用方决策）
    for para in scored:
        para["threshold"] = get_threshold(para["section_type"], threshold)

    return {
        "overall_risk": overall,
        "paragraphs": scored,
    }


def main():
    parser = argparse.ArgumentParser(description="分析文本的 AIGC 风险")
    parser.add_argument("input", nargs="?", help="输入文件路径 (.txt 或 .md)")
    parser.add_argument("--text", "-T", help="直接传入文本（交互模式用）")
    parser.add_argument("--output", "-o", help="输出 JSON 文件路径")
    parser.add_argument("--threshold", "-t", type=float, default=None, help="风险阈值")
    parser.add_argument("--patterns", "-p", help="模式库目录路径")
    args = parser.parse_args()

    # 确定输入
    if args.text:
        text = args.text
        is_markdown = False
    elif args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"[错误] 文件不存在: {input_path}", file=sys.stderr)
            sys.exit(1)
        if input_path.suffix not in (".txt", ".md"):
            print(f"[错误] 不支持的格式: {input_path.suffix}", file=sys.stderr)
            sys.exit(1)
        text = input_path.read_text(encoding="utf-8")
        is_markdown = input_path.suffix == ".md"
    else:
        print("[错误] 请提供输入文件路径或 --text 参数", file=sys.stderr)
        sys.exit(1)

    if not text.strip():
        print("[错误] 输入内容为空", file=sys.stderr)
        sys.exit(1)

    patterns_dir = Path(args.patterns) if args.patterns else None

    try:
        result = analyze_text(text, is_markdown, args.threshold, patterns_dir)
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
