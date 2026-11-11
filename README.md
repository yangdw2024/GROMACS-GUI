# GROMACS-GUI · 分子动力学模拟与分析集成桌面平台

<div align="center">

![Version](https://img.shields.io/badge/version-v4.4.0--rc.1-blue)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-green)
![PyQt5](https://img.shields.io/badge/PyQt5-5.15+-orange)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey)
![License](https://img.shields.io/badge/license-MIT%20(Pending%20Review)-yellow)

[English Documentation](README_EN.md) | [更新日志 (CHANGELOG)](CHANGELOG.md) | [工程验收文档](docs/engineering/FINAL_ENGINEERING_REPORT.md)

</div>

---

## 一、项目简介

**GROMACS-GUI** 是一款基于 Python + PyQt5 开发的专业分子动力学模拟与后处理桌面软件，致力于为科研人员提供现代化、模块化、高可靠的 GROMACS 工作流集成环境：

- **双布局、双主题、双语言**：支持「左侧垂直导航工作台」与「经典双栏标签视图」切换，Slate 深/浅色专业科研主题切换，以及 **中文 / English 实时无重启切换**；
- **组件化七大功能页**：MD 全流程与 SA 溶剂蒸发、结构处理、增强采样（伞形采样/WHAM/PLUMED）、轨迹预处理与工具、结果分析与自动科研绘图、MMPBSA 自由能计算、自定义脚本批处理；
- **科研计算安全机制**：
  - SA 溶剂分批蒸发逐轮 NPT 结构与速度继承、严格跨轮 CPT 隔离校验、同轮中断安全续跑；
  - `grompp -maxwarn` 安全上限门禁（拒绝盲目 `-maxwarn 200`）；
  - 溶剂删除支持旧版 GRO 记录顺序兼容 (`bottom`/`top`) 与物理空间 Z 坐标排序 (`z_top`/`z_bottom`)；
  - 任务后置物理自检 (`NaN/Inf`、LINCS 爆炸拦截，且对正常 NPT 压力自然波动零误报)。

---

## 二、目录结构与模块化架构

```text
GROMACS-GUI/
├── source/
│   ├── main.py                         # 应用主入口 (含 multiprocessing.freeze_support)
│   ├── gromacs_gui_v4.py               # 兼容入口
│   ├── core/                           # 核心基础设施 (版本管理、配置、日志、崩溃捕获、资源监控)
│   ├── simulation/                     # 纯科研计算与命令构建层 (无 Qt 耦合)
│   │   ├── md_runner.py                # MD 流水线、SA 逐轮继承命令与 -maxwarn 策略
│   │   ├── mdp_builder.py              # EM / NVT / NPT / MD / 退火 / 伞形 / PLUMED 参数生成
│   │   ├── analysis.py                 # 分析、轨迹、结构、MMPBSA 参数与 NDX 组解析
│   │   └── validation.py               # GRO 结构与 md.log 物理一致性后置自检
│   └── gui/
│       ├── main_window.py              # 薄化主窗口外壳 (装配、导航、主题、语言、统一调度)
│       ├── i18n.py                     # 中英双语翻译与科研术语词典
│       ├── themes/theme_tokens.py      # Slate 深浅色 Design System 与语义化 QSS
│       ├── tabs/                       # 七大独立功能组件
│       │   ├── md_tab.py               # Part 1: MD 模拟与 SA 溶剂蒸发 / 退火
│       │   ├── structure_tab.py        # Part 2: 结构准备与校验
│       │   ├── advanced_tab.py         # Part 3: 伞形采样 / WHAM / PLUMED
│       │   ├── trajectory_tab.py       # Part 4: 轨迹预处理流水线与工具
│       │   ├── analysis_tab.py         # Part 5: 结果分析、片段 RDF 与科研绘图
│       │   ├── mmpbsa_tab.py           # Part 6: MMPBSA 计算 (实验性支持有机体系)
│       │   └── script_tab.py           # Part 7: PowerShell / Batch / Shell 自定义脚本
│       ├── dialogs/                    # MDP 编辑器、实时曲线监控、错误诊断等弹窗
│       └── workers/                    # GromacsWorker (QThread + Windows Job 内存限制)
├── build_scripts/
│   ├── build_windows_portable.py       # 可复现 Windows 便携包构建 + SHA256 + --smoke-test
│   └── installer_v43.iss               # Inno Setup 安装脚本 (相对路径)
├── tests/unit/                         # 198+ 自动化单元测试 (Ubuntu & Windows 双平台 CI)
└── docs/engineering/                   # 架构设计、测试矩阵、科研验证与工程交付总报告
```

---

## 三、安装、开发与运行指南

### 1. 环境准备
- **操作系统**：Windows 10/11 (64-bit) 或 Linux (X11/Wayland/Offscreen)
- **Python**：3.11 / 3.12 / 3.13
- **GROMACS**：需自行安装官方或 CUDA 编译版 GROMACS 2025.x / 2026.x（本软件不捆绑分发第三方 GROMACS 二进制文件）

### 2. 从源码运行与测试
```bash
git clone https://github.com/yangdw2024/GROMACS-GUI.git
cd GROMACS-GUI
pip install -r requirements.txt

# 启动图形界面
python source/gromacs_gui_v4.py

# 运行全量自动化单元测试
python -m pytest tests/unit -v
```

### 3. 可复现 Windows 便携版打包与校验
```bash
pip install pyinstaller
python build_scripts/build_windows_portable.py --smoke-test
```
构建产物将生成于 `release/` 目录：
- `GROMACS-GUI-v<version>-win64-portable.zip`（独立便携运行包，只读目录下自动回退至 `%LOCALAPPDATA%\GROMACS-GUI` 写入配置与日志）
- `SHA256SUMS.txt`

---

## 四、科学适用性与已知限制

1. **SA 溶剂蒸发模块**：`bottom` / `top` 选项兼容历史 GRO 文件顺序；若需按物理盒子空间 Z 轴方向优先移除分子，请显式选用 **`按空间 Z 坐标从顶部/底部蒸发 (Z-Top / Z-Bottom)`**。
2. **MMPBSA 模块（实验性提示）**：支持通过 `轨迹帧间隔` 将 ps 精确换算为 `gmx_MMPBSA` 1-based 帧索引，支持解析 `.ndx` 动态指定 `-cg` 受体/配体组别并自动生成 `mmpbsa.in`。**请注意**：针对高分子/小分子有机光伏等非蛋白体系的隐式溶剂结合自由能计算仍属实验性用途，需用户自行验证力场拓扑与介电参数适用性。
3. **开源许可待确认声明**：仓库根目录 [`LICENSE`](LICENSE) 声明为 MIT 协议，但软件内弹窗（`source/gui/app.py`）保留了非商业销售限制条款。在版权人确认统一方案前，请勿擅自用于商业分发。

---

## 五、版权与贡献

- **作者**：YangDewu (阳德武) — Copyright (c) 2026 YangDewu. All rights reserved.
- **贡献方式**：欢迎在 `dev` 分支提交 Issue 与 Pull Request，所有合并均需通过 Ubuntu 与 Windows 双平台 GitHub Actions CI 检验。
