"""相似度计算模块测试。"""
import pytest
from utils.similarity import (
    calculate_similarity,
    find_consecutive_matches,
    find_longest_common_substring,
    find_sentence_level_matches,
    format_report,
    ngrams,
    suggest_techniques,
    tokenize,
    _char_tokenize,
    _filter_stopwords,
    CONSECUTIVE_WARNING,
)


class TestTokenize:
    def test_char_tokenize_cjk(self):
        tokens = _char_tokenize("你好世界")
        assert tokens == ["你", "好", "世", "界"]

    def test_char_tokenize_mixed(self):
        tokens = _char_tokenize("测试123abc")
        assert tokens == ["测", "试", "123"]

    def test_char_tokenize_empty(self):
        assert _char_tokenize("") == []

    def test_tokenize_fallback(self):
        """无 jieba 时 fallback 到字符级"""
        tokens = tokenize("测试文本", mode="char")
        assert len(tokens) == 4

    def test_tokenize_word_mode(self):
        """word 模式应返回非空 token 列表"""
        tokens = tokenize("本研究分析了重要问题", mode="word")
        assert len(tokens) >= 2


class TestNgrams:
    def test_bigrams(self):
        result = ngrams(["a", "b", "c", "d"], 2)
        assert result == [("a", "b"), ("b", "c"), ("c", "d")]

    def test_trigrams(self):
        result = ngrams(["a", "b", "c", "d"], 3)
        assert result == [("a", "b", "c"), ("b", "c", "d")]

    def test_ngrams_too_short(self):
        result = ngrams(["a"], 2)
        assert result == []


class TestLongestCommonSubstring:
    def test_identical(self):
        assert find_longest_common_substring("测试", "测试") == 2

    def test_no_match(self):
        assert find_longest_common_substring("abc", "xyz") == 0

    def test_partial_match(self):
        result = find_longest_common_substring("这是一个测试文本", "那是一个测试案例")
        assert result >= 4  # "是一个测试"


class TestCalculateSimilarity:
    def test_identical_text(self):
        m = calculate_similarity("测试文本", "测试文本")
        assert m["unigram_overlap"] == 1.0
        assert m["max_consecutive"] == 4

    def test_completely_different(self):
        m = calculate_similarity("甲乙丙丁", "子丑寅卯")
        assert m["unigram_overlap"] == 0.0
        assert m["max_consecutive"] == 0

    def test_returns_expected_keys(self):
        m = calculate_similarity("测试", "文本")
        expected = {
            "unigram_overlap", "bigram_overlap", "trigram_overlap",
            "max_consecutive", "vocabulary_diversity",
            "original_char_count", "rewritten_char_count",
            "token_mode", "content_word_overlap",
        }
        assert set(m.keys()) == expected

    def test_empty_input(self):
        m = calculate_similarity("", "测试")
        assert m["unigram_overlap"] == 0.0

    def test_word_count(self):
        m = calculate_similarity("这是一个测试", "这是一次检验")
        assert m["original_char_count"] == 6
        assert m["rewritten_char_count"] == 6


class TestFindConsecutiveMatches:
    def test_no_match(self):
        matches = find_consecutive_matches("甲乙丙丁", "子丑寅卯", min_length=2)
        assert matches == []

    def test_short_match_below_threshold(self):
        matches = find_consecutive_matches("测试文本", "测试案例", min_length=5)
        assert matches == []


class TestFindSentenceLevelMatches:
    def test_empty_input(self):
        assert find_sentence_level_matches("", "") == []

    def test_similar_sentences(self):
        orig = "本研究分析了重要的学术问题。本研究发现了新的研究方法。"
        rewr = "本研究分析了关键的学术问题。本研究发现了新的研究方法。"
        matches = find_sentence_level_matches(orig, rewr, threshold=0.5)
        assert len(matches) >= 1

    def test_no_matches_below_threshold(self):
        orig = "甲乙丙丁。"
        rewr = "子丑寅卯。"
        matches = find_sentence_level_matches(orig, rewr, threshold=0.5)
        assert matches == []


class TestSuggestTechniques:
    def test_high_consecutive(self):
        techs = suggest_techniques({"max_consecutive": 15, "trigram_overlap": 0})
        assert "句式重构" in techs

    def test_medium_consecutive(self):
        techs = suggest_techniques({"max_consecutive": 11, "trigram_overlap": 0})
        assert "句式重构" in techs

    def test_high_trigram(self):
        techs = suggest_techniques({"max_consecutive": 5, "trigram_overlap": 0.3})
        assert "同义词替换" in techs

    def test_default(self):
        techs = suggest_techniques({"max_consecutive": 3, "trigram_overlap": 0.1})
        assert "同义词替换" in techs


class TestFormatReport:
    def test_report_contains_metrics(self):
        report = format_report("测试原文", "改写后文本")
        assert "相似度分析报告" in report
        assert "字/词重叠率" in report
        assert "最长连续匹配" in report

    def test_report_pass(self):
        report = format_report("甲乙丙丁", "子丑寅卯")
        assert "通过" in report


class TestFilterStopwords:
    def test_filters_function_words(self):
        tokens = ["的", "研究", "了", "分析"]
        result = _filter_stopwords(tokens)
        assert result == ["研究", "分析"]

    def test_empty(self):
        assert _filter_stopwords([]) == []
