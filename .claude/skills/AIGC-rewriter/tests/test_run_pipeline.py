"""Tests for the unified pipeline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from scripts.run_pipeline import cmd_analyze, cmd_verify, format_analyze_output, format_verify_output


class MockArgs:
    """Mock argparse args for testing."""
    def __init__(self, **kwargs):
        self.text = kwargs.get("text", None)
        self.file = kwargs.get("file", None)
        self.platform = kwargs.get("platform", "turnitin")
        self.threshold = kwargs.get("threshold", None)
        self.original = kwargs.get("original", None)
        self.rewritten = kwargs.get("rewritten", None)
        self.section = kwargs.get("section", "body")
        self.techniques = kwargs.get("techniques", None)
        self.intensity = kwargs.get("intensity", "medium")


class TestCmdAnalyze:
    def test_basic_analyze(self):
        args = MockArgs(text="In recent years, it is worth noting that deep learning plays a crucial role.")
        result = cmd_analyze(args)
        assert "overall_risk" in result
        assert "paragraphs" in result
        assert "preserve_terms" in result
        assert result["mode"] == "analyze"

    def test_empty_text(self):
        # Empty text with no file should return error
        args = MockArgs(text="   ")
        result = cmd_analyze(args)
        assert "error" in result

    def test_format_output(self):
        args = MockArgs(text="The model was trained on a large dataset for testing purposes.")
        result = cmd_analyze(args)
        report = format_analyze_output(result)
        assert "AIGC Risk Analysis Report" in report
        assert "Overall Risk" in report


class TestCmdVerify:
    def test_basic_verify(self, tmp_path):
        orig = tmp_path / "orig.txt"
        orig.write_text("In recent years, it is worth noting that this plays a crucial role.", encoding="utf-8")
        rew = tmp_path / "rew.txt"
        rew.write_text("This is important for the field.", encoding="utf-8")

        args = MockArgs(original=str(orig), rewritten=str(rew))
        result = cmd_verify(args)
        assert "risk_before" in result
        assert "risk_after" in result
        assert "similarity" in result
        assert "verdict" in result
        assert result["mode"] == "verify"

    def test_format_verify_output(self, tmp_path):
        orig = tmp_path / "orig.txt"
        orig.write_text("The model performed well on the benchmark dataset.", encoding="utf-8")
        rew = tmp_path / "rew.txt"
        rew.write_text("The approach achieved strong results on the evaluation data.", encoding="utf-8")

        args = MockArgs(original=str(orig), rewritten=str(rew))
        result = cmd_verify(args)
        report = format_verify_output(result)
        assert "Rewrite Verification Report" in report
        assert "Risk Score Change" in report
