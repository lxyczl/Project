"""
Edge case detection
Identify edge cases in pipeline and provide guidance
"""
import re
from pathlib import Path


def _load_protected_terms() -> set[str]:
    """Load protected terms from domains.md and builtin.json."""
    terms = set()
    skill_dir = Path(__file__).parent.parent

    # From references/domains.md
    domains_file = skill_dir / "references" / "domains.md"
    if domains_file.exists():
        in_preserves = False
        for line in domains_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("### Protected Terms"):
                in_preserves = True
                continue
            if stripped.startswith("### ") and in_preserves:
                in_preserves = False
                continue
            if in_preserves and stripped and not stripped.startswith("#"):
                # Parse comma-separated or line-separated terms
                if "," in stripped:
                    terms.update(t.strip().lower() for t in stripped.split(",") if t.strip())
                elif stripped.startswith("- "):
                    terms.add(stripped[2:].strip().lower())

    # From patterns/builtin.json
    builtin_file = skill_dir / "patterns" / "builtin.json"
    if builtin_file.exists():
        try:
            import json
            data = json.loads(builtin_file.read_text(encoding="utf-8"))
            terms.update(t.lower() for t in data.get("protected_terms", []))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    return terms


def detect_edge_cases(text: str) -> list[dict]:
    """Detect text edge cases, return [{type, message, severity, skip_rewrite}]"""
    issues = []
    text_stripped = text.strip()
    word_count = len(re.findall(r"[a-zA-Z]+(?:'[a-z]+)?|\d+\.?\d*%?", text_stripped))

    # 1. Short text (less than 50 words)
    if word_count < 50:
        issues.append({
            "type": "short_text",
            "message": f"Text too short ({word_count} words), rewrite effect limited. Suggest providing at least 50 words",
            "severity": "warning",
            "skip_rewrite": False,
        })

    # 2. Non-English text
    chinese_chars = len(re.findall(r"[一-鿿]", text_stripped))
    if chinese_chars > 0 and word_count == 0:
        issues.append({
            "type": "non_english",
            "message": "Non-English text detected, this skill only supports English academic texts",
            "severity": "error",
            "skip_rewrite": True,
        })

    # 3. Non-academic text
    colloquial = ["lol", "omg", "tbh", "imo", "btw", "gonna", "wanna", "gotta",
                  "kinda", "sorta", "y'all", "ain't", "666", "yolo", "fomo"]
    found_colloquial = [w for w in colloquial if w.lower() in text_stripped.lower()]
    if found_colloquial:
        issues.append({
            "type": "non_academic",
            "message": f"Non-academic expressions detected ({', '.join(found_colloquial[:3])}), this skill is designed for academic papers",
            "severity": "warning",
            "skip_rewrite": False,
        })

    # 4. Long text (over 1000 words)
    if word_count > 1000:
        issues.append({
            "type": "long_text",
            "message": f"Text long ({word_count} words), suggest paragraph-by-paragraph rewrite for quality",
            "severity": "info",
            "skip_rewrite": False,
        })

    # 5. Heavy formulas/citations — skip rewrite if > 30% of content
    formula_count = len(re.findall(r'\$.*?\$', text_stripped))
    latex_count = len(re.findall(r'\\begin\{equation\}|\\\[.*?\\\]', text_stripped, re.DOTALL))
    citation_count = len(re.findall(r'\[\d+\]|\([A-Z][a-z]+,?\s*\d{4}\)', text_stripped))
    formula_citation_total = formula_count + latex_count + citation_count
    if word_count > 0 and formula_citation_total > 0:
        # Estimate formula/citation density (rough: each counts as ~5 words)
        density = (formula_citation_total * 5) / word_count
        if density > 0.3:
            issues.append({
                "type": "formula_heavy",
                "message": f"Text is {density:.0%} formulas/citations ({formula_citation_total} instances), rewrite space very limited",
                "severity": "warning",
                "skip_rewrite": True,
            })
        elif formula_citation_total > 5:
            issues.append({
                "type": "formulas_citations",
                "message": f"Text contains {formula_count + latex_count} formulas and {citation_count} citations, limited rewrite space",
                "severity": "info",
                "skip_rewrite": False,
            })

    # 6. Term dense — using actual protected terms from references
    if word_count > 20:
        protected_terms = _load_protected_terms()
        if protected_terms:
            words_lower = set(re.findall(r"[a-zA-Z]+", text_stripped.lower()))
            matched_terms = sum(1 for t in protected_terms if t in text_stripped.lower())
            if matched_terms > 0:
                term_ratio = matched_terms / word_count
                if term_ratio > 0.3:
                    issues.append({
                        "type": "term_dense",
                        "message": f"Dense technical terms ({matched_terms} protected terms detected, {term_ratio:.0%} ratio), limited rewrite space",
                        "severity": "info",
                        "skip_rewrite": False,
                    })

    # 7. Direct quotes
    quotes = re.findall(r'["""]\s*.{20,}?\s*["""]', text_stripped)
    if len(quotes) > 2:
        issues.append({
            "type": "direct_quotes",
            "message": f"Text contains {len(quotes)} direct quotes, quoted portions cannot be rewritten",
            "severity": "info",
            "skip_rewrite": False,
        })

    return issues


def should_skip_rewrite(issues: list[dict]) -> bool:
    """Determine if rewrite should be skipped based on edge cases."""
    return any(issue.get("skip_rewrite") for issue in issues)


def format_edge_case_report(issues: list[dict]) -> str:
    """Format edge case report."""
    if not issues:
        return ""

    severity_icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}
    lines = ["## Edge Case Detection"]
    for issue in issues:
        icon = severity_icon.get(issue["severity"], "")
        lines.append(f"   {icon} [{issue['type']}] {issue['message']}")
    return "\n".join(lines)
