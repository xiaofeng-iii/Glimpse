<!--
  逐字折叠展开文字：效果与分段结构参考 vue-bits FoldText
  （MIT + Commons Clause，条款见仓库根 THIRD_PARTY_NOTICES.md），
  原样副本在 upstream/vue-bits/src/content/TextAnimations/FoldText/。
  本地化差异：动画由 gsap 改写为纯 CSS（关键帧只定义 from 折叠态、
  基态即终态，reduced-motion 或动画不支持时直接呈现完成态）；
  原版的折痕受光（::after 渐层 + multiply）两度被否：multiply 在
  WebView2 下常驻不归零、渐变字色版被用户裁定去掉泛光——最终只保留
  纯色折叠展开。样式走项目 token，只保留顶边铰链、挂载即播、
  逐字拆分一种用法。
-->
<script setup lang="ts">
import { computed } from 'vue'
import { DISPLAY_FONT_STACK } from '@/utils/display-font'

const props = withDefaults(defineProps<{
  text: string
  fontSize?: number
}>(), {
  fontSize: 72,
})

const DURATION_MS = 650
const STAGGER_MS = 45

const characters = computed(() => Array.from(props.text))
</script>

<template>
  <span
    class="fold-text block w-full text-center"
    :style="{
      fontSize: `${props.fontSize}px`,
      fontWeight: 700,
      fontFamily: DISPLAY_FONT_STACK,
      '--fold-duration': `${DURATION_MS}ms`,
      '--fold-stagger': `${STAGGER_MS}ms`,
    }"
    role="img"
    :aria-label="text"
  >
    <span class="fold-text__stage" aria-hidden="true">
      <span
        v-for="(char, index) in characters"
        :key="index"
        class="fold-text__char"
        :style="{ '--fold-i': index }"
      >{{ char === ' ' ? '\u00A0' : char }}</span>
    </span>
  </span>
</template>

<style scoped>
.fold-text {
  line-height: 1.05;
  color: var(--color-primary);
  user-select: none;
}

/* 基态即终态（字面已展平、纯色）。起始角取 -84° 而非越过 90° 的 -92°：
   从背面态动画穿越 90° 翻回正面时 WebView2 的可见性切换不可靠，元素会
   全程隐身只剩淡入；不越界则全程正面，翻转逐帧可见 */
.fold-text__char {
  display: inline-block;
  transform: perspective(700px) rotateX(0deg);
  transform-origin: 50% 0%;
  animation: fold-text-unfold var(--fold-duration, 650ms) cubic-bezier(0.215, 0.61, 0.355, 1) both;
  animation-delay: calc(var(--fold-i, 0) * var(--fold-stagger, 45ms));
}

@keyframes fold-text-unfold {
  from {
    opacity: 0;
    transform: perspective(700px) rotateX(-84deg);
  }
  to {
    opacity: 1;
    transform: perspective(700px) rotateX(0deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .fold-text__char {
    animation: none;
  }
}
</style>
