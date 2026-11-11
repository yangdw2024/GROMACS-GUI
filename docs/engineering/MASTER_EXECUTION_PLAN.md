# GROMACS-GUI 全工程自主开发总执行计划
## Master Execution Plan

本文件依据《GROMACS-GUI 全项目自主工程开发总指令》制定，作为项目架构演进、质量工程、科研计算可靠性与发布的唯一权威路线图。

---

## 一、工程目标与分级验收门禁

将 GROMACS-GUI 建设为：**现代化、模块化、可靠、易用、支持中英文、具备科研计算安全保障、能够正式安装与发布的成熟分子动力学桌面软件**。

### 验收门禁体系（L1–L8）

| 级别 | 验收内容 | 最低通过标准 |
|:---|:---|:---|
| **L1** | **代码结构** | 核心模块边界清晰，代码无全局单例滥用，全部源码可导入并无语法警告 |
| **L2** | **自动化测试** | 本地 `tests/unit` 全部通过，GitHub Actions CI 双矩阵 (Python 3.11 & 3.12) 全绿通过 |
| **L3** | **GUI 功能** | 七大功能页组件化独立挂载，主窗口命令调度、配置保存/加载、任务生命周期正常 |
| **L4** | **科研工作流** | SA 逐轮 NPT 继承、CPT 同轮恢复、GRO/TOP 分子数守恒及物理有效性在测试体系闭环证实 |
| **L5** | **视觉体验** | 左导航工作台、顶部状态栏、折叠终端、双主题在 880x620 至 1920x1080 及 100%~200% DPI 无裁切 |
| **L6** | **文档与国际化** | 中英文界面支持（无硬编码中文逻辑依赖），开发者手册、用户手册与 Changelog 完备 |
| **L7** | **产品构建** | Windows 独立安装包 / 便携包构建成功，在无开发环境干净机器上通过 Smoke Test |
| **L8** | **正式交付** | GitHub PR 审查完备，Tag 发布，Release Assets 上传，SHA256 校验公布 |

---

## 二、六大里程碑与任务依赖关系

```text
M0: 基线接管与治理基建 (PR #6 合并, 治理文档建立)
  │
  ├──► M1: 七大功能页完整组件化 (P1 轨迹 -> P2 结构 -> P3 高级SA -> P4 基础MD -> P5 结果分析)
  │      │
  │      ├──► M2: UI/UX 深度打磨与视觉交付 (P6 视觉审查 -> P7 设计系统 -> P8 响应式与体验 -> P9 视觉回归)
  │      │
  │      └──► M3: 中英文国际化与语言系统 (P10 完整 i18n 引擎，数据模型与文案解耦)
  │
  ├──► M4: 科研计算可靠性与缺陷治理 (P11 Issue #2 告警与安全治理 -> P12 Issue #5 MMPBSA 全功能增强)
  │
  └──► M5: 质量工程与跨平台加固 (P13 任务生命周期 -> P14 架构精简 -> P15 扩展自动化测试 -> P16 静态检查)
         │
         └──► M6: 生产打包与正式发布 (P17 文档体系 -> P18 协议 -> P19 Windows 构建 -> P20 门禁验收 -> P21 正式 Release)
```

---

## 三、任务清单与当前状态

| 任务编号 | 任务名称 | 所属里程碑 | 对应分支 / PR | 状态 | 关键交付物 |
|:---|:---|:---|:---|:---|:---|
| **P0** | 完成 PR #6 (MMPBSA 组件化合并) | M0 | `refactor/extract-mmpbsa-tab` (PR #6) | **COMPLETED** | Merge SHA: `bce87528`，CI 成功 |
| **P0.1** | 建立工程进化与持续执行机制 | M0 | `chore/setup-engineering-governance` | **IN_PROGRESS** | `docs/engineering/` 10 个核心文件 |
| **P1** | Part 4 轨迹处理组件化 | M1 | `refactor/extract-trajectory-tab` | PENDING | `source/gui/tabs/trajectory_tab.py`, 测试 |
| **P2** | Part 2 结构处理组件化 | M1 | `refactor/extract-structure-tab` | PENDING | `source/gui/tabs/structure_tab.py`, 状态解耦 |
| **P3** | Part 3 高级模拟组件化 | M1 | `refactor/extract-advanced-tab` | PENDING | `source/gui/tabs/advanced_tab.py`, SA回归 |
| **P4** | Part 1 基础 MD 组件化 | M1 | `refactor/extract-md-tab` | PENDING | `source/gui/tabs/md_tab.py`, 多步骤调度 |
| **P5** | Part 5 结果分析组件化 | M1 | `refactor/extract-analysis-tab` | PENDING | `source/gui/tabs/analysis_tab.py`, 批处理 |
| **P6** | 正式视觉审核与基线评估 | M2 | — | PENDING | 多分辨率基线对照实物分析 |
| **P7** | 形成完整 Design System | M2 | `feature/theme-design-system` | PENDING | 集中 Token, 语义化 QSS |
| **P8** | 全局信息架构与交互优化 | M2 | `feature/ui-ux-enhancements` | PENDING | 抽屉优化, 经典/现代布局完善 |
| **P9** | UI 跨分辨率视觉回归测试 | M2 | — | PENDING | 880~1920, 100%~200% DPI 无裁切 |
| **P10** | 完整中英文国际化 (i18n) | M3 | `feature/i18n-support` | PENDING | `source/gui/i18n.py`, 键值字典, 术语表 |
| **P11** | 治理 Issue #2 (计算安全与状态一致) | M4 | `fix/issue-2-scientific-safety` | PENDING | `-maxwarn` 治理, 物理量合理性检查 |
| **P12** | 治理 Issue #5 (MMPBSA 全参数生效) | M4 | `feature/mmpbsa-full-parameters` | PENDING | 采样参数, 并行, 图片导出, 组别选择 |
| **P13** | 任务生命周期与进程管控重构 | M5 | `refactor/task-lifecycle` | PENDING | QThread 优雅启停, 资源不泄露 |
| **P14** | 主窗口架构精炼 | M5 | `refactor/main-window-shell` | PENDING | `main_window.py` 降至装配层职责 |
| **P15** | 自动化测试矩阵加固 | M5 | `test/matrix-hardening` | PENDING | 跨平台路径, 快照, 边界覆盖 |
| **P16** | 静态检查与依赖声明规整 | M5 | `chore/lint-and-deps` | PENDING | pyproject/requirements, ruff 规范 |
| **P17** | 完整中英文文档体系 | M6 | `docs/documentation-suite` | PENDING | README (zh/en), 用户手册, 架构手册 |
| **P18** | 许可证与版权一致性审查 | M6 | — | PENDING | LICENSE / 协议说明对齐 |
| **P19** | Windows 生产构建体系 | M6 | `build/installer-packaging` | PENDING | PyInstaller / Inno Setup 自动化打包 |
| **P20** | 发布前全项门禁验收 | M6 | — | PENDING | L1–L8 逐项严格客观检验 |
| **P21** | 正式版本发布 (Release) | M6 | `master` / GitHub Release | PENDING | Release Assets, SHA256, Tag 发布 |
