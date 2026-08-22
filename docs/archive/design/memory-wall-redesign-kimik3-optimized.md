# 前端 UI 沉稳化改造对比说明

> 归档状态：2026-08-04 前端视觉改造记录，不是当前界面事实来源。
> 当前产品与架构说明见 [`docs/README.md`](../../README.md)；现行界面以代码和
> 自动化测试为准。

分支：`feat/memory-wall-redesign-kimik3-optimized`
基线：`feat/memory-wall-redesign`
范围：仅 `glimpse-frontend/`，纯样式层调整，不改动任何组件 props、事件、状态管理与交互逻辑。

## 设计理念

原有界面偏"消费级"风格：大圆角（16–24px）、高饱和主色（#405cf5 / #ff6b24）、
浓重的发光投影、悬浮位移动效，视觉噪音较多。本次改造以**沉稳、专业、踏实**为目标，
遵循三条原则：

1. **收敛几何语言**：缩小圆角、压低投影，让界面"落地"而不是"飘浮"。
2. **统一色彩语义**：全站只保留一套主色（深宝蓝）+ 一套功能色（砖橙），
   清除历史遗留的青色 / 紫色 / 亮橙杂色。
3. **提升信息密度与对比**：收紧间距、压平字级、加深弱色文字，让层次靠
   对比而非装饰来建立。

## 一、设计令牌（`src/styles/main.css` CSS 变量）

| 令牌 | 修改前 | 修改后 | 说明 |
|---|---|---|---|
| `--radius-sm/md/lg/xl` | 8 / 12 / 16 / 20px | 6 / 8 / 10 / 12px | 全局圆角收敛一档 |
| `--color-primary` | `#405cf5`（亮蓝紫） | `#3b56c9`（深宝蓝） | 降饱和、加深，更稳重 |
| `--color-primary-hover` | `#314de9` | `#3048ab` | 同步加深 |
| `--color-accent` | `#ff6b24`（亮橙） | `#d9601c`（砖橙） | 截图按钮色，去荧光感 |
| `--color-text-muted` | `#7a879d` | `#66738a` | 弱文字加深，对比度 4.0→约 4.8:1 |
| `--color-border` | `#e1e5ee` | `#dde2ea` | 边框略加深，轮廓更清晰 |
| `--shadow-card` | `0 8px 24px / 6%` 单层 | `0 1px 2px + 0 6px 16px` 双层浅影 | 投影贴地，不再"悬浮" |
| `--shadow-modal` | `0 24px 72px / 20%` | `0 20px 56px / 18%` | 模态投影收敛 |
| 暗色主题 primary/accent | `#7185ff` / `#ff8a4c` | `#8494ff` / `#e07b3d` | 暗色下同步降饱和 |

## 二、全局组件类（`main.css`）

| 组件 | 修改前 | 修改后 |
|---|---|---|
| 标题栏 | 高 64px，左右 padding 24px | 高 56px，padding 20px |
| 品牌 Logo | 36px，圆角 10.4px，蓝色发光投影 | 32px，圆角 7px，浅灰投影 |
| `.card` | 圆角 20px，hover 橙色边框 + 大投影 | 圆角 10px，hover 主色 26% 边框 + 浅影 |
| `.btn-primary` / `.capture-button` | 圆角 14px，padding 12.5×16px，发光投影 12px 26px，hover 上浮 | 圆角 8px，padding 10×16px，投影 2px 8px，hover 不再位移 |
| `.btn-secondary` | 圆角 14px，青色边框（历史遗留），青色文字 | 圆角 8px，中性边框，灰蓝文字，hover 转深色 |
| `.search-bar` | 圆角 20px，聚焦橙色光晕（与主色冲突） | 圆角 10px，聚焦主色光晕 |
| `.status-pill` / `.badge` | 全圆胶囊（999px），字重 700 | 小圆角 6px 矩形标签，字重 600 |
| `kbd` 快捷键提示 | 全圆胶囊 | 5px 小圆角，更"键盘键帽"感 |
| 确认对话框 | padding 24px，区块间距 20–24px | padding 20px，区块间距 16–20px |
| 加载 spinner / logo 投影 / 徽章 | 青色系（#235d67，旧配色残留） | 统一改用主色变量 |

