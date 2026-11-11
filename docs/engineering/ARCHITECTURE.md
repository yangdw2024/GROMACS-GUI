# 软件系统架构与模块边界设计
## System Architecture & Module Boundaries

---

## 一、架构愿景与分层模型

GROMACS-GUI 遵循“**界面层薄化、计算逻辑收敛、基础设施隔离、状态单向流动**”的设计原则，彻底打破早期将全部界面、进程调用、文件 IO 堆叠在单个大文件中的单体架构。

### 目标架构分层

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   Layer 1: Application Shell (应用外壳)                 │
│  - 主窗口装配 (GromacsGUI)                                             │
│  - 顶部状态栏 (TopHeaderBar) + 胶囊徽标 (GmxBadge / GpuBadge)           │
│  - 左侧垂直导航工作台 (LeftNavRail) + 经典双栏布局回退开关              │
│  - 底部可折叠日志终端 (BottomConsoleDrawer)                            │
│  - 主题引擎 (source/gui/themes/) + 国际化多语言 (source/gui/i18n/)      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (组合 / 信号调度)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   Layer 2: GUI Tabs (功能页面组件)                      │
├── GUI Tabs (全部 7 大组件已独立抽离完毕)
│   ├── Part 1: MD Simulation (source/gui/tabs/md_tab.py)
│   ├── Part 2: Structure Processing (source/gui/tabs/structure_tab.py)
│   ├── Part 3: Advanced Simulation (source/gui/tabs/advanced_tab.py)
│   ├── Part 4: Trajectory Processing (source/gui/tabs/trajectory_tab.py)
│   ├── Part 5: Analysis & Plotting (source/gui/tabs/analysis_tab.py)
│   ├── Part 6: MMPBSA (source/gui/tabs/mmpbsa_tab.py)
│   └── Part 7: Custom Scripts (source/gui/tabs/script_tab.py)
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (构造注入环境 / 发送任务请求信号)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│               Layer 3: Application & Scientific Services               │
│  - 模拟命令与流程构建 (source/simulation/md_runner.py, mdp_builder.py) │
│  - 分析工具命令构建 (source/simulation/analysis.py)                    │
│  - 流程模板生成引擎 (source/gui/script_templates.py)                   │
│  - 内嵌溶剂处理脚本生成 (source/gui/embedded_scripts.py)               │
│  - 核心服务 (source/core/): 版本管理, 资源监控, 崩溃捕获, 错误诊断     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (进程派发 / 异步 IO)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     Layer 4: Execution Infrastructure                  │
│  - GromacsWorker (QThread 包装, Windows Job Object 内存限制, Stdin)    │
│  - GROMACS 本地多版本二进制探测与调度                                   │
│  - 外部分析工具链 (gmx_MMPBSA, Python, Shell, PowerShell)               │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 二、页面组件通信契约（无全局单例）

所有抽离出来的 `Tab` 组件必须遵循以下标准化通信契约：

```python
class ComponentTabBase(QWidget):
    # 核心信号：上抛待执行的命令列表、工作目录及步骤描述
    run_requested = pyqtSignal(object, str, str)  # (cmd_list, work_dir, step_name)
    # 日志信号：上抛消息文本与分级 ('info', 'success', 'warning', 'error', 'cmd')
    log_requested = pyqtSignal(str, str)

    def __init__(self, get_work_dir: Callable[[], str], parent=None):
        super().__init__(parent)
        self._get_work_dir = get_work_dir

    def set_running_state(self, running: bool):
        """当外部任务执行开始或结束时，联动锁定/解锁本页面内的运行按钮"""
        pass

    def get_config(self) -> dict:
        """配置持久化导出"""
        return {}

    def set_config(self, data: dict):
        """配置持久化恢复"""
        pass
```

### 规则与约束
1. **禁止逆向引用**：Tab 组件内部禁止调用 `self.parent().parent().some_widget`；
2. **禁止独立启动线程**：所有后台命令必须组装为 `cmd` 后通过 `run_requested` 统一上抛给主窗口的 `run_command`；
3. **主窗口保留属性别名**：在 `GromacsGUI` 中必须通过别名指向 `self.<tab_name>.<widget_name>`，保证旧有自动化测试与外部脚本 100% 兼容。
