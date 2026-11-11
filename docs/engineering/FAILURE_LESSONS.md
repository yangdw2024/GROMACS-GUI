# 工程失败复盘与开发经验规则库
## Failure Lessons & Prevention Rules

本文件记录项目推进过程中遇到的所有重大故障、CI 阻塞原因及其转化出的不可逾越的开发规则。

---

## 一、重大失败案例与根因复盘

### 案例 1：PyQt5 GUI 集成测试导致 GitHub Actions CI 无限挂起（Cancelled）
- **现象**：`test_main_window_script_tab_integration` 在本地 Windows 极快通过，但在 GitHub Actions `ubuntu-latest` 上 Python 3.11/3.12 任务均卡住，最终超时取消（Run ID 42837880862）。
- **根因**：测试用例直接触发了 `win.script_run_btn.click()`，导致主窗口实例化真实的 `GromacsWorker`（`QThread`）并启动子进程。在 Linux 无头环境下，`cmd` 进程不存在导致异常分支，且由于窗口关闭时后台 QThread 仍在运行，Python 进程析构与 Qt 底层线程死锁。
- **进化规则**：
  - **规则 1**：GUI 组件单元测试**严禁启动真实的 `QThread` 或外部物理进程**。必须将统一调度入口（`run_command`）用 `mock.MagicMock()` 完全接管；
  - **规则 2**：所有无头测试必须在 `try...finally` 块中确保 `worker.stop()` 与 `win.close()`，测试结束零线程/零进程残留。

### 案例 2：重构抽离后方法尾部残留旧代码引发 `NameError`
- **现象**：`main_window.py` 在将 `run_script` 委托给 `ScriptTab` 后，方法末尾遗留了一行 `self.run_command(cmd, wd, step_name)`。
- **根因**：编辑重构未做全量静态扫描与旧接口直接调用测试，局部变量未定义导致只要调用该方法就必定抛出 `NameError`。
- **进化规则**：
  - **规则 3**：组件拆分后，旧有在主窗口保留的公共代理方法必须编写**显式直接调用测试**，断言其无 `NameError`，且必须通过 Mock 校验其派发次数为 1（防重复派发）。

### 案例 3：Windows 换行符 CRLF 污染导致 Bash 脚本测试失败
- **现象**：在 Windows 上检出或修改 Shell 脚本后，换行符变成 `\r\n`，导致 Linux 上 `bash -n` 或运行报语法错误，`test_delete_solvent.py` 中 `b"\r" not in script.read_bytes()` 断言失败。
- **根因**：缺乏跨平台 Git 换行符约束。
- **进化规则**：
  - **规则 4**：仓库根目录建立 `.gitattributes`，显式指定 `*.sh text eol=lf` 与 `*.slurm text eol=lf`；测试与提交前统一运行 `sed -i 's/\r$//'`。

### 案例 4：Windows 10/11 默认应用别名导致 `python3` 误报可用
- **现象**：Shell 脚本中 `command -v python3` 探测到 `/c/Users/.../WindowsApps/python3`，执行时弹出 Windows 商店安装重定向或退出码 9009。
- **根因**：Windows 系统内置的空包装器未被校验。
- **进化规则**：
  - **规则 5**：Shell/脚本探测 Python 时，必须追加真实执行校验：`python3 -c "import sys" >/dev/null 2>&1`，若失败则安全回退至 `python`。

### 案例 5：Batch 导出模板中 `for /l` 循环体内未转义括号导致 CMD 语法崩溃
- **现象**：导出的 `.bat` 脚本在 CMD 执行报 `... was unexpected at this time`。
- **根因**：CMD 批处理解析规则：在 `for (...) do (...)` 括号代码块中，内含的 `echo mdrun (10ps)...` 括号会被 CMD 错误提前截断块。
- **进化规则**：
  - **规则 6**：CMD 批处理中严禁在循环体内直接使用未转义的半角括号，统一采用 `echo mdrun 10ps...` 或转义符 `^(10ps^)`.
