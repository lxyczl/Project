"""pytest 配置：统一 sys.path，确保测试能找到所有模块。"""
import sys
from pathlib import Path

# 项目根目录
SKILL_DIR = Path(__file__).resolve().parent.parent
# scripts 目录
SCRIPTS_DIR = SKILL_DIR / "scripts"

# 添加到 sys.path（幂等）
for p in (str(SKILL_DIR), str(SCRIPTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)
