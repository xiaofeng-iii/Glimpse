<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSettingsStore } from '@/stores/settings'
import { t } from '@/utils/i18n'
import { injectTourSamples, removeTourSamples } from '@/utils/tour-samples'

type TourRoute = { name: 'home' } | { name: 'settings'; query: { section: string } }

type TourStep = {
  titleKey: Parameters<typeof t>[0]
  descriptionKey?: Parameters<typeof t>[0]
  gateHintKey?: Parameters<typeof t>[0]
  /** data-tour 锚点；null = 居中说明卡（欢迎/完成/锚点缺失降级） */
  target: string | null
  route?: TourRoute
  /** 等待用户真实完成操作后自动前进 */
  gate?: 'add-memory' | 'enter-settings'
}

// 引导脚本：欢迎 → 截图 → 添加记忆(实测) → 搜索(自由尝试) → 搜索来源 → 设置入口 → AI 配置 → 完成。
const tourSteps: readonly TourStep[] = [
  {
    titleKey: 'onboarding.tour.welcomeTitle',
    descriptionKey: 'onboarding.tour.welcomeDescription',
    target: null,
  },
  {
    titleKey: 'onboarding.tour.captureTitle',
    descriptionKey: 'onboarding.tour.captureDescription',
    target: 'capture-button',
    route: { name: 'home' },
  },
  {
    titleKey: 'onboarding.tour.addMemoryTitle',
    descriptionKey: 'onboarding.tour.addMemoryDescription',
    gateHintKey: 'onboarding.tour.addMemoryGate',
    target: 'add-memory-button',
    route: { name: 'home' },
    gate: 'add-memory',
  },
  {
    titleKey: 'onboarding.tour.searchTitle',
    descriptionKey: 'onboarding.tour.searchDescription',
    target: 'search-input',
    route: { name: 'home' },
  },
  {
    titleKey: 'onboarding.tour.searchSourceTitle',
    descriptionKey: 'onboarding.tour.searchSourceDescription',
    target: 'search-source',
    route: { name: 'home' },
  },
  {
    titleKey: 'onboarding.tour.settingsEntryTitle',
    descriptionKey: 'onboarding.tour.settingsEntryDescription',
    gateHintKey: 'onboarding.tour.settingsEntryGate',
    target: 'settings-entry',
    gate: 'enter-settings',
  },
  {
    titleKey: 'onboarding.tour.aiTitle',
    descriptionKey: 'onboarding.tour.aiDescription',
    target: 'settings-ai-fields',
    route: { name: 'settings', query: { section: 'ai' } },
  },
  {
    titleKey: 'onboarding.tour.finishTitle',
    target: null,
  },
]

const HOLE_PADDING_PX = 6
const CARD_GAP_PX = 12
const CARD_VIEWPORT_MARGIN_PX = 12
const CARD_WIDTH_FALLBACK_PX = 300
const CARD_HEIGHT_FALLBACK_PX = 168
const TARGET_POLL_INTERVAL_MS = 100
const TARGET_POLL_TIMEOUT_MS = 5000
// 门控满足后延迟一小步再前进，让用户先看到自己操作的结果
const GATE_ADVANCE_DELAY_MS = 600

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (event: 'complete'): void
}>()

const route = useRoute()
const router = useRouter()
const settingsStore = useSettingsStore()

const stepIndex = ref(0)
const targetResolved = ref(false)
const centeredFallback = ref(false)
const positioned = ref(false)
const holeRect = ref<{ left: number; top: number; width: number; height: number } | null>(null)
const cardPosition = ref<{ left: string; top: string } | null>(null)
const cardElement = ref<HTMLElement | null>(null)
const nextButton = ref<HTMLButtonElement | null>(null)

// 步骤激活令牌：异步找锚点期间步已切换时，旧激活的结果全部作废
let activationToken = 0
let currentTarget: HTMLElement | null = null
let gateTimer: number | null = null
let gateObserver: MutationObserver | null = null
let gateDialogSeen = false
let updateRaf = 0
let originElement: HTMLElement | null = null
let finishing = false

