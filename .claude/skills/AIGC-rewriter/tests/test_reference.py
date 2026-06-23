"""Tests for reference document loader."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.reference_loader import (
    load_domains,
    load_synonyms,
    get_domain_preserve_terms,
    get_domain_replacements,
    get_synonym_suggestions,
)


class TestLoadDomains:
    def test_load_successfully(self, references_dir):
        domains = load_domains(references_dir)
        assert len(domains) > 0
        assert "CS/AI" in domains

    def test_structure(self, references_dir):
        domains = load_domains(references_dir)
        for domain, data in domains.items():
            assert "preserves" in data
            assert "replacements" in data
            assert isinstance(data["preserves"], list)
            assert isinstance(data["replacements"], dict)

    def test_missing_file(self, tmp_path):
        domains = load_domains(tmp_path)
        assert domains == {}


class TestLoadSynonyms:
    def test_load_successfully(self, references_dir):
        synonyms = load_synonyms(references_dir)
        assert len(synonyms) > 0
        assert "show" in synonyms

    def test_missing_file(self, tmp_path):
        synonyms = load_synonyms(tmp_path)
        assert synonyms == {}


class TestGetDomainPreserveTerms:
    def test_found_terms(self, references_dir):
        domains = load_domains(references_dir)
        text = "We used deep learning and Transformer models."
        terms = get_domain_preserve_terms(text, domains)
        assert "deep learning" in terms
        assert "Transformer" in terms

    def test_no_terms(self, references_dir):
        domains = load_domains(references_dir)
        text = "We used a simple linear model."
        terms = get_domain_preserve_terms(text, domains)
        assert "deep learning" not in terms


class TestGetDomainReplacements:
    def test_found_replacements(self, references_dir):
        domains = load_domains(references_dir)
        text = "We used a model to analyze the data."
        replacements = get_domain_replacements(text, domains)
        assert "model" in replacements

    def test_no_replacements(self, references_dir):
        domains = load_domains(references_dir)
        text = "This xyzzy has no matching terms at all."
        replacements = get_domain_replacements(text, domains)
        assert len(replacements) == 0


class TestGetSynonymSuggestions:
    def test_found_suggestions(self, references_dir):
        synonyms = load_synonyms(references_dir)
        text = "The results show significant improvement."
        suggestions = get_synonym_suggestions(text, synonyms)
        assert "show" in suggestions
        assert "significant" in suggestions
