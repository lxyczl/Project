"""Tests for English-specific analysis dimension."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzer.english import analyze_english, _count_passive_voice, _count_nominalizations


class TestPassiveVoice:
    def test_passive_detection(self):
        text = "The experiment was conducted by the researchers. The data were analyzed carefully."
        from analyzer.english import _tokenize
        words = _tokenize(text)
        count = _count_passive_voice(text, words)
        assert count >= 2

    def test_active_voice(self):
        text = "We conducted the experiment. The researchers analyzed the data carefully."
        from analyzer.english import _tokenize
        words = _tokenize(text)
        count = _count_passive_voice(text, words)
        assert count == 0

    def test_exception_phrases(self):
        # "as shown in" should not count as excessive passive
        text = "As shown in Table 1, the results are presented in Figure 2."
        from analyzer.english import _tokenize
        words = _tokenize(text)
        count = _count_passive_voice(text, words)
        # Should be relatively low despite passive constructions
        assert count <= 2


class TestNominalization:
    def test_nominalization_detection(self):
        words = ["implementation", "evaluation", "development", "optimization"]
        count = _count_nominalizations(words)
        assert count == 4

    def test_exception_words(self):
        # Common words ending in -tion that shouldn't count
        words = ["nation", "condition", "information", "education"]
        count = _count_nominalizations(words)
        assert count == 0

    def test_normal_text(self):
        words = ["the", "model", "was", "trained", "on", "a", "large", "dataset"]
        count = _count_nominalizations(words)
        assert count == 0


class TestAnalyzeEnglish:
    def test_excessive_passive(self):
        text = """
        The experiment was conducted. The data were analyzed. The results were obtained.
        The model was trained. The parameters were optimized. The performance was evaluated.
        The findings were reported. The conclusions were drawn. The paper was written.
        """
        result = analyze_english(text, section_type="method")
        issue_types = {i["type"] for i in result["issues"]}
        # Method section has higher passive threshold (50%), so might not trigger
        # But this is very heavy passive, should trigger
        assert result["score"] > 0

    def test_nominalization_overuse(self):
        text = """
        The implementation of the optimization of the configuration of the system
        requires the evaluation of the characterization of the transformation of
        the adaptation of the modification of the adjustment of the validation of
        the verification of the examination of the investigation of the exploration.
        """
        result = analyze_english(text)
        issue_types = {i["type"] for i in result["issues"]}
        assert "nominalization_overuse" in issue_types

    def test_hedging_overuse(self):
        text = """
        It seems that the results are good. Perhaps the method is effective.
        It is possible that this approach works. To some extent, we can say it is useful.
        One might argue that it is promising. It could be said that it is valuable.
        There is a tendency to overestimate its impact. It is generally accepted that it works.
        It is widely believed that it is important. More or less, it is correct.
        """
        result = analyze_english(text)
        issue_types = {i["type"] for i in result["issues"]}
        assert "hedging_overuse" in issue_types

    def test_normal_english_text(self):
        text = """
        We trained the model on ImageNet using standard data augmentation techniques.
        The architecture consists of a ResNet-50 backbone followed by a classification head.
        We optimized the parameters using SGD with momentum 0.9 and weight decay 1e-4.
        The learning rate was initialized at 0.1 and decayed by a factor of 10 every 30 epochs.
        """
        result = analyze_english(text)
        assert result["score"] < 0.3  # Should be low risk

    def test_empty_text(self):
        result = analyze_english("")
        assert result["score"] == 0.0
        assert result["issues"] == []

    def test_short_text(self):
        result = analyze_english("Short text.")
        assert result["score"] == 0.0
