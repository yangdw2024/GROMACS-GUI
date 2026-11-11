# 技术债与缺陷追踪总账
## Issue & Technical Debt Register

---

| 序号 | 标识与链接 | 类型 | 严重级别 | 当前状态 | 说明与处理情况 |
|:---:|:---|:---:|:---:|:---:|:---|
| **1** | PR #1 / SA继承 | 科研缺陷 | P0 | **RESOLVED** | 逐轮 NPT 结构继承与 CPT 严格同轮恢复已在 PR #1 修复并验证。 |
| **2** | PR #3 / UI外壳 | 架构/体验 | P1 | **RESOLVED** | 现代化左导航、双主题、经典布局回退已合并 `dev`。 |
| **3** | PR #4, #6, #8–#12 | 架构解耦 | P1 | **RESOLVED** | 七大功能页全面拆离至 `source/gui/tabs/`，`main_window.py` 降至装配调度层。 |
| **4** | PR #13 / 视觉审查 | UI 缺陷 | P0 | **RESOLVED** | 修复 1280px 顶栏挤压重叠、深色主题文字对比度不足、浅色终端变白、抽屉溢出及左导航截断；补充跨分辨率几何断言测试。 |
| **5** | PR #14 / 双语 | 新特性 | P1 | **RESOLVED** | 落地完整中英文切换与 `itemData` 逻辑解耦。 |
| **6** | [Issue #5](https://github.com/yangdw2024/GROMACS-GUI/issues/5) | 功能缺陷 | P1 | **CLOSED** | 已通过 PR #16（Merge `029de6ca`）修复时间帧换算、NDX 组动态读取、`mmpbsa.in` 生成、MPI 并行与环境检测，Issue #5 已关闭。 |
| **7** | [Issue #2](https://github.com/yangdw2024/GROMACS-GUI/issues/2) | 科研安全 | P1 | **PARTIALLY RESOLVED** | PR #15 与 PR #13 已解决 `-maxwarn 200`、后置物理自检、Z 轴溶剂删除、QSS 范围及 GUI 几何测试。<br>**遗留低风险项**：`embedded_scripts.py` 与 `examples/*/delete_solvent.py` 脚本单一事实来源 (SSOT) 仍建议后续统一；全局与配置类双重读取 (`ConfigManager` vs `save_config`) 可继续精简。 |
| **8** | P18 / 许可证冲突 | 合规门禁 | P0 (Release Blocker) | **OPEN (需版权人确认)** | 仓库根目录 `LICENSE` 为 **MIT**（允许商用），而软件内协议 `source/gui/app.py:73` 声明“禁止商业销售或付费服务”。在版权人确认方案 A（纯 MIT）或方案 B（非商业协议）前，暂阻断正式稳定版合并 `master`。 |
| **9** | P19 / Inno Setup | 打包工具 | P2 | **OPEN (环境缺省)** | 宿主环境未安装 Inno Setup (`iscc.exe`)，已更新修正 `installer_v43.iss` 相对路径，并提供可直接发布的 `win64-portable.zip` 便携包。 |
