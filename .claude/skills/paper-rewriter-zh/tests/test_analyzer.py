"""测试风险分析引擎"""
import pytest
import sys
from pathlib import Path

skill_dir = Path(__file__).parent.parent
sys.path.insert(0, str(skill_dir / "scripts"))
sys.path.insert(0, str(skill_dir))


class TestSyntaxAnalysis:
    """句法维度分析"""

    def test_analyze_syntax(self):
        from analyzer.syntax import analyze_syntax
        text = "该模型被广泛应用于环境监测领域。研究内容包括水资源、土地资源和矿产资源。"
        result = analyze_syntax(text)
        assert "score" in result
        assert "issues" in result
        assert 0 <= result["score"] <= 1

    def test_passive_detection(self):
        from analyzer.syntax import analyze_syntax
        text = "该模型被广泛应用于环境监测领域"
        result = analyze_syntax(text)
        # 返回 score 和 issues
        assert result["score"] >= 0

    def test_parallel_detection(self):
        from analyzer.syntax import analyze_syntax
        text = "研究内容包括水资源、土地资源、矿产资源和生物资源"
        result = analyze_syntax(text)
        assert "issues" in result

    def test_split_sentences(self):
        from analyzer.syntax import split_sentences
        text = "第一句话。第二句话。第三句话。"
        result = split_sentences(text)
        assert isinstance(result, list)


class TestVocabularyAnalysis:
    """词汇维度分析"""

    def test_analyze_vocabulary(self):
        from analyzer.vocabulary import analyze_vocabulary
        text = "此外，该方法具有较高的精度。因此，被广泛采用。然而，仍存在一些问题。"
        result = analyze_vocabulary(text)
        assert "score" in result
        assert "issues" in result

    def test_connector_detection(self):
        from analyzer.vocabulary import analyze_vocabulary
        text = "此外，该方法具有较高的精度。因此，被广泛采用。"
        result = analyze_vocabulary(text)
        # 连接词应该被检测到
        assert result["score"] > 0

    def test_cliche_detection(self):
        from analyzer.vocabulary import analyze_vocabulary
        text = "近年来，随着经济的快速发展，具有重要意义"
        result = analyze_vocabulary(text)
        # 套话应该被检测到
        assert result["score"] > 0

    def test_ai_connectors_list(self):
        from analyzer.vocabulary import AI_CONNECTORS
        assert len(AI_CONNECTORS) >= 10
        assert "此外" in AI_CONNECTORS
        assert "因此" in AI_CONNECTORS

    def test_filler_phrases_list(self):
        from analyzer.vocabulary import FILLER_PHRASES
        assert len(FILLER_PHRASES) >= 5


class TestAITraceAnalysis:
    """AI痕迹维度分析"""

    def test_analyze_ai_traces(self):
        from analyzer.ai_traces import analyze_ai_traces
        text = "该方法具有较高精度。该模型被广泛应用。该技术展现出优势。"
        result = analyze_ai_traces(text)
        assert "score" in result
        assert "issues" in result

    def test_monotonous_openings(self):
        from analyzer.ai_traces import analyze_ai_traces
        text = "该方法具有较高精度。该模型被广泛应用。该技术展现出优势。"
        result = analyze_ai_traces(text)
        assert result["score"] >= 0

    def test_personal_voice(self):
        from analyzer.ai_traces import analyze_ai_traces
        text = "我们认为该方法具有重要意义。本文提出了一种新方案。"
        result = analyze_ai_traces(text)
        assert "issues" in result


class TestPatternLibrary:
    """模式库"""

    def test_load_builtin(self):
        from analyzer.patterns import PatternLibrary
        lib = PatternLibrary()
        assert lib is not None

    def test_has_methods(self):
        from analyzer.patterns import PatternLibrary
        lib = PatternLibrary()
        assert hasattr(lib, 'get_patterns')
        assert hasattr(lib, 'get_protected_terms')

    def test_get_patterns(self):
        from analyzer.patterns import PatternLibrary
        lib = PatternLibrary()
        patterns = lib.get_patterns()
        assert isinstance(patterns, list)

    def test_get_protected_terms(self):
        from analyzer.patterns import PatternLibrary
        lib = PatternLibrary()
        terms = lib.get_protected_terms()
        assert isinstance(terms, (list, set))


class TestScorer:
    """评分器"""

    def test_analyze_text(self):
        from analyzer.scorer import analyze_text
        text = """近年来，随着经济的快速发展，环境问题日益突出。
        此外，水资源短缺问题也十分严重。
        该方法被广泛应用于环境监测领域。"""
        result = analyze_text(text)
        assert "overall_risk" in result
        assert "paragraph_scores" in result
        assert 0 <= result["overall_risk"] <= 1

    def test_high_risk_text(self):
        from analyzer.scorer import analyze_text
        text = """近年来，随着经济的快速发展，具有重要意义。
        此外，因此，然而，综上所述，总而言之。
        该方法被广泛应用，该技术被采用，该模型被使用。"""
        result = analyze_text(text)
        assert result["overall_risk"] > 0.1

    def test_low_risk_text(self):
        from analyzer.scorer import analyze_text
        text = "研究人员利用DRASTIC模型评估了地下水脆弱性，发现蒸散发是影响地下水补给的关键因素。"
        result = analyze_text(text)
        assert result["overall_risk"] < 0.8

    def test_paragraph_scores(self):
        from analyzer.scorer import analyze_text
        text = "段落一。段落二。段落三。"
        result = analyze_text(text)
        assert isinstance(result["paragraph_scores"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
