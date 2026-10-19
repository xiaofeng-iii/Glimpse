import type { Directive } from 'vue'

export type HintTooltipValue = string | { label: string; shortcut?: string }

// 全局共享一个提示元素：同一时刻只会有一个悬浮说明可见（与原生 title 行为一致）。
// 触发元素本身不带任何包裹节点，指令直接挂在按钮/控件上，不改动布局结构。
type HintTriggerElement = HTMLElement & {
  __hintTooltipValue?: HintTooltipValue
  __hintTooltipCleanup?: () => void
}

const SHOW_DELAY_MS = 300
const TRIGGER_GAP = 6
const VIEWPORT_MARGIN = 8

let tooltipEl: HTMLElement | null = null
let activeTrigger: HintTriggerElement | null = null
let showTimer: ReturnType<typeof window.setTimeout> | null = null

const normalize = (value: HintTooltipValue | null | undefined) => {
  if (typeof value === 'string') {
    return { label: value, shortcut: '' }
  }
  return { label: value?.label ?? '', shortcut: value?.shortcut ?? '' }
}

const clearShowTimer = () => {
  if (showTimer !== null) {
    window.clearTimeout(showTimer)
    showTimer = null
  }
}

const handleViewportShift = () => {
  hideTooltip()
}

const bindViewportListeners = () => {
  window.addEventListener('scroll', handleViewportShift, true)
  window.addEventListener('resize', handleViewportShift)
}

const unbindViewportListeners = () => {
  window.removeEventListener('scroll', handleViewportShift, true)
  window.removeEventListener('resize', handleViewportShift)
}

const positionTooltip = (trigger: HTMLElement, tooltip: HTMLElement) => {
  const rect = trigger.getBoundingClientRect()
  const tooltipWidth = tooltip.offsetWidth
  const tooltipHeight = tooltip.offsetHeight
  const maxLeft = Math.max(window.innerWidth - tooltipWidth - VIEWPORT_MARGIN, VIEWPORT_MARGIN)
  const left = Math.min(
    Math.max(rect.left + rect.width / 2 - tooltipWidth / 2, VIEWPORT_MARGIN),
    maxLeft,
  )
  const above = rect.top - TRIGGER_GAP - tooltipHeight
  const top = above >= VIEWPORT_MARGIN ? above : rect.bottom + TRIGGER_GAP
  // 缩放动画的原点跟随落位：按钮上方时自底缘向上展开，下方时自顶缘向下展开。
  tooltip.classList.toggle('hint-tooltip--below', above < VIEWPORT_MARGIN)
  tooltip.style.left = `${left}px`
  tooltip.style.top = `${top}px`
}

const showTooltip = (trigger: HintTriggerElement) => {
  const { label, shortcut } = normalize(trigger.__hintTooltipValue)
  if (!label) {
    return
  }

  hideTooltip()

  const tooltip = document.createElement('div')
  tooltip.className = 'hint-tooltip'
  tooltip.setAttribute('role', 'tooltip')

  const labelEl = document.createElement('span')
  labelEl.textContent = label
  tooltip.appendChild(labelEl)

  if (shortcut) {
    const kbd = document.createElement('kbd')
    kbd.className = 'hint-tooltip__kbd'
    kbd.textContent = shortcut
    tooltip.appendChild(kbd)
  }

  document.body.appendChild(tooltip)
  tooltipEl = tooltip
  activeTrigger = trigger
  positionTooltip(trigger, tooltip)
  bindViewportListeners()
}

function hideTooltip(trigger?: HintTriggerElement) {
  clearShowTimer()
  if (trigger && trigger !== activeTrigger) {
    return
  }
  tooltipEl?.remove()
  if (tooltipEl) {
    unbindViewportListeners()
  }
  tooltipEl = null
  activeTrigger = null
}

const scheduleShow = (trigger: HintTriggerElement) => {
  clearShowTimer()
  showTimer = window.setTimeout(() => {
    showTimer = null
    showTooltip(trigger)
  }, SHOW_DELAY_MS)
}

export const hintTooltip: Directive<HintTriggerElement, HintTooltipValue> = {mounted(el, binding) {
    el.__hintTooltipValue = binding.value

    let pointerDown = false

    const handlePointerEnter = () => scheduleShow(el)
    const handlePointerLeave = () => hideTooltip(el)
    const handlePointerDown = () => {
      pointerDown = true
      hideTooltip(el)
      document.addEventListener(
        'pointerup',
        () => {
          pointerDown = false
        },
        { once: true },
      )
    }
    const handleFocus = () => {
      if (!pointerDown) {
        scheduleShow(el)
      }
    }
    const handleBlur = () => hideTooltip(el)

    el.addEventListener('pointerenter', handlePointerEnter)
    el.addEventListener('pointerleave', handlePointerLeave)
    el.addEventListener('pointerdown', handlePointerDown)
    el.addEventListener('focus', handleFocus)
    el.addEventListener('blur', handleBlur)

    el.__hintTooltipCleanup = () => {
      el.removeEventListener('pointerenter', handlePointerEnter)
      el.removeEventListener('pointerleave', handlePointerLeave)
      el.removeEventListener('pointerdown', handlePointerDown)
      el.removeEventListener('focus', handleFocus)
      el.removeEventListener('blur', handleBlur)
    }
  },
  updated(el, binding) {
    el.__hintTooltipValue = binding.value
    // 对象形式每次渲染都是新引用，须按规范化后的内容比较：
    // 只有说明/快捷键真的变化才刷新，避免无关重渲染重启入场动画。
    const prev = normalize(binding.oldValue)
    const next = normalize(binding.value)
    if ((prev.label !== next.label || prev.shortcut !== next.shortcut) && activeTrigger === el) {
      showTooltip(el)
    }
  },
  beforeUnmount(el) {
    hideTooltip(el)
    el.__hintTooltipCleanup?.()
    delete el.__hintTooltipCleanup
    delete el.__hintTooltipValue
  },
}

// 原生悬浮提示铁幕：悬停到达前把任何残留的 title 属性摘除，
// 浏览器原生气泡因此永不出现；应用内悬浮说明统一由 v-hint-tooltip 呈现，未配置即不显示。
export const installNativeTooltipGuard = () => {
  window.addEventListener(
    'pointerover',
    (event) => {
      if (!(event.target instanceof Element)) {
        return
      }
      event.target.closest('[title]')?.removeAttribute('title')
    },
    { capture: true },
  )
}
