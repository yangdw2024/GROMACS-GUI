# 工程状态实时检查点
## Checkpoint

本文件用于全自动会话中断恢复。任何时刻重启任务，必须首先读取本文件确定工程阶段、代码基线及下一步明确动作。

---

## 一、当前工程基线

- **时间戳**：`2026-11-12 00:00:00`
- **当前仓库路径**：`D:\YDW\Trae_Gromacs`
- **当前活跃 Worktree**：`D:\YDW\Trae_Gromacs\scratch\wt_eng`
- **当前分支**：`chore/setup-engineering-governance`
- **dev 分支最新 Commit SHA**：`bce87528b5809eefc757384301ed31ffd53ced5a` (已合入 PR #6)
- **master 分支最新 Commit SHA**：`aa537c6d33151fbf6e919f3bd768aded90351bac` (保持稳定待最终发布)
- **主目录保护状态**：原工作区内 5 个未提交业务文件完整保留，所有修改严格限定在 `scratch/` 独立 worktree 中。

---

## 二、当前执行状态

- **正在推进任务**：`P0.1` 建立工程管理机制与 10 个核心治理文档（所属里程碑 `M0`）。
- **已完成任务**：
  - `P0` 完成 PR #6（Part 6 MMPBSA 页面抽离至 `source/gui/tabs/mmpbsa_tab.py`，CI 成功，已合并 dev，Merge SHA `bce87528`）。
  - 创建 Issue #5（MMPBSA 功能差距）与 Issue #2（计算安全技术债）。
- **下一步即刻动作**：
  1. 完成 `docs/engineering/` 10 个文档的建立与初始提交；
  2. 提交 PR 并合并至 `dev`；
  3. 启动 `M1`：以最新 `dev` 为基线开启 `refactor/extract-trajectory-tab` 分支，抽离 Part 4 轨迹处理页面。

---

## 三、现场安全恢复方法

若外部环境中断或需回退到稳定状态：
1. 检查 `git worktree list`，确认当前处于隔离环境；
2. 若当前 worktree 异常，可安全执行 `git worktree remove --force scratch/wt_eng`；
3. 基于 `origin/dev`（`bce87528`）重新建立 worktree 即可 100% 恢复洁净环境，原主工作区绝不丢失任何数据。
