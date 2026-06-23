"""Tests for vocabulary analysis dimension."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzer.vocabulary import analyze_vocabulary, _tokenize, AI_CONNECTORS


class TestTokenize:
    def test_basic_tokenization(self):
        text = "The model achieved 95% accuracy."
        tokens = _tokenize(text)
        assert len(tokens) > 0
        assert "model" in [t.lower() for t in tokens]

    def test_empty_text(self):
        tokens = _tokenize("")
        assert tokens == []

    def test_contraction_handling(self):
        text = "We don't think it's working."
        tokens = _tokenize(text)
        assert len(tokens) > 0


class TestAnalyzeVocabulary:
    def test_normal_text(self, sample_normal_text, patterns_dir):
        from analyzer.patterns import PatternLibrary
        lib = PatternLibrary.load(patterns_dir)
        result = analyze_vocabulary(sample_normal_text, lib.get_patterns())
        assert "score" in result
        assert "issues" in result
        assert result["score"] < 0.5  # Normal text should have low risk

    def test_cliche_dense_text(self, patterns_dir):
        text = "In recent years, it is worth noting that this plays a crucial role. Furthermore, it has gained significant attention."
        from analyzer.patterns import PatternLibrary
        lib = PatternLibrary.load(patterns_dir)
        result = analyze_vocabulary(text, lib.get_patterns())
        assert result["score"] > 0.2
        issue_types = {i["type"] for i in result["issues"]}
        assert "cliche_detected" in issue_types

    def test_connector_overuse(self, patterns_dir):
        text = "The model was trained. However, the results were bad. Therefore, we changed it. Furthermore, we added layers. Moreover, we adjusted rates. Additionally, we used augmentation. Consequently, it improved."
        from analyzer.patterns import PatternLibrary
        lib = PatternLibrary.load(patterns_dir)
        result = analyze_vocabulary(text, lib.get_patterns())
        issue_types = {i["type"] for i in result["issues"]}
        assert "connector_overuse" in issue_types

    def test_platform_weighting(self, patterns_dir):
        text = "In recent years, this has gained significant attention."
        from analyzer.patterns import PatternLibrary
        lib = PatternLibrary.load(patterns_dir)
        result_turnitin = analyze_vocabulary(text, lib.get_patterns(), "turnitin")
        result_gptzero = analyze_vocabulary(text, lib.get_patterns(), "gptzero")
        # Turnitin should have higher score due to higher platform weights
        assert result_turnitin["score"] >= result_gptzero["score"]


class TestConnectors:
    def test_connector_list_complete(self):
        assert len(AI_CONNECTORS) >= 15
        assert "however" in AI_CONNECTORS
        assert "therefore" in AI_CONNECTORS
        assert "furthermore" in AI_CONNECTORS
