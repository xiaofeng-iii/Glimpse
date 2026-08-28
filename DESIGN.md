---
version: alpha
name: "Glimpse"
description: "A compact desktop memory workspace built for fast capture, scanning, and recall."
colors:
  canvas: "#f6f7fa"
  header: "#f9f8f7"
  surface: "#ffffff"
  surface-subtle: "#f4f6f9"
  surface-hover: "#edf0f5"
  text: "#1a2334"
  text-secondary: "#49566c"
  text-muted: "#66738a"
  border: "#dde2ea"
  border-strong: "#c3cbda"
  primary: "#3b56c9"
  primary-hover: "#3048ab"
  primary-soft: "#edf0fa"
  accent: "#d9601c"
  success: "#1f9d62"
  warning: "#d97706"
  danger: "#d92d20"
  focus: "#3b56c9"
  on-primary: "#ffffff"
typography:
  sans:
    fontFamily: "Segoe UI, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "14px"
    lineHeight: "22px"
  cjk:
    fontFamily: "PingFang SC, PingFang HK, Helvetica Neue, Helvetica, Microsoft YaHei, 微软雅黑, Arial, sans-serif"
    fontSize: "14px"
    lineHeight: "22px"
  utility:
    fontFamily: "Segoe UI, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "12px"
    lineHeight: "20px"
rounded:
  DEFAULT: "8px"
  sm: "6px"
  md: "8px"
  lg: "10px"
  xl: "12px"
spacing:
  control-height: "40px"
  compact-control-height: "36px"
  page-gutter: "20px"
  grid-gap: "12px"
  section-gap: "20px"
  toolbar-surface-inset: "12px"
  compound-control-inset: "3px"
components:
  app-header:
    backgroundColor: "{colors.header}"
    textColor: "{colors.text}"
    height: "35px"
  app-canvas:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.text}"
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.md}"
    height: "{spacing.control-height}"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "{colors.on-primary}"
  button-capture:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.md}"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
  toolbar-surface:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.xl}"
    padding: "{spacing.toolbar-surface-inset}"
  compact-control:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
    height: "{spacing.compact-control-height}"
  search-mode-selector:
    rounded: "{rounded.sm}"
    padding: "{spacing.compound-control-inset}"
  surface-subtle:
    backgroundColor: "{colors.surface-subtle}"
    textColor: "{colors.text-secondary}"
  surface-hover:
    backgroundColor: "{colors.surface-hover}"
    textColor: "{colors.text}"
  metadata:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-muted}"
    typography: "{typography.utility}"
  filter-selected:
    backgroundColor: "{colors.primary-soft}"
    textColor: "{colors.primary-hover}"
    rounded: "{rounded.sm}"
  popover:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.xl}"
  dialog:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.xl}"
  state-success:
    backgroundColor: "{colors.success}"
    textColor: "{colors.on-primary}"
  state-warning:
    backgroundColor: "{colors.warning}"
    textColor: "{colors.text}"
  state-danger:
    backgroundColor: "{colors.danger}"
    textColor: "{colors.on-primary}"
  focus-ring:
    backgroundColor: "{colors.focus}"
    textColor: "{colors.on-primary}"
---

# Glimpse Design System

## Overview

Glimpse 应该像一只整理得很好的桌面索引盒：打开后先看到记忆，工具安静地排在手边，需要时马上够得到。

这是一个高频桌面工具，不是展示品牌的网页。设计取舍按以下顺序判断：召回效率、状态清晰、信息密度，最后才是装饰。界面可以有性格，但不能抢记忆内容的注意力。

深蓝色串起搜索、选择和确认路径；砖橙色只留给截图，让“找回”和“捕捉”在第一眼就能区分。其余结构依靠冷静的中性色、一像素边框和克制的层级完成。

产品同时维护 zh-CN 与 en-US。使用场景以 Windows 桌面窗口为主，用户往往只停留几秒，因此控件需要紧凑、位置稳定，中文和英文切换时也不能改变页面骨架。

不要把 Glimpse 做成营销页或玻璃拟态展板。大段空白、装饰性渐变、到处都是的胶囊按钮、强烈发光和为了“高级感”而增加的动效，都不属于它。

### 文档与实现的关系

本文件是唯一的设计文档，记录已经接受的视觉方向和规则。运行时数值由 `glimpse-frontend/src/styles/main.css` 中的 CSS 变量实现，本文件镜像这些值并解释用法。设计规则变化时，应在同一变更中更新本文件、运行时 token 和相关共享组件。

## Colors

### 角色先于色值

- `primary` 是搜索模式、选择状态、普通主要操作和焦点反馈的深蓝色。
- `accent` 是截图专用的砖橙色，不承担通用主要操作。
- `surface` 承载卡片、工具浮层和输入控件；`canvas` 是页面背板。
- `surface-subtle` 用于分组、空状态和低强调区域，不能替代选中状态。
- success、warning、danger 只表达对应语义，不参与装饰。

