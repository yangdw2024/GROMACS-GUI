# 更新日志 (CHANGELOG)

所有版本的重要架构演进、科研可靠性修复与工程变更均记录于本文件。

---

## [v4.4.0-rc.1] - 2026-11-12 (Release Candidate)

### 架构与模块化 (Architecture)
- **七大功能页面全面组件化**：完成 Part 1 (`MdTab`)、Part 2 (`StructureTab`)、Part 3 (`AdvancedTab`)、Part 4 (`TrajectoryTab`)、Part 5 (`AnalysisTab`)、Part 6 (`MmpbsaTab`)、Part 7 (`ScriptTab`) 从巨石单体 `main_window.py` 的全面剥离（`main_window.py` 由 7,445 行精简 57% 至纯外壳装配调度层）。
- **任务生命周期精准化 (`GromacsWorker`)**：严格区分任务 `success` / `stopped`（用户主动中止）/ `failed`（非零退出）/ `unknown`（退出码缺失），并在窗口关闭 `closeEvent` 优雅释放运行中后台线程。

### UI / UX 与国际化 (Design System & i18n)
- **落地完整 Design System (`source/gui/themes/theme_tokens.py`)**：建立 Slate 深/浅色专业科研配色与语义属性选择器，全面移除各 Tab 内硬编码的彩虹高饱和按钮与深色底低对比度文本。
- **双层非重叠响应式顶栏**：重构 `topHeaderBar` 与独立全宽 `workdirBar`、双行紧凑硬件配置抽屉 `sysConfigDrawer` 及加宽左导航栏，在 `880×620` 至 `1920×1080` 及 `100%–200%` DPI 下实现几何零重叠。
- **中英文国际化 (`source/gui/i18n.py`)**：支持界面一键实时切换 `中文 / EN`，并将计算逻辑与 ComboBox 显示文案完全解耦，保证切换语言后生成的 GROMACS 命令 100% 一致，且全面兼容旧版 V1.0 中文配置 JSON。

### 科研计算可靠性 (Scientific Reliability)
- **Issue #2 安全治理 (`source/simulation/validation.py`, `md_runner.py`, `embedded_scripts.py`)**：
  - 将盲目的 `-maxwarn 200` 收敛为受控策略 `SA_SAFE_MAXWARN = 5` 与 `validate_maxwarn` 边界校验；
  - 新增 `validate_gro_structure()` 与 `validate_md_log()` 后置物理自检（检测 `NaN/Inf`、盒子塌陷、LINCS/SETTLE 爆炸，且显式豁免正常 NPT 瞬时压力波动）；
  - 为溶剂删除新增物理空间 Z 轴排序模式 (`z_top` / `z_bottom`)，同时 100% 保留原有 `bottom`/`top` GRO 顺序兼容行为。
- **Issue #5 MMPBSA 全功能增强 (`source/simulation/analysis.py`, `mmpbsa_tab.py`)**：
  - 实现 `convert_ps_to_mmpbsa_frames()` 时间到 1-based 帧索引严谨换算；
  - 新增 `parse_ndx_groups()` 真实读取 `.ndx` 组号消除 `-cg 1 13` 硬编码；
  - 自动生成 `mmpbsa.in` 并接入 MPI 并行 (`mpirun -np`)、图表导出规格及外部 `gmx_MMPBSA` 环境前置检测。

### 质量工程与 Windows 打包 (Quality & Packaging)
- **跨平台 CI 矩阵**：`.github/workflows/ci.yml` 扩展为 `ubuntu-latest` + `windows-latest` × Python `3.11 / 3.12` 四路矩阵，全部 **198 passed, 6 skipped**。
- **修复 Windows 冻结打包版启动崩溃**：解决 `py-cpuinfo` 在 PyInstaller 冻结态下子进程死锁与 Windows GBK 控制台日志输出 Emoji 引发的 `UnicodeEncodeError`，新增 `--smoke-test` 启动验证与 `build_windows_portable.py` 自动化构建流水线。

---

## [v4.3.0] - 2026-07-16
- 修复 GPU 检测崩溃、无 GPU 兼容模式与程序图标重设计。

## [v4.2.0] - 2026-07-09
- 修复溶剂蒸发循环结构继承、UI 布局与断点续跑校验。
