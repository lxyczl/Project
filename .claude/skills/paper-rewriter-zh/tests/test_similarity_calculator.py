"""相似度计算器测试"""
import sys
from pathlib import Path

# 将 scripts 目录加入 path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from similarity_calculator import (
    tokenize,
    _char_tokenize,
    _filter_stopwords,
    _split_sentences,
    STOPWORDS,
    ngrams,
    calculate_similarity,
    find_consecutive_matches,
    find_longest_common_substring,
    find_sentence_level_matches,
    format_report,
    CONSECUTIVE_WARNING,
    CONSECUTIVE_CAUTION,
    TRIGRAM_CAUTION,
    UNIGRAM_CAUTION,
)


class TestTokenize:
    def test_chinese_chars(self):
        assert tokenize("研究方法", mode="char") == ["研", "究", "方", "法"]

    def test_word_mode_returns_list(self):
        """word mode 返回列表（jieba 安装时为词列表，否则为字符列表）"""
        result = tokenize("研究方法", mode="word")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_char_mode_returns_chars(self):
        """char mode 始终返回字符列表"""
        result = tokenize("研究方法", mode="char")
        assert result == ["研", "究", "方", "法"]

    def test_filter_stopwords(self):
        """_filter_stopwords 过滤停用词"""
        tokens = ["研究", "的", "方法", "了"]
        filtered = _filter_stopwords(tokens)
        assert "的" not in filtered
        assert "了" not in filtered
        assert "研究" in filtered
        assert "方法" in filtered

    def test_stopwords_constant_exists(self):
        """STOPWORDS 集合存在且非空"""
        assert isinstance(STOPWORDS, set)
        assert len(STOPWORDS) > 0

    def test_numbers(self):
        assert tokenize("2024年", mode="char") == ["2024", "年"]

    def test_mixed(self):
        result = tokenize("本研究采用InVEST模型", mode="char")
        assert "本" in result
        assert "研" in result
        # 英文字母不被提取（只提取汉字和数字）
        assert "I" not in result

    def test_empty(self):
        assert tokenize("", mode="char") == []

    def test_punctuation_ignored(self):
        result = tokenize("研究表明，X很重要。", mode="char")
        assert "，" not in result
        assert "。" not in result


class TestNgrams:
    def test_bigram(self):
        tokens = ["a", "b", "c"]
        assert ngrams(tokens, 2) == [("a", "b"), ("b", "c")]

    def test_trigram(self):
        tokens = ["a", "b", "c", "d"]
        assert ngrams(tokens, 3) == [("a", "b", "c"), ("b", "c", "d")]

    def test_too_short(self):
        assert ngrams(["a"], 2) == []


class TestFindLongestCommonSubstring:
    def test_identical(self):
        assert find_longest_common_substring("研究方法", "研究方法") == 4

    def test_no_match(self):
        assert find_longest_common_substring("ABC", "XYZ") == 0

    def test_partial_match(self):
        # "研究方法" 和 "本研究方法论" 中 "研究方法" 是最长公共子串
        assert find_longest_common_substring("研究方法有效", "本研究方法论") == 4

    def test_empty(self):
        assert find_longest_common_substring("", "研究") == 0
        assert find_longest_common_substring("研究", "") == 0

    def test_different_positions(self):
        # 关键测试：匹配不在同一位置
        # 原文："A B C D E"，改写："X A B C D Y"
        # 位置对齐法会漏掉，DP 能找到 "A B C D" (长度4)
        assert find_longest_common_substring("研究方法有效", "本研究方法") == 4


class TestCalculateSimilarity:
    def test_identical_texts(self):
        result = calculate_similarity("研究表明X很重要", "研究表明X很重要")
        assert result["unigram_overlap"] == 1.0
        assert result["max_consecutive"] == 7

    def test_completely_different(self):
        result = calculate_similarity("研究方法", "天气晴朗")
        assert result["unigram_overlap"] == 0.0
        assert result["max_consecutive"] == 0

    def test_synonym_replacement(self):
        orig = "研究表明该方法具有重要意义"
        rewrite = "研究显示此方法具有重大价值"
        result = calculate_similarity(orig, rewrite)
        # 词重叠率应该较高（共享很多词）
        assert result["unigram_overlap"] > 0.3
        # 但连续匹配应该被打破
        assert result["max_consecutive"] < 13

    def test_empty_texts(self):
        result = calculate_similarity("", "")
        assert result["unigram_overlap"] == 0
        assert result["max_consecutive"] == 0

    def test_returns_all_fields(self):
        result = calculate_similarity("测试文本", "改写文本")
        expected_keys = {
            "unigram_overlap", "bigram_overlap", "trigram_overlap",
            "max_consecutive", "vocabulary_diversity",
            "original_char_count", "rewritten_char_count",
            "token_mode", "content_word_overlap"
        }
        assert set(result.keys()) == expected_keys

    def test_returns_token_mode(self):
        result = calculate_similarity("测试文本", "改写文本")
        assert "token_mode" in result
        assert result["token_mode"] in ("word", "char")

    def test_returns_content_word_overlap(self):
        result = calculate_similarity("研究表明该方法具有重要意义", "研究显示此方法具有重大价值")
        assert "content_word_overlap" in result
        assert 0 <= result["content_word_overlap"] <= 1

    def test_max_consecutive_always_char_level(self):
        """max_consecutive 始终按字符级计算"""
        result = calculate_similarity("研究方法", "研究方法")
        assert result["max_consecutive"] == 4  # 4 个字符，不论 token_mode