同一页面的背板必须连续。浮层周围不应出现一条来源不明的色带；工具栏外侧使用所在页面的背景，内部表面再通过边框和阴影抬起。

深色主题改变具体色值，但不改变角色。捕捉仍是橙色，召回仍是蓝色，次要信息仍比正文安静。

## Typography

英文界面默认使用 Segoe UI，并保留 PingFang SC 和 Microsoft YaHei 回退；简体中文界面使用与智谱开放平台一致的字体栈，macOS 优先采用 PingFang SC，Windows 回退到普通 Microsoft YaHei。品牌名、开发标记和等宽内容继续使用各自的拉丁或等宽字体，避免改变识别性和字符宽度。Windows 上的阅读速度比字体展示性更重要。

- 页面和面板标题通常为 16px，使用 semibold 或 bold。
- 控件和正文通常为 13–14px。
- 日期、标签、快捷键和元数据使用 11–12px。
- 数量与日期在需要稳定对齐时使用等宽数字。

标准字号与行高固定对应为：12/20px、14/22px、16/24px、20/28px、24/32px、30/38px、38/46px。组件不得用局部行高覆盖这组比例；表中未定义的特殊字号沿用组件现有值，确认后再并入标准刻度。

中文与拉丁字符保持正常大小写和直立排版。文案直接说动作和结果，例如“应用”“重置”“截图”，不使用营销口吻，也不让一个标签同时承担说明文的工作。

## Layout

### 空间表达关系

默认页面水平边距为 20px，记忆卡片间距为 12px，相关功能通常相隔 10–12px。数值不是平均撒在页面上的装饰：同组元素靠近，不同功能组拉开；标题更靠近自己说明的内容，而不是靠近外层容器。

桌面壳拥有视口，搜索工具栏和标题区域保持稳定，记忆墙与详情面板负责内部滚动。加载、空状态和错误状态要占住相同内容区域，避免持续存在的控件移动。

### 应用头部

应用头部固定为 35dp 高；在 Tauri/WebView 中以 `35px` CSS 逻辑像素实现，由系统缩放映射到物理像素。浅色主题使用 `rgb(249, 248, 247)`，通过一像素底边和短距离阴影与内容区分层。左侧依次放置 24dp Logo、应用名称、分隔线和设置入口；进入设置或详情后，该位置仅显示返回按钮，不重复展示页面名称。设置入口使用 28dp 紧凑图标按钮。右侧保留服务状态，并将最小化、最大化/还原、关闭组成无间距的标准窗口控制组：最小化使用横线，最大化使用单方框，还原使用重叠方框，关闭使用叉号；关闭悬停采用系统式红底白图标。窗口按钮保持一致宽度、直角相接并贴齐窗口右缘，不使用缩放箭头或卡片式圆角。

### 搜索工具栏

首页搜索区域是一块完整的工具浮层。页面左右为 20px 留白，浮层内部 padding 为 12px。搜索框、开发工具、截图和添加记忆按钮使用 36px 的紧凑高度，截图与添加记忆按钮的左右内边距统一为 14px；搜索模式分段控件与刷新按钮使用更紧凑的 32px 高度，模式文字为 13px。一级功能之间保持约 10px 间距。刷新（或源码启动时的 DEV）与截图之间使用一条短竖线分隔操作组。“添加记忆”使用深蓝主操作并固定在砖橙色“截图”右侧，让手动记录与画面捕捉相邻但不混淆。

搜索工具栏固定在记忆窗格顶部，并使用全局 `--z-sticky: 100` 层级。记忆窗格是首页左侧唯一的垂直滚动容器；数量栏、分组标题和记忆卡片随内容一起向上滚动，并延伸到浮栏背后、应用头下方。浮栏外层保持透明，只在控件表面背后使用一层从 60% 页面背景色向下淡出的遮罩；独立的 4px 背景模糊层通过渐变蒙版由模糊过渡到清晰，避免矩形边界。浮栏主体保持不透明，不重复施加模糊。右侧详情面板保持独立，不共享这条滚动链。

桌面窗口最小支持 520px 宽度。窄屏可以换行，但不能换一套视觉语言：控件高度、组内间距、圆角和操作顺序保持不变。

### 记忆墙与分割线

分割线用来整理空间，不用来切开整个窗口。“n 条记忆”标题栏保持紧凑，上方留白略大于文字到下方分割线的距离，让它既承接搜索工具栏，又明确属于记忆墙。记忆墙内容在各响应式宽度下都比搜索浮条左右各延伸 4px；分割线与记忆内容边缘对齐，并使用约 72% 的边框强度。普通内容分割线不应直接顶到软件两侧。

