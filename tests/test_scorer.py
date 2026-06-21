import pytest
from analyzer.scorer import score_paragraph, compute_overall_risk

def test_high_risk_paragraph():
    text = "综上所述，本文提出了一种基于深度学习的方法。该方法具有重要意义，取得了较好的效果。实验结果表明，该方法不仅性能优越，而且适用范围广泛。"
    result = score_paragraph(text, "body", [])
    assert result["risk"] > 0.5
    assert result["priority"] > 0

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
