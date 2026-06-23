"""模式库加载器（英文）。"""

import json
from pathlib import Path
from typing import List, Optional, Set


class PatternLibrary:
    """加载并管理内置、用户自定义和机器学习的模式规则。"""

    def __init__(self) -> None:
        self._patterns: List[dict] = []
        self._protected_terms: Set[str] = set()
        self._learned_path: Optional[Path] = None
        self._learned_data: dict = {
            "patterns": [],
            "protected_terms": [],
            "success_strategies": [],
        }

    @classmethod
    def load(cls, base_dir: Path) -> "PatternLibrary":
        """从目录加载 builtin.json / user.json / learned.json。"""
        lib = cls()
        lib._learned_path = base_dir / "learned.json"
        seen_ids: Set[str] = set()

        for filename in ("builtin.json", "user.json", "learned.json"):
            filepath = base_dir / filename
            data = cls._safe_load(filepath)
            if data:
                for pattern in data.get("patterns", []):
                    pid = pattern.get("id")
                    if pid and pid in seen_ids:
                        lib._patterns = [p for p in lib._patterns if p.get("id") != pid]
                    if pid:
                        seen_ids.add(pid)
                    lib._patterns.append(pattern)
                lib._protected_terms.update(data.get("protected_terms", []))
                if filename == "learned.json":
                    lib._learned_data = data
                    lib._learned_data.setdefault("success_strategies", [])
                    lib._learned_data.setdefault("patterns", [])
                    lib._learned_data.setdefault("protected_terms", [])

        return lib

    @staticmethod
    def _safe_load(path: Path) -> Optional[dict]:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def get_patterns(self) -> List[dict]:
        return list(self._patterns)

    def get_protected_terms(self) -> Set[str]:
        return set(self._protected_terms)

    def add_learned_pattern(self, pattern: dict) -> None:
        self._patterns.append(pattern)
        self._learned_data["patterns"].append(pattern)

    def add_success_strategy(self, strategy: dict) -> None:
        self._learned_data["success_strategies"].append(strategy)

    def get_success_strategies(self) -> List[dict]:
        return list(self._learned_data.get("success_strategies", []))

    def get_learned_patterns(self) -> List[dict]:
        return [p for p in self._patterns if p.get("source") == "learned"]

    def save_learned(self) -> None:
        if self._learned_path:
            try:
                self._learned_path.write_text(
                    json.dumps(self._learned_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except OSError as e:
                print(f"Warning: Failed to save learned.json ({e})")
