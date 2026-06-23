"""Tests for learning functions (learn_stubborn_patterns, learn_success)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.analyze import learn_stubborn_patterns, learn_success


class TestLearnStubbornPatterns:
    def test_basic_stubborn(self, patterns_dir, tmp_path):
        """Test learning stubborn patterns that survive rewrite."""
        # Copy patterns to tmp for isolation
        import shutil
        tmp_patterns = tmp_path / "patterns"
        tmp_patterns.mkdir()
        for f in patterns_dir.glob("*.json"):
            shutil.copy(f, tmp_patterns / f.name)

        # Text with cliches that persist after rewrite
        original = "In recent years, this has gained significant attention."
        rewritten = "In recent years, this has gained notable attention."

        result = learn_stubborn_patterns(original, rewritten, tmp_patterns)
        assert "learned_count" in result
        assert "stubborn_patterns" in result
        # "in recent years" should be identified as stubborn
        assert any("in recent years" in p.lower() for p in result["stubborn_patterns"])

    def test_no_stubborn(self, patterns_dir, tmp_path):
        """Test when no patterns survive rewrite."""
        import shutil
        tmp_patterns = tmp_path / "patterns"
        tmp_patterns.mkdir()
        for f in patterns_dir.glob("*.json"):
            shutil.copy(f, tmp_patterns / f.name)

        # Original has cliche, rewrite removes it
        original = "In recent years, this has gained attention."
        rewritten = "This has recently attracted attention."

        result = learn_stubborn_patterns(original, rewritten, tmp_patterns)
        # "in recent years" should NOT be stubborn since it was removed
        assert result["learned_count"] == 0 or \
               not any("in recent years" in p.lower() for p in result["stubborn_patterns"])


class TestLearnSuccess:
    def test_basic_success(self, patterns_dir, tmp_path):
        """Test recording successful rewrite strategies."""
        import shutil
        tmp_patterns = tmp_path / "patterns"
        tmp_patterns.mkdir()
        for f in patterns_dir.glob("*.json"):
            shutil.copy(f, tmp_patterns / f.name)

        # Original has cliches, rewrite removes them
        original = "In recent years, it is worth noting that this plays a crucial role."
        rewritten = "This is important for the field."

        result = learn_success(original, rewritten, 0.8, 0.3, tmp_patterns)
        assert result["recorded"] is True
        assert result["eliminated_count"] > 0
        assert result["risk_reduction"] == 0.5

    def test_no_elimination(self, patterns_dir, tmp_path):
        """Test when no patterns are eliminated."""
        import shutil
        tmp_patterns = tmp_path / "patterns"
        tmp_patterns.mkdir()
        for f in patterns_dir.glob("*.json"):
            shutil.copy(f, tmp_patterns / f.name)

        # Both have same patterns
        original = "In recent years, this has attention."
        rewritten = "In recent years, this has attention."

        result = learn_success(original, rewritten, 0.5, 0.5, tmp_patterns)
        assert result["recorded"] is True
        assert result["eliminated_count"] == 0
        assert result["risk_reduction"] == 0.0


class TestLearningIntegration:
    def test_full_learning_cycle(self, patterns_dir, tmp_path):
        """Test complete learning cycle: stubborn + success."""
        import shutil
        tmp_patterns = tmp_path / "patterns"
        tmp_patterns.mkdir()
        for f in patterns_dir.glob("*.json"):
            shutil.copy(f, tmp_patterns / f.name)

        # Round 1: some patterns survive
        original1 = "In recent years, it is worth noting that this plays a crucial role."
        rewritten1 = "In recent years, this is important."

        result1 = learn_stubborn_patterns(original1, rewritten1, tmp_patterns)
        assert result1["learned_count"] >= 0

        # Round 2: successful rewrite
        original2 = "It is worth noting that this has gained significant attention."
        rewritten2 = "This has attracted research interest."

        result2 = learn_success(original2, rewritten2, 0.7, 0.3, tmp_patterns)
        assert result2["recorded"] is True

        # Verify learned.json was updated
        learned_file = tmp_patterns / "learned.json"
        assert learned_file.exists()
        import json
        learned_data = json.loads(learned_file.read_text(encoding="utf-8"))
        assert "patterns" in learned_data
        assert "success_strategies" in learned_data
