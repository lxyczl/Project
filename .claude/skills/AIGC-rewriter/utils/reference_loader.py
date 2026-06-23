"""
Reference document parser
Parses references/domains.md and references/synonyms.md into structured data.

Adapted from AIGC-rewriter-zh for English.
"""
import re
from pathlib import Path


def load_domains(ref_dir: Path = None) -> dict:
    """Parse domains.md → {discipline: {preserves: [...], replacements: {original: [replacements...]}}}"""
    if ref_dir is None:
        ref_dir = Path(__file__).parent.parent / "references"
    domains_file = ref_dir / "domains.md"
    if not domains_file.exists():
        return {}

    text = domains_file.read_text(encoding="utf-8")
    domains = {}
    current_domain = None
    current_preserves = []
    current_replacements = {}
    section = None  # "preserves" or "replacements"

    for line in text.splitlines():
        stripped = line.strip()

        if stripped.startswith("## ") and not stripped.startswith("### "):
            if current_domain:
                domains[current_domain] = {
                    "preserves": current_preserves,
                    "replacements": current_replacements,
                }
            current_domain = stripped[3:].strip()
            current_preserves = []
            current_replacements = {}
            section = None

        elif stripped.startswith("### Protected Terms"):
            section = "preserves"
        elif stripped.startswith("### Replacements"):
            section = "replacements"
        elif stripped.startswith("### ") or stripped.startswith("**Note**"):
            section = None
        elif stripped.startswith("---") or stripped.startswith("#"):
            pass

        elif section == "preserves" and current_domain and stripped:
            # Terms may be comma-separated or on separate lines
            if "," in stripped and "→" not in stripped:
                terms = [t.strip() for t in stripped.split(",") if t.strip()]
                current_preserves.extend(terms)
            elif stripped.startswith("- "):
                term = stripped[2:].strip()
                if term:
                    current_preserves.append(term)

        elif section == "replacements" and stripped.startswith("- ") and "→" in stripped:
            match = re.match(r"-\s*(.+?)\s*→\s*(.+)", stripped)
            if match:
                src = match.group(1).strip()
                targets = [t.strip() for t in match.group(2).split(",") if t.strip()]
                current_replacements[src] = targets

    if current_domain:
        domains[current_domain] = {
            "preserves": current_preserves,
            "replacements": current_replacements,
        }

    return domains


def load_synonyms(ref_dir: Path = None) -> dict:
    """Parse synonyms.md → {original: [replacements...]}"""
    if ref_dir is None:
        ref_dir = Path(__file__).parent.parent / "references"
    synonyms_file = ref_dir / "synonyms.md"
    if not synonyms_file.exists():
        return {}

    text = synonyms_file.read_text(encoding="utf-8")
    synonyms = {}

    for line in text.splitlines():
        stripped = line.strip()
        match = re.match(r"\|\s*(.+?)\s*\|\s*(.+?)\s*\|", stripped)
        if match:
            src = match.group(1).strip()
            targets_str = match.group(2).strip()
            if src in ("Original", "---") or targets_str in ("Replacements", "---"):
                continue
            if "|" in targets_str:
                targets_str = targets_str.split("|")[0].strip()
            targets = [t.strip() for t in targets_str.replace("、", ",").split(",") if t.strip()]
            if targets and src:
                synonyms[src] = targets

    return synonyms


def get_domain_preserve_terms(text: str, domains: dict) -> list[str]:
    """Extract protected terms found in text."""
    found = []
    for domain, data in domains.items():
        for term in data.get("preserves", []):
            if term.lower() in text.lower():
                found.append(term)
    return list(set(found))


def get_domain_replacements(text: str, domains: dict, domain: str = None) -> dict:
    """Find available discipline-specific replacements in text."""
    replacements = {}
    search_domains = {domain: domains[domain]} if domain and domain in domains else domains

    for dname, data in search_domains.items():
        for src, targets in data.get("replacements", {}).items():
            if src.lower() in text.lower():
                replacements[src] = targets

    return replacements


def get_synonym_suggestions(text: str, synonyms: dict) -> dict:
    """Find available synonym replacements in text."""
    suggestions = {}
    for src, targets in synonyms.items():
        if src.lower() in text.lower():
            suggestions[src] = targets
    return suggestions
