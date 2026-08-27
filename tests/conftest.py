# -*- coding: utf-8 -*-
"""pytest 公共 fixture 配置"""
import sys
import os
import pytest
from pathlib import Path

# 将 source 目录加入 Python 路径，使测试可以直接 import core 模块
PROJECT_ROOT = Path(__file__).parent.parent
SOURCE_DIR = PROJECT_ROOT / "source"

if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))


@pytest.fixture
def project_root():
    """项目根目录路径"""
    return PROJECT_ROOT


@pytest.fixture
def source_dir():
    """source 目录路径"""
    return SOURCE_DIR


@pytest.fixture
def gromacs_base():
    """GROMACS 安装根目录"""
    return PROJECT_ROOT / "gromacs"


@pytest.fixture
def test_dir():
    """测试数据目录（ClFFCl 体系）"""
    return PROJECT_ROOT / "test" / "ClFFCl_analysis_test"


@pytest.fixture
def simple_test_dir():
    """简单测试数据目录"""
    return PROJECT_ROOT / "test" / "test_simple"
