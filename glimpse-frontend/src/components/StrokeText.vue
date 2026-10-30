<!--
  逐字描边书写文字：效果与 SVG 双层结构参考 vue-bits StrokeText
  （MIT + Commons Clause，条款见仓库根 THIRD_PARTY_NOTICES.md），
  原样副本在 upstream/vue-bits/src/content/TextAnimations/StrokeText/。
  本地化差异：动画由 gsap 改写为纯 CSS（关键帧只定义 from 态、
  基态即终态，reduced-motion 或动画不支持时直接呈现完成态），
  样式走项目 token，只保留挂载即播的一种用法。
-->
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  text: string
  fontSize?: number
}>(), {
  fontSize: 30,
})

const DRAW_MS = 900
const STAGGER_MS = 70
const FILL_EXTRA_MS = 180

const strokeTextRef = ref<SVGTextElement | null>(null)
const box = ref<{ x: number; y: number; width: number; height: number } | null>(null)
let disposed = false

const uid = Math.random().toString(36).slice(2, 10)
const wipeId = `stroke-text-wipe-${uid}`

// 成字加粗走真实粗体字面：全局栈的 'YaHei UI Adjusted' 度量覆盖面只有
// 400 档（700 会退化为合成加粗），此处绕开它让中文落到有真实 Bold 的
// 'Microsoft YaHei'。两层同栈同字重 → 描边沿成字外缘画、与填充逐字重合。
const BOLD_FONT_STACK = "'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"

const characters = computed(() => Array.from(props.text))
// 描边总时长 = 首字画线 + 逐字错峰；填充在描边收尾后再擦入
const fillDelayMs = computed(() =>
  DRAW_MS + STAGGER_MS * Math.max(0, characters.value.length - 1) + FILL_EXTRA_MS)
const dash = computed(() => Math.max(props.fontSize * 7, 200))
const viewBox = computed(() =>
  box.value
    ? `${box.value.x} ${box.value.y} ${box.value.width} ${box.value.height}`
    : `0 ${-props.fontSize} 600 ${props.fontSize * 1.3}`)

const measure = () => {
  if (disposed) return
  const node = strokeTextRef.value
  if (!node) return
  let bbox: DOMRect | undefined
  try {
    bbox = node.getBBox()
  } catch {
    return
  }
  if (!bbox || !bbox.width) return
  const pad = props.fontSize * 0.12
  box.value = {
    x: bbox.x - pad,
    y: bbox.y - pad,
    width: bbox.width + pad * 2,
    height: bbox.height + pad * 2,
  }
}

onMounted(() => {
  measure()
  // 中文字体异步就位后重测一次，避免 viewBox 按回退字体裁剪文字
  document.fonts?.ready?.then(measure).catch(() => {})
})

onUnmounted(() => {
  disposed = true
})

watch(() => [props.text, props.fontSize], () => measure(), { flush: 'post' })
</script>

<template>
  <span
    class="stroke-text block w-full leading-0"
    :style="{
      '--st-dash': dash,
      '--st-draw-ms': `${DRAW_MS}ms`,
      '--st-stagger-ms': `${STAGGER_MS}ms`,
      '--st-fill-delay-ms': `${fillDelayMs}ms`,
    }"
    role="img"
    :aria-label="text"
  >
    <svg
      class="block w-full"
      :style="{ height: `${Math.round(props.fontSize * 1.3)}px` }"
      :viewBox="viewBox"
      preserveAspectRatio="xMidYMid meet"
      aria-hidden="true"
    >
      <defs v-if="box">
        <clipPath :id="wipeId" clipPathUnits="userSpaceOnUse">
          <rect
            class="stroke-text__wipe"
            :x="box.x"
            :y="box.y"
            :width="box.width"
            :height="box.height"
          />
        </clipPath>
      </defs>

      <text
        ref="strokeTextRef"
        class="stroke-text__layer select-none"
        x="0"
        y="0"
        fill="none"
        :stroke="'var(--color-primary)'"
        stroke-width="1.4"
        stroke-linejoin="round"
        stroke-linecap="round"
        :style="{
          fontSize: `${props.fontSize}px`,
          fontWeight: 700,
          fontFamily: BOLD_FONT_STACK,
        }"
      >
        <tspan
          v-for="(char, index) in characters"
          :key="`s-${index}`"
          class="stroke-text__stroke-char"
          :style="{ '--st-i': index }"
        >{{ char }}</tspan>
      </text>

      <text
        class="stroke-text__layer stroke-text__fill select-none"
        x="0"
        y="0"
        :fill="'var(--color-primary)'"
        stroke="none"
        :clip-path="box ? `url(#${wipeId})` : undefined"
        :style="{
          fontSize: `${props.fontSize}px`,
          fontWeight: 700,
          fontFamily: BOLD_FONT_STACK,
        }"
      >
        <tspan v-for="(char, index) in characters" :key="`f-${index}`">{{ char }}</tspan>
      </text>
    </svg>
  </span>
</template>

<style scoped>
.stroke-text__layer {
  white-space: pre;
}

.stroke-text__stroke-char {
  stroke-dasharray: var(--st-dash, 1400);
  animation: stroke-text-draw var(--st-draw-ms, 900ms) cubic-bezier(0.33, 1, 0.68, 1) both;
  animation-delay: calc(var(--st-i, 0) * var(--st-stagger-ms, 70ms));
}

/* 基态即终态（描边已画满、擦入矩形已展开），关键帧只回放 from 态：
   动画被禁用或不支持时直接呈现完成结果 */
@keyframes stroke-text-draw {
  from {
    stroke-dashoffset: var(--st-dash, 1400);
  }
}

.stroke-text__wipe {
  animation: stroke-text-wipe 550ms cubic-bezier(0.33, 1, 0.68, 1) both;
  animation-delay: var(--st-fill-delay-ms, 1150ms);
}

@keyframes stroke-text-wipe {
  from {
    width: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .stroke-text__stroke-char,
  .stroke-text__wipe {
    animation: none;
  }
}
</style>
