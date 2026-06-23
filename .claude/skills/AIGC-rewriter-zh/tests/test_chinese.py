"""中文特化分析测试。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyzer.chinese import analyze_chinese


def test_excessive_le():
    """"了"字密度过高应被检测。"""
    text = "这个方法被证明了是有效的。实验验证了这个结论。我们观察了数据变化了。结果表明了方法的优势了。这个改进了整体性能了。"
    result = analyze_chinese(text)
    assert result["score"] > 0
    assert any(i["type"] == "excessive_le" for i in result["issues"])


def test_de_nesting():
    """"的"字嵌套过深应被检测（需要 >2 处匹配）。"""
    # 构造 3+ 处"的"字三层嵌套
    text = ("基于深度学习的方法的性能的提升的幅度超过了预期。"
            "该模型的精度的提升的幅度令人满意。"
            "系统的效率的改善的幅度也很显著。"
            "这是一个额外的句子用来凑长度。")
    result = analyze_chinese(text)
    assert any(i["type"] == "de_nesting" for i in result["issues"])


def test_bei_suo_pattern():
    """"被…所…"句式应被检测（需要 >2 处匹配）。"""
    # "被...所..." 需要在 20 字内同时出现
    text = ("该理论被实验所验证。该框架被业界所认可。"
            "该方案被数据所支持。该结论被文献所引用。"
            "这是一个额外的句子用来凑长度。")
    result = analyze_chinese(text)
    assert any(i["type"] == "bei_suo_pattern" for i in result["issues"])


def test_short_text_skipped():
    """少于 50 字的文本应跳过分析。"""
    result = analyze_chinese("短文本。")
    assert result["score"] == 0.0
    assert result["issues"] == []


def test_normal_text():
    """正常文本不应被误判。"""
    text = ("笔者在搭建实验环境时遇到了一个意外——服务器的 GPU 内存不够。"
            "最后换了 batch size 才解决，虽然浪费了不少时间。")
    result = analyze_chinese(text)
    assert result["score"] < 0.3


def test_score_capped_at_one():
    """风险分不应超过 1.0。"""
    # 构造触发所有维度的文本
    text = ("了了了了了了了了了了了了了了了了了了了了了了了了了了了了了了了了了了了了了了了了。"
            "被这个结果所验证了。被那个方法所证明了。被实验所支持了。")
    result = analyze_chinese(text)
    assert result["score"] <= 1.0
