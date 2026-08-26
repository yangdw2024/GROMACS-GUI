# GROMACS 动力学模拟与分析集成工具

<div align="center">

![Version](https://img.shields.io/badge/version-v4.3.0-blue)
![Python](https://img.shields.io/badge/python-3.13-green)
![PyQt5](https://img.shields.io/badge/PyQt5-GUI-orange)
![License](https://img.shields.io/badge/license-MIT-brightgreen)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

</div>

## 项目简介

GROMACS GUI 是一款基于 Python + PyQt5 开发的分子动力学模拟图形化工具，将复杂的 GROMACS 命令行操作封装为直观的图形界面，覆盖从结构准备到结果分析的分子动力学模拟全流程。内置 13 个核心框架模块，提供 NASA FDIR 级别的错误纠正、ISO 27001 级别的审计追踪、以及自动版本管理等企业级能力。

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

### 三层分离架构

```
┌─────────────────────────────────────────────┐
│              UI 层                           │  PyQt5 图形界面
├─────────────────────────────────────────────┤
│           核心框架层 (13 模块)                 │  单例模式 + 设计模式
├─────────────────────────────────────────────┤
│              资源层                           │  GROMACS 引擎
└─────────────────────────────────────────────┘
```

### 核心框架模块

| 模块 | 职责 | 设计模式 |
|------|------|----------|
| `config_manager` | 配置统一管理，深度合并 + 边界校验 | 单例 + 观察者 |
| `workflow_engine` | 工作流引擎，6 态状态机 + 断点续跑 | 单例 + 状态机 |
| `error_handler` | 统一错误处理，12 类分类 + 4 级严重度 | 单例 + 策略 |
| `correction_mechanism` | NASA FDIR 纠错：GPU 降级 / 内存调优 / 重试退避 | 单例 + 策略 |
| `review_mechanism` | 三级审查：启动前 / 运行中 / 执行后 | 单例 + 组合 |
| `event_bus` | 事件总线：通配符订阅 + 优先级 + 弱引用 | 单例 + Pub-Sub |
| `resource_monitor` | 资源监控：CPU / 内存 / 磁盘 / GPU + 告警 | 单例 + 观察者 |
| `gromacs_service` | GROMACS 命令封装 + 版本评分 + TTL 缓存 | 单例 + 外观 |
| `version_manager` | 版本管理：6 级校验 + SHA256 去重 + 白名单 | 单例 + 管道 |
| `crash_handler` | 崩溃捕获：全局钩子 + 双格式报告 | 单例 + 拦截器 |
| `logger` | 日志系统：四级通道（主 + 分级 + 控制台 + UI） | 单例 + 观察者 |
| `audit_mechanism` | ISO 27001 审计：13 类操作 + 导出 | 单例 + 命令 |
| `auto_updater` | 自动更新：SHA256 校验 + 备份回滚 | 单例 + 快照 |

### 关键机制

#### NASA FDIR 纠错链

错误发生时按类别自动分派修复策略：

- GPU 不可用 → 自动降级 CPU 模式
- 内存 >90% → 线程数减半
- 文件被占用 → 指数退避重试
- 子进程超时 → 超时翻倍重试（最多 3 次）
- 配置错误 → 回滚默认配置

#### 三级审查体系

```
启动前 (Standard)         运行中 (Runtime)          执行后 (Post)
 ├─ 输入文件检查           ├─ 进程存活检查           ├─ 输出文件完整性
 ├─ 参数边界校验           ├─ 输出文件生成检查        ├─ 日志错误扫描
 ├─ 磁盘空间 ≥ 5GB         ├─ 内存使用率监控          └─ 综合判定
 └─ GPU 可用性匹配          └─ 资源阈值告警
```

---

## 项目结构

```
Trae_Gromacs/
├── source/                          # 源代码
│   ├── gromacs_gui_v4.py            # 主程序 (13,000+ 行)
│   ├── core/                        # 核心框架 (13 模块)
│   │   ├── __init__.py
│   │   ├── config_manager.py       # 配置管理
│   │   ├── workflow_engine.py       # 工作流引擎
│   │   ├── error_handler.py        # 错误处理
│   │   ├── correction_mechanism.py # FDIR 纠错
│   │   ├── review_mechanism.py      # 审查机制
│   │   ├── event_bus.py            # 事件总线
│   │   ├── resource_monitor.py     # 资源监控
│   │   ├── gromacs_service.py      # GROMACS 服务
│   │   ├── version_manager.py      # 版本管理
│   │   ├── crash_handler.py        # 崩溃捕获
│   │   ├── logger.py               # 日志系统
│   │   ├── audit_mechanism.py      # 审计追踪
│   │   └── auto_updater.py        # 自动更新
│   └── config/                      # 配置文件
│       ├── app_config.json         # 应用配置
│       └── latest_version.json     # 版本信息
├── resources/                       # 资源文件
│   ├── app_icon.ico                 # 程序图标
│   ├── app_icon.png
│   └── GROMACS_GUI使用说明_V4.0.md
├── build_scripts/                   # 构建脚本
│   └── build_release.bat           # 一键打包脚本
├── version.config                   # 版本配置
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
pip install PyQt5 numpy psutil
```

### 从源码运行

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

### 从发布包运行

1. 下载 `GROMACS_GUI_v4.3.0_Release.zip`
2. 解压到任意目录
3. 双击 `启动程序.bat` 或 `GROMACS_GUI_v4.3.0.exe` 即可运行

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
