# 第三方素材声明（Third-Party Notices）

本仓库在开发过程中参考、改编了以下第三方素材。各素材的许可证条款适用于
其衍生部分；本文件用于保留其要求的版权与许可声明。

## vue-bits（https://vue-bits.dev）

- 来源仓库：https://github.com/DavidHDev/vue-bits
- 许可证：MIT + Commons Clause License Condition v1.0
- 版权所有：Copyright (c) 2025 David Haz
- 许可证要点：允许在任何应用、网站或产品中使用、复制、修改、合并、发布与
  分发（含商业目的）；不得单独出售、再许可或再分发组件本身（单独、打包、
  模板或移植形式）。
- 使用方式：本仓库按"本地化改造"方式采用其交互设计——仅参考组件行为与
  结构，视觉与实现全部改写为项目自有设计系统与代码；不直接分发其源码。
- 已采用组件：micro/swipe-toast（通知浮层的拖拽关闭、悬停暂停与堆叠交互
  参考），落地于 `glimpse-frontend/src/components/toast/`；micro/warm-tooltip
  （悬浮说明的 warm 连续体验：共享气泡、位置/宽高弹簧滑动、速度倾侧与
  模糊出场机制参考），落地于 `glimpse-frontend/src/directives/hint-tooltip.ts`；
  text-animations/stroke-text（新手引导欢迎卡的逐字描边书写效果参考，
  动画本地改写为纯 CSS），落地于 `glimpse-frontend/src/components/StrokeText.vue`；
  text-animations/fold-text（新手引导完成卡的逐字折叠展开效果参考，
  动画本地改写为纯 CSS），落地于 `glimpse-frontend/src/components/FoldText.vue`。

## motion-v（https://motion.dev）

- npm 包：motion-v（MIT License）
- 用途：动画地基（MotionValue 与弹簧动画），通知浮层的回弹收尾使用。
