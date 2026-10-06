# UI 组件选型速查表

要写某类界面时，先在这张表里找该用哪个现成零件。**有就复用，样式不合场景
就给它加 variant/prop，绝不为单个页面新造平行组件**（`DESIGN.md` 明令）。
动手前的判断顺序见 [`ui-checklist.md`](./ui-checklist.md)。

表里的数值只为快速定位，**唯一事实源是 `glimpse-frontend/src/styles/main.css`
的 token 与各组件源码**；发现下表与源码不符时，以源码为准并更新本行——这与
`DESIGN.md` 附录"规格是派生物"的规则一致。

## 浮层与弹窗

| 场景 | 用这个 | 说明 |
|---|---|---|
| 需要用户"确认/取消"的打断式询问（含删除等破坏性操作） | `ConfirmDialog.vue` | 非 destructive 分支默认带琥珀警示三角图标；常规提示不要直接套这个壳，先按 `ui-checklist.md` 第 1 条判断该用 alert 还是无图标中性变体 |
| 信息展示型浮层（更新说明、详情速览），跟随某个触发元素弹出 | `UpdateNotesPopover.vue` | reka-ui Popover，自带标题栏+右上角关闭按钮（已统一 `XMarkIcon` 14px）+`notes-popover` 样式与进场动画；body 已隐藏滚动条、禁横滑 |
| 大图预览 | `ImagePreviewModal.vue` | `.image-preview-dialog`；关闭按钮 = 32px 无框标准规格（见"按钮"表叉号行），翻页箭头用 `.image-preview-stage__arrow` 40px 大档 |
| 右键/上下文菜单 | `MemoryContextMenu.vue` / `ImageContextMenu.vue` / `EditTextContextMenu.vue` | 菜单项 32px（`--control-h-md`），结构 `.x-context-menu` + `__item` + `__divider` |

## 按钮

| 场景 | 类名 | 高度档 | 字重/备注 |
|---|---|---|---|
| 主路径动作（搜索、召回确认） | `.btn-primary` | 32px md | 字重 400、带品牌投影——**只给主路径**，低频/次级动作别拿这个分量 |
| 次级动作 | `.btn-secondary` | 32px md | 字重 400、静息 `surface-subtle` 无描边、悬停 `surface-hover`——静息态与内嵌块同色，别再手动调底 |
| 低频破坏性操作（设置区"恢复默认"等） | `.btn-ghost-danger` | 32px md | 字重 400、无投影、hover 才显危险色——这是克制基调的现成榜样 |
| 弹窗/浮层里的动作按钮（确认/取消、查看详情/立即更新等低频操作） | 在基础按钮类上叠 `.btn-sm`（如 `.btn-primary.btn-sm`、`.btn-secondary.btn-sm`） | **28px sm** | 字重 400、13px、无投影。弹窗操作不是主路径，别用默认 32px 的分量 |
| 确认破坏性操作（弹窗内） | `.btn-danger`（弹窗内叠 `.btn-sm`） | 32px md（弹窗内 28px） | 实心危险色 |
| 窗口级关闭按钮（弹窗、浮窗、侧栏头部的叉） | `XMarkIcon` `h-3.5 w-3.5`（14px）+ 32px 无框按钮（muted 色、hover `surface-hover`） | 32px md | 唯一例外：软件头窗口关闭 15px；列表内联小叉（toast、标签清除）不属此类；**禁止自绘叉形 SVG** |
| 顶栏/紧凑工具区的纯图标按钮 | `.shell-icon-button` | **裸用 40px**；顶栏须对齐 28px 档 | 裸用是 2.5rem 且 hover 带 transform 位移；放进顶栏要按"设置齿轮"的 `desktop-shell__settings-button` 覆盖到 1.75rem、hover 改纯背景。新加顶栏图标按钮务必与邻居同尺寸同 hover |
| 顶栏带文字的导航（返回等） | `.shell-navigation-button` | 28px sm | 字重 600 |
| 窗口最小化/关闭等系统区 | `.window-control` | 顶栏通高、直角贴右缘 | 不加圆角 |

## 输入控件

| 场景 | 类名 | 规格 |
|---|---|---|
| 设置区输入框 | `.setting-input`（Settings.vue 局部） | 32px（`--control-h-md`）、文本框限宽 320px、数字框限宽 120px、聚焦只变边框色 |
| 设置区三段式切换器 | `.theme-switcher`（Settings.vue 局部） | 32px 高、扁平线框浅底+独立平移滑块 |
| 侧栏内嵌块（摘要/识别文本） | `SummaryEditor.vue` compact / `OcrText.vue` compact | `surface-subtle` 10px 圆角无框内衬约 12px；块头行内操作 28px；编辑态白底框浮起 |
| 搜索工具区控件 | SearchToolbar 内部 | 紧凑 32px 档 |

## 尺寸/形状/z 档位（镜像 token，以 main.css 为准）

- 控件高度：`--control-h-sm` 28px / `--control-h-md` 32px / `--control-h-lg` 40px，**只此三档**。
- 圆角刻度：`--radius-sm` 6 / `--radius-md` 8 / `--radius-lg` 10 / `--radius-xl` 12。同心规则见 `DESIGN.md`"形状的同心规则"。
- z 层级：`--z-sticky` 100 → `--z-dropdown` 200 → `--z-popover` 300 → `--z-backdrop` 500 → `--z-dialog` 600 → `--z-toast` 900。
- 阴影只给真正浮起的表面：卡片 `--shadow-card`、模态 `--shadow-modal`；不拿阴影替代边框或选中态。

## 排版

正文/控件 13–14px、标题 16px 起、元数据 11–12px。行高 token `--line-height-*`
镜像 main.css。英文 Segoe UI、中文 PingFang SC 优先 Windows 回退雅黑；需稳定
对齐的数量与日期用等宽数字（`font-variant-numeric: tabular-nums`）。图标只用
Heroicons Outline，控件图标约 18–20px、空状态 24–28px，不用 emoji 替代。
