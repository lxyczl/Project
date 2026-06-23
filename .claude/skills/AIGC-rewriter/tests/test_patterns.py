"""Tests for pattern library module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzer.patterns import PatternLibrary


class TestPatternLibrary:
    def test_load_builtin(self, patterns_dir):
        lib = PatternLibrary.load(patterns_dir)
        patterns = lib.get_patterns()
        assert len(patterns) > 0

    def test_protected_terms(self, patterns_dir):
        lib = PatternLibrary.load(patterns_dir)
        terms = lib.get_protected_terms()
        assert "deep learning" in terms
        assert "Transformer" in terms

    def test_pattern_structure(self, patterns_dir):
        lib = PatternLibrary.load(patterns_dir)
        patterns = lib.get_patterns()
        for p in patterns:
            assert "id" in p
            assert "type" in p
            assert "match" in p

    def test_missing_file(self, tmp_path):
        lib = PatternLibrary.load(tmp_path)
        assert lib.get_patterns() == []

    def test_corrupted_file(self, tmp_path):
        (tmp_path / "builtin.json").write_text("not valid json", encoding="utf-8")
        lib = PatternLibrary.load(tmp_path)
        # Should handle gracefully
        assert lib.get_patterns() == []