const step = computed(() => tourSteps[stepIndex.value] ?? tourSteps[0])
const isWelcome = computed(() => stepIndex.value === 0)
const isFinish = computed(() => stepIndex.value === tourSteps.length - 1)
const isAnchoredMode = computed(() => Boolean(step.value.target) && !centeredFallback.value)
const cardVisible = computed(() => !isAnchoredMode.value || positioned.value)
const showCounter = computed(() => !isWelcome.value && !isFinish.value)
// 欢迎卡不计步：真正编号的引导步从截图步的 1 开始
const counterLabel = computed(() => `${stepIndex.value} / ${tourSteps.length - 1}`)

const holeStyle = computed(() => {
  const rect = holeRect.value
  if (!rect) return null
  return {
    left: `${rect.left}px`,
    top: `${rect.top}px`,
    width: `${rect.width}px`,
    height: `${rect.height}px`,
  }
})

// 四向拦截片盖住挖孔以外的整个视口：锚定步只有高亮目标可点击
const blockerStyles = computed(() => {
  const rect = holeRect.value
  if (!rect) return []
  return [
    { left: '0px', top: '0px', right: '0px', height: `${rect.top}px` },
    { left: '0px', top: `${rect.top + rect.height}px`, right: '0px', bottom: '0px' },
    { left: '0px', top: `${rect.top}px`, width: `${rect.left}px`, height: `${rect.height}px` },
    { left: `${rect.left + rect.width}px`, top: `${rect.top}px`, right: '0px', height: `${rect.height}px` },
  ]
})

const descriptionText = computed(() => {
  if (!step.value.descriptionKey) return ''
  if (step.value.titleKey === 'onboarding.tour.captureTitle') {
    return t(step.value.descriptionKey, { hotkey: captureHotkeyLabel.value })
  }
  return t(step.value.descriptionKey)
})

const gateHintText = computed(() => (
  step.value.gateHintKey ? t(step.value.gateHintKey) : ''
))

const hotkeyLabels: Record<string, string> = {
  ctrl: 'Ctrl',
  shift: 'Shift',
  alt: 'Alt',
  cmd: 'Win',
}

const formatHotkeyLabel = (hotkey?: string) => {
  if (!hotkey) return 'Ctrl + Shift + G'
  return hotkey
    .split('+')
    .map((part) => {
      const normalized = part.trim().replace(/^<|>$/g, '').toLowerCase()
      return hotkeyLabels[normalized]
        ?? (normalized.length === 1 ? normalized.toUpperCase() : normalized)
    })
    .join(' + ')
}

const captureHotkeyLabel = computed(() =>
  formatHotkeyLabel(settingsStore.settings?.hotkeys?.screenshot),
)

const primaryLabel = computed(() => t(
  isWelcome.value
    ? 'onboarding.tour.start'
    : isFinish.value
      ? 'onboarding.tour.done'
      : 'onboarding.tour.next',
))

const queryTarget = (name: string) =>
  document.querySelector<HTMLElement>(`[data-tour="${name}"]`)

const needsRouteSync = (target: TourRoute) => {
  if (route.name !== target.name) return true
  if ('query' in target) return route.query.section !== target.query.section
  return false
}

const waitForTarget = (name: string, token: number) =>
  new Promise<HTMLElement | null>((resolve) => {
    const startedAt = Date.now()
    const attempt = () => {
      if (token !== activationToken) return resolve(null)
      const element = queryTarget(name)
      if (element) return resolve(element)
      if (Date.now() - startedAt > TARGET_POLL_TIMEOUT_MS) return resolve(null)
      window.setTimeout(attempt, TARGET_POLL_INTERVAL_MS)
    }
    attempt()
  })

const cancelGate = () => {
  if (gateTimer !== null) {
    window.clearTimeout(gateTimer)
    gateTimer = null
  }
  gateObserver?.disconnect()
  gateObserver = null
  gateDialogSeen = false
}

const goNext = () => {
  if (stepIndex.value >= tourSteps.length - 1) {
    void finish()
    return
  }
  stepIndex.value += 1
  void activateStep()
}

const goPrev = () => {
  if (stepIndex.value <= 0) return
  stepIndex.value -= 1
  void activateStep()
}

// 引导持有导航权：结束时回首页；被设置页未保存守卫拦下时也不卡死，直接收尾
const finish = async () => {
  if (finishing) return
  finishing = true
  cancelGate()
  void removeTourSamples()
  if (route.name && route.name !== 'home') {
    try {
      await router.push({ name: 'home' })
    } catch {
      // 导航被守卫拒绝时引导照常结束
    }
  }
  emit('complete')
}

