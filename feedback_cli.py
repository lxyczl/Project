"""反馈学习系统 CLI。

SKILL.md 通过 Bash 调用此脚本完成：记录会话 → 获取建议 → 生成报告。
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from feedback_system import FeedbackSystem


def main():
    parser = argparse.ArgumentParser(description="AIGC 改写反馈学习系统")
    sub = parser.add_subparsers(dest="command")

    # record: 记录一次改写会话
    p_record = sub.add_parser("record", help="记录改写会话")
    p_record.add_argument("--original", required=True, help="原文")
    p_record.add_argument("--rewritten", required=True, help="改写后文本")
    p_record.add_argument("--risk-before", type=float, required=True, help="改写前风险分")
    p_record.add_argument("--risk-after", type=float, required=True, help="改写后风险分")
    p_record.add_argument("--section", default="body", help="章节类型")
    p_record.add_argument("--techniques", nargs="*", default=[], help="使用的技巧")
    p_record.add_argument("--issues", nargs="*", default=[], help="解决的 issue type")

    # suggest: 获取改写建议
    p_suggest = sub.add_parser("suggest", help="获取改写建议")
    p_suggest.add_argument("--section", default="body", help="章节类型")
    p_suggest.add_argument("--intensity", default="medium", choices=["light", "medium", "heavy"])

    # report: 策略报告
    sub.add_parser("report", help="生成策略报告")

    # vocab: 记录词汇偏好
    p_vocab = sub.add_parser("vocab", help="记录成功的词汇替换")
    p_vocab.add_argument("--original", required=True, help="原文词")
    p_vocab.add_argument("--rewritten", required=True, help="替换词")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    fs = FeedbackSystem()

    if args.command == "record":
        result = fs.record_session(
            original_text=args.original,
            rewritten_text=args.rewritten,
            risk_before=args.risk_before,
            risk_after=args.risk_after,
            section_type=args.section,
            techniques_used=args.techniques,
            issues_resolved=args.issues,
        )
        print(json.dumps({
            "session_id": result["session_id"],
            "success": result["success"],
            "risk_reduction": result["risk_reduction"],
        }, ensure_ascii=False, indent=2))

    elif args.command == "suggest":
        result = fs.get_rewrite_suggestions(args.section, args.intensity)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "report":
        print(fs.get_strategy_report())

    elif args.command == "vocab":
        fs.record_vocabulary_preference(args.original, args.rewritten)
        print(json.dumps({"recorded": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
