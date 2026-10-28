// 本地化改编自 vue-bits micro/warm-tooltip（MIT + Commons Clause，(c) 2025 David Haz）。
// 原样副本：upstream/vue-bits/src/content/Micro/WarmTooltip/WarmTooltip.vue。
import { animate, motionValue, useSpring, useVelocity } from 'motion-v'
import type { Directive } from 'vue'


export type HintTooltipValue = string | { label: string; shortcut?: string }

// 全局共享一个气泡：同一时刻只有一个悬浮说明可见，且触发元素之间移动时
// 气泡不销毁，位置/宽高由弹簧动画接管（vue-bits WarmTooltip 的 warm 机制）。
// 触发元素本身不带任何包裹节点，指令直接挂在按钮/控件上，不改动布局结构。
type HintTriggerElement = HTMLElement & {
  __hintTooltipValue?: HintTooltipValue
  __hintTooltipCleanup?: () => void
}

type Side = 'top' | 'bottom'

const SHOW_DELAY_MS = 300
const CLOSE_GRACE_MS = 80
const WARM_WINDOW_MS = 300
const POP_DURATION_MS = 140
const TRAVEL_SPRING = { type: 'spring' as const, duration: 0.32, bounce: 0.1 }
const POP_EASE = [0.23, 1, 0.32, 1] as const
// 原版 cross-slide：warm 切换时文字层方向性交叉滑动，气泡本体透明度不动。
const LABEL_SWAP_MS = 140
const LABEL_SWAP_SHIFT = 10
const LABEL_SWAP_BLUR = 3
const LABEL_SWAP_EASE = 'cubic-bezier(0.23, 1, 0.32, 1)'
const FULL_LEAN_SPEED = 1200
// 倾侧幅度是唯一加码的样式系数：原版默认 0°（lean prop），这里取 2.5° 的克制值。
const MAX_LEAN_DEG = 2.5
// 原版倾侧弹簧：速度值先经弹簧平滑再进旋转，避免逐帧抖动。
const LEAN_SPRING = { stiffness: 260, damping: 22, mass: 0.4 }
const POP_SCALE = 0.94
const POP_BLUR_PX = 4
const POP_RISE_PX = 4
const TRIGGER_GAP = 8
const VIEWPORT_MARGIN = 8
const ARROW_INSET = 12

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))
const normalize = (value: HintTooltipValue | null | undefined) => {
  if (typeof value === 'string') {
    return { label: value, shortcut: '' }
  }
  return { label: value?.label ?? '', shortcut: value?.shortcut ?? '' }
}

// 气泡 DOM 结构（外层负责位移与尺寸，pop 层负责缩放/模糊/倾侧）：
// .hint-tooltip > .hint-tooltip__pop > (__label + __kbd + __arrow)
// 两层分离使位置弹簧与出场动画互不覆盖 transform。
let tooltipEl: HTMLElement | null = null
let popEl: HTMLElement | null = null
let contentEl: HTMLElement | null = null
let labelEl: HTMLElement | null = null
let kbdEl: HTMLElement | null = null
let arrowEl: HTMLElement | null = null
let tooltipSide: Side = 'top'

let activeTrigger: HintTriggerElement | null = null
let showTimer: ReturnType<typeof window.setTimeout> | null = null
let closeTimer: ReturnType<typeof window.setTimeout> | null = null
let finishTimer: ReturnType<typeof window.setTimeout> | null = null
let closing = false
let warmUntil = -Infinity

const ax = motionValue(0)
const ay = motionValue(0)
const aw = motionValue(0)
const ah = motionValue(0)
const presence = motionValue(0)
// useVelocity 内部的 useMotionValueEvent 会在组件实额外注册一次 onUnmounted
// （指令运行在实例外，Vue 仅告警、无副作用）；其帧循环速度归零即自停，
// 对 velocity 值的订阅在 unbindMotion 统一释放。
const velocityX = useVelocity(ax)
const leanUnit = useSpring(0, LEAN_SPRING)

let motionUnsubscribers: (() => void)[] = []
let motionBound = false

const reducedMotion = () =>
  typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

