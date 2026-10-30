# 原样拷贝区（upstream）

本目录存放参考过的第三方组件的**原样副本**：字节级不动一个字符
（`.gitattributes` 对本目录关闭行尾规范化）。用途：

- 上游更新时把新版本原位覆盖进来，`git diff` 直接看出上游改了什么；
- 本地化改造改坏时，对照原件找回。

## 规约

- 原样文件**禁止任何修改**——不格式化、不改行尾、不写头注释；来源信息只
  记录在本 README 与本地化文件的头部注释里。
- 新组件先原样入库（提交说明「原样入库」），再在 `glimpse-frontend/src/`
  做本地化改造（提交说明「本地化适配」，适配文件头部写来源注释指向本区）。
- 目录内保留上游完整相对路径（如 `vue-bits/src/content/...`），便于整目录
  与上游 checkout 做对比。
- 本目录在 `glimpse-frontend/` 之外，天然不进构建、类型检查与依赖检查；
  任何代码不得 import 本目录内文件。

## 来源清单

### vue-bits（https://github.com/DavidHDev/vue-bits）

- 许可：MIT + Commons Clause License Condition v1.0，
  Copyright (c) 2025 David Haz；条款要点见仓库根 `THIRD_PARTY_NOTICES.md`。
- 上游版本：main @ `3766ebeeed37ec35bce29f001b6d101c7b17da35`（2026-10-28 取回）。
- 已入库组件与本地化落点：
  - `src/content/Micro/WarmTooltip/WarmTooltip.vue` →
    `glimpse-frontend/src/directives/hint-tooltip.ts`（悬浮说明 warm 机制）。
  - `src/content/Micro/SwipeToast/SwipeToast.vue` →
    `glimpse-frontend/src/components/toast/`（通知浮层交互参考，弹簧参数
    为本地自定，校准手感时对照此原件）。
  - `src/content/TextAnimations/StrokeText/StrokeText.vue` →
    `glimpse-frontend/src/components/StrokeText.vue`（新手引导欢迎卡的
    逐字描边书写效果参考；动画实现本地改写为纯 CSS，无 gsap 依赖）。
  - `src/content/TextAnimations/FoldText/FoldText.vue` →
    `glimpse-frontend/src/components/FoldText.vue`（新手引导完成卡的
    逐字折叠展开效果参考；动画实现本地改写为纯 CSS，无 gsap 依赖）。
