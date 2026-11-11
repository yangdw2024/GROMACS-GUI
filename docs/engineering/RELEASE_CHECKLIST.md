# 正式版本发布检查清单与准出准则
## Release Checklist & Production Quality Gates

---

## 一、v4.4.0-rc.1 发布前全项门禁检验结果

| 门禁条目 | 检验内容 | 判定状态 | 真实证据 |
|:---|:---|:---:|:---|
| **Gate 1** | 代码与依赖审查 (L1) | **PASS** | 全部 `.py` 文件通过 `py_compile`；依赖清晰声明于 `requirements.txt` 与 `pyproject.toml` |
| **Gate 2** | 自动化测试全绿 (L2) | **PASS** | 本地 **198 passed, 6 skipped**；GitHub Actions 4 路矩阵 (`ubuntu` & `windows` × `3.11 / 3.12`) 全绿 |
| **Gate 3** | GUI 功能与生命周期 (L3) | **PASS** | 七大页面独立测试通过；`GromacsWorker` 严格区分成功/停止/失败/未知状态 |
| **Gate 4** | 科研可靠性闭环 (L4) | **PASS** | SA 逐轮结构继承、CPT 隔离、`-maxwarn` 安全上限、后置物理自检与 Z 轴排序完备 |
| **Gate 5** | 视觉体验与 DPI (L5) | **PASS** | 880×620 ~ 1920×1080、深浅主题、现代/经典布局实拍与零重叠测试通过 |
| **Gate 6** | 文档与国际化 (L6) | **PASS** | 中英文界面切换、旧 JSON 兼容加载、`README.md`/`README_EN.md`/`CHANGELOG.md` 齐全 |
| **Gate 7** | 生产包构建与干净启动 (L7) | **PASS (便携包)** | `GROMACS-GUI-v4.4.0-rc.1-win64-portable.zip` 构建完成，干净解压执行 `--smoke-test` 通过 |
| **Gate 8** | 安全、隐私与许可证 (L8) | **BLOCKED (许可证冲突)** | 不含任何科研轨迹/密钥/GROMACS 第三方二进制；但存在 **`LICENSE` (MIT) vs `app.py` (非商用)** 冲突 |

---

## 二、门禁决策结论

依据总指令第 11 章 **P21** 条款：因 **Gate 8 许可证文本不一致**（且本机缺少 `iscc.exe` 编译 Inno 安装向导及真实外部 `gmx_MMPBSA` 包在线验证），**本次不强行合并 `master` 发布正式稳定版**，而是以明确标识的 **预发布候选版 (`v4.4.0-rc.1`)** 交付全套经过验证的源码、便携数据包与 SHA256 校验，并将阻断详情交版权人最终拍板。