const clearTimer = (timer: ReturnType<typeof window.setTimeout> | null) => {
  if (timer !== null) {
    window.clearTimeout(timer)
  }
}

// 外层目标尺寸 = 内容容器渲染尺寸 + pop 的 padding 与边框（合称 chrome）。
// 只量内容不量 chrome 会让气泡盒子比文字矮/窄 10px：文字溢出气泡底边、箭头压进文字。
let popChromeX = 0
let popChromeY = 0

const measure = () => ({
  width: (contentEl?.offsetWidth ?? 0) + popChromeX,
  height: (contentEl?.offsetHeight ?? 0) + popChromeY,
})

// jsdom 下所有 rect/offset 均为 0：钳制后落点固定为 (8, 8)，保持下方落位与测试稳定。
const pickSide = (trigger: HintTriggerElement, height: number): Side => {
  const rect = trigger.getBoundingClientRect()
  return rect.top - TRIGGER_GAP - height >= VIEWPORT_MARGIN ? 'top' : 'bottom'
}

// 气泡 DOM 结构（外层负责位移与尺寸，pop 层负责缩放/模糊/倾侧）：
// .hint-tooltip > .hint-tooltip__pop > (__content > __label + __kbd) + __arrow
// 两层分离使位置弹簧与出场动画互不覆盖 transform。
let anchorLeft = 0
let anchorTop = 0

const paintPlace = () => {
  if (!tooltipEl) {
    return
  }
  const width = aw.get()
  const height = ah.get()
  const x = ax.get()
  // 横向必须画动画当前值 ax（纯 JS 取值，非 DOM 读）；画预计算锚点会让弹簧形同虚设、气泡瞬移。
  const left = clamp(x, VIEWPORT_MARGIN, Math.max(VIEWPORT_MARGIN, window.innerWidth - VIEWPORT_MARGIN - width))
  const top = ay.get()
  tooltipEl.style.transform = `translate(${left}px, ${top}px)`
  tooltipEl.style.width = `${width}px`
  tooltipEl.style.height = `${height}px`
  if (arrowEl) {
    arrowEl.style.left = `${clamp(x + width / 2 - left, ARROW_INSET, Math.max(ARROW_INSET, width - ARROW_INSET))}px`
  }
}

// 计算并写入锚点（气泡左边界的未钳制目标值与顶/底锚线）。
// 横向必须用本次目标宽度：首显示时 aw 还是初始 0、warm 移动时是旧宽度，
// 读动画当前值会把气泡左缘钉在按钮中心（整体偏半个气泡宽）。
let targetWidth = 0

const updateAnchor = (trigger: HintTriggerElement, width: number) => {
  const rect = trigger.getBoundingClientRect()
  anchorLeft = rect.left + rect.width / 2 - width / 2
  anchorTop = tooltipSide === 'top' ? rect.top - TRIGGER_GAP : rect.bottom + TRIGGER_GAP
}

const paintPop = () => {
  if (!popEl) {
    return
  }
  const p = clamp(presence.get(), 0, 1)
  popEl.style.opacity = String(p)
  if (reducedMotion()) {
    popEl.style.transform = 'none'
    popEl.style.filter = 'none'
    return
  }
  const scale = POP_SCALE + (1 - POP_SCALE) * p
  const rise = (1 - p) * POP_RISE_PX * (tooltipSide === 'top' ? 1 : -1)
  const rotate = leanUnit.get() * MAX_LEAN_DEG * (tooltipSide === 'top' ? 1 : -1)
  popEl.style.transform = `translateY(${rise}px) scale(${scale}) rotate(${rotate}deg)`
  popEl.style.filter = `blur(${POP_BLUR_PX * (1 - p)}px)`
}

const updateLean = () => {
  leanUnit.set(clamp(-velocityX.get() / FULL_LEAN_SPEED, -1, 1))
}

