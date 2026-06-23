"""
分析引擎测试
"""
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzer.syntax import analyze_syntax, split_sentences
from analyzer.vocabulary import analyze_vocabulary, tokenize
from analyzer.ai_traces import analyze_ai_traces
from analyzer.english import analyze_english
from analyzer.structure import analyze_structure
from analyzer.scorer import score_paragraph, score_paragraphs, compute_overall_risk
from analyzer.paragraphs import split_paragraphs, detect_section
from analyzer.patterns import PatternLibrary


class TestSyntaxAnalyzer:
    """句法分析测试"""

    def test_split_sentences(self):
        text = "The method is effective. The results show improvement. It works well."
        sentences = split_sentences(text)
        assert len(sentences) == 3

    def test_uniform_sentence_length(self):
        """句长过于均匀应检测到"""
        text = (
            "The method is very effective for this problem. "
            "The results show great improvement in accuracy. "
            "The model performs well on the benchmark dataset. "
            "The approach demonstrates significant improvements."
        )
        result = analyze_syntax(text)
        types = {i["type"] for i in result["issues"]}
        assert "uniform_sentence_length" in types

    def test_excessive_passive(self):
        """被动语态过多应检测到"""
        text = (
            "The experiment was conducted by the researchers. "
            "The data was analyzed by the team. "
            "The results were validated by experts. "
            "The findings were confirmed by independent studies."
        )
        result = analyze_syntax(text)
        types = {i["type"] for i in result["issues"]}
        assert "excessive_passive" in types

    def test_normal_text_low_score(self):
        """正常文本应该低分"""
        text = (
            "We analyzed the data using a novel approach. "
            "The results were surprising — the model outperformed all baselines. "
            "However, some limitations remain. "
            "Future work should address these challenges."
        )
        result = analyze_syntax(text)
        assert result["score"] < 0.5

    def test_passive_irregular(self):
        """不规则被动语态应被检测到"""
        text = (
            "The data was run through the model. "
            "The results were put into the table. "
            "The values were set by the algorithm. "
            "The samples were cut into pieces."
        )
        result = analyze_syntax(text)
        types = {i["type"] for i in result["issues"]}
        assert "excessive_passive" in types

    def test_split_sentences_abbreviations(self):
        """缩写不应导致误切"""
        text = "Dr. Smith conducted the experiment. The results were promising. Prof. Johnson reviewed the paper."
        sentences = split_sentences(text)
        # "Dr. Smith conducted the experiment" 应为一句，不应被切开
        assert any("Dr. Smith" in s for s in sentences)
        assert any("Prof. Johnson" in s for s in sentences)


class TestVocabularyAnalyzer:
    """词汇分析测试"""

    def test_tokenize(self):
        text = "The method is effective"
        tokens = tokenize(text)
        assert "the" in tokens
        assert "method" in tokens

    def test_low_ttr(self):
        """词汇重复率高应检测到（CTTR 下需高度重复）"""
        text = (
            "The model is good. The model is good. The model is good. "
            "The model is good. The model is good. The model is good. "
            "The model is good. The model is good. The model is good. "
            "The model is good."
        )
        result = analyze_vocabulary(text, [])
        types = {i["type"] for i in result["issues"]}
        assert "low_ttr" in types

    def test_connector_overuse(self):
        """连接词过多应检测到"""
        text = (
            "Furthermore, the results are good. Moreover, the model is fast. "
            "Consequently, we can use it. Nevertheless, there are limits. "
            "Additionally, the code is clean. Hence, it is recommended."
        )
        result = analyze_vocabulary(text, [])
        types = {i["type"] for i in result["issues"]}
        assert "connector_overuse" in types

    def test_cliche_detection(self):
        """套话应被检测到"""
        text = "In recent years, the method has gained significant attention. It is worth noting that the results are promising."
        result = analyze_vocabulary(text, [])
        types = {i["type"] for i in result["issues"]}
        assert "cliche_detected" in types

    def test_normal_text_low_score(self):
        """正常文本应该低分"""
        text = (
            "We used a random forest model to predict groundwater levels. "
            "The features included rainfall, temperature, and land use. "
            "Cross-validation confirmed the model's robustness."
        )
        result = analyze_vocabulary(text, [])
        assert result["score"] < 0.5

    def test_cttr_short_text_no_false_positive(self):
        """短文本不应因 TTR 低而误报"""
        text = "The method is effective. The approach works well."
        result = analyze_vocabulary(text, [])
        types = {i["type"] for i in result["issues"]}
        assert "low_ttr" not in types


class TestAITracesAnalyzer:
    """AI 痕迹检测测试"""

    def test_too_fluent(self):
        """过于流畅应检测到"""
        text = (
            "The method is effective for this problem. "
            "The results show significant improvement. "
            "The model outperforms all baselines. "
            "The approach demonstrates superior accuracy. "
            "The findings confirm the hypothesis. "
            "The analysis reveals important patterns."
        )
        result = analyze_ai_traces(text)
        types = {i["type"] for i in result["issues"]}
        assert "too_fluent" in types

    def test_no_personal_voice(self):
        """缺少个人表达应检测到"""
        text = (
            "The method is effective. The results show improvement. "
            "The model performs well. The approach is robust. "
            "The findings are significant. The analysis is complete. "
            "The conclusions support the hypothesis."
        )
        result = analyze_ai_traces(text)
        types = {i["type"] for i in result["issues"]}
        assert "no_personal_voice" in types

    def test_normal_text_low_score(self):
        """有个人表达的文本应该低分"""
        text = (
            "We found that the method works well. Our results show improvement. "
            "I think the model is robust. We believe the approach is novel. "
            "Our analysis reveals interesting patterns. We observed strong correlations."
        )
        result = analyze_ai_traces(text)
        assert result["score"] < 0.5


