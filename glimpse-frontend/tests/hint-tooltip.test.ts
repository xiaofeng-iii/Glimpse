import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import {
  __resetGeometrySuppressForTests,
  hintTooltip,
  installNativeTooltipGuard,
} from '../src/directives/hint-tooltip'

const platformMocks = vi.hoisted(() => {
  const geometryHandlers: Array<() => void> = []
  return {
    geometryHandlers,
    fireGeometryChange: () => geometryHandlers.forEach((handler) => handler()),
  }
})

vi.mock('@/platform/desktop', () => ({
  listenForWindowGeometryChange: vi.fn(async (handler: () => void) => {
    platformMocks.geometryHandlers.push(handler)
    return () => {}
  }),
}))

const Harness = defineComponent({
  template: `
    <button v-hint-tooltip="{ label: '设置', shortcut: 'Ctrl+,' }" type="button">触发按钮</button>
  `,
})

const NoShortcutHarness = defineComponent({
  template: `
    <button v-hint-tooltip="'关闭'" type="button">触发按钮</button>
  `,
})

const PairHarness = defineComponent({
  template: `
    <div>
      <button id="first" v-hint-tooltip="'第一个'" type="button">一</button>
      <button id="second" v-hint-tooltip="'第二个'" type="button">二</button>
    </div>
  `,
})

const mountHarness = (component: ReturnType<typeof defineComponent>) =>
  mount(component, {
    attachTo: document.body,
    global: {
      directives: {
        'hint-tooltip': hintTooltip,
      },
    },
  })