// warm 切换的文字交叉滑动（原版 onEnter/onLeave 的 layer 机制，方向语义照搬）：
// 新文字自移动方向一侧(+dir)滑入，旧文字幽灵层向反方向(-dir)滑出——文字层逆着气泡
// 行进方向滑动，是原版"减速带"手感的来源。两者同时进行。
const crossSlideLabel = (dir: number) => {
  const wrap = contentEl
  if (!wrap || typeof wrap.animate !== 'function') {
    return
  }
  const ghost = wrap.cloneNode(true) as HTMLElement
  ghost.className = 'hint-tooltip__content-ghost'
  ghost.setAttribute('aria-hidden', 'true')
  wrap.appendChild(ghost)
  const out = ghost.animate(
    [
      { transform: 'none', opacity: 1, filter: 'blur(0px)' },
      { transform: `translate(${-LABEL_SWAP_SHIFT * dir}px, 0)`, opacity: 0, filter: `blur(${LABEL_SWAP_BLUR}px)` },
    ],
    { duration: LABEL_SWAP_MS, easing: LABEL_SWAP_EASE, fill: 'forwards' },
  )
  out.onfinish = () => ghost.remove()
  wrap.animate(
    [
      { transform: `translate(${LABEL_SWAP_SHIFT * dir}px, 0)`, opacity: 0, filter: `blur(${LABEL_SWAP_BLUR}px)` },
      { transform: 'none', opacity: 1, filter: 'blur(0px)' },
    ],
    { duration: LABEL_SWAP_MS, easing: LABEL_SWAP_EASE },
  )
}

const bindMotion = () => {
  if (motionBound) {
    return
  }
  motionBound = true
  motionUnsubscribers = [
    ax.on('change', paintPlace),
    ay.on('change', paintPlace),
    aw.on('change', paintPlace),
    ah.on('change', paintPlace),
    presence.on('change', paintPop),
    leanUnit.on('change', paintPop),
    velocityX.on('change', updateLean),
  ]
}

const unbindMotion = () => {
  motionUnsubscribers.forEach((off) => off())
  motionUnsubscribers = []
  motionBound = false
  ;[ax, ay, aw, ah, presence, leanUnit].forEach((value) => value.stop())
}

// 原版行为：气泡激活期间在触发元素之外按下指针，即走宽限隐藏路径。
const handleOutsidePointerDown = (event: PointerEvent) => {
  if (activeTrigger && event.target instanceof Node && !activeTrigger.contains(event.target)) {
    hideTooltip(undefined, false)
  }
}

const handleViewportShift = () => {
  // 滚动/缩放只重新跟随触发元素位置，不再销毁气泡；尺寸变化由下次 show 处理。
  if (!activeTrigger || closing) {
    return
  }
  const rect = activeTrigger.getBoundingClientRect()
  tooltipSide = pickSide(activeTrigger, ah.get())
  tooltipEl?.classList.toggle('hint-tooltip--below', tooltipSide === 'bottom')
  anchorLeft = rect.left + rect.width / 2 - targetWidth / 2
  anchorTop = tooltipSide === 'top' ? rect.top - TRIGGER_GAP : rect.bottom + TRIGGER_GAP
  ax.jump(anchorLeft)
  ay.jump(tooltipSide === 'top' ? anchorTop - ah.get() : anchorTop)
  paintPlace()
}

const bindViewportListeners = () => {
  window.addEventListener('scroll', handleViewportShift, true)
  window.addEventListener('resize', handleViewportShift)
  document.addEventListener('visibilitychange', handleDocumentHidden)
  document.addEventListener('pointerdown', handleOutsidePointerDown, true)
}

const unbindViewportListeners = () => {
  window.removeEventListener('scroll', handleViewportShift, true)
  window.removeEventListener('resize', handleViewportShift)
  document.removeEventListener('visibilitychange', handleDocumentHidden)
  document.removeEventListener('pointerdown', handleOutsidePointerDown, true)
}

const handleDocumentHidden = () => {
  if (document.visibilityState === 'hidden') {
    destroyTooltip()
  }
}

const destroyTooltip = () => {
  clearTimer(showTimer)
  clearTimer(closeTimer)
  clearTimer(finishTimer)
  showTimer = null
  closeTimer = null
  finishTimer = null
  closing = false
  tooltipEl?.remove()
  tooltipEl = null
  popEl = null
  contentEl = null
  labelEl = null
  kbdEl = null
  arrowEl = null
  activeTrigger = null
  unbindViewportListeners()
  unbindMotion()
}

