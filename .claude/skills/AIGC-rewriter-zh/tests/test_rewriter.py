"""改写执行层测试（context / verify / diff）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rewriter.context import build_context
from rewriter.verify import verify_accuracy
from rewriter.diff import generate_diff_report


# ── context ──

def test_build_context_basic():
    paras = [{"text": f"段落{i}。", "section_type": "body"} for i in range(5)]
    ctx = build_context(paras, 2)
    assert len(ctx["before"]) == 2
    assert len(ctx["after"]) == 2
    assert ctx["target"] == "段落2。"


def test_build_context_at_start():
    paras = [{"text": f"段落{i}。", "section_type": "body"} for i in range(5)]
    ctx = build_context(paras, 0)
    assert ctx["before"] == []
    assert len(ctx["after"]) == 2


def test_build_context_at_end():
    paras = [{"text": f"段落{i}。", "section_type": "body"} for i in range(5)]
    ctx = build_context(paras, 4)
    assert len(ctx["before"]) == 2
    assert ctx["after"] == []


def test_build_context_out_of_range():
    paras = [{"text": "段落。", "section_type": "body"}]
    try:
        build_context(paras, 5)
        assert False, "应抛出 IndexError"
    except IndexError:
        pass


def test_build_context_empty_list():
    try:
        build_context([], 0)
        assert False, "应抛出 ValueError"
    except ValueError:
        pass


# ── verify ──

def test_verify_safe_rewrite():
    original = "围护结构的热工性能直接影响建筑能耗模拟的结果。"
    rewritten = "围护结构的热工特性对建筑能耗模拟的输出有直接影响。"
    result = verify_accuracy(original, rewritten, {"围护结构", "建筑能耗模拟"})
    assert result["is_safe"]


def test_verify_term_replaced():
    original = "围护结构的热工性能直接影响建筑能耗模拟的结果。"
    rewritten = "外围结构的热工特性对建筑能耗模拟的输出有直接影响。"
    result = verify_accuracy(original, rewritten, {"围护结构", "建筑能耗模拟"})
    assert not result["is_safe"]
    assert any(s["type"] == "term_replaced" for s in result["suspects"])


def test_verify_number_changed():
    original = "准确率达到 95.3%，误差为 0.02。"
    rewritten = "准确率达到 90%，误差为 0.02。"
    result = verify_accuracy(original, rewritten, set())
    assert not result["is_safe"]
    assert any(s["type"] == "number_changed" for s in result["suspects"])


def test_verify_length_anomaly():
    original = "这是一段正常的文本。"
    rewritten = "短。"
    result = verify_accuracy(original, rewritten, set())
    assert any(s["type"] == "length_anomaly" for s in result["suspects"])


def test_verify_empty_input():
    result = verify_accuracy("", "改写文本", set())
    assert not result["is_safe"]
    assert result["suspects"][0]["type"] == "empty_text"


# ── diff ──

def test_diff_report_basic():
    results = [{
        "index": 0,
        "section_type": "body",
        "original_risk": 0.8,
        "rewritten_risk": 0.2,
        "original_text": "综上所述，本文提出了一种方法。",
        "rewritten_text": "回到前文的问题，本文的方案如下。",
        "suspects": [],
    }]
    report = generate_diff_report(results)
    assert "0" in report
    assert "0.80" in report
    assert "0.20" in report
    assert "无" in report


def test_diff_report_with_suspects():
    results = [{
        "index": 3,
        "section_type": "method",
        "original_risk": 0.7,
        "rewritten_risk": 0.3,
        "original_text": "原文内容。",
        "rewritten_text": "改写内容。",
        "suspects": [{"type": "term_replaced", "detail": "术语消失", "severity": "high"}],
    }]
    report = generate_diff_report(results)
    assert "术语消失" in report


def test_diff_report_empty():
    assert generate_diff_report([]) == ""


def test_diff_report_truncates_long_text():
    results = [{
        "index": 0,
        "section_type": "body",
        "original_risk": 0.5,
        "rewritten_risk": 0.2,
        "original_text": "A" * 100,
        "rewritten_text": "B" * 100,
        "suspects": [],
    }]
    report = generate_diff_report(results)
    assert "A" * 50 + "..." in report
    assert "B" * 50 + "..." in report
