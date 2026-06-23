"""词汇分布分析测试。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyzer.vocabulary import analyze_vocabulary


def test_cliche_detection():
    """套话应被检测（依赖模式库）。"""
    from analyzer.patterns import PatternLibrary
    from pathlib import Path
    lib = PatternLibrary.load(Path(__file__).resolve().parent.parent / "patterns")
    text = "综上所述，本文提出了一种方法。值得注意的是，该方法取得了较好的效果。"
    result = analyze_vocabulary(text, lib.get_patterns())
    assert result["score"] > 0
    assert any(i["type"] == "cliche_detected" for i in result["issues"])


def test_clean_text():
    """无 AI 特征的文本应低风险。"""
    text = "这个方案的思路来自对问题的拆解。我们先处理核心矛盾，再扩展到边界情况。"
    result = analyze_vocabulary(text, [])
    # 不传模式库，纯检测连接词频率和 TTR
    assert result["score"] < 0.3


def test_connector_overuse():
    """连接词过多应被检测。"""
    text = "因此我们做了第一件事。然而结果不理想。此外还有第二个问题。同时第三个问题也出现了。总之需要重新考虑。"
    result = analyze_vocabulary(text, [])
    assert any(i["type"] == "connector_overuse" for i in result["issues"])


def test_low_ttr():
    """词汇丰富度低应被检测。"""
    # 重复用词
    text = "这个方法很好。这个方法确实好。这个方法非常好。这个方法特别好。这个方法相当好。"
    result = analyze_vocabulary(text, [])
    assert any(i["type"] == "low_ttr" for i in result["issues"])


def test_pattern_library_integration():
    """模式库中的 pattern 应被用于检测。"""
    patterns = [
        {"id": "test_001", "type": "cliche", "match": "测试词", "replacements": ["替换词"],
         "platform_weight": {"cnki": 0.8}}
    ]
    text = "这段文字包含测试词，用于验证模式库匹配。"
    result = analyze_vocabulary(text, patterns)
    assert any("测试词" in i["detail"] for i in result["issues"])


def test_sentence_pattern_type():
    """sentence_pattern 类型的正则规则应被匹配。"""
    patterns = [
        {"id": "test_002", "type": "sentence_pattern", "match": "通过.*方法.*实现了",
         "replacements": ["借助…方法，达成了"], "platform_weight": {"cnki": 0.7}}
    ]
    text = "通过深度学习方法实现了目标检测。"
    result = analyze_vocabulary(text, patterns)
    assert any("通过" in i["detail"] for i in result["issues"])


def test_empty_text():
    """空文本应返回零风险。"""
    result = analyze_vocabulary("", [])
    assert result["score"] == 0.0


def test_platform_weight_affects_score():
    """不同平台权重应影响风险分。"""
    patterns = [
        {"id": "test_001", "type": "cliche", "match": "综上所述",
         "replacements": ["从整体来看"], "platform_weight": {"cnki": 0.9, "vip": 0.3}}
    ]
    text = "综上所述，本文提出了一种方法。"
    result_cnki = analyze_vocabulary(text, patterns, platform="cnki")
    result_vip = analyze_vocabulary(text, patterns, platform="vip")
    # cnki 权重更高，风险分应更高
    assert result_cnki["score"] >= result_vip["score"]


def test_platform_none_uses_full_weight():
    """不指定平台时，所有 pattern 权重为 1.0。"""
    patterns = [
        {"id": "test_001", "type": "cliche", "match": "综上所述",
         "replacements": ["从整体来看"], "platform_weight": {"cnki": 0.9}}
    ]
    text = "综上所述，本文提出了一种方法。"
    result = analyze_vocabulary(text, patterns, platform=None)
    assert result["score"] > 0
