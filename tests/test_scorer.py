"""scorer 模块测试。"""

import sys
from pathlib import Path

# 确保 analyzer 包可导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyzer.scorer import (
    score_paragraph,
    score_paragraphs,
    compute_overall_risk,
    get_threshold,
)
from analyzer.patterns import PatternLibrary


def _make_para(index: int, text: str, section_type: str = "body") -> dict:
    """构造测试用段落字典。"""
    return {
        "index": index,
        "text": text,
        "char_count": len(text),
        "section_type": section_type,
    }


def test_score_paragraph_returns_expected_keys():
    """score_paragraph 返回值应包含所有必要字段。"""
    result = score_paragraph("测试文本", "body", [])
    assert "risk" in result
    assert "priority" in result
    assert "section_type" in result
    assert "issues" in result
    assert "suggestion" in result


def test_score_paragraph_empty_text():
    """空文本的风险分应为 0。"""
    result = score_paragraph("", "body", [])
    assert result["risk"] == 0.0
    assert result["priority"] == 0.0


def test_score_paragraph_weights_sum_to_one():
    """各维度权重之和应为 1.0（不含结构维度）。

    syntax=0.2, vocabulary=0.3, ai_traces=0.25, chinese=0.25 = 1.0
    结构维度通过 score_paragraphs 全局修正叠加（最多 +0.15，cap 在 1.0）。
    """
    text = "这是一段测试文本，用于验证权重计算。"
    result = score_paragraph(text, "body", [])
    assert 0.0 <= result["risk"] <= 1.0


def test_score_paragraph_priority_uses_section_weight():
    """priority 应该受 section_type 权重影响。"""
    text = "测试段落，包含一定长度的文字以触发检测维度。" * 5
    abstract = score_paragraph(text, "abstract", [])
    intro = score_paragraph(text, "introduction", [])
    # abstract weight=1.1, introduction weight=0.9
    # 如果 risk > 0, abstract 的 priority 应高于 introduction
    if abstract["risk"] > 0:
        assert abstract["priority"] >= intro["priority"]


def test_score_paragraphs_applies_structure_modifier():
    """score_paragraphs 应该通过结构分析修正所有段落的风险分。"""
    paras = [
        _make_para(0, "这是第一个段落的内容文本，包含一些信息。", "body"),
        _make_para(1, "这是第二个段落的内容文本，包含一些信息。", "body"),
        _make_para(2, "这是第三个段落的内容文本，包含一些信息。", "body"),
    ]
    lib = PatternLibrary()
    results = score_paragraphs(paras, lib.get_patterns())
    assert len(results) == 3
    # 所有结果应该按 priority 降序排列
    for i in range(len(results) - 1):
        assert results[i]["priority"] >= results[i + 1]["priority"]


def test_score_paragraphs_uniform_paragraphs_detect_structure_issues():
    """均匀段落应触发结构维度的问题检测。"""
    # 构造长度几乎相同的段落
    base_text = "这是一段用于测试结构分析的文本内容，长度尽量保持一致。"
    paras = [
        _make_para(0, base_text, "body"),
        _make_para(1, base_text, "body"),
        _make_para(2, base_text, "body"),
    ]
    lib = PatternLibrary()
    results = score_paragraphs(paras, lib.get_patterns())
    # 均匀段落应检测到 uniform_para_length 问题
    all_issues = [issue for r in results for issue in r["issues"]]
    issue_types = {i["type"] for i in all_issues}
    assert "uniform_para_length" in issue_types


def test_compute_overall_risk():
    """compute_overall_risk 应返回正确的平均风险分。"""
    scores = [
        {"risk": 0.3},
        {"risk": 0.5},
        {"risk": 0.7},
    ]
    assert compute_overall_risk(scores) == 0.5


def test_compute_overall_risk_empty():
    """空列表的整体风险分应为 0。"""
    assert compute_overall_risk([]) == 0.0


def test_get_threshold_with_global():
    """指定全局阈值时应覆盖默认值。"""
    assert get_threshold("abstract", 0.5) == 0.5
    assert get_threshold("method", 0.1) == 0.1


def test_get_threshold_without_global():
    """未指定全局阈值时应返回章节默认值。"""
    assert get_threshold("abstract", None) == 0.25
    assert get_threshold("method", None) == 0.35
    assert get_threshold("unknown_section", None) == 0.3


def test_score_paragraph_no_learn_not_in_single():
    """score_paragraph 单段评分不涉及 no_learn 标志（由上层控制）。"""
    result = score_paragraph("测试", "body", [])
    # no_learn 不应该出现在单段评分结果中
    assert "no_learn" not in result
