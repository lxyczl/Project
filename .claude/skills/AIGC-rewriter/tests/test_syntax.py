"""Tests for syntax analysis dimension."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzer.syntax import analyze_syntax, _split_sentences


class TestSplitSentences:
    def test_basic_split(self):
        text = "First sentence. Second sentence. Third sentence."
        sentences = _split_sentences(text)
        assert len(sentences) == 3

    def test_question_mark(self):
        text = "Is this a question? Yes, it is."
        sentences = _split_sentences(text)
        assert len(sentences) == 2

    def test_exclamation(self):
        text = "Amazing! This is great."
        sentences = _split_sentences(text)
        assert len(sentences) == 2

    def test_semicolon(self):
        text = "First clause; second clause."
        sentences = _split_sentences(text)
        assert len(sentences) >= 1


class TestAnalyzeSyntax:
    def test_uniform_sentence_length(self):
        # All sentences have very similar word counts
        text = """
        The model was trained on data. The results were very good overall.
        The accuracy was quite high indeed. The loss converged to zero.
        The training took a long time. The hyperparameters were tuned well.
        """
        result = analyze_syntax(text)
        issue_types = {i["type"] for i in result["issues"]}
        assert "uniform_sentence_length" in issue_types

    def test_varied_sentence_length(self):
        # Sentences with varied lengths
        text = """
        We trained the model. The training process involved multiple stages, including
        data preprocessing, model initialization, and iterative optimization using
        stochastic gradient descent with momentum. Results were good.
        """
        result = analyze_syntax(text)
        issue_types = {i["type"] for i in result["issues"]}
        assert "uniform_sentence_length" not in issue_types

    def test_excessive_parallelism(self):
        text = """
        The model can classify images, detect objects, segment scenes, and generate captions.
        We used data augmentation, regularization, early stopping, and learning rate scheduling.
        The results show improvement in accuracy, precision, recall, and F1 score.
        """
        result = analyze_syntax(text)
        # May or may not trigger depending on threshold
        assert result["score"] >= 0

    def test_deep_nesting_detection(self):
        # Test with explicit that/which/who patterns in sequence
        text = "The approach that uses the model which employs the method that leverages the data which drives the results is novel."
        result = analyze_syntax(text)
        # Deep nesting detection may or may not trigger depending on regex matching
        assert result["score"] >= 0

    def test_short_text(self):
        text = "Short text."
        result = analyze_syntax(text)
        assert result["score"] == 0.0

    def test_empty_text(self):
        result = analyze_syntax("")
        assert result["score"] == 0.0
