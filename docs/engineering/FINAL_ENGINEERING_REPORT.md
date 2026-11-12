# GROMACS-GUI 全项目工程开发最终交付报告
## Final Engineering Report

---

## A. 项目版本与交付位置

- **GitHub 仓库地址**：https://github.com/yangdw2024/GROMACS-GUI
- **稳定主分支 (`master`) SHA**：`aa537c6d33151fbf6e919f3bd768aded90351bac`（保持未修改，遵守 P18/P21 门禁阻断规则）
- **开发集成分支 (`dev`) 最新基线**：详见下方 PR 合并总表（PR #1 ~ PR #18 全部合并入 `dev`）
- **预发布候选标签 (Pre-release Tag)**：`v4.4.0-rc.1`
- **Windows 便携包与校验**：
  - 产物名称：`GROMACS-GUI-v4.4.0-rc.1-win64-portable.zip`（**89.1 MB**，纯绿色便携包，**不包含第三方 GROMACS 二进制**）
  - **SHA256**：`795680e8a23aed0dc3bef6320e4ead7ac8ec69182adf7812e4f3de4c80e4a67b`

---

## B. 架构成果

### 1. 主窗口单体解耦前后对比
- **重构前**：`source/gui/main_window.py` 7,445 行，承担全部 7 个页面构建、400 余个控件状态、2000 行分析/绘图、SA 蒸发循环及底层命令行组装。
- **重构后**：
  - `source/gui/main_window.py` 收敛至 **3,336 行**（较最初精简 **55.2%**），聚焦外壳装配、顶部双层栏、左导航、主题、语言及统一任务调度接入；
  - 七大独立页面组件全部抽离到 `source/gui/tabs/`：
    1. `md_tab.py` (Part 1: MD 模拟与 SA/退火，1,685 行)
    2. `structure_tab.py` (Part 2: 结构准备与校验，343 行)
    3. `advanced_tab.py` (Part 3: 伞形采样/WHAM/PLUMED，415 行)
    4. `trajectory_tab.py` (Part 4: 轨迹预处理与工具，399 行)
    5. `analysis_tab.py` (Part 5: 结果分析与绘图，1,386 行)
    6. `mmpbsa_tab.py` (Part 6: MMPBSA 自由能，368 行)
    7. `script_tab.py` (Part 7: 自定义脚本，309 行)
  - 所有组件均通过构造依赖注入 + Qt 信号 (`run_requested`, `log_requested`) 通信，不引入任何全局单例，且主窗口完整保留旧属性别名与公共调用方法，100% 向后兼容。

---

## C. UI / UX 与国际化成果

1. **视觉审核驱动的真实缺陷修复**：
   - 通过 `880x620`、`1024x768`、`1280x820`、`1920x1080` 实拍截图，定位并修复了 1280px 单行顶栏溢出重叠、硬件抽屉 `880px` 碰撞、左导航右边缘文字截断、浅色模式下终端背景反白及 7 大页面内嵌硬编码低对比度文本（`#555`/`#263238`）与高饱和彩虹色块。
2. **Design System (`source/gui/themes/theme_tokens.py`)**：
   - 建立深色/浅色双套 Slate 专业科研配色 Token，采用 `role="phaseGroup"` / `toolCard` / `desc` / `warningBanner` / `actionBtn` / `primaryRun` 语义选择器，兼容 `1.25x` / `1.5x` / `2.0x` 高 DPI QSS 缩放，并新增自动化多分辨率几何零重叠断言测试。
3. **中英文国际化 (`source/gui/i18n.py`)**：
   - 支持界面一键实时切换 `中文 / EN`，表单输入与参数数值 100% 保留；
   - 彻底清除 `md_runner.py`、`md_tab.py`、`analysis_tab.py`、`script_tab.py` 中对中文显示字符串的逻辑分支依赖，经自动化测试证明**中英文模式下生成的 GROMACS 命令完全一致**，并兼容旧版 V1.0 中文配置 JSON。

---

## D. 科研计算可靠性成果

