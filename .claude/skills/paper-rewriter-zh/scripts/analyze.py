"""
风险分析引擎 CLI
用法：
  $PY analyze.py <文本文件>
  $PY analyze.py --text "直接输入文本"
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzer.scorer import analyze_text


def main():
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    if args[0] == "--text":
        text = " ".join(args[1:])
    else:
        fpath = Path(args[0])
        if not fpath.exists():
            print(f"错误: 文件不存在: {fpath}")
            sys.exit(1)
        try:
            text = fpath.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = fpath.read_text(encoding="gbk")

    result = analyze_text(text)

    print(f"## 风险分析结果")
    print(f"   综合风险: {result['overall_risk']:.3f}")
    print()

    if result.get("paragraph_scores"):
        print(f"## 段落风险排名 (共 {len(result['paragraph_scores'])} 段)")
        for ps in result["paragraph_scores"][:5]:
            section = ps.get("section_type", "body")
            print(f"   段落{ps['index']} [{section}]: 风险={ps['risk']:.3f}, 优先级={ps['priority']:.3f}")
            if ps.get("suggestion"):
                print(f"      建议: {ps['suggestion']}")
            for issue in ps.get("issues", [])[:3]:
                print(f"      - [{issue['type']}] {issue['detail']}")
        print()

    # 输出 JSON
    json_output = {
        "overall_risk": result["overall_risk"],
        "paragraph_count": len(result.get("paragraph_scores", [])),
        "top_risk": result["paragraph_scores"][0]["risk"] if result.get("paragraph_scores") else 0,
    }
    print(f"[JSON] {json.dumps(json_output, ensure_ascii=False)}", file=sys.stderr)


if __name__ == "__main__":
    main()
