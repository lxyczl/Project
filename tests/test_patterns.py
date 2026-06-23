"""模式库加载器测试。"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyzer.patterns import PatternLibrary


def test_load_patterns(tmp_path):
    """应正确加载 builtin.json 中的 pattern。"""
    builtin = {
        "patterns": [
            {"id": "test_001", "type": "cliche", "match": "测试词",
             "replacements": ["替换词"], "platform_weight": {"cnki": 0.8}}
        ],
        "protected_terms": ["测试术语"]
    }
    (tmp_path / "builtin.json").write_text(json.dumps(builtin, ensure_ascii=False), encoding="utf-8")
    lib = PatternLibrary.load(tmp_path)
    assert len(lib.get_patterns()) == 1
    assert lib.get_patterns()[0]["id"] == "test_001"


def test_protected_terms_merge(tmp_path):
    """多个文件的 protected_terms 应合并。"""
    builtin = {"patterns": [], "protected_terms": ["术语A"]}
    user = {"patterns": [], "protected_terms": ["术语B"]}
    (tmp_path / "builtin.json").write_text(json.dumps(builtin, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "user.json").write_text(json.dumps(user, ensure_ascii=False), encoding="utf-8")
    lib = PatternLibrary.load(tmp_path)
    terms = lib.get_protected_terms()
    assert "术语A" in terms
    assert "术语B" in terms


def test_add_and_save_learned(tmp_path):
    """添加的 learned pattern 应持久化。"""
    builtin = {"patterns": [], "protected_terms": []}
    (tmp_path / "builtin.json").write_text(json.dumps(builtin, ensure_ascii=False), encoding="utf-8")
    lib = PatternLibrary.load(tmp_path)
    lib.add_learned_pattern({"id": "learned_001", "type": "cliche", "match": "新词"})
    lib.save_learned()

    # 重新加载验证
    lib2 = PatternLibrary.load(tmp_path)
    ids = [p["id"] for p in lib2.get_patterns()]
    assert "learned_001" in ids


def test_load_missing_file(tmp_path):
    """缺少某个文件时不应崩溃。"""
    (tmp_path / "builtin.json").write_text('{"patterns": [], "protected_terms": []}', encoding="utf-8")
    lib = PatternLibrary.load(tmp_path)
    assert len(lib.get_patterns()) == 0


def test_load_corrupted_file(tmp_path):
    """损坏的文件应被跳过。"""
    (tmp_path / "builtin.json").write_text("not json", encoding="utf-8")
    (tmp_path / "user.json").write_text('{"patterns": [], "protected_terms": []}', encoding="utf-8")
    lib = PatternLibrary.load(tmp_path)
    assert len(lib.get_patterns()) == 0


def test_duplicate_id_override(tmp_path):
    """同 id 的 pattern 应被后者覆盖。"""
    builtin = {"patterns": [{"id": "p1", "type": "cliche", "match": "旧"}], "protected_terms": []}
    user = {"patterns": [{"id": "p1", "type": "cliche", "match": "新"}], "protected_terms": []}
    (tmp_path / "builtin.json").write_text(json.dumps(builtin, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "user.json").write_text(json.dumps(user, ensure_ascii=False), encoding="utf-8")
    lib = PatternLibrary.load(tmp_path)
    matches = [p["match"] for p in lib.get_patterns() if p["id"] == "p1"]
    assert matches == ["新"]


def test_get_patterns_returns_copy(tmp_path):
    """get_patterns 应返回副本，不影响内部状态。"""
    builtin = {"patterns": [{"id": "p1"}], "protected_terms": []}
    (tmp_path / "builtin.json").write_text(json.dumps(builtin, ensure_ascii=False), encoding="utf-8")
    lib = PatternLibrary.load(tmp_path)
    patterns = lib.get_patterns()
    patterns.clear()
    assert len(lib.get_patterns()) == 1
