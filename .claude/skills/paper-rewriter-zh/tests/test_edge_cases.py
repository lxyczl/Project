"""测试边界情况检测"""
import pytest
import sys
from pathlib import Path

scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))


class TestEdgeCases:
    """边界情况检测"""

    def test_short_text(self):
        from edge_cases import detect_edge_cases
        issues = detect_edge_cases("太短了")
        types = [i["type"] for i in issues]
        assert "short_text" in types

    def test_short_text_severity(self):
        from edge_cases import detect_edge_cases
        issues = detect_edge_cases("太短了")
        # 短文本是 warning 级别
        assert any(i["severity"] == "warning" for i in issues)

    def test_normal_text(self):
        from edge_cases import detect_edge_cases
        text = "这是一段正常的中文学术文本，长度足够用于分析和改写处理。" * 3
        issues = detect_edge_cases(text)
        error_issues = [i for i in issues if i["severity"] == "error"]
        assert len(error_issues) == 0

    def test_pure_english(self):
        from edge_cases import detect_edge_cases
        text = "This is a pure English text without any Chinese characters for testing purposes."
        issues = detect_edge_cases(text)
        types = [i["type"] for i in issues]
        assert "pure_english" in types

    def test_no_issues_for_normal_text(self):
        from edge_cases import detect_edge_cases
        text = "这是一段正常的中文学术文本，长度足够。" * 5
        issues = detect_edge_cases(text)
        # 正常文本不应该有 error 级别的问题
        error_issues = [i for i in issues if i["severity"] == "error"]
        assert len(error_issues) == 0

    def test_should_skip_on_skip_rewrite(self):
        from edge_cases import should_skip_rewrite
        issues = [{"type": "short_text", "severity": "warning", "message": "太短", "skip_rewrite": True}]
        assert should_skip_rewrite(issues) is True

    def test_should_not_skip_on_warning(self):
        from edge_cases import should_skip_rewrite
        issues = [{"type": "short_text", "severity": "warning", "message": "太短", "skip_rewrite": False}]
        assert should_skip_rewrite(issues) is False

    def test_format_report(self):
        from edge_cases import format_edge_case_report
        issues = [{"type": "short_text", "severity": "warning", "message": "文本太短"}]
        report = format_edge_case_report(issues)
        assert "边界情况" in report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
