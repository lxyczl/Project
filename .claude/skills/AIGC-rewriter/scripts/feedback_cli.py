"""Feedback learning system CLI.

SKILL.md calls this script via Bash to: record session → get suggestions → generate report.
"""

import argparse
import json
import sys
from pathlib import Path

# feedback_system is in same directory
from feedback_system import FeedbackSystem


def main():
    parser = argparse.ArgumentParser(description="AIGC rewrite feedback learning system")
    sub = parser.add_subparsers(dest="command")

    # record: record a rewrite session
    p_record = sub.add_parser("record", help="Record rewrite session")
    p_record.add_argument("--original", required=True, help="Original text")
    p_record.add_argument("--rewritten", required=True, help="Rewritten text")
    p_record.add_argument("--risk-before", type=float, required=True, help="Risk score before rewrite")
    p_record.add_argument("--risk-after", type=float, required=True, help="Risk score after rewrite")
    p_record.add_argument("--section", default="body", help="Section type")
    p_record.add_argument("--techniques", nargs="*", default=[], help="Techniques used")
    p_record.add_argument("--issues", nargs="*", default=[], help="Issue types detected before rewrite")

    # suggest: get rewrite suggestions
    p_suggest = sub.add_parser("suggest", help="Get rewrite suggestions")
    p_suggest.add_argument("--section", default="body", help="Section type")
    p_suggest.add_argument("--intensity", default="medium", choices=["light", "medium", "heavy"])

    # report: strategy report
    sub.add_parser("report", help="Generate strategy report")

    # vocab: record vocabulary preference
    p_vocab = sub.add_parser("vocab", help="Record successful vocabulary replacement")
    p_vocab.add_argument("--original", required=True, help="Original word")
    p_vocab.add_argument("--rewritten", required=True, help="Replacement word")

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
            issues_before=args.issues,
            issues_after=[],
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
