"""Tests for AI traces detection dimension."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzer.ai_traces import analyze_ai_traces


class TestAnalyzeAiTraces:
    def test_too_fluent_text(self):
        # Text with no informal markers
        text = """
        The model was trained on a large dataset. The results showed excellent performance.
        The accuracy was above ninety percent. The loss function converged well.
        The training took several hours. The hyperparameters were optimized carefully.
        The model was tested on new data. The generalization was satisfactory.
        """
        result = analyze_ai_traces(text)
        issue_types = {i["type"] for i in result["issues"]}
        assert "too_fluent" in issue_types

    def test_natural_text(self):
        # Text with informal markers (em dashes, parentheses, etc.)
        text = """
        The model — surprisingly — performed well on the test set. The results (see Table 1)
        showed significant improvement. We observed a 5% gain... which is notable.
        Interestingly, the baseline struggled with similar tasks.
        """
        result = analyze_ai_traces(text)
        issue_types = {i["type"] for i in result["issues"]}
        assert "too_fluent" not in issue_types

    def test_low_burstiness(self):
        # Sentences with very similar lengths
        sentences = [
            "The model was trained on the dataset.",
            "The results showed good performance.",
            "The accuracy was above ninety percent.",
            "The loss function converged well.",
            "The training took several hours.",
            "The hyperparameters were optimized.",
        ]
        text = " ".join(sentences)
        result = analyze_ai_traces(text)
        issue_types = {i["type"] for i in result["issues"]}
        assert "low_burstiness" in issue_types

    def test_no_personal_voice(self):
        # Long text without personal markers
        text = """
        The study investigates the effects of temperature on enzyme activity. The experiment
        was conducted using standard protocols. The samples were prepared according to the
        established methodology. The measurements were taken at regular intervals. The data
        were analyzed using statistical methods. The results demonstrate a clear relationship
        between temperature and enzyme function. The findings support the hypothesis.
        The implications of these results are discussed in the following section.
        The conclusion summarizes the main findings of this research.
        """
        result = analyze_ai_traces(text, section_type="introduction")
        issue_types = {i["type"] for i in result["issues"]}
        assert "no_personal_voice" in issue_types

    def test_with_personal_voice(self):
        # Text with personal markers
        text = """
        We investigated the effects of temperature on enzyme activity. Our experiments
        showed interesting results. We found that temperature significantly affects
        enzyme function. In our view, these findings have important implications.
        Notably, the results exceeded our expectations. We believe this approach
        opens new avenues for research. From our perspective, this is a significant advance.
        """
        result = analyze_ai_traces(text)
        issue_types = {i["type"] for i in result["issues"]}
        assert "no_personal_voice" not in issue_types

    def test_empty_text(self):
        result = analyze_ai_traces("")
        assert result["score"] == 0.0
        assert result["issues"] == []

    def test_short_text(self):
        result = analyze_ai_traces("Short text.")
        assert result["score"] == 0.0