class TestEnglishAnalyzer:
    """英文特有特征测试"""

    def test_excessive_the(self):
        """冠词过度使用应检测到"""
        text = "The method is the best. The results are the most accurate. The model is the fastest. The approach is the most robust."
        result = analyze_english(text)
        types = {i["type"] for i in result["issues"]}
        assert "excessive_the" in types

    def test_verbose_phrases(self):
        """冗长短语应检测到"""
        text = (
            "In order to test the model, we used data. "
            "Due to the fact that the results were good, we continued. "
            "For the purpose of validation, we applied cross-validation. "
            "In the process of analysis, we found patterns."
        )
        result = analyze_english(text)
        types = {i["type"] for i in result["issues"]}
        assert "verbose_phrases" in types

    def test_normal_text_low_score(self):
        """正常文本应该低分"""
        text = (
            "We trained a neural network on 10,000 samples. "
            "The architecture uses three hidden layers with ReLU activation. "
            "Our experiments show 95% accuracy on the test set."
        )
        result = analyze_english(text)
        assert result["score"] < 0.5

    def test_nominalization_exceptions(self):
        """常见非名词化词不应被标记"""
        text = (
            "The nation faces a critical condition regarding its education system. "
            "The government's protection policy requires attention and direction. "
            "The situation at the station called for immediate action."
        )
        result = analyze_english(text)
        types = {i["type"] for i in result["issues"]}
        assert "excessive_nominalization" not in types


class TestStructureAnalyzer:
    """结构分析测试"""

    def test_uniform_paragraph_length(self):
        """段落长度过于均匀应检测到"""
        paragraphs = [
            {"word_count": 50, "text": "A" * 200},
            {"word_count": 51, "text": "B" * 204},
            {"word_count": 49, "text": "C" * 196},
            {"word_count": 50, "text": "D" * 200},
        ]
        result = analyze_structure(paragraphs)
        types = {i["type"] for i in result["issues"]}
        assert "uniform_para_length" in types

    def test_normal_structure_low_score(self):
        """正常结构应该低分"""
        paragraphs = [
            {"word_count": 30, "text": "Short paragraph."},
            {"word_count": 80, "text": "A much longer paragraph with more content and details."},
            {"word_count": 50, "text": "Medium length paragraph."},
        ]
        result = analyze_structure(paragraphs)
        assert result["score"] < 0.5


class TestScorer:
    """评分器测试"""

    def test_score_paragraph(self):
        """段落评分应返回完整结果"""
        text = "In recent years, the method has gained significant attention."
        result = score_paragraph(text, "introduction", [])
        assert "risk" in result
        assert "priority" in result
        assert "issues" in result
        assert "suggestion" in result
        assert 0 <= result["risk"] <= 1

    def test_score_paragraphs_sorted(self):
        """批量评分应按优先级排序"""
        paragraphs = [
            {"index": 0, "text": "In recent years, the method has gained significant attention.", "section_type": "introduction", "word_count": 11},
            {"index": 1, "text": "We used a novel approach to solve this problem.", "section_type": "methods", "word_count": 10},
            {"index": 2, "text": "The results are very good and the model is excellent.", "section_type": "results", "word_count": 11},
        ]
        results = score_paragraphs(paragraphs, [])
        assert len(results) == 3
        # 应该按优先级降序
        assert results[0]["priority"] >= results[1]["priority"] >= results[2]["priority"]

    def test_compute_overall_risk(self):
        """整体风险分应为平均值"""
        scores = [{"risk": 0.3}, {"risk": 0.5}, {"risk": 0.7}]
        assert compute_overall_risk(scores) == 0.5


class TestParagraphSplitter:
    """段落切分测试"""

    def test_split_paragraphs(self):
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        paragraphs = split_paragraphs(text)
        assert len(paragraphs) == 3

    def test_detect_section(self):
        assert detect_section("Introduction") == "introduction"
        assert detect_section("Methods") == "methods"
        assert detect_section("Results") == "results"
        assert detect_section("Discussion") == "discussion"
        assert detect_section("Conclusion") == "conclusion"

    def test_empty_text(self):
        assert split_paragraphs("") == []


class TestPatternLibrary:
    """模式库测试"""

    def test_load_builtin(self):
        patterns_dir = Path(__file__).parent.parent / "patterns"
        if patterns_dir.exists():
            lib = PatternLibrary.load(patterns_dir)
            patterns = lib.get_patterns()
            assert len(patterns) > 0

    def test_protected_terms(self):
        patterns_dir = Path(__file__).parent.parent / "patterns"
        if patterns_dir.exists():
            lib = PatternLibrary.load(patterns_dir)
            terms = lib.get_protected_terms()
            assert "DRASTIC" in terms
            assert "InVEST" in terms


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
