"""Test configuration for AIGC-rewriter."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


import pytest


@pytest.fixture
def sample_academic_text():
    """Sample academic text for testing."""
    return """
    Deep learning has gained significant attention in recent years. Furthermore, it has been shown to play a crucial role in various applications. Moreover, the results indicate that neural networks achieve state-of-the-art performance. Additionally, a growing body of evidence suggests that these methods pave the way for future innovations.

    The model was trained on a large dataset. The accuracy was above ninety percent. The loss function converged well. The training took several hours. The hyperparameters were optimized. The model was tested on new data. The generalization was satisfactory.

    It is worth noting that this approach has several advantages. However, there are also limitations. Therefore, further research is needed. Nevertheless, the results are promising.
    """


@pytest.fixture
def sample_normal_text():
    """Sample normal academic text (low risk)."""
    return """
    We evaluated our method on three benchmark datasets. As shown in Table 1, the proposed approach achieves 94.5% accuracy on CIFAR-10. The experimental setup follows the protocol described in prior work [1, 2].

    Our model uses a standard convolutional architecture with batch normalization. We trained it using SGD with momentum for 200 epochs. The learning rate was initialized at 0.1 and decayed by a factor of 10 every 60 epochs.

    The results demonstrate that our method outperforms existing approaches by a significant margin. On ImageNet, we observe a 2.3% improvement in top-1 accuracy compared to the baseline.
    """


@pytest.fixture
def patterns_dir():
    """Path to patterns directory."""
    return Path(__file__).parent.parent / "patterns"


@pytest.fixture
def references_dir():
    """Path to references directory."""
    return Path(__file__).parent.parent / "references"