const handlePrimary = () => {
  if (isFinish.value) void finish()
  else goNext()
}

const scheduleUpdate = () => {
  if (updateRaf) return
  updateRaf = window.requestAnimationFrame(() => {
    updateRaf = 0
    updatePosition()
  })
}

const positionCard = (rect: DOMRect) => {
  const cardWidth = cardElement.value?.offsetWidth || CARD_WIDTH_FALLBACK_PX
  const cardHeight = cardElement.value?.offsetHeight || CARD_HEIGHT_FALLBACK_PX
  const viewportWidth = window.innerWidth
  const viewportHeight = window.innerHeight

  let top = rect.bottom + HOLE_PADDING_PX + CARD_GAP_PX
  if (top + cardHeight > viewportHeight - CARD_VIEWPORT_MARGIN_PX) {
    const above = rect.top - HOLE_PADDING_PX - CARD_GAP_PX - cardHeight
    top = above >= CARD_VIEWPORT_MARGIN_PX ? above : CARD_VIEWPORT_MARGIN_PX
  }
  const rawLeft = rect.left + rect.width / 2 - cardWidth / 2
  const left = Math.min(
    Math.max(rawLeft, CARD_VIEWPORT_MARGIN_PX),
    Math.max(CARD_VIEWPORT_MARGIN_PX, viewportWidth - cardWidth - CARD_VIEWPORT_MARGIN_PX),
  )

  holeRect.value = {
    left: rect.left - HOLE_PADDING_PX,
    top: rect.top - HOLE_PADDING_PX,
    width: rect.width + HOLE_PADDING_PX * 2,
    height: rect.height + HOLE_PADDING_PX * 2,
  }
  cardPosition.value = { left: `${left}px`, top: `${top}px` }
  positioned.value = true
}

const updatePosition = () => {
  if (!props.open || !isAnchoredMode.value) return
  const target = currentTarget?.isConnected
    ? currentTarget
    : queryTarget(step.value.target ?? '')
  if (!target) {
    centeredFallback.value = true
    positioned.value = false
    return
  }
  currentTarget = target
  positionCard(target.getBoundingClientRect())
}

const advanceFromGate = () => {
  if (gateTimer !== null) return
  gateTimer = window.setTimeout(() => {
    gateTimer = null
    goNext()
  }, GATE_ADVANCE_DELAY_MS)
}

const setupGate = () => {
  if (step.value.gate === 'enter-settings') {
    if (route.name === 'settings') advanceFromGate()
    return
  }
  if (step.value.gate === 'add-memory') {
    gateObserver = new MutationObserver(() => {
      if (queryTarget('add-memory-dialog')) {
        gateDialogSeen = true
      } else if (gateDialogSeen) {
        advanceFromGate()
      }
    })
    gateObserver.observe(document.body, { childList: true, subtree: true })
  }
}

const activateStep = async () => {
  const token = ++activationToken
  cancelGate()
  currentTarget = null
  targetResolved.value = false
  centeredFallback.value = false
  positioned.value = false
  holeRect.value = null
  cardPosition.value = null

  await nextTick()
  if (token !== activationToken) return
  nextButton.value?.focus({ preventScroll: true })

  if (!step.value.target) return

  if (step.value.route && needsRouteSync(step.value.route)) {
    try {
      await router.push(step.value.route)
    } catch {
      // 守卫拒绝时留在原地，找锚点失败会降级为居中卡
    }
    if (token !== activationToken) return
  }

  const target = await waitForTarget(step.value.target, token)
  if (token !== activationToken || !target || !target.isConnected) {
    if (token === activationToken) centeredFallback.value = true
    return
  }

  currentTarget = target
  targetResolved.value = true
  target.scrollIntoView({ block: 'center', inline: 'nearest' })
  await nextTick()
  if (token !== activationToken) return
  positionCard(target.getBoundingClientRect())
  setupGate()
}

// 引导期间用户手动离开当前步声明的路由时，回到该步应在的页面；
// 设置入口步例外：点击齿轮前往设置页正是该步等待的动作
watch(() => route.fullPath, () => {
  if (!props.open || finishing) return
  if (step.value.gate === 'enter-settings' && route.name === 'settings') {
    advanceFromGate()
    return
  }
  const target = step.value.route
  if (target && needsRouteSync(target)) void activateStep()
})

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

