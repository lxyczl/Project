"""参考文档加载器测试。"""
import pytest
from utils.reference_loader import (
    load_domains,
    load_synonyms,
    get_domain_preserve_terms,
    get_domain_replacements,
    get_synonym_suggestions,
)


class TestLoadDomains:
    def test_loads_domains(self):
        domains = load_domains()
        assert len(domains) >= 10

    def test_domain_has_preserves(self):
        domains = load_domains()
        cs = domains.get("计算机科学与人工智能", {})
        assert "深度学习" in cs.get("preserves", [])

    def test_domain_has_replacements(self):
        domains = load_domains()
        cs = domains.get("计算机科学与人工智能", {})
        assert "深度学习" in cs.get("replacements", {})

    def test_domain_replacement_values(self):
        domains = load_domains()
        cs = domains.get("计算机科学与人工智能", {})
        targets = cs["replacements"]["深度学习"]
        assert "深层学习" in targets


class TestLoadSynonyms:
    def test_loads_synonyms(self):
        synonyms = load_synonyms()
        assert len(synonyms) >= 50

    def test_common_words_present(self):
        synonyms = load_synonyms()
        assert "研究" in synonyms
        assert "表明" in synonyms
        assert "重要" in synonyms

    def test_synonym_values(self):
        synonyms = load_synonyms()
        assert "探究" in synonyms["研究"]
        assert "显示" in synonyms["表明"]


class TestGetDomainPreserveTerms:
    def test_finds_cs_terms(self):
        domains = load_domains()
        terms = get_domain_preserve_terms(
            "本文使用卷积神经网络进行图像分类", domains
        )
        assert "卷积神经网络" in terms

    def test_no_match(self):
        domains = load_domains()
        terms = get_domain_preserve_terms("普通文本没有专业术语", domains)
        assert terms == []

    def test_dedup(self):
        domains = load_domains()
        terms = get_domain_preserve_terms(
            "深度学习和深度学习方法", domains
        )
        assert terms.count("深度学习") == 1


class TestGetDomainReplacements:
    def test_finds_replacements(self):
        domains = load_domains()
        replacements = get_domain_replacements(
            "本文采用深度学习方法", domains
        )
        assert "深度学习" in replacements

    def test_no_match(self):
        domains = load_domains()
        replacements = get_domain_replacements("普通文本", domains)
        assert replacements == {}


class TestGetSynonymSuggestions:
    def test_finds_suggestions(self):
        synonyms = load_synonyms()
        suggestions = get_synonym_suggestions("本研究分析了重要问题", synonyms)
        assert "研究" in suggestions
        assert "重要" in suggestions
        assert "问题" in suggestions

    def test_no_match(self):
        synonyms = load_synonyms()
        suggestions = get_synonym_suggestions("甲乙丙丁", synonyms)
        assert suggestions == {}

    def test_values_are_lists(self):
        synonyms = load_synonyms()
        suggestions = get_synonym_suggestions("研究表明", synonyms)
        for v in suggestions.values():
            assert isinstance(v, list)
            assert len(v) > 0
