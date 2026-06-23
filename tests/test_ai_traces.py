"""AI 痕迹检测测试。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyzer.ai_traces import analyze_ai_traces


def test_too_fluent():
    """过于工整的文本应被标记。"""
    text = ("这是一个非常标准的学术论文段落。它包含了完整的句子结构。"
            "每个句子都很规范。没有口语化的表达。行文非常工整。"
            "所有句子都遵循主谓宾结构。语言表达严谨规范。")
    result = analyze_ai_traces(text)
    assert result["score"] > 0
    assert any(i["type"] == "too_fluent" for i in result["issues"])


def test_natural_text():
    """自然文本不应被误判。"""
    text = ("笔者在实验中发现——意外地——结果和预期不同。"
            "可能是参数设置的问题，也可能是数据本身的噪声。不确定。"
            "后来查了文献才知道，这个现象（虽然少见）其实有人报道过。"
            "嗯，学到了。下次得更仔细地做预实验。"
            "说实话，当时有点沮丧。不过调整之后效果好了不少。"
            "最终结果还算满意，虽然中间踩了不少坑。")
    result = analyze_ai_traces(text)
    assert result["score"] < 0.3


def test_low_burstiness():
    """连续句子长度相近应被检测。"""
    # 构造 5 句长度非常接近的文本
    text = ("这是第一个句子内容。这是第二个句子内容。"
            "这是第三个句子内容。这是第四个句子内容。"
            "这是第五个句子内容。这是第六个句子内容。")
    result = analyze_ai_traces(text)
    assert any(i["type"] == "low_burstiness" for i in result["issues"])


def test_no_personal_voice():
    """长文本无主观标记应被检测。"""
    text = ("研究表明该方法有效。实验验证了其性能。数据支持这一结论。"
            "分析显示显著提升。测试结果令人满意。评估确认了优势。"
            "对比实验证实了改进。统计检验表明差异显著。"
            "该方法在多个指标上表现优异。综合评价为正面。"
            "后续研究可进一步优化。应用前景广阔。")
    result = analyze_ai_traces(text)
    assert any(i["type"] == "no_personal_voice" for i in result["issues"])


def test_short_text_skips():
    """短文本应跳过检测。"""
    result = analyze_ai_traces("短文本。")
    assert result["score"] == 0.0
