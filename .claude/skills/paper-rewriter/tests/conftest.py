"""pytest 配置 — 抑制 nltk 未安装时的预期警告"""
import warnings
import pytest


@pytest.fixture(autouse=True)
def _suppress_nltk_warning():
    """在测试中抑制 nltk 未安装的 UserWarning（预期行为）"""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="nltk.*未安装", category=UserWarning)
        yield
