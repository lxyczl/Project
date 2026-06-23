"""测试完整 pipeline"""
import pytest


class TestPipeline:
    """完整 pipeline 测试"""

    def test_run_basic(self):
        from run_pipeline import run
        result = run(
            original="深度学习是人工智能的核心技术，广泛应用于计算机视觉领域",
            rewritten="机器学习是AI的关键技术，在图像识别方面应用广泛",
            domain="计算机",
            intensity="中度"
        )
        assert "session_id" in result
        assert "similarity" in result
        assert "evaluation" in result
        assert "hot_sentences" in result
        assert "needs_iteration" in result

    def test_run_returns_verdict(self):
        from run_pipeline import run
        result = run(
            original="测试文本内容",
            rewritten="改写后的文本",
            domain="通用",
            intensity="中度"
        )
        assert result["evaluation"]["verdict"] in ["excellent", "success", "warning", "fail"]

    def test_run_with_risk_analysis(self):
        from run_pipeline import run
        result = run(
            original="近年来，随着经济的快速发展，环境问题日益突出。此外，水资源短缺问题也十分严重。",
            rewritten="近年来，随着经济的快速发展，环境问题日益突出。此外，水资源短缺问题也十分严重。",
            domain="环境科学",
            intensity="中度"
        )
        assert "risk_analysis" in result
        assert "overall_risk" in result["risk_analysis"]

    def test_run_with_preserve_terms(self):
        from run_pipeline import run
        result = run(
            original="使用DRASTIC模型和GIS技术进行地下水脆弱性评估",
            rewritten="利用DRASTIC模型与GIS方法开展地下水脆弱性评价",
            domain="环境科学",
            intensity="中度"
        )
        assert "preserve_terms" in result
        assert isinstance(result["preserve_terms"], list)

    def test_format_output(self):
        from run_pipeline import run, format_output
        result = run(
            original="测试文本",
            rewritten="改写文本",
            domain="通用",
            intensity="中度"
        )
        output = format_output(result)
        assert isinstance(output, str)
        assert len(output) > 0

    def test_edge_case_short_text(self):
        from run_pipeline import run
        result = run(
            original="短",
            rewritten="改",
            domain="通用",
            intensity="中度"
        )
        assert result.get("skip_rewrite") is True or len(result.get("edge_cases", [])) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
