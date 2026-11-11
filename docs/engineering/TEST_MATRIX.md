# 自动化测试矩阵与质量门禁规范
## Test Matrix & Quality Engineering

---

## 一、自动化测试套件清单

| 测试文件 | 用例数 | 核心验证范围 | 执行结果 |
|:---|:---:|:---|:---:|
| `tests/unit/test_analysis.py` | 20 | 分析/轨迹/结构/预处理/MMPBSA 命令构建 | **PASS** |
| `tests/unit/test_core_modules.py` | 32 | 核心基础设施 (Config, ResourceMonitor, VersionManager, 语法与方法校验) | **PASS** |
| `tests/unit/test_delete_solvent.py` | 18 | SA 溶剂删除算法、GRO/TOP 对账、截断与假成功防御 | **PASS** |
| `tests/unit/test_gui_modern.py` | 9 | 左导航、双主题、经典回退、配置一致性、多分辨率与 DPI 几何零重叠 | **PASS** |
| `tests/unit/test_md_runner.py` | 36 | MD 流水线、SA 逐轮继承、CPT 恢复、`-maxwarn` 安全边界校验 | **PASS** |
| `tests/unit/test_mdp_builder.py` | 41 | 全部 MDP 与 PLUMED 参数文件生成快照 | **PASS** |
| `tests/unit/test_script_tab.py` | 6 | Part 7 `ScriptTab` 42 组模板等价性、命令派发与防重发 | **PASS** |
| `tests/unit/test_mmpbsa_tab.py` | 7 | Part 6 `MmpbsaTab` 时间帧换算、NDX 组解析、MPI 与环境检测 | **PASS** |
| `tests/unit/test_trajectory_tab.py` | 5 | Part 4 `TrajectoryTab` 工具与五步法流水线隔离验证 | **PASS** |
| `tests/unit/test_structure_tab.py` | 5 | Part 2 `StructureTab` 力场注入与命令派发验证 | **PASS** |
| `tests/unit/test_advanced_tab.py` | 6 | Part 3 `AdvancedTab` 伞形 MDP/WHAM/PLUMED 验证 | **PASS** |
| `tests/unit/test_analysis_tab.py` | 8 | Part 5 `AnalysisTab` 19 项工具、片段索引与 matplotlib 离屏出图 | **PASS** |
| `tests/unit/test_md_tab.py` | 7 | Part 1 `MdTab` 默认值 (`dt=0.002`)、跳过逻辑、SA 蒸发与退火 | **PASS** |
| `tests/unit/test_i18n.py` | 5 | 中英字典完整性、表单状态保留、科学命令语言不变性与英文几何零重叠 | **PASS** |
| `tests/unit/test_validation.py` | 6 | GRO/md.log 物理一致性校验、NPT 压力波动豁免、Z 轴溶剂删除、Worker 生命周期 | **PASS** |
| `tests/unit/test_packaging_and_paths.py` | 5 | 中文 Unicode 与 Windows 空格路径、只读目录回退、Spec 完整度、GBK Emoji 容错、`--smoke-test` | **PASS** |
| **总计 (`tests/unit`)** | **204 (198+6)** | **覆盖核心逻辑、七大组件、i18n、科研安全、跨平台与打包入口** | **198 passed, 6 skipped, 0 failed** |

*(注：跳过的 6 项用例为本地 GROMACS 扫描路径与平台特异性条件跳过；`tests/integration/` 属于需真实安装 GROMACS 二进制的联调测试，不强制于无 GROMACS 的云端 CI 运行。)*

---

## 二、CI 运行矩阵

- **GitHub Actions Workflow** (`.github/workflows/ci.yml`)：
  - `ubuntu-latest` × Python `3.11`：**SUCCESS**
  - `ubuntu-latest` × Python `3.12`：**SUCCESS**
  - `windows-latest` × Python `3.11`：**SUCCESS**
  - `windows-latest` × Python `3.12`：**SUCCESS**
- **实机打包 Smoke Test**：
  - `build_scripts/build_windows_portable.py --smoke-test` 产出的 `GROMACS_GUI_v4.3.0.exe` 解压至干净隔离目录执行 `--smoke-test`，输出 `SMOKE_TEST_OK tabs=7`（退出码 `0`）。