describe('v-hint-tooltip', () => {
  afterEach(() => {
    vi.useRealTimers()
    __resetGeometrySuppressForTests()
    document.body.innerHTML = ''
  })

  it('不改动按钮本身，默认不渲染提示', () => {
    const wrapper = mountHarness(Harness)

    const button = wrapper.get('button')
    expect(button.text()).toBe('触发按钮')
    expect(button.attributes('title')).toBeUndefined()
    expect(document.querySelector('.hint-tooltip')).toBeNull()

    wrapper.unmount()
  })

  it('悬停延迟后显示说明文字与快捷键键帽', async () => {
    vi.useFakeTimers()
    const wrapper = mountHarness(Harness)

    await wrapper.get('button').trigger('pointerenter')
    vi.advanceTimersByTime(600)

    const tooltip = document.querySelector('.hint-tooltip')
    expect(tooltip).not.toBeNull()
    expect(tooltip?.getAttribute('role')).toBe('tooltip')
    expect(tooltip?.textContent).toContain('设置')
    expect(tooltip?.querySelector('kbd')?.textContent).toBe('Ctrl+,')

    wrapper.unmount()
  })

  it('拖动中抑制合成悬停，停手后光标所在触发元素立即回应', async () => {
    vi.useFakeTimers()
    const wrapper = mountHarness(Harness)
    const button = wrapper.get('button')

    // 正常路径：悬停出现，移开关闭
    await button.trigger('pointerenter')
    vi.advanceTimersByTime(600)
    expect(document.querySelector('.hint-tooltip')).not.toBeNull()
    await button.trigger('pointerleave')
    vi.advanceTimersByTime(600)
    expect(document.querySelector('.hint-tooltip')).toBeNull()

    // 拖动中（停手判定窗口内）：合成 pointerenter 不重现气泡
    platformMocks.fireGeometryChange()
    await button.trigger('pointerenter')
    vi.advanceTimersByTime(100)
    expect(document.querySelector('.hint-tooltip')).toBeNull()

    // 停手（几何事件静默 200ms）：光标仍停在触发元素上 → 立即显示
    vi.advanceTimersByTime(100)
    expect(document.querySelector('.hint-tooltip')).not.toBeNull()
    await button.trigger('pointerleave')
    vi.advanceTimersByTime(600)
    expect(document.querySelector('.hint-tooltip')).toBeNull()

    // 拖动中已移开的合成悬停（enter 后又 leave）：停手后不回应
    platformMocks.fireGeometryChange()
    await button.trigger('pointerenter')
    await button.trigger('pointerleave')
    vi.advanceTimersByTime(300)
    expect(document.querySelector('.hint-tooltip')).toBeNull()

    wrapper.unmount()
  })

  it('键盘聚焦路径照常显示，不受拖动抑制影响', async () => {
    vi.useFakeTimers()
    const wrapper = mountHarness(Harness)

    await wrapper.get('button').trigger('focus')
    vi.advanceTimersByTime(600)
    expect(document.querySelector('.hint-tooltip')).not.toBeNull()

    wrapper.unmount()
  })

  it('鼠标按下即隐藏气泡，按住期间不保持显示', async () => {
    vi.useFakeTimers()
    const wrapper = mountHarness(Harness)
    const button = wrapper.get('button')

    await button.trigger('pointerenter')
    vi.advanceTimersByTime(600)
    expect(document.querySelector('.hint-tooltip')).not.toBeNull()

    await button.trigger('pointerdown')
    vi.advanceTimersByTime(600)
    expect(document.querySelector('.hint-tooltip')).toBeNull()

    wrapper.unmount()
  })

  it('延迟内移出不显示，移出经过关闭宽限后移除气泡', async () => {
    vi.useFakeTimers()
    const wrapper = mountHarness(Harness)
    const button = wrapper.get('button')

    await button.trigger('pointerenter')
    vi.advanceTimersByTime(200)
    await button.trigger('pointerleave')
    vi.advanceTimersByTime(600)
    expect(document.querySelector('.hint-tooltip')).toBeNull()

    await button.trigger('pointerenter')
    vi.advanceTimersByTime(600)
    expect(document.querySelector('.hint-tooltip')).not.toBeNull()
    await button.trigger('pointerleave')
    // 80ms 关闭宽限内气泡仍在（warm 连续体验的窗口），退场结束后移除。
    expect(document.querySelector('.hint-tooltip')).not.toBeNull()
    vi.advanceTimersByTime(400)
    expect(document.querySelector('.hint-tooltip')).toBeNull()

    wrapper.unmount()
  })

  it('字符串形式只显示说明，不渲染键帽', async () => {
    vi.useFakeTimers()
    const wrapper = mountHarness(NoShortcutHarness)

    await wrapper.get('button').trigger('pointerenter')
    vi.advanceTimersByTime(600)

    const tooltip = document.querySelector('.hint-tooltip')
    expect(tooltip).not.toBeNull()
    expect(tooltip?.textContent).toContain('关闭')
    expect(tooltip?.querySelector('kbd')).toBeNull()

    wrapper.unmount()
  })

  it('卸载触发元素时移除提示', async () => {
    vi.useFakeTimers()
    const wrapper = mountHarness(Harness)

    await wrapper.get('button').trigger('pointerenter')
    vi.advanceTimersByTime(400)
    expect(document.querySelector('.hint-tooltip')).not.toBeNull()

    wrapper.unmount()
    expect(document.querySelector('.hint-tooltip')).toBeNull()
  })

  it('上方空间不足时落到下方并切换缩放原点', async () => {
    vi.useFakeTimers()
    const wrapper = mountHarness(Harness)

    await wrapper.get('button').trigger('pointerenter')
    vi.advanceTimersByTime(400)

    const tooltip = document.querySelector('.hint-tooltip')
    expect(tooltip).not.toBeNull()
    // jsdom 的 getBoundingClientRect 全为 0，上方必无空间，稳定走下方落位。
    expect(tooltip?.classList.contains('hint-tooltip--below')).toBe(true)

    wrapper.unmount()
  })

  it('warm 窗口内移向相邻按钮：不重新等待，同一气泡直接换内容', async () => {
    vi.useFakeTimers()
    const wrapper = mountHarness(PairHarness)

    await wrapper.get('#first').trigger('pointerenter')
    vi.advanceTimersByTime(400)
    const tooltip = document.querySelector('.hint-tooltip')
    expect(tooltip?.textContent).toContain('第一个')

    await wrapper.get('#first').trigger('pointerleave')
    await wrapper.get('#second').trigger('pointerenter')
    // 没有再次等待 300ms：气泡立刻换到第二个按钮的内容。
    expect(document.querySelectorAll('.hint-tooltip')).toHaveLength(1)
    expect(tooltip?.textContent).toContain('第二个')
    expect(tooltip?.textContent).not.toContain('第一个')

    wrapper.unmount()
  })

  it('冷启动之间没有 warm 残留：超出 warm 窗口后重新走延迟', async () => {
    vi.useFakeTimers()
    const wrapper = mountHarness(PairHarness)

    await wrapper.get('#first').trigger('pointerenter')
    vi.advanceTimersByTime(400)
    await wrapper.get('#first').trigger('pointerleave')
    vi.advanceTimersByTime(1000)

    await wrapper.get('#second').trigger('pointerenter')
    expect(document.querySelector('.hint-tooltip')).toBeNull()
    vi.advanceTimersByTime(400)
    expect(document.querySelector('.hint-tooltip')?.textContent).toContain('第二个')

    wrapper.unmount()
  })

  it('气泡销毁后的 warm 窗口内再进入：立即全量重现，不重走冷启动延迟', async () => {
    vi.useFakeTimers()
    const wrapper = mountHarness(PairHarness)

    await wrapper.get('#first').trigger('pointerenter')
    vi.advanceTimersByTime(400)
    await wrapper.get('#first').trigger('pointerleave')
    // 80ms 关闭宽限 + 112ms 退场 → 气泡已销毁，但 300ms warm 窗口（自 beginClose 起算）未过。
    vi.advanceTimersByTime(300)
    expect(document.querySelector('.hint-tooltip')).toBeNull()

    await wrapper.get('#second').trigger('pointerenter')
    // 窗口内复活：不等待 300ms 冷启动延迟，立即出现。
    expect(document.querySelector('.hint-tooltip')).not.toBeNull()
    expect(document.querySelector('.hint-tooltip')?.textContent).toContain('第二个')
    // 复活走"全量出现"而非冷启动出场：presence 直跳 1，初始不透明度即满
    // （死分支回潮时会从 0 起步做 140ms 出场动画）。
    expect(document.querySelector('.hint-tooltip .hint-tooltip__pop')?.style.opacity).toBe('1')

    wrapper.unmount()
  })

  it('原生提示铁幕：悬停即摘除 title 属性', () => {
    installNativeTooltipGuard()
    const button = document.createElement('button')
    button.setAttribute('title', '原生提示')
    document.body.appendChild(button)

    button.dispatchEvent(new Event('pointerover', { bubbles: true }))
    expect(button.getAttribute('title')).toBeNull()
  })
})
