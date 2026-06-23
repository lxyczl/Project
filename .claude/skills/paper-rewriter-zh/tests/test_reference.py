"""测试参考文档加载"""
import pytest


class TestReferenceLoader:
    """参考文档加载"""

    def test_load_domains(self):
        from reference_loader import load_domains
        domains = load_domains()
        assert len(domains) > 0
        # 应该有至少一个学科
        assert any(key != "_default" for key in domains.keys())

    def test_load_synonyms(self):
        from reference_loader import load_synonyms
        synonyms = load_synonyms()
        assert len(synonyms) > 0

    def test_get_preserve_terms(self):
        from reference_loader import load_domains, get_domain_preserve_terms
        domains = load_domains()
        text = "使用DRASTIC模型和GIS技术进行地下水脆弱性评估"
        terms = get_domain_preserve_terms(text, domains)
        assert "DRASTIC" in terms or "GIS" in terms

    def test_get_domain_replacements(self):
        from reference_loader import load_domains, get_domain_replacements
        domains = load_domains()
        text = "该研究采用了先进的方法"
        replacements = get_domain_replacements(text, domains, "通用")
        assert isinstance(replacements, dict)

    def test_get_synonym_suggestions(self):
        from reference_loader import load_synonyms, get_synonym_suggestions
        synonyms = load_synonyms()
        text = "研究表明该方法具有重要意义"
        suggestions = get_synonym_suggestions(text, synonyms)
        assert isinstance(suggestions, dict)


class TestDomainsMd:
    """domains.md 内容检查"""

    def test_has_preserves(self):
        from reference_loader import load_domains
        domains = load_domains()
        # 至少一个学科有保护术语
        has_preserves = any(
            len(d.get("preserves", [])) > 0
            for d in domains.values()
            if isinstance(d, dict)
        )
        assert has_preserves

    def test_has_replacements(self):
        from reference_loader import load_domains
        domains = load_domains()
        has_replacements = any(
            len(d.get("replacements", {})) > 0
            for d in domains.values()
            if isinstance(d, dict)
        )
        assert has_replacements


class TestSynonymsMd:
    """synonyms.md 内容检查"""

    def test_has_entries(self):
        from reference_loader import load_synonyms
        synonyms = load_synonyms()
        assert len(synonyms) >= 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
