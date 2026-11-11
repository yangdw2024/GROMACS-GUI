# 自动化测试矩阵与质量门禁规范
## Test Matrix & Quality Engineering

---

## 一、测试套件分类与规模清单

截至 PR #6 合并，全仓库单元与集成测试套件规模如下：

| 测试模块 | 用例数 | 覆盖核心内容 | 关键断言与测试方式 |
|:---|:---:|:---|:---|
| `tests/unit/test_analysis.py` | 20 | 结果分析命令构建 (`energy`, `rmsd`, `rdf`, `msd`, `mmpbsa`) | 快照对比、选项参数拼装、组输入校验 |
| `tests/unit/test_core_modules.py` | 19 | 核心基础设施 (`ErrorHandler`, `ResourceMonitor`, `VersionManager`) | 系统资源获取、内存限制、版本探测 |
| `tests/unit/test_delete_solvent.py` | 18 | SA 溶剂删除算法、GRO/TOP 对账、截断检测、命令行参数优先级 | 合成水/CF 体系、负数 TOP 拦截、假成功防御 |
| `tests/unit/test_gui_modern.py` | 8 | 现代化 UI 外壳、左导航同步、双主题切换、经典回退、响应式顶栏 | PyQt5 无头 (`offscreen`) 状态机与配置往返 |
| `tests/unit/test_md_runner.py` | 35 | MD 流水线构建、SA 逐轮继承命令、同轮 CPT 恢复、已完成轮次检测 | 依赖隔离 Mock、文件链完整度、严格轮次判定 |
| `tests/unit/test_mdp_builder.py` | 41 | 全部 MDP 参数生成器 (EM, NVT, NPT, MD, SA, 退火, 伞形, PLUMED) | MDP 关键参数格式、温度阶梯、控压算法断言 |
| `tests/unit/test_script_tab.py` | 6 | Part 7 自定义脚本组件 (`ScriptTab`)，14 套模板等价性，命令生成 | 信号槽触发、Mock 调度器隔离、临时脚本输出 |
| `tests/unit/test_mmpbsa_tab.py` | 5 | Part 6 MMPBSA 组件 (`MmpbsaTab`)，默认参数，别名兼容，运行锁 | 控件默认值、命令等价性、单次派发防重发 |
| **全量总计** | **152 (147+5)** | **核心调度、工作流、分析算法与 GUI 核心交互** | **147 passed, 6 skipped, 0 failed** |

---

## 二、测试环境与执行规则

### 1. 运行平台矩阵
- **本地宿主**：Windows 11 x64, Python 3.13 / Miniconda3, NVIDIA RTX 5060 Ti, CUDA 13.1, AVX-512；
- **云端 CI**：GitHub Actions `ubuntu-latest`, Python 3.11 & 3.12 双版本矩阵。

### 2. Qt 无头测试三大铁律
1. **环境变量强制隔离**：所有无头测试必须在引入 PyQt5 前确保 `QT_QPA_PLATFORM=offscreen`；
2. **命令调度强制 Mock**：GUI 组件单元测试**严禁启动真实的 `GromacsWorker` QThread 或外部进程**（如 `cmd`, `powershell`, `gmx`），必须使用 `mock.MagicMock()` 接管；
3. **模态弹窗强制拦截**：使用 `mock.patch("PyQt5.QtWidgets.QMessageBox.warning")` 等拦截弹窗，防止无头环境挂起；
4. **生命周期零残留**：在 `try...finally` 块中调用 `win.close()` 与 `qapp.processEvents()`，确保无悬挂线程或子进程。