文字与图片记忆卡统一使用 `270px` 高度。图片记忆卡的媒体框固定为较浅的 `148px`，并配合 `object-contain` 在不裁切截图的前提下减少上下留白；节省出的空间用于把下方总结由三行扩展为四行。

纯文本记忆使用内容优先的两段式索引卡变体：上方以 `primary-soft` 浅蓝底承载最多八行的正文预览，下方使用独立白色信息区，时间固定在右侧，左侧保留为未来自定义 Tag 的稳定容器；在真实 Tag 功能落地前不显示占位标签或说明文案。文字卡与图片卡统一为 `270px` 高，不因同一行内容类型不同产生高度跳变；正文区域保持对称的左右内边距，不为平台或选中图标预留额外空间。不使用类型标签、文档图标、彩色竖线或“手动添加”等重复元数据。内容类型只作为数据属性和筛选条件存在。它不是“图片加载失败”的占位状态；详情与检查器也不展示类型标签、媒体或 OCR 模块，只保留正文、索引状态、复制、编辑和管理操作。

### 筛选面板

筛选是可扩展的工具面板。当前提供“时间范围”和“内容类型”两组条件；内容类型使用“图片”“文本”两个方形复选框，未勾选时不限制类型，单独或同时勾选时按任一匹配，并同时作用于浏览与搜索结果。点击有效条件后筛选立即生效，面板保持打开；“应用筛选”按钮仍会提交当前条件并关闭面板。自定义日期在起止日期完整且顺序有效后立即生效，无效日期由“应用筛选”继续提供行内校验。后续来源渠道等维度沿用同一分组结构：分组标题和纵向选项列表。分组之间只用垂直留白建立层级，不绘制穿过标题的横线。未落地的筛选能力不提前显示为假控件。

分组标题必须明显属于下面的选项。所有分组复用同一标题下间距、选项容器和可点击行，面板标题、筛选分组和底部操作区形成清楚的三级结构，不用说明性大段文案填充空间。时间范围等互斥条件使用圆形单选框；内容类型等可组合条件使用方形复选框。

筛选面板默认宽度约 290px，并以 `surface-subtle` 作为连续工具表面。标题栏高度约 60px，内容区水平内边距 20px；单个条件的点击区约 22px，相邻点击区之间保留 8px 空白，文字行高约 16px，使整体行距继续收紧但选项边界不粘连。选项悬停不改变背景深浅，避免在连续列表里制造闪烁感。

筛选触发器使用 15px 漏斗图标；启用筛选后由线框切换为实心，工具栏不再展示条件数量、条件摘要或可清除标签，具体条件仍在面板内查看和重置。记忆墙标题滚动至搜索浮条下方时，触发器以短动画收缩为仅图标入口并固定在内容区右上角；浮动状态使用 70% 页面背景色遮罩和 4px 背景模糊，不保留整条标题栏遮罩。

单选按钮使用 16px 圆形：未选中时为中性描边，选中时为完整蓝色圆面与 6px 白色中心点。多选按钮使用 16px 方形与白色勾选标记，沿用相同的行高、文字间距和焦点状态。底部操作区用一像素分割线固定分区，“应用筛选”与“重置”两个按钮等宽、保持 36px 高度并使用 6px 圆角。该密度参考桌面属性面板：直观、可扫读，不做表单卡片化装饰。

自定义日期当前复用浏览器原生 `date` 控件，产品接受 Windows/Chromium 提供的日历弹层几何、语言和键盘行为；应用负责字段标签、错误提示与日期范围校验。若未来需要让弹层语言独立于操作系统或统一跨平台几何，应迁移到一个共享的 authored 日期组件，而不是在筛选面板内局部仿制。

## Elevation & Depth

Glimpse 依靠边框和轻微色差建立大部分层级。阴影只负责把真正的浮层从背板上抬起，不负责制造“高级感”。

- 记忆卡片静止时保持平稳，悬停或选中时才略微加强边框与阴影；侧栏打开后的选中对应关系只由卡片轮廓表达，不在内容上叠加勾选图标。
- 软件头保留整宽标题栏结构，直接使用一层柔和的下投影，不增加圆角表面或额外容器。
- 首页搜索工具栏可以使用低强度常驻阴影，因为它是独立的高频功能表面。
- 弹窗和遮罩使用 `--shadow-modal`，与普通卡片明确区分。
- backdrop blur 不是视觉目标，也不能代替边框；只有存在真实半透明叠层时才有意义。

接近全宽的横向表面不能直接套用卡片的长距离阴影。搜索工具栏使用专用短距阴影，并在自身与下一模块的间距内完成衰减；阴影不得在相邻标题区域形成连续横向色带。

任何悬浮效果都不应改变组件尺寸或推动周围内容。

## Shapes

Glimpse 使用紧凑的圆角矩形：小型控件 6px，普通按钮和卡片 8px，大型表面 10–12px。完整胶囊只用于很小的数量标签或圆形控制。