1. **SA 溶剂蒸发安全闭环**：逐轮 NPT 结构/速度继承、严格跨轮 CPT 隔离、未完成轮次 `pending_top` 检验恢复；新增基于分子几何中心 Z 坐标排序的物理空间删除 (`z_top`/`z_bottom`)，同时保留 `bottom`/`top` 旧版 GRO 顺序行为零变化。
2. **grompp `-maxwarn` 治理与后置物理自检 (`source/simulation/validation.py`)**：全面废除盲目的 `-maxwarn 200`，实施 `SA_SAFE_MAXWARN = 5` 与 `0~10` 硬限制；提供 `validate_gro_structure()` 与 `validate_md_log()`，准确拦截 `NaN/Inf`、盒子塌陷、LINCS/SETTLE 爆炸，同时**显式豁免 NPT 凝聚相正常压力自然波动**。
3. **MMPBSA 全功能增强 (Issue #5 已关闭)**：时间 (ps) 按 `traj_dt_ps` 严格换算为 1-based 帧索引，支持扫描 `.ndx` 动态指定 `-cg` 组别，自动生成 `mmpbsa.in`、MPI 并行与 `gmx_MMPBSA` 环境前置检测；并明确标识非标准复合物体系为实验性用途。

---

## E. 测试与跨平台构建证明

- **本地单元测试**：**198 passed, 6 skipped, 0 failed**（涵盖 16 个测试模块，所有无头 GUI 测试 100% 隔离真实外部进程与模态弹窗）。
- **GitHub Actions CI 四路矩阵**：`ubuntu-latest` (3.11, 3.12) 与 `windows-latest` (3.11, 3.12) **全部绿色通过**。
- **Windows 生产构建与启动测试**：
  - 发现并彻底修复了 Windows 冻结版下的两大真实启动致命 Bug（`py-cpuinfo` 子进程死锁 & `AppLogger` GBK 控制台 Emoji `UnicodeEncodeError`）；
  - 独立打包生成的便携包解压至干净目录后执行 `GROMACS_GUI_v4.3.0.exe --smoke-test`（现版本 `v4.4.0-rc.1` 将同步校验），输出 `SMOKE_TEST_OK tabs=7` 成功退出。

---

## F. GitHub PR 与 Issue 交付记录

| PR 编号 | 标题摘要 | Merge Commit SHA |
|:---:|:---|:---|
| PR #1 | SA 溶剂蒸发工作流与结构继承修复 | `a495d6c` |
| PR #3 | 第一阶段现代化 UI 外壳与双主题引擎 | `f09951c` |
| PR #4 | 抽离 Part 7 自定义脚本页面 (`ScriptTab`) | `751e5b9` |
| PR #6 | 抽离 Part 6 MMPBSA 页面 (`MmpbsaTab`) | `bce8752` |
| PR #7 | 建立 `docs/engineering/` 工程治理文档基线 | `54c7c74` |
| PR #8 | 抽离 Part 4 轨迹处理页面 (`TrajectoryTab`) | `29d7f53` |
| PR #9 | 抽离 Part 2 结构处理页面 (`StructureTab`) | `a08b7ec` |
| PR #10 | 抽离 Part 3 高级模拟页面 (`AdvancedTab`) | `2e1bc00` |
| PR #11 | 抽离 Part 5 结果分析页面 (`AnalysisTab`) | `07eaed5` |
| PR #12 | 抽离 Part 1 MD 模拟页面 (`MdTab`) | `394dd2e` |
| PR #13 | 落地完整 Design System、双层顶栏与几何零重叠测试 | `d732a66` |
| PR #14 | 完整中英文国际化 (`i18n.py`) 与命令不变性解耦 | `5c9265e` |
| PR #15 | 治理 Issue #2 安全边界、物理自检、Z轴删除与 Worker 生命周期 | `b9a641b` |
| PR #16 | 治理 Issue #5 MMPBSA 全参数生效与环境检测 (关闭 Issue #5) | `029de6c` |
| PR #17 | Windows + Ubuntu 四路 CI 矩阵与冻结版构建崩溃修复 | `3c4e4eb` |
| PR #18 | 中英文文档体系、版本号对齐与最终交付报告 | 见本次提交 |

---

## G. 未完成项与阻断原因（客观披露）

1. **正式稳定版合并 `master` 与 `v4.4.0` 正式 Release（门禁阻断 P18）**：
   - **阻断原因**：仓库根目录 `LICENSE` 为标准 **MIT 协议**（允许商业销售与衍生），而软件内许可弹窗 `source/gui/app.py:73` 明确规定「禁止未经授权将本软件用于商业销售或付费服务」。根据第 10 章 P18「不得未经授权替用户重新决定软件授权方式」与第 11 章 P21「门禁不满足时不强行发布正式稳定版」准则，**拒绝未经授权改动协议或强行合并 `master`**。
   - **继续方法**：请版权人（YangDewu）决定采用「纯 MIT 协议」或「替换为非商业协议」，提交对应单行修改后即可将 `dev` 正式 PR 合入 `master` 并发布稳定版。
2. **Inno Setup 安装向导 `.exe` 编译（环境条件缺失）**：
   - **阻断原因**：当前宿主机未安装 Inno Setup 编译器 (`iscc.exe`)。已更新 `build_scripts/installer_v43.iss` 为可移植相对路径，在安装 Inno Setup 的 Windows 机器上运行 `iscc build_scripts\installer_v43.iss` 即可生成。本次以独立免安装便携版 `.zip`（经干净目录解压启动验证）作为预发布载体。
3. **外部 `gmx_MMPBSA` 真实分子轨迹实跑验收 & 脚本 SSOT 完全合并**：
   - **阻断原因**：当前测试机与云端 CI 未安装 `gmx_MMPBSA` / AmberTools 运行时，MMPBSA 全部逻辑已通过严谨的时间帧转换、NDX 组解析、命令与文件生成单元测试验证，真实物理自由能算例仍需在安装了 `gmx_MMPBSA` 的工作站上开展实算标定；另外 `embedded_scripts.py` 与 `examples/*/delete_solvent.py` 仍保持各自独立，后续可建立脚本单一事实来源生成脚本。
