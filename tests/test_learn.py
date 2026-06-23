"""学习功能测试（--learn-stubborn / --learn-success）。"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyze import learn_stubborn_patterns, learn_success


def test_learn_stubborn_records_pattern(tmp_path):
    """改写后仍存在的 pattern 应被记录到 learned.json。"""
    builtin = {
        "patterns": [
            {"id": "cliche_001", "type": "cliche", "match": "综上所述",
             "replacements": ["从整体来看"], "platform_weight": {"cnki": 0.9}}
        ],
        "protected_terms": []
    }
    (tmp_path / "builtin.json").write_text(json.dumps(builtin, ensure_ascii=False), encoding="utf-8")

    result = learn_stubborn_patterns(
        "综上所述，本文提出了一种方法。",
        "综上所述，本文的方案如下。",
        tmp_path,
    )
    assert result["learned_count"] == 1
    assert "综上所述" in result["stubborn_patterns"]

    # 验证 learned.json 已写入
    learned = json.loads((tmp_path / "learned.json").read_text(encoding="utf-8"))
    assert len(learned["patterns"]) == 1
    assert learned["patterns"][0]["source"] == "learned"


def test_learn_stubborn_no_match(tmp_path):
    """改写后消失的 pattern 不应被记录。"""
    builtin = {
        "patterns": [
            {"id": "cliche_001", "type": "cliche", "match": "综上所述",
             "replacements": ["从整体来看"], "platform_weight": {"cnki": 0.9}}
        ],
        "protected_terms": []
    }
    (tmp_path / "builtin.json").write_text(json.dumps(builtin, ensure_ascii=False), encoding="utf-8")

    result = learn_stubborn_patterns(
        "综上所述，本文提出了一种方法。",
        "从整体来看，本文的方案如下。",
        tmp_path,
    )
    assert result["learned_count"] == 0
    assert result["stubborn_patterns"] == []


def test_learn_stubborn_empty_original(tmp_path):
    """空原文应返回零学习。"""
    (tmp_path / "builtin.json").write_text('{"patterns": [], "protected_terms": []}', encoding="utf-8")
    result = learn_stubborn_patterns("", "改写文本", tmp_path)
    assert result["learned_count"] == 0


def test_learn_success_records_strategy(tmp_path):
    """成功改写应记录策略到 learned.json。"""
    builtin = {
        "patterns": [
            {"id": "cliche_001", "type": "cliche", "match": "综上所述",
             "replacements": ["从整体来看"], "platform_weight": {"cnki": 0.9}}
        ],
        "protected_terms": []
    }
    (tmp_path / "builtin.json").write_text(json.dumps(builtin, ensure_ascii=False), encoding="utf-8")

    result = learn_success(
        "综上所述，本文提出了一种方法。",
        "从整体来看，本文的方案如下。",
        0.8, 0.2,
        tmp_path,
    )
    assert result["recorded"] is True
    assert result["eliminated_count"] == 1
    assert "综上所述" in result["eliminated_patterns"]

    # 验证 learned.json 已写入成功策略
    learned = json.loads((tmp_path / "learned.json").read_text(encoding="utf-8"))
    assert len(learned["success_strategies"]) == 1
    assert learned["success_strategies"][0]["reduction"] == 0.6


def test_learn_success_no_eliminated(tmp_path):
    """改写后仍存在的 pattern 不算成功。"""
    builtin = {
        "patterns": [
            {"id": "cliche_001", "type": "cliche", "match": "综上所述",
             "replacements": ["从整体来看"], "platform_weight": {"cnki": 0.9}}
        ],
        "protected_terms": []
    }
    (tmp_path / "builtin.json").write_text(json.dumps(builtin, ensure_ascii=False), encoding="utf-8")

    result = learn_success(
        "综上所述，本文提出了一种方法。",
        "综上所述，本文的方案如下。",
        0.8, 0.6,
        tmp_path,
    )
    assert result["recorded"] is True
    assert result["eliminated_count"] == 0
