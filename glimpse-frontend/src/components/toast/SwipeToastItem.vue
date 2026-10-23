<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import {
  CheckIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline'
import { animate, motionValue, useReducedMotion } from 'motion-v'
import type { Notification } from '@/stores/notification'
import { useNotificationStore } from '@/stores/notification'
import { t } from '@/utils/i18n'
import {
  DRAG_DEAD_ZONE_PX,
  pushSample,
  rubberband,
  shouldDismiss,
  velocityOf,
  type SwipeSample,
} from '@/utils/swipe-gesture'

const props = defineProps<{
  notification: Notification
}>()

const notificationStore = useNotificationStore()
const cardElement = ref<HTMLElement | null>(null)

const TYPE_TOKENS: Record<Notification['type'], string> = {
  success: 'var(--color-success)',
  error: 'var(--color-danger)',
  warning: 'var(--color-warning)',
  info: 'var(--color-primary)',
}
const TYPE_ICONS: Record<Notification['type'], typeof CheckIcon> = {
  success: CheckIcon,
  error: XMarkIcon,
  warning: ExclamationTriangleIcon,
  info: InformationCircleIcon,
}
const iconToken = (type: Notification['type']) => TYPE_TOKENS[type]
const iconOf = (type: Notification['type']) => TYPE_ICONS[type]

// —— 进出场节奏（与 demo 同构，数值在下方 CSS：进场 400ms 底部升起、
// 退场 0.7×/0.5× 压缩）；曲线 easeOutQuint 近似 cubic-bezier(0.23,1,0.32,1)。——
const EASE_OUT: [number, number, number, number] = [0.23, 1, 0.32, 1]
const EXIT_FINISH_MS = 340
// @starting-style 支持检测：不支持的环境（老内核/jsdom）渲染后翻 mounted
// 标志，让首帧从隐藏态过渡到就位态——与 starting-style 走同一条过渡。
const HAS_STARTING_STYLE = typeof window !== 'undefined' && 'CSSStartingStyleRule' in window

type Phase = 'open' | 'closing'
const phase = ref<Phase>('open')
const instant = ref(false)
const mounted = ref(HAS_STARTING_STYLE)

// 卡片的 transform/opacity 由 motionValue 手写 style：拖拽和弹簧动画
// 不经过 Vue 渲染，与 lift wrapper 的 CSS 过渡分属两层、互不干扰。
const y = motionValue(0)
const fade = motionValue(1)
const reduce = useReducedMotion()

const offs: Array<() => void> = []
let finishTimer: ReturnType<typeof setTimeout> | undefined
let frame = 0

// —— 倒计时：悬停（仅鼠标）/聚焦/拖拽/文档失焦时暂停，剩时续跑 ——
let remaining = props.notification.duration
let startedAt = 0
let timer: ReturnType<typeof setTimeout> | null = null
const flags = { hover: false, interacting: false, focus: false, hidden: false }
let leaving = false
let pendingClose: 'timeout' | null = null

const startTimer = () => {
  if (timer || remaining <= 0 || phase.value !== 'open' || leaving) return
  startedAt = Date.now()
  timer = setTimeout(onExpire, remaining)
}
const stopTimer = () => {
  if (!timer) return
  clearTimeout(timer)
  timer = null
  remaining = Math.max(0, remaining - (Date.now() - startedAt))
}
const syncPause = () => {
  if (flags.hover || flags.interacting || flags.focus || flags.hidden) stopTimer()
  else startTimer()
}
function onExpire() {
  timer = null
  remaining = 0
  if (dragState) {
    // 拖拽中到时不打断手势，排队到松手后再收尾
    pendingClose = 'timeout'
    return
  }
  close()
}

// —— 相位机：closing 走 CSS 退场（lift wrapper 过渡），swipe 走弹簧 ——
const finish = () => {
  notificationStore.dismiss(props.notification.id)
}
const close = () => {
  if (phase.value !== 'open' || leaving) return
  if (dragState) {
    pendingClose = 'timeout'
    return
  }
  stopTimer()
  phase.value = 'closing'
  clearTimeout(finishTimer)
  finishTimer = setTimeout(finish, EXIT_FINISH_MS)
}
// 关闭途中再按下：把卡片拉回来（demo 的 rescue），重置后倒计时从头计。
const rescue = () => {
  clearTimeout(finishTimer)
  finishTimer = undefined
  y.set(0)
  fade.set(1)
  phase.value = 'open'
  leaving = false
  remaining = props.notification.duration
  syncPause()
}

// —— 拖拽手势：pointer capture 绑在卡片上（demo 同构），纵向 only ——
interface Drag {
  id: number
  startY: number
  grab: number | null
  moved: boolean
  hist: SwipeSample[]
}
let dragState: Drag | null = null

const swipeOut = (dy: number, velocity: number) => {
  stopTimer()
  leaving = true
  pendingClose = null
  const card = cardElement.value
  if (!reduce.value && card) {
    // 甩出：带着释放速度的弹簧滑出视野（目标 = 当前位移 + 卡片高）
    void animate(y, dy + card.offsetHeight, {
      type: 'spring',
      duration: 0.3,
      bounce: 0,
      velocity: velocity * 1000,
    })
  }
  void animate(fade, 0, { duration: 0.2, ease: EASE_OUT }).then(finish)
}

const handlePointerDown = (event: PointerEvent) => {
  if (event.button !== 0) return
  if (event.target instanceof Element && event.target.closest('button')) return
  if (phase.value === 'closing') {
    rescue()
  } else if (dragState || leaving) {
    return
  }
  try {
    cardElement.value?.setPointerCapture(event.pointerId)
  } catch {
    // capture 不可用（jsdom 等），事件仍会派发给卡片
  }
  y.stop()
  dragState = {
    id: event.pointerId,
    startY: event.clientY,
    grab: null,
    moved: false,
    hist: [[performance.now(), y.get()]],
  }
  flags.interacting = true
  syncPause()
}

const handlePointerMove = (event: PointerEvent) => {
  const drag = dragState
  if (!drag || drag.id !== event.pointerId) return
  if (drag.grab === null) {
    if (Math.abs(event.clientY - drag.startY) < DRAG_DEAD_ZONE_PX) return
    drag.grab = event.clientY - y.get()
  }
  const raw = event.clientY - drag.grab
  drag.moved = true
  const next = rubberband(raw)
  y.set(next)
  pushSample(drag.hist, performance.now(), next)
}

const handlePointerUp = (event: PointerEvent) => {
  const drag = dragState
  if (!drag || drag.id !== event.pointerId) return
  dragState = null
  try {
    cardElement.value?.releasePointerCapture(event.pointerId)
  } catch {
    // 已释放
  }
  flags.interacting = false
  const dy = y.get()
  const velocity = velocityOf(drag.hist, performance.now())
  if (shouldDismiss(dy, velocity)) {
    swipeOut(dy, velocity)
    return
  }
  if (drag.moved) {
    // 未达阈值：带速度的弹簧回弹（含过冲 bounce 0.2；减少动态时 200ms ease）
    void animate(
      y,
      0,
      reduce.value
        ? { duration: 0.2, ease: EASE_OUT }
        : { type: 'spring', duration: 0.5, bounce: 0.2, velocity: velocity * 1000 },
    )
  }
  const queued = pendingClose
  pendingClose = null
  if (queued) close()
  else syncPause()
}

const handlePointerEnter = (event: PointerEvent) => {
  // 触屏点按不应暂停倒计时，只有真实悬停才暂停
  if (event.pointerType === 'mouse') {
    flags.hover = true
    syncPause()
  }
}
const handlePointerLeave = (event: PointerEvent) => {
  if (event.pointerType === 'mouse') {
    flags.hover = false
    syncPause()
  }
}
const handleFocusIn = () => {
  flags.focus = true
  syncPause()
}
const handleFocusOut = (event: FocusEvent) => {
  if (!(event.currentTarget instanceof Node)
    || !event.currentTarget.contains(event.relatedTarget as Node | null)) {
    flags.focus = false
    syncPause()
  }
}
const handleVisibilityChange = () => {
  flags.hidden = document.hidden
  syncPause()
}

onMounted(() => {
  if (props.notification.duration > 0) startTimer()
  if (!HAS_STARTING_STYLE) {
    // rAF 翻 mounted：让首帧以隐藏态渲染，下一帧过渡到就位态
    if (window.requestAnimationFrame) frame = window.requestAnimationFrame(() => (mounted.value = true))
    else mounted.value = true
  }
  offs.push(
    y.on('change', (value: number) => {
      if (cardElement.value) cardElement.value.style.transform = `translateY(${value}px)`
    }),
    fade.on('change', (value: number) => {
      if (cardElement.value) cardElement.value.style.opacity = String(value)
    }),
  )
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onBeforeUnmount(() => {
  if (frame) window.cancelAnimationFrame?.(frame)
  clearTimeout(finishTimer)
  if (timer) clearTimeout(timer)
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  offs.forEach((off) => off())
  y.stop()
  fade.stop()
})
</script>

<template>
  <div
    class="swipe-toast min-w-[280px] max-w-[380px]"
    :class="{
      'swipe-toast--unmounted': !mounted,
      'swipe-toast--closing': phase === 'closing',
      'swipe-toast--instant': instant,
    }"
  >
    <div class="swipe-toast__lift">
      <div
        ref="cardElement"
        class="swipe-toast__card glass flex items-center gap-2.5 rounded-md px-3.5 py-2.5 outline-none select-none"
        role="status"
        aria-live="polite"
        tabindex="0"
        @pointerdown="handlePointerDown"
        @pointermove="handlePointerMove"
        @pointerup="handlePointerUp"
        @pointercancel="handlePointerUp"
        @pointerenter="handlePointerEnter"
        @pointerleave="handlePointerLeave"
        @focusin="handleFocusIn"
        @focusout="handleFocusOut"
      >
        <div
          class="flex h-6 w-6 flex-none items-center justify-center rounded-full"
          :style="{ background: iconToken(notification.type) }"
        >
          <component :is="iconOf(notification.type)" class="h-4 w-4 text-white" aria-hidden="true" />
        </div>

        <p class="flex-1 text-sm text-[var(--shell-ink)]">{{ notification.message }}</p>

        <button
          type="button"
          class="inline-flex flex-none items-center justify-center rounded p-1 text-[var(--shell-muted)] transition-colors duration-[160ms] ease-[ease] hover:bg-[var(--shell-control-hover)]"
          :aria-label="t('action.close')"
          @click.stop="close()"
          @pointerdown.stop
        >
          <XMarkIcon class="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 进出场（demo 同构）：lift wrapper 承担过渡，卡片 transform 归拖拽/弹簧。
 * 进场 = 底部升起 400ms；退场切换 closing 态，时长按 0.7×/0.5× 压缩。 */
.swipe-toast__lift {
  transform: translateY(0);
  opacity: 1;
  transition:
    transform 400ms cubic-bezier(0.23, 1, 0.32, 1),
    opacity 240ms ease;
}

@starting-style {
  .swipe-toast__lift {
    transform: translateY(100%);
    opacity: 0;
  }
}

/* 不支持 @starting-style 的环境：首帧隐藏，rAF 翻 mounted 走同一条过渡 */
.swipe-toast--unmounted .swipe-toast__lift {
  transform: translateY(100%);
  opacity: 0;
}

.swipe-toast--closing .swipe-toast__lift {
  transform: translateY(100%);
  opacity: 0;
  transition:
    transform 280ms cubic-bezier(0.23, 1, 0.32, 1),
    opacity 200ms ease;
}

.swipe-toast--instant .swipe-toast__lift {
  transition-duration: 0s;
}

.swipe-toast__card {
  touch-action: none;
  -webkit-tap-highlight-color: transparent;
}

@media (prefers-reduced-motion: reduce) {
  .swipe-toast__lift {
    transform: none;
    transition: opacity 200ms ease;
  }
}
</style>
