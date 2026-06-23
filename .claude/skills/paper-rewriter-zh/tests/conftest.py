"""pytest 配置"""
import sys
from pathlib import Path

# 添加 scripts 和 analyzer 目录到路径
skill_dir = Path(__file__).parent.parent
sys.path.insert(0, str(skill_dir / "scripts"))
sys.path.insert(0, str(skill_dir))
