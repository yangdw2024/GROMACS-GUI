# 工程状态实时检查点
## Checkpoint

---

## 一、当前工程基线

- **时间戳**：`2026-11-12`
- **当前仓库路径**：`D:\YDW\Trae_Gromacs`
- **主分支 (`master`) SHA**：`aa537c6d33151fbf6e919f3bd768aded90351bac`（严格保护，待版权人明确协议冲突解决方案后再决定正式合并）
- **开发主分支 (`dev`) 最新基线**：已合入 PR #1, #3, #4, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18
- **主目录保护状态**：原主工作目录内原有的 5 个未提交修改完整保护、零污染。

---

## 二、当前执行状态与收尾交接

- **已完成全部可执行工程里程碑 (M0–M6)**：
  - 七大功能页面全面拆分为 `source/gui/tabs/` 独立组件；
  - 完整 Design System + 实拍视觉修正 + 多分辨率几何零重叠门禁；
  - 完整中英文双语系统（`source/gui/i18n.py`）与命令语言无关性解耦；
  - Issue #2 与 Issue #5 科研安全性及 MMPBSA 功能增强全面落实（Issue #5 已关闭）；
  - GitHub Actions 升级为 Ubuntu + Windows 双系统 × Python 3.11/3.12 四路 CI 矩阵全绿；
  - Windows 便携生产构建 + 干净解压 `--smoke-test` 验证通过，并产出预发布候选版本 `v4.4.0-rc.1`。

---

## 三、待用户裁决的正式发布阻断项（P18 / P21）

1. **开源许可证冲突确认**：需版权人选择：
   - 方案 A：坚持纯 MIT License，移除 `source/gui/app.py:73` 中的非商业限制句；
   - 方案 B：维持非商业限制，将根目录 `LICENSE` 更换为 CC BY-NC-SA 4.0 或 PolyForm Noncommercial 1.0.0。
2. **可选构建工具**：如需生成 Windows `.exe` 向导安装器（在便携版 `.zip` 之外），需在具备 Inno Setup (`iscc.exe`) 的机器上编译 `build_scripts/installer_v43.iss`。
3. 待上述确认完成并合并 `dev` 至 `master` 后，即可正式发布 `v4.4.0` 稳定版 Release。
