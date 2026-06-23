"""句法特征分析测试。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyzer.syntax import analyze_syntax


def test_uniform_sentences():
    """句长过于均匀应触发风险。"""
    text = "这是第一个测试句子。这是第二个测试句子。这是第三个测试句子。"
    result = analyze_syntax(text)
    assert result["score"] > 0
    assert any(i["type"] == "uniform_sentence_length" for i in result["issues"])


def test_varied_sentences():
    """句长变化丰富应低风险。"""
    text = "短句。这是一个明显更长的句子，包含更多的内容和细节描述。中等长度的句子。"
    result = analyze_syntax(text)
    assert result["score"] < 0.3


def test_short_text():
    """少于 2 句的文本不应触发分析。"""
    result = analyze_syntax("一句话。")
    assert result["score"] == 0.0
    assert result["issues"] == []


def test_excessive_parallelism():
    """并列结构过多应被检测。"""
    text = "第一个内容，第二个内容，第三个内容，第四个内容。" * 3
    result = analyze_syntax(text)
    assert any(i["type"] == "excessive_parallelism" for i in result["issues"])


def test_deep_nesting():
    """深层嵌套应被检测。"""
    text = "基于深度学习的方法的性能的提升的幅度超过了预期。这是另一句话。"
    result = analyze_syntax(text)
    assert any(i["type"] == "deep_nesting" for i in result["issues"])


def test_score_capped_at_one():
    """风险分不应超过 1.0。"""
    # 构造触发所有维度的文本
    text = ("的的的的的的的的的的。" * 10 +
            "第一个，第二个，第三个，第四个。" * 5 +
            "这是完全相同长度的句子。这是完全相同长度的句子。这是完全相同长度的句子。")
    result = analyze_syntax(text)
    assert result["score"] <= 1.0
