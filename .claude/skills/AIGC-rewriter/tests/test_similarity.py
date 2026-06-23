"""Tests for similarity calculation module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.similarity import (
    calculate_similarity,
    find_longest_common_substring,
    find_sentence_level_matches,
    find_consecutive_matches,
    suggest_techniques,
    _word_tokenize,
    CONSECUTIVE_WARNING,
)


class TestTokenize:
    def test_basic_tokenization(self):
        text = "The model achieved 95% accuracy."
        tokens = _word_tokenize(text)
        assert len(tokens) > 0
        assert "model" in [t.lower() for t in tokens]

    def test_empty_text(self):
        tokens = _word_tokenize("")
        assert tokens == []


class TestCalculateSimilarity:
    def test_identical_texts(self):
        text = "The model was trained on a large dataset."
        result = calculate_similarity(text, text)
        assert result["unigram_overlap"] == 1.0
        assert result["bigram_overlap"] == 1.0
        assert result["trigram_overlap"] == 1.0
        assert result["max_consecutive"] > 0

    def test_completely_different(self):
        orig = "The model performed well on the benchmark."
        rew = "A cat sat on the mat in the sun."
        result = calculate_similarity(orig, rew)
        assert result["unigram_overlap"] < 0.5

    def test_partial_overlap(self):
        orig = "The model was trained on a large dataset to achieve high accuracy."
        rew = "We trained the model using a large dataset, achieving high accuracy."
        result = calculate_similarity(orig, rew)
        assert 0.2 < result["unigram_overlap"] < 0.8

    def test_empty_texts(self):
        result = calculate_similarity("", "")
        assert result["unigram_overlap"] == 0
        assert result["max_consecutive"] == 0


class TestFindLongestCommonSubstring:
    def test_identical(self):
        text = "hello world"
        assert find_longest_common_substring(text, text) > 0

    def test_no_match(self):
        assert find_longest_common_substring("abc", "xyz") == 0

    def test_partial_match(self):
        orig = "the model was trained"
        rew = "we trained the model"
        result = find_longest_common_substring(orig, rew)
        assert result >= 2  # At least "the model" or "trained the"


class TestFindSentenceLevelMatches:
    def test_matching_sentences(self):
        orig = "The model performed well. The results were excellent."
        rew = "The model performed well. The outcomes were excellent."
        matches = find_sentence_level_matches(orig, rew, threshold=0.5)
        assert len(matches) > 0

    def test_no_matches(self):
        orig = "The model performed well."
        rew = "A completely different topic here."
        matches = find_sentence_level_matches(orig, rew, threshold=0.5)
        assert len(matches) == 0

    def test_empty_texts(self):
        matches = find_sentence_level_matches("", "", threshold=0.5)
        assert matches == []


class TestFindConsecutiveMatches:
    def test_long_match(self):
        orig = "the quick brown fox jumps over the lazy dog"
        rew = "the quick brown fox runs over the lazy cat"
        matches = find_consecutive_matches(orig, rew, min_length=3)
        assert len(matches) > 0
        assert any(m["length"] >= 4 for m in matches)

    def test_no_match(self):
        matches = find_consecutive_matches("abc", "xyz", min_length=2)
        assert matches == []


class TestSuggestTechniques:
    def test_long_consecutive(self):
        metrics = {"max_consecutive": 10, "trigram_overlap": 0.1}
        techniques = suggest_techniques(metrics)
        assert "Restructure sentence" in techniques

    def test_high_trigram(self):
        metrics = {"max_consecutive": 3, "trigram_overlap": 0.3}
        techniques = suggest_techniques(metrics)
        assert "Synonym replacement" in techniques

    def test_low_similarity(self):
        metrics = {"max_consecutive": 2, "trigram_overlap": 0.1}
        techniques = suggest_techniques(metrics)
        assert len(techniques) > 0
