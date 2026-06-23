"""
参考文档解析器
解析 domains.md 和 synonyms.md 为结构化数据，供 pipeline 使用
"""
import re
from pathlib import Path


def load_domains(ref_dir: Path = None) -> dict:
    """解析 domains.md → {学科: {preserves: [...], replacements: {原词: [替换词...]}}}"""
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

        elif stripped.startswith("### 专业术语"):
            section = "preserves"
        elif stripped.startswith("### 替换词"):
            section = "replacements"
        elif stripped.startswith("### ") or stripped.startswith("**注意**"):
            section = None
        elif stripped.startswith("---") or stripped.startswith("#"):
            pass

        elif section == "preserves" and current_domain and stripped:
            # 顿号分隔的术语
            if "、" in stripped and "→" not in stripped:
                terms = [t.strip() for t in stripped.split("、") if t.strip()]
                current_preserves.extend(terms)

        elif section == "replacements" and stripped.startswith("- ") and "→" in stripped:
            match = re.match(r"-\s*(.+?)\s*→\s*(.+)", stripped)
            if match:
                src = match.group(1).strip()
                targets = [t.strip() for t in match.group(2).split("、") if t.strip()]
                current_replacements[src] = targets

    if current_domain:
        domains[current_domain] = {
            "preserves": current_preserves,
            "replacements": current_replacements,
        }

    return domains


def load_synonyms(ref_dir: Path = None) -> dict:
    """解析 synonyms.md → {原词: [替换词...]}"""
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
            if src in ("原词", "---") or targets_str in ("替换为", "---"):
                continue
            if "|" in targets_str:
                targets_str = targets_str.split("|")[0].strip()
            targets = [t.strip() for t in targets_str.replace("、", ",").split(",") if t.strip()]
            if targets and src:
                synonyms[src] = targets

    return synonyms


def get_domain_preserve_terms(text: str, domains: dict) -> list[str]:
    """从文本中提取需要保留的专业术语"""
    found = []
    for domain, data in domains.items():
        for term in data.get("preserves", []):
            if term in text:
                found.append(term)
    return list(set(found))


def get_domain_replacements(text: str, domains: dict, domain: str = None) -> dict:
    """从文本中找到可用的学科替换词"""
    replacements = {}
    search_domains = {domain: domains[domain]} if domain and domain in domains else domains

    for dname, data in search_domains.items():
        for src, targets in data.get("replacements", {}).items():
            if src in text:
                replacements[src] = targets

    return replacements


def get_synonym_suggestions(text: str, synonyms: dict) -> dict:
    """从文本中找到可用的同义词替换"""
    suggestions = {}
    for src, targets in synonyms.items():
        if src in text:
            suggestions[src] = targets
    return suggestions