## 三、页面与组件（Tailwind 类）

### 搜索工具栏（SearchToolbar）
- 容器纵向 padding 16px → 12px，控件高度 48px → 44px，间距 gap-3 → gap-2.5。
- 搜索框 `rounded-2xl` → `rounded-lg`，字号 16px → 14px，聚焦色 `blue-500` → 主色变量。
- 来源切换组：圆角 16→8/6px，选中态 `bg-blue-600` → 主色变量。
- 截图按钮：移除 `bg-orange-500`/`shadow-orange-500/15` 等写死工具类，颜色统一交给
  `.capture-button`（砖橙变量）；移除 hover 上浮位移。

### 记忆墙（MemoryWall / MemoryCard）
- 滚动区 `pt-5 pb-8` → `pt-4 pb-6`；网格间距 16px → 12px；分组间距 `space-y-6` → `space-y-5`。
- 日期分组标题：`text-sm font-medium` → `text-xs font-semibold tracking-wide`，
  降级为"小节标签"，让卡片成为视觉主角。
- 卡片：圆角 16→8px；选中态 `blue-600` 硬编码 → 主色变量；hover 不再上浮
  （移除 `-translate-y-0.5`），仅边框加深 + 浅影。
- 卡片正文：padding 16→14px，摘要 14px/24px 行高 → 13px/20px，信息密度提升。
- 匹配来源标签：全圆胶囊 → 小圆角矩形，颜色改为主色/强调色变量。

### 详情侧栏（MemoryInspector）与详情页（MemoryDetail）
- 头部 `py-4` → `py-3.5`，标题 18px → 16px，时间戳 14px → 12px。
- 内容区 `space-y-5 p-5` → `space-y-4 p-4`；按钮组 gap 12px → 10px。
- 详情页双栏间距 32px → 24px；区块间距 24px → 20px。

### 设置页（Settings）
- 布局间距 28px → 20px；侧导航圆角 24→12px，项高 56→48px。
- 内容卡片圆角 24→12px；区块 padding 24→20px；输入框圆角 14→8px、高 46→42px。
- 聚焦色 `#2563eb` 硬编码 → 主色变量；OCR 信息卡 `blue-50/blue-950` 硬编码 →
  主色 soft/ink 变量；维护卡片紫色图标 → 主色。
- 底部操作栏 `py-5` → `py-4`，按钮 padding 收窄。

### 其他
- 集群进度条（ClusterBar）：紫色系 → 主色系，padding 16→14px，移除 `hover:scale-105` 缩放动效。
- 通知 Toast：圆角 12→6px，padding 收紧，info 图标紫色 → 主色。
- 确认对话框（ConfirmDialog）：圆角 24→12px，图标容器 44px/16px 圆角 → 40px/8px。
- 媒体画廊（MediaGallery）：圆角 16→8px，缩略图 12→6px，选中框蓝色硬编码 → 主色变量。

## 四、未改动项（兼容性保证）

- 未新增/删除任何组件、props、emit 事件、路由与 store；所有 DOM 结构和 aria 属性保持原样。
- 未使用的历史组件（MemoryList / EmptyState / SearchBar / DetailPanel）未纳入本次改造。
- `button { min-height: 2.5rem }` 可访问性底线保留；`prefers-reduced-motion` 降级逻辑保留。
- 暗色主题所有覆盖规则同步更新，双主题表现一致。

## 五、验证

- `npm run build`（vue-tsc 类型检查 + vite 构建）：通过。
- `npm run test:run`（vitest）：通过（初次失败为 `node_modules` 安装残缺的环境问题，
  `npm ci` 重装后全绿，与本次样式改动无关）。
