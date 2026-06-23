"""
真实论文改写效果测试
使用内联样本数据，不依赖外部文件
"""
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from similarity_calculator import calculate_similarity, format_report


# ── 样本数据 ──────────────────────────────────────────────────────

SAMPLE_ABSTRACT_ORIG = (
    "Rapid urbanization and resource exploitation have led to the degradation of "
    "ecological environments, particularly in arid and semi-arid regions. "
    "Ecological security pattern (ESP) has been widely recognized as an effective "
    "approach for maintaining ecosystem stability. However, existing studies have "
    "primarily focused on surface ecological processes and largely overlooked "
    "subsurface systems, particularly groundwater, which plays a critical role "
    "in sustaining ecosystem functions in arid regions."
)

SAMPLE_ABSTRACT_REWRITTEN = (
    "Accelerating urban expansion and intensive resource extraction have "
    "progressively deteriorated global ecosystems, especially within arid and "
    "semi-arid regions. While ecological security pattern (ESP) construction has "
    "emerged as a widely accepted strategy for maintaining ecosystem equilibrium, "
    "current methodologies predominantly address surface-level conditions and "
    "systematically neglect subsurface systems—specifically groundwater—which "
    "represents a critical constraining factor in dryland environments."
)

SAMPLE_INTRO_ORIG = (
    "Driven by the accelerating process of urbanization and industrialization, "
    "the impact of human activities on the ecological environment has been "
    "increasingly intensified. The overexploitation of land resources has led "
    "to a continuous reduction in ecological space, and the spatial conflicts "
    "among ecological, production, and living land have become increasingly "
    "prominent. The construction of ecological security patterns has become "
    "an important approach for safeguarding ecological security."
)

SAMPLE_INTRO_REWRITTEN = (
    "Propelled by the concurrent intensification of urban expansion and "
    "industrial development, anthropogenic impacts on natural ecosystems have "
    "steadily increased, while the overexploitation of land resources has "
    "caused a persistent reduction in ecological space, making the structural "
    "conflicts among ecological, productive, and residential land uses more "
    "evident. The establishment of ecological security patterns has emerged as "
    "a vital mechanism for ensuring regional ecological integrity."
)

SAMPLE_METHODS_ORIG = (
    "Groundwater vulnerability refers to the sensitivity of groundwater "
    "systems to pollution and contamination. The DRASTIC model was used to "
    "evaluate groundwater vulnerability in the study area. The model considers "
    "seven hydrogeological parameters: Depth to water table, Net recharge, "
    "Aquifer media, Soil media, Topography, Impact of vadose zone, and "
    "Conductivity of the aquifer."
)

SAMPLE_METHODS_REWRITTEN = (
    "Groundwater vulnerability describes the capacity of aquifer systems to "
    "resist pollutant infiltration and migration under natural conditions. "
    "Based on the fundamental principles of the DRASTIC model and the "
    "ecological environment characteristics of the study area, this study "
    "selected six factors: groundwater table depth, KNDVI, soil medium, "
    "land cover type, topographic slope, and hydraulic conductivity to "
    "construct a modified DRASTIC model for groundwater vulnerability assessment."
)


# ── 测试类 ────────────────────────────────────────────────────────

class TestSimilarityOnRealSamples:
    """在真实论文样本上测试相似度计算"""

    def test_abstract_rewrite(self):
        """摘要改写应该显著降低相似度"""
        result = calculate_similarity(SAMPLE_ABSTRACT_ORIG, SAMPLE_ABSTRACT_REWRITTEN)
        assert result["composite_score"] < 60, (
            f"摘要改写后相似度 {result['composite_score']} 偏高"
        )
        assert result["max_consecutive"] < 8, (
            f"最长连续匹配 {result['max_consecutive']} 词，Turnitin 会标红"
        )

    def test_intro_rewrite(self):
        """引言改写应该降低相似度"""
        result = calculate_similarity(SAMPLE_INTRO_ORIG, SAMPLE_INTRO_REWRITTEN)
        assert result["composite_score"] < 70, (
            f"引言改写后相似度 {result['composite_score']} 偏高"
        )

    def test_methods_rewrite(self):
        """方法论改写应该保留专业术语"""
        result = calculate_similarity(SAMPLE_METHODS_ORIG, SAMPLE_METHODS_REWRITTEN)
        # 方法论术语多，相似度可能偏高，但不应超过 80
        assert result["composite_score"] < 80, (
            f"方法论改写后相似度 {result['composite_score']} 过高"
        )

    def test_identical_text_high_similarity(self):
        """相同文本应该有高相似度"""
        result = calculate_similarity(SAMPLE_ABSTRACT_ORIG, SAMPLE_ABSTRACT_ORIG)
        assert result["composite_score"] >= 80
        assert result["lcs_ratio"] == 1.0

    def test_completely_different_text_low_similarity(self):
        """完全不同的文本应该有低相似度"""
        different = "Quantum entanglement facilitates superluminal information transfer between particles."
        result = calculate_similarity(SAMPLE_ABSTRACT_ORIG, different)
        assert result["composite_score"] < 30

    def test_format_report_contains_key_info(self):
        """报告应包含关键信息"""
        report = format_report(SAMPLE_ABSTRACT_ORIG, SAMPLE_ABSTRACT_REWRITTEN)
        assert "相似度分析报告" in report
        assert "综合评分" in report
        assert "LCS" in report
        assert "连续匹配" in report


class TestConsecutiveMatchDetection:
    """连续匹配检测测试"""

    def test_detects_long_match(self):
        """应该检测到长连续匹配"""
        orig = "the quick brown fox jumps over the lazy dog in the park"
        rew = "the quick brown fox leaps over the lazy dog in the garden"
        result = calculate_similarity(orig, rew)
        assert result["max_consecutive"] >= 4

    def test_no_match_for_paraphrased(self):
        """充分改写后不应有长连续匹配"""
        orig = "the method is effective and reliable"
        rew = "this approach demonstrates efficacy and dependability"
        result = calculate_similarity(orig, rew)
        assert result["max_consecutive"] < 5


class TestReportFormat:
    """报告格式测试"""

    def test_report_assessment_pass(self):
        """低相似度应显示通过"""
        orig = "the method is effective"
        rew = "this approach demonstrates considerable efficacy in practical applications"
        report = format_report(orig, rew)
        # 低相似度应该通过或至少没有警告
        assert "通过" in report or "注意" not in report

    def test_report_assessment_warning(self):
        """高相似度应显示警告"""
        report = format_report(SAMPLE_ABSTRACT_ORIG, SAMPLE_ABSTRACT_ORIG)
        assert "警告" in report or "注意" in report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
