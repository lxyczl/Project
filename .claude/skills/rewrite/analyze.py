"""AIGC 风险分析引擎 CLI 入口。"""

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="分析文本的 AIGC 风险")
    parser.add_argument("input", help="输入文件路径 (.txt 或 .md)")
    parser.add_argument("--output", "-o", help="输出 JSON 文件路径")
    parser.add_argument("--threshold", "-t", type=float, default=0.3, help="风险阈值")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[错误] 文件不存在: {input_path}", file=sys.stderr)
        sys.exit(1)
    if input_path.suffix not in (".txt", ".md"):
        print(f"[错误] 不支持的格式: {input_path.suffix}，仅支持 .txt 和 .md", file=sys.stderr)
        sys.exit(1)

    text = input_path.read_text(encoding="utf-8")
    if not text.strip():
        print("[错误] 文件内容为空", file=sys.stderr)
        sys.exit(1)

    # 后续 Task 填充分析逻辑
    result = {"overall_risk": 0.0, "paragraphs": []}

    if args.output:
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
