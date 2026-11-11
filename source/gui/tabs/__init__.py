# -*- coding: utf-8 -*-
"""
GROMACS-GUI 独立功能页组件包
按模块逐步收敛 main_window.py 庞大单体。
"""

from .script_tab import ScriptTab
from .mmpbsa_tab import MmpbsaTab
from .trajectory_tab import TrajectoryTab
from .structure_tab import StructureTab

__all__ = ["ScriptTab", "MmpbsaTab", "TrajectoryTab", "StructureTab"]