const focusableInCard = () => (
  cardElement.value
    ? Array.from(cardElement.value.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
    : []
)

const trapFocus = (event: KeyboardEvent) => {
  const focusable = focusableInCard()
  if (!focusable.length) {
    event.preventDefault()
    cardElement.value?.focus()
    return
  }
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  const active = document.activeElement
  if (event.shiftKey && (active === first || !cardElement.value?.contains(active))) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && active === last) {
    event.preventDefault()
    first.focus()
  }
}

const handleKeydown = (event: KeyboardEvent) => {
  if (!props.open) return
  if (event.key === 'Escape') {
    event.preventDefault()
    event.stopPropagation()
    void finish()
  } else if (event.key === 'Tab') {
    trapFocus(event)
  }
}

// 引导期间禁止页面滚动：拦截层上的滚动会被吞、挖孔里的滚动会把目标滚出高亮，
// 用户滚走后就被困住。全部拦下；浮在引导之上的层（如添加记忆对话框）不受影响。
const TOUR_Z_THRESHOLD = 550

const isAboveTourOverlay = (element: Element | null): boolean => {
  let node = element
  while (node && node !== document.body) {
    const zIndex = window.getComputedStyle(node).zIndex
    if (zIndex !== 'auto') {
      const value = Number.parseInt(zIndex, 10)
      if (Number.isFinite(value) && value > TOUR_Z_THRESHOLD) return true
    }
    node = node.parentElement
  }
  return false
}

const preventBlockedScroll = (event: Event) => {
  if (event.target instanceof Element && isAboveTourOverlay(event.target)) return
  event.preventDefault()
}

const teardownOverlay = () => {
  cancelGate()
  activationToken += 1
  if (updateRaf) {
    window.cancelAnimationFrame(updateRaf)
    updateRaf = 0
  }
  document.removeEventListener('keydown', handleKeydown, true)
  document.removeEventListener('wheel', preventBlockedScroll, true)
  document.removeEventListener('touchmove', preventBlockedScroll, true)
  window.removeEventListener('resize', scheduleUpdate)
  window.removeEventListener('scroll', scheduleUpdate, true)
}

watch(
  () => props.open,
  async (open) => {
    if (open) {
      originElement = document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null
      finishing = false
      stepIndex.value = 0
      document.addEventListener('keydown', handleKeydown, true)
      document.addEventListener('wheel', preventBlockedScroll, { capture: true, passive: false })
      document.addEventListener('touchmove', preventBlockedScroll, { capture: true, passive: false })
      window.addEventListener('resize', scheduleUpdate)
      window.addEventListener('scroll', scheduleUpdate, true)
      // 空库时后台放入样例记忆，供搜索步体验；不阻塞步骤激活
      void injectTourSamples()
      await activateStep()
      return
    }

    teardownOverlay()
    await nextTick()
    if (originElement?.isConnected) {
      originElement.focus({ preventScroll: true })
    }
    originElement = null
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  teardownOverlay()
  if (originElement?.isConnected) originElement.focus({ preventScroll: true })
})
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="guided-tour" role="presentation">
      <template v-if="isAnchoredMode && positioned && holeStyle">
        <div
          class="guided-tour__hole"
          :style="holeStyle"
          aria-hidden="true"
        ></div>
        <div
          v-for="(blockerStyle, index) in blockerStyles"
          :key="index"
          class="guided-tour__blocker"
          :style="blockerStyle"
          aria-hidden="true"
        ></div>
      </template>
      <div v-else class="guided-tour__dim" aria-hidden="true"></div>

      <section
        ref="cardElement"
        class="guided-tour__card"
        :class="[
          isAnchoredMode ? 'guided-tour__card--anchored' : 'guided-tour__card--centered',
          { 'guided-tour__card--hidden': !cardVisible },
        ]"
        :style="isAnchoredMode && cardPosition ? cardPosition : undefined"
        role="dialog"
        aria-modal="true"
        aria-labelledby="guided-tour-title"
        :aria-describedby="descriptionText ? 'guided-tour-description' : undefined"
        tabindex="-1"
        data-testid="tour-card"
      >
        <div :key="step.titleKey" class="guided-tour__body">
          <p v-if="showCounter" class="guided-tour__counter">{{ counterLabel }}</p>
          <h2 id="guided-tour-title" class="guided-tour__title">{{ t(step.titleKey) }}</h2>
          <p v-if="descriptionText" id="guided-tour-description" class="guided-tour__description">
            {{ descriptionText }}
          </p>
          <p v-if="gateHintText" class="guided-tour__gate-hint">{{ gateHintText }}</p>
          <footer class="guided-tour__footer">
            <button
              v-if="!isWelcome && !isFinish"
              type="button"
              class="guided-tour__skip"
              data-testid="tour-skip"
              @click="finish"
            >
              {{ t('onboarding.tour.skip') }}
            </button>
            <button
              v-else-if="isWelcome"
              type="button"
              class="btn-secondary btn-sm"
              data-testid="tour-later"
              @click="finish"
            >
              {{ t('onboarding.tour.later') }}
            </button>
            <span class="guided-tour__footer-spacer"></span>
            <button
              v-if="stepIndex > 0"
              type="button"
              class="btn-secondary btn-sm"
              data-testid="tour-prev"
              @click="goPrev"
            >
              {{ t('onboarding.tour.prev') }}
            </button>
            <button
              ref="nextButton"
              type="button"
              class="btn-primary btn-sm"
              data-testid="tour-next"
              @click="handlePrimary"
            >
              {{ primaryLabel }}
            </button>
          </footer>
        </div>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
