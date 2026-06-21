import pytest
from analyzer.scorer import score_paragraph, compute_overall_risk, score_paragraphs, get_threshold

def test_high_risk_paragraph():
    # 9 sentences, uniform length (~20 chars), AI cliches + connectors + "的" nesting + "了" density
    # Triggers all 4 dimensions: syntax, vocabulary, ai_traces, chinese
    # Weights: syntax=0.2, vocabulary=0.25, ai_traces=0.2, chinese=0.2 (base=0.85, structure=0.15 via score_paragraphs)
    text = (
        "综上所述，本文提出了一种基于深度学习的方法。"
        "值得注意的是，该方法取得了较好的效果。"
        "此外，该方法具有较好的新的基于深度的意义。"
        "近年来该方法引起了广泛的关注和讨论。"
        "在此基础上，取得了较好的新的深度的效果。"
        "总之，该方法不仅性能优越，而且适用范围广泛。"
        "然而，该方法仍存在一些不足之处。"
        "同时，本文提出了较好的新的深度的方案。"
        "综上所述，该方法取得了较好的效果。"
    )
    # score_paragraph 基础分（不含结构维度），通过 score_paragraphs 加结构后应 > 0.4
    para = {"index": 0, "text": text, "char_count": len(text), "section_type": "body"}
    results = score_paragraphs([para], [])
    assert results[0]["risk"] > 0.4
    assert results[0]["priority"] > 0

def test_low_risk_paragraph():
    text = "笔者在搭建实验环境时遇到了一个意外——服务器的 GPU 内存不够。最后换了 batch size 才解决。"
    result = score_paragraph(text, "body", [])
    assert result["risk"] < 0.3

def test_priority_ranking():
    text = "综上所述，实验结果表明该方法有效。"
    body = score_paragraph(text, "body", [])
    discussion = score_paragraph(text, "discussion", [])
    assert discussion["priority"] > body["priority"]

def test_overall_risk():
    scores = [
        {"risk": 0.8, "section_type": "body"},
        {"risk": 0.2, "section_type": "body"},
    ]
    avg = compute_overall_risk(scores)
    assert 0.4 < avg < 0.6

def test_score_paragraphs_sorts_by_priority():
    paragraphs = [
        {"text": "低风险段落。", "section_type": "body", "index": 0},
        {"text": "综上所述，本文提出了一种基于深度学习的方法。值得注意的是，该方法取得了较好的效果。此外，该方法具有较好的新的基于深度的意义。近年来该方法引起了广泛的关注和讨论。在此基础上，取得了较好的新的深度的效果。总之，该方法不仅性能优越，而且适用范围广泛。然而，该方法仍存在一些不足之处。同时，本文提出了较好的新的深度的方案。综上所述，该方法取得了较好的效果。", "section_type": "body", "index": 1},
    ]
    results = score_paragraphs(paragraphs, [])
    assert results[0]["risk"] >= results[1]["risk"]

def test_get_threshold():
    assert get_threshold("body", None) == 0.3
    assert get_threshold("body", 0.5) == 0.5
    assert get_threshold("abstract", None) == 0.25