const beginClose = (instant: boolean) => {
  if (!tooltipEl || closing) {
    return
  }
  closing = true
  warmUntil = Date.now() + WARM_WINDOW_MS
  if (instant || reducedMotion()) {
    destroyTooltip()
    return
  }
  animate(presence, 0, { duration: (POP_DURATION_MS * 0.8) / 1000, ease: POP_EASE })
  finishTimer = window.setTimeout(destroyTooltip, POP_DURATION_MS * 0.8)
}

const showTooltip = (trigger: HintTriggerElement, instant = false) => {
  const { label, shortcut } = normalize(trigger.__hintTooltipValue)
  if (!label) {
    return
  }

  clearTimer(closeTimer)
  clearTimer(finishTimer)
  closeTimer = null
  finishTimer = null
  closing = false

  const isWarm = !!tooltipEl && activeTrigger !== trigger
  const prevTrigger = activeTrigger
  const { label: prevLabel, shortcut: prevShortcut } = normalize(prevTrigger?.__hintTooltipValue)
  const contentChanged = prevLabel !== label || prevShortcut !== shortcut
  let moveDir = 1
  if (prevTrigger && prevTrigger !== trigger) {
    const a = prevTrigger.getBoundingClientRect()
    const b = trigger.getBoundingClientRect()
    moveDir = Math.sign(b.left + b.width / 2 - (a.left + a.width / 2)) || 1
  }

  if (!tooltipEl) {
    const tooltip = document.createElement('div')
    tooltip.className = 'hint-tooltip'
    tooltip.setAttribute('role', 'tooltip')

    const pop = document.createElement('div')
    pop.className = 'hint-tooltip__pop'
    const content = document.createElement('span')
    content.className = 'hint-tooltip__content'
    const text = document.createElement('span')
    text.className = 'hint-tooltip__label'
    content.appendChild(text)
    pop.appendChild(content)
    const arrow = document.createElement('span')
    arrow.className = 'hint-tooltip__arrow'
    arrow.setAttribute('aria-hidden', 'true')
    pop.appendChild(arrow)
    tooltip.appendChild(pop)
    document.body.appendChild(tooltip)

    tooltipEl = tooltip
    popEl = pop
    contentEl = content
    labelEl = text
    arrowEl = arrow
    // chrome 在气泡创建时读一次；jsdom 的 computed style 为空串，回退 0 不影响测试。
    const cs = getComputedStyle(pop)
    popChromeX =
      (parseFloat(cs.paddingLeft) || 0) + (parseFloat(cs.paddingRight) || 0) +
      (parseFloat(cs.borderLeftWidth) || 0) + (parseFloat(cs.borderRightWidth) || 0)
    popChromeY =
      (parseFloat(cs.paddingTop) || 0) + (parseFloat(cs.paddingBottom) || 0) +
      (parseFloat(cs.borderTopWidth) || 0) + (parseFloat(cs.borderBottomWidth) || 0)
    bindMotion()
    bindViewportListeners()
  }

  activeTrigger = trigger
  if (labelEl) {
    labelEl.textContent = label
  }

  if (shortcut) {
    if (!kbdEl) {
      kbdEl = document.createElement('kbd')
      kbdEl.className = 'hint-tooltip__kbd'
      contentEl?.appendChild(kbdEl)
    }
    kbdEl.textContent = shortcut
  } else {
    kbdEl?.remove()
    kbdEl = null
  }

  const { width, height } = measure()
  tooltipSide = pickSide(trigger, height)
  tooltipEl?.classList.toggle('hint-tooltip--below', tooltipSide === 'bottom')
  updateAnchor(trigger, width)
  targetWidth = width
  const targetX = anchorLeft
  const targetY = tooltipSide === 'top' ? anchorTop - height : anchorTop

  if (instant || reducedMotion()) {
    // 原版 instant 模式（键盘 focus-visible）：位移直跳、全量出现，不做任何动画。
    ax.jump(targetX)
    ay.jump(targetY)
    aw.jump(width)
    ah.jump(height)
    presence.jump(1)
  } else if (isWarm) {
    // warm 滑移（原版 move 模式）：位置/宽高弹簧过去，气泡透明度全程保持 1 不闪；
    // 文字层做方向性交叉滑动；若关闭淡出中途被接管（80ms 宽限内），presence 快速回满。
    animate(ax, targetX, TRAVEL_SPRING)
    animate(ay, targetY, TRAVEL_SPRING)
    animate(aw, width, TRAVEL_SPRING)
    animate(ah, height, TRAVEL_SPRING)
    if (contentChanged) {
      crossSlideLabel(moveDir)
    }
    animate(presence, 1, { duration: 0.12, ease: POP_EASE })
  } else if (!tooltipEl && Date.now() < warmUntil) {
    // warm 窗口内复活（原版行为）：气泡已销毁但窗口未过，直接全量出现，不重走冷启动出场。
    ax.jump(targetX)
    ay.jump(targetY)
    aw.jump(width)
    ah.jump(height)
    presence.jump(1)
  } else {
    ax.jump(targetX)
    ay.jump(targetY)
    aw.jump(width)
    ah.jump(height)
    presence.jump(0)
    animate(presence, 1, { duration: POP_DURATION_MS / 1000, ease: POP_EASE })
  }
  paintPlace()
  paintPop()
}

