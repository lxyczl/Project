"""测试相似度计算器"""
import pytest
import sys
from pathlib import Path

scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))


class TestTokenize:
    """分词测试"""

    def test_basic(self):
        from similarity_calculator import tokenize
        result = tokenize("深度学习模型")
        assert len(result) > 0

    def test_word_mode(self):
        from similarity_calculator import tokenize
        result = tokenize("深度学习是人工智能的核心技术", mode="word")
        assert len(result) > 0

    def test_char_mode(self):
        from similarity_calculator import tokenize
        result = tokenize("深度学习", mode="char")
        assert len(result) == 4
        assert "深" in result


class TestNgrams:
    """n-gram 测试"""

    def test_bigram(self):
        from similarity_calculator import ngrams
        tokens = ["深度", "学习", "模型"]
        result = ngrams(tokens, 2)
        assert len(result) == 2
        assert ("深度", "学习") in result

    def test_trigram(self):
        from similarity_calculator import ngrams
        tokens = ["深度", "学习", "模型", "应用"]
        result = ngrams(tokens, 3)
        assert len(result) == 2


class TestConsecutiveMatches:
    """连续匹配测试"""

    def test_identical_text(self):
        from similarity_calculator import calculate_similarity
        text = "深度学习是人工智能的核心技术"
        result = calculate_similarity(text, text)
        assert result["max_consecutive"] >= 5

    def test_no_match(self):
        from similarity_calculator import calculate_similarity
        result = calculate_similarity("深度学习模型", "生态环境保护")
        assert result["max_consecutive"] < 3


class TestCalculateSimilarity:
    """综合相似度计算"""

    def test_identical(self):
        from similarity_calculator import calculate_similarity
        text = "深度学习是人工智能的核心技术，广泛应用于计算机视觉领域"
        result = calculate_similarity(text, text)
        assert result["max_consecutive"] >= 10
        assert result["trigram_overlap"] > 0.5

    def test_different(self):
        from similarity_calculator import calculate_similarity
        original = "深度学习是人工智能的核心技术"
        rewritten = "生态环境保护需要多方面协同努力"
        result = calculate_similarity(original, rewritten)
        assert result["max_consecutive"] < 5
        assert result["trigram_overlap"] < 0.3

    def test_returns_required_fields(self):
        from similarity_calculator import calculate_similarity
        result = calculate_similarity("测试文本", "改写文本")
        assert "unigram_overlap" in result
        assert "bigram_overlap" in result
        assert "trigram_overlap" in result
        assert "max_consecutive" in result
        assert "token_mode" in result

    def test_format_report(self):
        from similarity_calculator import format_report
        original = "深度学习是人工智能的核心技术"
        rewritten = "机器学习是AI的关键技术"
        report = format_report(original, rewritten)
        assert "相似度" in report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