### 先看线条，再决定是否同心

DOM 嵌套不等于视觉嵌套。只有内外两层可见线条靠得很近，并且会被看成同一个复合控件时，才计算同心圆角：

```text
内层圆角 = 外层圆角 − 内外线条的视觉距离
```

搜索模式选择是标准例子。外框圆角为 6px，内缩为 3px，按钮圆角因此为 3px。外框 padding、相邻按钮 gap 都引用同一个 3px 变量，缝隙始终一致。

搜索工具栏浮层则不是这种情况。它有 12px 的宽松内边距，里面放着多个独立控件，所以外层保持 12px，内部一级控件统一为 6px。不要机械计算出 0px 的内层圆角，也不要为了保住内层圆角而夸大外层。

同一层级的相邻组件必须使用同一套圆角。真正联动的嵌套尺寸通过组件变量表达，不在模板里散落互不相关的字面值。

## Components

### 基础状态

所有可交互控件都需要默认、悬停、按下、键盘聚焦、禁用和忙碌状态。焦点必须清晰可见；禁用控件保留原有尺寸，但不响应操作。加载时替换内容而不是撑大按钮。

操作使用原生 `button`，导航使用 `a`。图标按钮必须有本地化的可访问名称。不要依赖浏览器原生 `alert`、`confirm` 或 `prompt` 构成产品体验。

### 搜索

搜索框非空时显示应用自己的清除按钮。清除立即恢复完整结果，并把焦点还给输入框。远程搜索默认防抖 300ms，忽略或取消过期请求；中文输入法组合期间不提前提交。

搜索模式是一个紧密复合控件。它的外层内缩、相邻按钮间距和内层圆角共享组件变量，不能分别调整。

### 按钮与动作

普通主要操作使用深蓝色，截图使用砖橙色。中性描边按钮负责重置、取消和次要动作，危险操作保持独立。搜索工具栏中的按钮属于紧凑变体，使用 36px 高度和 6px 圆角；常规页面按钮仍使用 40px 高度和 8px 圆角。

### 筛选

筛选条件以业务分组扩展，不为每个新维度重做面板。选中状态同时使用背景、边框或文字变化，不能只依赖颜色深浅。“应用”和“重置”固定在底部操作区，加载时位置不变。

### 图标、动效与滚动

Heroicons Outline 是唯一图标族。控件图标通常为 18–20px，空状态图标为 24–28px；不使用 emoji 或临时文字图形替代。

状态变化使用 140–180ms 的短过渡，不让卡片大幅抬升。全局样式必须尊重 `prefers-reduced-motion`。滚动条由应用全局样式统一管理，新滚动区域不需要额外 opt-in 类名。

单张截图完成或集群截图提交后立即显示真实记忆卡片；OCR 与 AI 尚未返回时，卡片、侧边详情和独立详情页复用同一个分析等待态。等待时间不可精确估算，因此使用不确定进度条和明确文案，不显示虚假百分比。同一分析任务在不同界面出现的进度条共享墙钟相位，稍后打开的详情直接加入当前动画位置，不从头播放。减少动态效果时停止进度条位移，但保留状态文字和静态进度轨道。分析完成后在原卡片原位替换内容，不插入第二张卡片，也不移动当前选择。

### 实现边界

组件消费语义 token，不复制颜色或系统圆角。使用稳定、表达业务含义的类名，例如 `.search-toolbar__source-switcher`；Vue 生成的 `data-v-*` 哈希不是可依赖的选择器。

响应式变化只重排布局，不改变同一个控件的名称、状态和视觉身份。出现新的同类场景时，先扩展共享结构，再考虑局部例外。

## Do's and Don'ts

### Do

- 先判断内容与工具的主次，再决定尺寸和留白。
- 让标题靠近它说明的控件，让不同功能组之间有清楚的呼吸。
- 同一层级统一高度、圆角、间距和状态反馈。
- 可见描边贴近时按实际距离计算同心圆角；相距较远时使用组件标准圆角。
- 让复合控件的 padding、gap 和相关圆角共享变量。
- 让分割线与内容对齐，而不是连接窗口边缘。
- 新增筛选维度时复用现有分组结构。
- 同时检查浅色、深色、窄屏、键盘焦点和禁用状态。

### Don't

- 不用大面积空白、巨大圆角或装饰性渐变伪造层次。
- 不把截图橙色挪给普通主要操作。
- 不让阴影替代边框、选中状态或信息结构。
- 不因为 DOM 有父子关系就强制同心圆角。
- 不在同一层级混用相近但不同的圆角和间距。
- 不让普通分割线顶到软件两侧。
- 不依赖 `data-v-*`、一次性选择器或散落的魔法数字。
- 不为单个页面发明一套平行组件。
