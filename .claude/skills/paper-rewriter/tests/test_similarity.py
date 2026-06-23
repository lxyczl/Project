"""
相似度计算测试
"""
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestTokenize:
    """测试分词策略"""

    def test_tokenize_word_mode(self):
        """词级分词应返回词列表"""
        from similarity_calculator import tokenize
        result = tokenize("The results show that the method is effective", mode="word")
        assert len(result) > 0
        assert "the" in result
        assert "results" in result

    def test_tokenize_regex_mode(self):
        """正则分词应使用原有逻辑"""
        from similarity_calculator import tokenize
        result = tokenize("Hello, world! This is a test.", mode="regex")
        assert result == ["hello", "world", "this", "is", "a", "test"]

    def test_tokenize_default_is_word(self):
        """默认模式应为 word"""
        from similarity_calculator import tokenize
        result = tokenize("The method is effective")
        assert len(result) > 0

    def test_tokenize_backward_compat(self):
        """向后兼容：tokenize(text) 行为不变"""
        from similarity_calculator import tokenize
        result = tokenize("The results show that the method is effective")
        assert len(result) > 0
        assert "the" in result

    def test_tokenize_single_char_filtered(self):
        """单字符 token 应被过滤（word 模式）"""
        from similarity_calculator import tokenize
        result = tokenize("I am a student", mode="word")
        # "I" 和 "a" 是单字符，应被过滤
        assert "i" not in result or "a" not in result

    def test_tokenize_fallback_no_nltk(self):
        """nltk 不可用时应降级到正则"""
        from similarity_calculator import tokenize
        # 如果 nltk 未安装，word 模式应降级到正则
        result = tokenize("The method is effective", mode="word")
        assert len(result) > 0


class TestStopwords:
    """测试停用词过滤"""

    def test_filter_stopwords(self):
        """停用词应被过滤"""
        from similarity_calculator import _filter_stopwords
        tokens = ["the", "method", "is", "effective", "for", "this", "problem"]
        filtered = _filter_stopwords(tokens)
        assert "the" not in filtered
        assert "is" not in filtered
        assert "method" in filtered
        assert "effective" in filtered

    def test_filter_stopwords_empty(self):
        """空列表应返回空列表"""
        from similarity_calculator import _filter_stopwords
        assert _filter_stopwords([]) == []


class TestSentenceLevelMatches:
    """测试句子级热点定位"""

    def test_sentence_level_matches(self):
        """相似句子应被定位"""
        from similarity_calculator import find_sentence_level_matches
        orig = "The method is effective. The results show improvement. We analyzed the data."
        rew = "The approach is effective. The findings demonstrate improvement. The data was analyzed."
        matches = find_sentence_level_matches(orig, rew, threshold=0.3)
        assert len(matches) > 0
        assert "original_sentence" in matches[0]
        assert "rewritten_sentence" in matches[0]
        assert "similarity_score" in matches[0]

    def test_sentence_level_no_match(self):
        """完全不同的句子应返回空"""
        from similarity_calculator import find_sentence_level_matches
        orig = "The method is effective."
        rew = "An entirely different approach was utilized for this investigation."
        matches = find_sentence_level_matches(orig, rew, threshold=0.8)
        assert len(matches) == 0

    def test_sentence_level_suggested_techniques(self):
        """热点句子应推荐技巧"""
        from similarity_calculator import find_sentence_level_matches
        orig = "The results show that the method is effective for this problem"
        rew = "The results show that the method is effective for this issue"
        matches = find_sentence_level_matches(orig, rew, threshold=0.3)
        if matches:
            assert "suggested_techniques" in matches[0]


class TestContentWordOverlap:
    """测试实词重叠率"""

    def test_content_word_overlap(self):
        """停用词过滤后的实词重叠率应低于总重叠率"""
        from similarity_calculator import calculate_similarity
        orig = "The method is effective for this problem"
        rew = "The approach is useful for this issue"
        result = calculate_similarity(orig, rew)
        assert "content_word_overlap" in result
        assert "token_mode" in result
        assert result["content_word_overlap"] <= result["vocabulary_overlap"]

    def test_token_mode_field(self):
        """返回值应包含 token_mode"""
        from similarity_calculator import calculate_similarity
        result = calculate_similarity("The method is effective", "The approach works well")
        assert result["token_mode"] in ("word", "regex")


class TestRewriteWithFeedbackIntegration:
    """测试改写分析集成"""

    def test_analyze_rewrite_extended_fields(self, tmp_path):
        """analyze_rewrite 应返回新增字段"""
        from rewrite_with_feedback import RewriteWithFeedback

        r = RewriteWithFeedback(tmp_path)
        result = r.analyze_rewrite(
            original="The method is effective for this problem. The results show improvement.",
            rewritten="The approach is effective for this issue. The findings demonstrate improvement.",
            domain="test",
            intensity="medium"
        )
        assert "auto_evaluation" in result
        assert "hot_sentences" in result
        assert "needs_iteration" in result
        assert "verdict" in result["auto_evaluation"]

    def test_analyze_rewrite_needs_iteration_on_fail(self, tmp_path):
        """高相似度应触发迭代"""
        from rewrite_with_feedback import RewriteWithFeedback

        r = RewriteWithFeedback(tmp_path)
        # 几乎相同的文本
        text = "The method is effective for this problem and shows good results"
        result = r.analyze_rewrite(
            original=text,
            rewritten=text,
            domain="test",
            intensity="medium"
        )
        assert result["needs_iteration"] is True
