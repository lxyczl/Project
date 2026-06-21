"""文件 I/O 工具。"""

import json
from pathlib import Path
from typing import Any, Optional


def read_text_file(path: Path) -> str:
    """读取文本文件，自动检测编码。"""
    return path.read_text(encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    """写入 JSON 文件。"""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path) -> Optional[dict]:
    """加载 JSON 文件，不存在或损坏返回 None。"""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