function hideTooltip(trigger?: HintTriggerElement, instant = false) {
  clearTimer(showTimer)
  showTimer = null
  if (trigger && trigger !== activeTrigger) {
    return
  }
  if (instant || !tooltipEl) {
    destroyTooltip()
    return
  }
  clearTimer(closeTimer)
  closeTimer = window.setTimeout(() => beginClose(false), CLOSE_GRACE_MS)
}

const scheduleShow = (trigger: HintTriggerElement) => {
  clearTimer(showTimer)
  clearTimer(closeTimer)
  clearTimer(finishTimer)
  closeTimer = null
  finishTimer = null
  if (tooltipEl || Date.now() < warmUntil) {
    // warm 窗口内（气泡仍在或刚关闭）：立即接管，不重新等待冷启动延迟。
    showTooltip(trigger)
    return
  }
  showTimer = window.setTimeout(() => {
    showTimer = null
    showTooltip(trigger)
  }, SHOW_DELAY_MS)
}

export const hintTooltip: Directive<HintTriggerElement, HintTooltipValue> = {
  mounted(el, binding) {
    el.__hintTooltipValue = binding.value

    let pointerDown = false

    const handlePointerEnter = () => scheduleShow(el)
    const handlePointerLeave = () => hideTooltip(el)
    const handlePointerDown = () => {
      pointerDown = true
      // 原版鼠标按下走宽限隐藏（80ms 内被重新进入可取消），非立即销毁。
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
      if (pointerDown) {
        return
      }
      // 原版：键盘 focus-visible 即时全量出现（instant 模式），不等延迟、无出场动画。
      if (typeof el.matches === 'function' && el.matches(':focus-visible')) {
        showTooltip(el, true)
      } else {
        scheduleShow(el)
      }
    }
    const handleBlur = () => hideTooltip(el, true)
    const handleKeydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        hideTooltip(el, true)
      }
    }

    el.addEventListener('pointerenter', handlePointerEnter)
    el.addEventListener('pointerleave', handlePointerLeave)
    el.addEventListener('pointerdown', handlePointerDown)
    el.addEventListener('focus', handleFocus)
    el.addEventListener('blur', handleBlur)
    el.addEventListener('keydown', handleKeydown)

    el.__hintTooltipCleanup = () => {
      el.removeEventListener('pointerenter', handlePointerEnter)
      el.removeEventListener('pointerleave', handlePointerLeave)
      el.removeEventListener('pointerdown', handlePointerDown)
      el.removeEventListener('focus', handleFocus)
      el.removeEventListener('blur', handleBlur)
      el.removeEventListener('keydown', handleKeydown)
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
    hideTooltip(el, true)
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
