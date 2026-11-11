# GROMACS-GUI 全工程自主开发总执行计划
## Master Execution Plan (Final Status)

本文件依据《GROMACS-GUI 全项目自主工程开发总指令》持续维护，记录完整里程碑状态与验证结论。

---

## 一、工程验收分级结果总览（L1–L8）

| 级别 | 验收内容 | 实际状态 | 客观核验证据 |
|:---|:---|:---:|:---|
| **L1** | **代码结构** | **PASS** | 七大模块抽离完毕，`main_window.py` 收敛为应用外壳（3,336 行），全部源码通过 `py_compile` |
| **L2** | **自动化测试** | **PASS** | 本地 198 passed / 6 skipped；GitHub Actions 4 路矩阵 (`ubuntu-latest` + `windows-latest` × Python `3.11` & `3.12`) 全绿 |
| **L3** | **GUI 功能** | **PASS** | 七大功能页独立挂载与信号调度通过测试，`GromacsWorker` 严格区分成功/停止/失败/未知状态 |
| **L4** | **科研工作流** | **PASS (有适用边界)** | SA 逐轮结构继承、CPT 隔离、`-maxwarn` 安全上限、后置物理自检与 Z 轴排序完备；真实外部 `gmx_MMPBSA` 需用户装包实测 |
| **L5** | **视觉体验** | **PASS** | 双主题、双层非重叠顶栏、`880x620`~`1920x1080` 及 `100%~200%` DPI 通过实拍截图审查与零重叠断言 |
| **L6** | **文档与兼容** | **PASS** | `README.md` / `README_EN.md` / `CHANGELOG.md` / 中英文切换 (`i18n.py`) 与旧版 JSON 配置向后兼容 |
| **L7** | **产品构建** | **PASS (便携版)** | Windows 便携包 `GROMACS-GUI-v4.4.0-rc.1-win64-portable.zip` + SHA256 构建完成并通过干净环境 `--smoke-test`；Inno Setup 安装程序需 `iscc.exe` 编译 |
| **L8** | **正式交付** | **PRE-RELEASE RC** | 因根目录 `LICENSE` (MIT) 与软件内禁止商用条款存在法律冲突 (P18)，不强行合并 `master`；已交付完整 `dev` 集成与预发布候选版 `v4.4.0-rc.1` |

---

## 二、全阶段任务完成清单 (M0–M6)

| 任务编号 | 任务名称 | PR / 分支 | 状态 | 关键交付物与 Merge SHA |
|:---|:---|:---|:---:|:---|
| **P0** | PR #6 MMPBSA 组件化合并 | PR #6 | **COMPLETED** | `bce87528` (`source/gui/tabs/mmpbsa_tab.py`) |
| **P0.1** | 建立工程持续执行治理体系 | PR #7 | **COMPLETED** | `54c7c74a` (`docs/engineering/`) |
| **P1** | Part 4 轨迹处理组件化 | PR #8 | **COMPLETED** | `29d7f535` (`source/gui/tabs/trajectory_tab.py`) |
| **P2** | Part 2 结构处理组件化 | PR #9 | **COMPLETED** | `a08b7ecc` (`source/gui/tabs/structure_tab.py`) |
| **P3** | Part 3 高级模拟组件化 | PR #10 | **COMPLETED** | `2e1bc00c` (`source/gui/tabs/advanced_tab.py`) |
| **P4** | Part 1 基础与全流程 MD 组件化 | PR #12 | **COMPLETED** | `394dd2ea` (`source/gui/tabs/md_tab.py`) |
| **P5** | Part 5 结果分析与可视化组件化 | PR #11 | **COMPLETED** | `07eaed56` (`source/gui/tabs/analysis_tab.py`) |
| **P6–P9** | 正式视觉审核 + Design System + 双层顶栏 + 多分辨率测试 | PR #13 | **COMPLETED** | `d732a66e` (`theme_tokens.py`, 实拍对比与几何零重叠测试) |
| **P10** | 完整中英文国际化与命令语言不变性解耦 | PR #14 | **COMPLETED** | `5c9265e2` (`source/gui/i18n.py`, `tests/unit/test_i18n.py`) |
| **P11 & P13** | 治理 Issue #2 安全边界、Z轴溶剂删除、物理自检与生命周期 | PR #15 | **COMPLETED** | `b9a641b2` (`validation.py`, `md_runner.py`, `gromacs_worker.py`) |
| **P12** | 治理 Issue #5 MMPBSA 全参数生效与环境检测 | PR #16 | **COMPLETED** | `029de6ca` (已关闭 Issue #5) |
| **P14–P16, P19** | Windows/Ubuntu 双平台 CI、打包崩溃修复与可复现构建 | PR #17 | **COMPLETED** | `3c4e4ebf` (`build_windows_portable.py`, `--smoke-test`) |
| **P17–P21** | 中英文文档、许可证冲突留档、门禁检查与 RC 预发布 | PR #18 | **COMPLETED** | `README.md`, `README_EN.md`, `CHANGELOG.md`, `FINAL_ENGINEERING_REPORT.md` |
