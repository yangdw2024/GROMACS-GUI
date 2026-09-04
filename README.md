# GROMACS 动力学模拟与分析集成工具

<div align="center">

![Version](https://img.shields.io/badge/version-v4.3.0-blue)
![Python](https://img.shields.io/badge/python-3.13-green)
![PyQt5](https://img.shields.io/badge/PyQt5-GUI-orange)
![License](https://img.shields.io/badge/license-MIT-brightgreen)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

</div>

## 项目简介

GROMACS GUI 是一款基于 Python + PyQt5 开发的分子动力学模拟图形化工具，将复杂的 GROMACS 命令行操作封装为直观的图形界面，覆盖从结构准备到结果分析的分子动力学模拟全流程。内置错误自动纠正、操作审计、版本管理等模块。

**无需记忆任何命令行参数，零门槛上手分子动力学模拟。**

---

## 核心功能

### 七大功能模块

| 模块 | 功能 |
|------|------|
| **MD 模拟** | 能量最小化 → 离子化 → NVT → NPT → 生产模拟 → 相分离 → 溶剂蒸发 → 退火 |
| **结构处理** | 盒子构建、溶剂化、离子添加、位置限制 |
| **高级模拟** | 伞形采样、元动力学、ABF、拉伸动力学、退火（PLUMED 增强采样） |
| **轨迹处理** | trjconv/trjcat 格式转换、PBC 处理、质心居中 |
| **结果分析** | RMSD / RMSF / Rg / RDF / 氢键 / SASA / PCA / 能量 / 聚类 / 批量分析 |
| **MMPBSA** | 结合自由能计算 |
| **自定义脚本** | 用户自定义脚本运行 |

### 辅助系统

- **MDP 可视化编辑器** — 9 个子标签页，实时预览所有 MDP 参数
- **实时监控面板** — 温度 / 压力 / 能量 / 密度曲线实时绘制
- **智能错误诊断器** — 自动分析错误日志，提供中文修复建议
- **多版本管理器** — 6 级校验 + SHA256 去重 + 白名单保护
- **自动更新** — 全量 / 增量更新，SHA256 校验，备份回滚
- **审计追踪** — 13 类操作全留痕，按天归档
- **崩溃捕获** — 全局异常钩子，双格式 (JSON + LOG) 报告
- **GPU 兼容** — 自动检测 GPU，无 GPU 时强制 CPU 模式

---

## 架构设计

### 三层结构

```
┌─────────────────────────────────────────────┐
│              UI 层                           │  PyQt5 图形界面
├─────────────────────────────────────────────┤
│           核心框架层 (15 个功能模块)            │  配置/日志/监控/版本管理
├─────────────────────────────────────────────┤
│              资源层                           │  GROMACS 引擎
└─────────────────────────────────────────────┘
```

### 核心框架模块

| 模块 | 职责 |
|------|------|
| `config_manager` | 配置读写与合并 |
| `logger` | 日志记录 |
| `error_handler` | 错误分类与提示 |
| `resource_monitor` | CPU / 内存 / 磁盘 / GPU 监控 |
| `gromacs_service` | GROMACS 命令封装与版本识别 |
| `wsl_gromacs_service` | WSL 下的 GROMACS 命令封装 |
| `workflow_engine` | 模拟流程状态管理 |
| `event_bus` | 模块间消息传递 |
| `review_mechanism` | 运行前 / 中 / 后检查 |
| `correction_mechanism` | 错误自动纠正（GPU 降级 / 重试） |
| `audit_mechanism` | 操作审计 |
| `auto_updater` | 程序自动更新 |
| `version_manager` | GROMACS 版本管理 |
| `crash_handler` | 崩溃捕获与报告 |
| `wsl_update_manager` | WSL 更新管理 |

### 关键机制

#### 错误自动纠正

运行出错时按类别自动处理：

- GPU 不可用 → 自动降级 CPU 模式
- 内存 >90% → 线程数减半
- 文件被占用 → 指数退避重试
- 子进程超时 → 超时翻倍重试（最多 3 次）
- 配置错误 → 回滚默认配置

#### 运行检查

```
启动前                      运行中                    执行后
 ├─ 输入文件检查           ├─ 进程存活检查           ├─ 输出文件完整性
 ├─ 参数边界校验           ├─ 输出文件生成检查        ├─ 日志错误扫描
 ├─ 磁盘空间检查           ├─ 内存使用率监控          └─ 综合判定
 └─ GPU 可用性匹配          └─ 资源阈值告警
```

---

## 项目结构

```
Trae_Gromacs/
├── source/                          # 源代码
│   ├── main.py                      # 程序入口
│   ├── gromacs_gui_v4.py            # 兼容入口（转调 gui 包）
│   ├── gui/                         # GUI 层
│   │   ├── app_context.py           # 运行时路径/版本配置/GMX与硬件检测
│   │   ├── main_window.py           # 主窗口 GromacsGUI
│   │   ├── app.py                   # 启动引导（协议/崩溃处理/单实例）
│   │   ├── embedded_scripts.py      # 嵌入的溶剂/添加剂删除脚本
│   │   ├── dialogs/                 # 对话框
│   │   │   ├── error_diagnosis.py   # 错误诊断
│   │   │   ├── mdp_editor.py        # MDP 可视化编辑器
│   │   │   ├── simulation_monitor.py # 实时监控
│   │   │   ├── custom_template.py   # 自定义模板
│   │   │   └── help_dialog.py       # 帮助
│   │   ├── widgets/                 # 自定义控件
│   │   │   └── curve_widget.py      # 实时曲线
│   │   └── workers/                 # 工作线程
│   │       ├── gromacs_worker.py    # GROMACS 执行线程
│   │       └── data_extractor.py    # 数据提取线程
│   ├── core/                        # 核心框架 (15 个功能模块)
│   │   ├── config_manager.py       # 配置管理
│   │   ├── logger.py               # 日志记录
│   │   ├── error_handler.py        # 错误处理
│   │   ├── resource_monitor.py     # 资源监控
│   │   ├── gromacs_service.py      # GROMACS 命令封装
│   │   ├── wsl_gromacs_service.py  # WSL GROMACS 命令封装
│   │   ├── workflow_engine.py      # 工作流状态管理
│   │   ├── event_bus.py            # 模块间消息传递
│   │   ├── review_mechanism.py      # 运行检查
│   │   ├── correction_mechanism.py # 错误自动纠正
│   │   ├── audit_mechanism.py      # 操作审计
│   │   ├── auto_updater.py         # 自动更新
│   │   ├── version_manager.py      # 版本管理
│   │   ├── crash_handler.py        # 崩溃捕获
│   │   └── wsl_update_manager.py   # WSL 更新管理
│   └── config/                      # 配置文件
│       ├── app_config.json         # 应用配置
│       └── latest_version.json     # 版本信息
├── tests/                           # pytest 测试
│   ├── unit/                        # 单元测试
│   └── integration/                 # 集成测试（需 GROMACS 引擎）
├── resources/                       # 资源文件
│   ├── app_icon.ico                 # 程序图标
│   ├── app_icon.png
│   └── GROMACS_GUI使用说明_V4.0.md
├── build_scripts/                   # 构建脚本（仅保留最终版，历史版本在 archive/）
├── version.config                   # 版本配置
├── requirements.txt                 # Python 依赖
├── 说明书.md                         # 用户手册
└── .gitignore
```

> **注意**: GROMACS 引擎二进制文件 (`gromacs/`)、Python 环境 (`miniconda3/`)、发布包 (`release_package/`) 等大型文件不纳入版本控制，请参考下方「环境准备」章节自行配置。

---

## 快速开始

### 环境要求

- **操作系统**: Windows 10/11 (64-bit)
- **Python**: 3.10+ (推荐 3.13)
- **GROMACS**: 2025.1 或 2026.x (需单独安装)
- **GPU**（可选）: NVIDIA GPU + CUDA 13.0+

### 安装依赖

```bash
pip install -r requirements.txt
```

### 从源码运行

```bash
# 克隆仓库
git clone https://github.com/yangdw2024/Trae_Gromacs.git
cd Trae_Gromacs

# 安装依赖
pip install -r requirements.txt

# 将 GROMACS 安装到 gromacs/ 目录（或修改配置中的扫描路径）
# 确保 gmx.exe 可用

# 启动程序
python source/gromacs_gui_v4.py
```

### ⚡ 方式一：直接下载完整程序包（推荐）

**重要：请勿下载 GitHub 自动生成的 "Source code (zip)"，那只是源码（不到 1MB），无法直接运行！**

请从 [Releases 页面](https://github.com/yangdw2024/Trae_Gromacs/releases/tag/v4.3.0) 下载完整的一体化程序包：

1. 打开 [Releases 页面](https://github.com/yangdw2024/Trae_Gromacs/releases/tag/v4.3.0)
2. 下载 **GROMACS_GUI_v4.3.0_Full_Package.zip**（1.37 GB）—— 这是一体化完整包（GUI + GROMACS 引擎）
3. 解压到任意目录
4. 双击 `start.bat` 启动 —— **直接可用，无需任何额外安装！**

**包含内容**：
- PyInstaller 打包的 exe、Python 3.13 运行时、PyQt5 等所有依赖
- GROMACS 2026.x 引擎（含 CUDA 13.0 GPU 加速库）
- 启动脚本、卸载脚本

**无需安装**：Python、GROMACS、CUDA（均已内置）。

**提示**：即使没有 NVIDIA GPU，软件也会自动切换到纯 CPU 模式正常运行。

### 方式二：从源码运行

```bash
# 克隆仓库
git clone https://github.com/yangdw2024/Trae_Gromacs.git
cd Trae_Gromacs

# 安装依赖
pip install PyQt5 numpy psutil

# 将 GROMACS 安装到 gromacs/ 目录（或修改配置中的扫描路径）
# 确保 gmx.exe 可用

# 启动程序
python source/gromacs_gui_v4.py
```

### 打包发布

```bash
# 运行构建脚本（自动生成 exe + zip）
cd build_scripts
build_release.bat
```

---

## 使用指南

### 基本工作流

1. **选择工作目录** — 顶部路径栏选择模拟工作目录
2. **选择 GROMACS 版本** — 自动扫描或手动指定 GROMACS 安装路径
3. **MD 模拟标签页** — 按阶段依次执行：EM1 → EM2 → 离子化 → NVT → NPT → 生产
4. **结果分析标签页** — 选择分析类型，填入文件名，一键运行
5. **轨迹处理** — 格式转换、PBC 处理等

### 溶剂蒸发（分批模式）

溶剂蒸发模块支持断点续跑：

1. 设置总轮数和每轮蒸发分子数
2. 勾选「分批蒸发模式」
3. 中断后可通过设置起始轮数恢复续跑
4. 程序自动维护 `current.top` / `current.gro` 文件链

### GPU 配置

- 有 NVIDIA GPU：勾选「启用 GPU」并选择 GPU 编号
- 无 NVIDIA GPU：程序自动检测并禁用 GPU 选项，GROMACS 以纯 CPU 模式运行
- 环境变量 `GMX_DISABLE_GPU_DETECTION` 在无 GPU 时自动设置

---

## 技术栈

| 技术 | 用途 |
|------|------|
| Python 3.13 | 主开发语言 |
| PyQt5 | GUI 框架 |
| PyInstaller | 打包为 Windows 可执行文件 |
| GROMACS | 分子动力学引擎 |
| PLUMED | 增强采样插件 |
| psutil | 系统资源监控 |
| numpy | 数据处理 |

---

## 版本历史

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| v4.3.0 | 2026-07-16 | 修复 GPU 检测崩溃、属性名错误、无 GPU 兼容、图标重设计 |
| v4.2.0 | 2026-07-09 | 卸载程序、UI 布局修复、溶剂蒸发断点续跑 |
| v4.1.0 | 2026-06-28 | 多版本管理、自动更新、审计追踪 |
| v4.0.0 | 2026-06-15 | 初始发布，七大功能模块 |

---

## 许可证

[MIT License](LICENSE)

## 作者

**YangDewu** — Copyright (c) 2026 YangDewu. All rights reserved.

---

## 贡献

欢迎提交 Issue 和 Pull Request。

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request