/* 挖孔本体透明，巨大的 spread 阴罩负责遮暗其余一切；2px 主色环贴孔缘 */
.guided-tour__hole {
  position: fixed;
  z-index: var(--z-tour);
  pointer-events: none;
  border-radius: calc(var(--radius-lg) + 2px);
  box-shadow:
    0 0 0 2px var(--color-primary),
    0 0 0 200vmax var(--color-overlay);
  animation: guided-tour-in 160ms ease-out;
}

/* 居中模式（欢迎/完成/降级）：全屏遮罩本身拦截点击，只留说明卡可操作 */
.guided-tour__dim {
  position: fixed;
  z-index: var(--z-tour);
  inset: 0;
  pointer-events: auto;
  background: var(--color-overlay);
  animation: guided-tour-in 160ms ease-out;
}

/* 锚定模式：透明拦截片盖住挖孔以外区域（视觉仍由挖孔的巨幅阴影承担） */
.guided-tour__blocker {
  position: fixed;
  z-index: var(--z-tour);
  pointer-events: auto;
  background: transparent;
}

.guided-tour__card {
  position: fixed;
  z-index: calc(var(--z-tour) + 1);
  width: 300px;
  max-width: calc(100vw - 1.5rem);
  padding: 0.875rem 1rem 0.75rem;
  border: 1px solid var(--shell-line);
  border-radius: var(--radius-lg);
  background: var(--color-surface-raised);
  box-shadow: var(--shadow-modal);
  color: var(--shell-ink);
}

.guided-tour__card--hidden {
  visibility: hidden;
}

.guided-tour__card--centered {
  top: 50%;
  left: 50%;
  width: 340px;
  transform: translate(-50%, -50%);
}

.guided-tour__card--anchored {
  animation: guided-tour-in 160ms ease-out;
}

.guided-tour__body {
  animation: guided-tour-body-in 140ms ease-out;
}

.guided-tour__counter {
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  color: var(--shell-muted);
}

.guided-tour__title {
  margin-top: 2px;
  font-size: 14px;
  font-weight: 600;
  color: var(--shell-ink);
}

.guided-tour__description {
  margin-top: 4px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--shell-muted);
}

.guided-tour__gate-hint {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--color-primary);
}

.guided-tour__footer {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}

.guided-tour__footer-spacer {
  flex: 1;
}

.guided-tour__skip {
  padding: 0 2px;
  font-size: 12px;
  color: var(--shell-muted);
  transition: color 160ms ease;
}

.guided-tour__skip:hover {
  color: var(--shell-ink);
}

@keyframes guided-tour-in {
  from {
    opacity: 0;
  }
}

@keyframes guided-tour-body-in {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .guided-tour__hole,
  .guided-tour__dim,
  .guided-tour__card--anchored,
  .guided-tour__body {
    animation-duration: 1ms;
  }
}
</style>
