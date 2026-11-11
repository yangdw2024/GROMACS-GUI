# 技术债与缺陷追踪总账
## Issue & Technical Debt Register

---

## 一、未解决与已解决问题跟踪表

| 序号 | 标识与链接 | 类型 | 影响模块 | 严重级别 | 当前状态 | 描述与处理方案 |
|:---:|:---|:---:|:---|:---:|:---:|:---|
| **1** | PR #1 / Issue #2 | 缺陷/安全 | SA 溶剂蒸发 | P0 | **RESOLVED** | 逐轮 NPT 结构继承缺失，同轮中断误重删。已通过 PR #1、PR #4 彻底修复。 |
| **2** | PR #3 / UI 外壳 | 体验/架构 | UI 导航与顶栏 | P1 | **RESOLVED** | 顶部栏窄屏裁切、经典布局回退不完整、主题选择器全局污染。已在 PR #3 修复并合入 `dev`。 |
| **3** | PR #4 / 调度残留 | 缺陷/测试 | Part 7 自定义脚本 | P0 | **RESOLVED** | `run_script` 残留 `run_command` 导致 `NameError`，测试未 Mock 导致 CI 挂起。已在 PR #4 修复合入。 |
| **4** | PR #6 / 组件化 | 重构/解耦 | Part 6 MMPBSA | P1 | **RESOLVED** | 成功从 `main_window.py` 抽离 `source/gui/tabs/mmpbsa_tab.py`，保持 12 项别名透明代理，CI 成功合入。 |
| **5** | [Issue #2](https://github.com/yangdw2024/GROMACS-GUI/issues/2) | 技术债 | 全局/计算安全 | P1 | **OPEN** | 1) 全局 `-maxwarn 200` 收敛至物理白名单；<br>2) 模拟后置物理量合理性自检 (势能 NaN/LINCS 崩溃)；<br>3) 跨 PBC 边界断裂分子完整性提示；<br>4) `embedded_scripts.py` 与独立脚本单一事实来源 (SSOT) 统一；<br>5) 配置管理收敛。 |
| **6** | [Issue #5](https://github.com/yangdw2024/GROMACS-GUI/issues/5) | 功能缺陷 | Part 6 MMPBSA | P1 | **OPEN** | 1) 起止时间 `mmpbsa_start/end` 未生效；<br>2) 间隔 `mmpbsa_interval` 未生效；<br>3) 线程 `mmpbsa_nt` 未生效；<br>4) 图片输出未接入；<br>5) `-cg 1 13` 组别硬编码问题；<br>6) `gmx_MMPBSA` 外部环境与输入文件兼容性。 |
| **7** | Issue #2 追录项 | 技术债 | UI / 测试 | P2 | **OPEN** | 1) 应用级 QSS 选择器范围精细化；<br>2) GUI 几何布局与响应式自动断言测试。 |