class TestFindConsecutiveMatches:
    def test_no_matches(self):
        matches = find_consecutive_matches("研究方法", "天气晴朗", min_length=2)
        assert matches == []

    def test_finds_match(self):
        # 构造一个有13字连续匹配的文本
        orig = "本研究采用定量分析方法对数据进行处理和分析"
        rewrite = "本文运用定量分析方法对数据开展处理与分析"
        matches = find_consecutive_matches(orig, rewrite, min_length=4)
        # 应该找到 "定量分析方法对数据" 这样的连续匹配
        assert len(matches) > 0
        assert all(m["length"] >= 4 for m in matches)

    def test_min_length_filter(self):
        orig = "研究方法有效"
        rewrite = "研究方法可行"
        # min_length=3 应该找到 "研究方法"
        matches = find_consecutive_matches(orig, rewrite, min_length=3)
        assert len(matches) > 0
        # min_length=5 不应该找到
        matches = find_consecutive_matches(orig, rewrite, min_length=5)
        assert len(matches) == 0


class TestEdgeCases:
    def test_tokenize_only_punctuation(self):
        assert tokenize("，。！？", mode="char") == []

    def test_calculate_similarity_one_empty(self):
        result = calculate_similarity("研究方法", "")
        assert result["original_char_count"] == 4
        assert result["rewritten_char_count"] == 0
        assert result["unigram_overlap"] == 0

    def test_find_consecutive_matches_empty_input(self):
        assert find_consecutive_matches("", "研究方法", min_length=2) == []
        assert find_consecutive_matches("研究方法", "", min_length=2) == []
        assert find_consecutive_matches("", "", min_length=2) == []
    def test_constants_defined(self):
        assert CONSECUTIVE_WARNING == 13
        assert CONSECUTIVE_CAUTION == 10
        assert TRIGRAM_CAUTION == 0.3
        assert UNIGRAM_CAUTION == 0.7


class TestFormatReport:
    def test_report_contains_sections(self):
        report = format_report("研究方法", "探究途径")
        assert "相似度分析报告" in report
        assert "基本信息" in report
        assert "相似度指标" in report
        assert "评估结果" in report

    def test_report_warning_on_high_match(self):
        # 完全相同的文本应该触发警告（13字以上连续匹配）
        report = format_report("研究方法具有重要意义和价值", "研究方法具有重要意义和价值")
        assert "警告" in report

    def test_report_caution_on_medium_match(self):
        # 10字连续匹配触发注意
        report = format_report("研究方法具有重要意义", "研究方法具有重要意义")
        assert "注意" in report

    def test_report_caution_on_high_trigram(self):
        # 三元组重叠率高但连续匹配不长
        # 完全不同的短文本，但共享很多字
        report = format_report("研究方法具有重要意义", "探究途径具有重大价值")
        # 字重叠率高，应触发某种注意
        assert "注意" in report or "通过" in report

    def test_report_pass_on_low_similarity(self):
        # 完全不同的文本应该通过
        report = format_report("研究方法具有重要意义", "天气晴朗万里无云")
        assert "通过" in report


class TestSplitSentences:
    def test_basic_split(self):
        assert _split_sentences("研究表明X很重要。Y具有重要意义。") == ["研究表明X很重要。", "Y具有重要意义。"]

    def test_multiple_punctuations(self):
        result = _split_sentences("A。B；C？D！")
        assert len(result) == 4

    def test_empty(self):
        assert _split_sentences("") == []
        assert _split_sentences("   ") == []

    def test_no_punctuation(self):
        # 无标点时整个文本作为一句
        assert _split_sentences("没有标点的句子") == ["没有标点的句子"]

    def test_newline_split(self):
        result = _split_sentences("第一行\n第二行")
        assert len(result) == 2


class TestFindSentenceLevelMatches:
    """句子级热点定位测试"""

    def test_finds_similar_sentence(self):
        orig = "研究表明X很重要。Y具有重要意义。"
        rew = "研究显示X非常关键。Y具有重大价值。"
        matches = find_sentence_level_matches(orig, rew, threshold=0.3)
        assert len(matches) > 0
        assert "original_sentence" in matches[0]
        assert "rewritten_sentence" in matches[0]
        assert "similarity_score" in matches[0]
        assert "max_consecutive" in matches[0]

    def test_no_match_below_threshold(self):
        orig = "天气晴朗万里无云。"
        rew = "研究方法具有重要意义。"
        matches = find_sentence_level_matches(orig, rew, threshold=0.5)
        assert len(matches) == 0

    def test_empty_input(self):
        assert find_sentence_level_matches("", "研究方法") == []
        assert find_sentence_level_matches("研究方法", "") == []
        assert find_sentence_level_matches("", "") == []

    def test_multiple_sentences(self):
        orig = "A导致B。C影响D。E促进F。"
        rew = "A造成B。X影响Y。E推动F。"
        matches = find_sentence_level_matches(orig, rew, threshold=0.3)
        # 至少匹配到 2 句（A->A, E->E）
        assert len(matches) >= 2

    def test_returns_sorted_by_similarity(self):
        orig = "研究方法有效。数据分析困难。"
        rew = "研究方法可行。数据处理复杂。"
        matches = find_sentence_level_matches(orig, rew, threshold=0.2)
        if len(matches) >= 2:
            assert matches[0]["similarity_score"] >= matches[1]["similarity_score"]


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
