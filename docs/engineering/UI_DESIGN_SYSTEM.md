# 现代化 UI 设计系统与视觉规范
## UI / UX Design System

---

## 一、设计理念与视觉原则

GROMACS-GUI 致力于打造符合现代高水准科研软件特征的桌面界面：**克制、专业、清晰、无视觉噪音、操作层级扁平**。杜绝原版中高饱和度“彩虹按钮堆叠”与刺眼的黑白纯色切换。

---

## 二、Design Tokens 规范

主题 Token 集中定义于 `source/gui/themes/theme_tokens.py`，禁止在业务页面内硬编码 Hex 颜色。

### 1. 颜色体系 (Color Tokens)

| Token 键名 | 深色模式 (Dark) | 浅色模式 (Light) | 语义说明 |
|:---|:---:|:---:|:---|
| `bg_app` | `#0F172A` (Slate 900) | `#F1F5F9` (Slate 100) | 全局底层窗体背景色 |
| `bg_surface` | `#1E293B` (Slate 800) | `#FFFFFF` (Pure White) | 一级卡片、左导航条、顶栏背景 |
| `bg_elevated` | `#263349` | `#F8FAFC` | 输入框、次级容器、悬浮抽屉背景 |
| `bg_console` | `#090D16` | `#0F172A` | 底部运行终端背景（浅色模式保持暗色护眼） |
| `bg_hover` | `#334155` | `#E2E8F0` | 控件悬停背景 |
| `bg_active_nav` | `#1D4ED8` | `#EFF6FF` | 导航选中背景 |
| `border` | `#334155` | `#CBD5E1` | 默认分隔线与边框 |
| `border_focus` | `#3B82F6` | `#2563EB` | 输入框/焦点激活边框 |
| `text_primary` | `#F8FAFC` | `#0F172A` | 主要高对比度正文与标题 |
| `text_secondary` | `#94A3B8` | `#475569` | 说明文字、参数标签 |
| `text_muted` | `#64748B` | `#94A3B8` | 占位提示、禁用文本 |
| `group_title` | `#93C5FD` | `#0D47A1` | GroupBox 分组标题高亮色 |
| `primary` | `#2563EB` | `#2563EB` | 品牌主色 (Cobalt Blue) |
| `success` | `#10B981` | `#059669` | 运行/成功/正常状态 (Emerald Green) |
| `danger` | `#EF4444` | `#DC2626` | 停止/错误/危险状态 (Rose Red) |
| `warning` | `#F59E0B` | `#D97706` | 警告/提示状态 (Amber Orange) |

### 2. 字体与排印体系 (Typography)
- **主界面字体**：优先采用 `"Microsoft YaHei UI"`, `"Microsoft YaHei"`, `"Segoe UI"`, `sans-serif`；
- **终端与代码字体**：`"Consolas"`, `"Cascadia Mono"`, `"Courier New"`, `monospace`；
- **字阶**：
  - 页面大标题：`13.5pt` (`font-weight: bold`)；
  - 卡片分组标题：`10.5pt` (`font-weight: bold`)；
  - 常用字段标签：`9.0pt` (`font-weight: 600`)；
  - 徽标与次级说明：`8.5pt` (`font-weight: 500`)；
  - 紧凑辅助说明：`8.0pt`。

### 3. 圆角与间距规范 (Radius & Spacing)
- **圆角**：
  - 卡片与对话框：`6px ~ 8px`；
  - 输入框与按钮：`4px ~ 6px`；
  - 状态胶囊徽标：`6px ~ 11px`；
- **间距**：全局栅格基于 `4px / 8px / 12px / 16px`。

---

## 三、响应式断点与布局规则

主窗口自适应流控逻辑由 `main_window.py::_adapt_responsive_topbar` 实现：

| 窗口宽度断点 | 布局形态 | 顶栏适配规则 | 适用场景 |
|:---|:---|:---|:---|
| **$< 960\text{ px}$** | 极限紧凑 | 隐藏“工作目录:”文本标签，路径输入框收缩至 80~100px，胶囊采用微型简写（`GMX 2026.3` / `GPU`），全部辅助工具收纳至“更多 ▾”菜单 | 880x620 最小窗口尺寸 |
| **$960\text{ px} \sim 1180\text{ px}$** | 标准工作台 | 恢复完整工作目录标题，GPU 显示型号，更多工具常驻 | 1024x768 分辨率 |
| **$\ge 1180\text{ px}$** | 宽屏工作台 | MDP编辑、监控、保存、加载平铺展示于顶栏，更多工具保留低频运维操作 | 1280x820, 1920x1080 生产环境 |
