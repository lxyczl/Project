"""结构规律分析测试。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyzer.structure import analyze_structure


def _make_para(index: int, text: str, section_type: str = "body") -> dict:
    return {"index": index, "text": text, "char_count": len(text), "section_type": section_type}


def test_uniform_paragraphs():
    """长度过于均匀的段落应被检测。"""
    paras = [
        _make_para(0, "A" * 100),
        _make_para(1, "B" * 100),
        _make_para(2, "C" * 100),
    ]
    result = analyze_structure(paras)
    assert result["score"] > 0
    assert any(i["type"] == "uniform_para_length" for i in result["issues"])


def test_varied_paragraphs():
    """长度差异大的段落不应触发风险。"""
    paras = [
        _make_para(0, "短段"),
        _make_para(1, "B" * 200),
        _make_para(2, "C" * 50),
    ]
    result = analyze_structure(paras)
    assert result["score"] < 0.3


def test_too_few_paragraphs():
    """少于 3 段不应触发分析。"""
    paras = [_make_para(0, "第一段"), _make_para(1, "第二段")]
    result = analyze_structure(paras)
    assert result["score"] == 0.0


def test_uniform_para_start():
    """段首句模式重复应被检测。"""
    paras = [
        _make_para(0, "本文提出了一种新的方法，用于解决这个问题。"),
        _make_para(1, "本文提出了一种新的框架，用于优化性能。"),
        _make_para(2, "本文提出了一种新的方案，用于降低成本。"),
        _make_para(3, "本文提出了一种新的思路，用于提升效率。"),
    ]
    result = analyze_structure(paras)
    assert any(i["type"] == "uniform_para_start" for i in result["issues"])


def test_empty_list():
    """空列表应返回零风险。"""
    result = analyze_structure([])
    assert result["score"] == 0.0
