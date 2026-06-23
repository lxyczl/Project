"""analyze.py 集成测试。"""

import sys
from pathlib import Path

# 确保项目根目录可导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyze import analyze_text


SAMPLE_TEXT = """近年来，随着建筑能耗问题日益突出，建筑能耗模拟技术得到了广泛关注。
建筑能耗模拟是评估建筑节能性能的重要手段，对于推动建筑节能具有重要意义。
本文提出了一种基于深度学习的建筑能耗预测方法，通过构建神经网络模型实现了对建筑能耗的精准预测。
实验结果表明，该方法在预测精度和计算效率方面均优于传统方法。"""


def test_analyze_text_returns_overall_risk():
    """analyze_text 应返回 overall_risk 字段。"""
    result = analyze_text(SAMPLE_TEXT, False, None, None)
    assert "overall_risk" in result
    assert isinstance(result["overall_risk"], float)


def test_analyze_text_returns_paragraphs():
    """analyze_text 应返回 paragraphs 列表。"""
    result = analyze_text(SAMPLE_TEXT, False, None, None)
    assert "paragraphs" in result
    assert isinstance(result["paragraphs"], list)
    assert len(result["paragraphs"]) > 0


def test_analyze_text_returns_no_learn():
    """analyze_text 默认应返回 no_learn=False。"""
    result = analyze_text(SAMPLE_TEXT, False, None, None)
    assert "no_learn" in result
    assert result["no_learn"] is False


def test_analyze_text_no_learn_true():
    """传入 no_learn=True 时，结果应反映该标志。"""
    result = analyze_text(SAMPLE_TEXT, False, None, None, no_learn=True)
    assert result["no_learn"] is True


def test_analyze_text_empty_input():
    """空输入应返回零风险。"""
    result = analyze_text("  ", False, None, None)
    assert result["overall_risk"] == 0.0
    assert result["paragraphs"] == []


def test_analyze_text_with_threshold():
    """指定阈值时，结果中的段落应携带 threshold 字段。"""
    result = analyze_text(SAMPLE_TEXT, False, 0.2, None)
    for para in result["paragraphs"]:
        assert "threshold" in para
        assert para["threshold"] == 0.2


def test_analyze_text_paragraph_structure():
    """每个段落结果应包含 risk、priority、section_type、issues、suggestion。"""
    result = analyze_text(SAMPLE_TEXT, False, None, None)
    for para in result["paragraphs"]:
        assert "risk" in para
        assert "priority" in para
        assert "section_type" in para
        assert "issues" in para
        assert "suggestion" in para
        assert "index" in para


def test_analyze_text_risk_range():
    """整体风险分应在 [0, 1] 范围内。"""
    result = analyze_text(SAMPLE_TEXT, False, None, None)
    assert 0.0 <= result["overall_risk"] <= 1.0


def test_analyze_text_markdown_mode():
    """Markdown 模式下应正确识别章节。"""
    md_text = "# 引言\n这是引言内容。\n\n# 方法\n这是方法内容。"
    result = analyze_text(md_text, True, None, None)
    section_types = {p["section_type"] for p in result["paragraphs"]}
    assert "introduction" in section_types or "method" in section_types
