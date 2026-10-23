import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import SwipeToastItem from '@/components/toast/SwipeToastItem.vue'
import SwipeToastHost from '@/components/toast/SwipeToastHost.vue'
import { useNotificationStore } from '@/stores/notification'
import type { Notification } from '@/stores/notification'

const mockState = vi.hoisted(() => ({ reduced: true }))

const createFakeMotionValue = (initial: number) => {
  let value = initial
  return {
    get: () => value,
    set: (next: number) => { value = next },
    on: () => () => {},
    stop: vi.fn(),
    destroy: vi.fn(),
  }
}

vi.mock('motion-v', () => ({
  animate: vi.fn(() => Promise.resolve()),
  motionValue: (initial: number) => createFakeMotionValue(initial),
  useReducedMotion: () => ({ get value() { return mockState.reduced } }),
}))

const makeNotification = (overrides: Partial<Notification> = {}): Notification => ({
  id: 1,
  message: '已保存',
  type: 'success',
  duration: 2000,
  ...overrides,
})

const mountItem = (notification: Notification) =>
  mount(SwipeToastItem, { props: { notification }, attachTo: document.body })

describe('SwipeToastItem', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockState.reduced = true
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.useRealTimers()
    document.body.innerHTML = ''
  })

  it('dismisses itself through the store when the countdown runs out', async () => {
    vi.useFakeTimers()
    const store = useNotificationStore()
    store.show('超时消息', 'info', 1000)
    const item = mountItem(store.notifications[0])
    await flushPromises()

    // 退场走 CSS（closing 态），340ms 后从队列移除
    vi.advanceTimersByTime(1000)
    expect(store.notifications).toHaveLength(1)
    await item.vm.$nextTick()
    expect(item.find('.swipe-toast--closing').exists()).toBe(true)
    vi.advanceTimersByTime(340)
    expect(store.notifications).toHaveLength(0)
    item.unmount()
  })

  it('pauses the countdown while hovered and resumes with the remaining time', async () => {
    vi.useFakeTimers()
    const store = useNotificationStore()
    store.show('悬停消息', 'info', 2000)
    const item = mountItem(store.notifications[0])

    await flushPromises()
    vi.advanceTimersByTime(500)
    await item.find('.swipe-toast__card').trigger('pointerenter', { pointerType: 'mouse' })
    vi.advanceTimersByTime(60_000)
    expect(store.notifications).toHaveLength(1)

    await item.find('.swipe-toast__card').trigger('pointerleave', { pointerType: 'mouse' })
    vi.advanceTimersByTime(1499)
    expect(store.notifications).toHaveLength(1)
    vi.advanceTimersByTime(1)
    // 到时后进入退场，再 340ms 从队列移除
    await item.vm.$nextTick()
    expect(item.find('.swipe-toast--closing').exists()).toBe(true)
    vi.advanceTimersByTime(340)
    expect(store.notifications).toHaveLength(0)
    item.unmount()
  })

  it('does not pause for touch pointer types', async () => {
    vi.useFakeTimers()
    const store = useNotificationStore()
    store.show('触屏消息', 'info', 1000)
    const item = mountItem(store.notifications[0])
    await flushPromises()

    await item.find('.swipe-toast__card').trigger('pointerenter', { pointerType: 'touch' })
    vi.advanceTimersByTime(1000)
    await item.vm.$nextTick()
    expect(item.find('.swipe-toast--closing').exists()).toBe(true)
    vi.advanceTimersByTime(340)
    expect(store.notifications).toHaveLength(0)
    item.unmount()
  })

  it('dismisses on a downward swipe past the distance threshold', async () => {
    mockState.reduced = false
    const store = useNotificationStore()
    store.show('可拖拽消息', 'info', 30_000)
    const item = mountItem(store.notifications[0])
    const card = item.find('.swipe-toast__card')

    await card.trigger('pointerdown', { button: 0, clientY: 100, pointerId: 1 })
    // 死区突破的首次移动锚定 grab（偏移为 0），第二次移动才产生实际位移
    await card.trigger('pointermove', { clientY: 160, pointerId: 1 })
    await card.trigger('pointermove', { clientY: 220, pointerId: 1 })
    await card.trigger('pointerup', { clientY: 220, pointerId: 1 })
    await flushPromises()

    const { animate } = await import('motion-v')
    // 甩出走弹簧 + 淡出两条动画，随后从队列移除
    expect(animate).toHaveBeenCalledTimes(2)
    expect(store.notifications).toHaveLength(0)
    item.unmount()
  })

  it('springs back with the release velocity when the swipe is too short', async () => {
    mockState.reduced = false
    vi.useFakeTimers()
    const { animate } = await import('motion-v')
    const store = useNotificationStore()
    store.show('回弹消息', 'info', 30_000)
    const item = mountItem(store.notifications[0])
    const card = item.find('.swipe-toast__card')

    await card.trigger('pointerdown', { button: 0, clientY: 100, pointerId: 1 })
    await card.trigger('pointermove', { clientY: 120, pointerId: 1 })
    await card.trigger('pointermove', { clientY: 140, pointerId: 1 })
    // 停顿 200ms 再松手：速度采样已停滞，位移 20px 也不构成轻弹
    vi.advanceTimersByTime(200)
    await card.trigger('pointerup', { clientY: 140, pointerId: 1 })

    expect(animate).toHaveBeenCalledTimes(1)
    const options = vi.mocked(animate).mock.calls[0][2] as { type: string; bounce: number }
    expect(options.type).toBe('spring')
    expect(options.bounce).toBe(0.2)
    expect(store.notifications).toHaveLength(1)
    item.unmount()
  })

  it('ignores presses that stay inside the dead zone', async () => {
    const { animate } = await import('motion-v')
    const store = useNotificationStore()
    store.show('死区消息', 'info', 30_000)
    const item = mountItem(store.notifications[0])
    const card = item.find('.swipe-toast__card')

    await card.trigger('pointerdown', { button: 0, clientY: 100, pointerId: 1 })
    await card.trigger('pointermove', { clientY: 102, pointerId: 1 })
    await card.trigger('pointerup', { clientY: 102, pointerId: 1 })

    expect(animate).not.toHaveBeenCalled()
    expect(store.notifications).toHaveLength(1)
    item.unmount()
  })

  it('does not start a drag from the close button', async () => {
    const { animate } = await import('motion-v')
    const store = useNotificationStore()
    store.show('按钮消息', 'info', 30_000)
    const item = mountItem(store.notifications[0])

    await item.get('button').trigger('pointerdown', { button: 0, clientY: 100, pointerId: 1 })
    const card = item.find('.swipe-toast__card')
    await card.trigger('pointermove', { clientY: 160, pointerId: 1 })

    expect(animate).not.toHaveBeenCalled()
    item.unmount()
  })

  it('rescues a closing toast when pressed again', async () => {
    vi.useFakeTimers()
    const store = useNotificationStore()
    store.show('抢救消息', 'info', 500)
    const item = mountItem(store.notifications[0])
    await flushPromises()

    vi.advanceTimersByTime(500)
    await item.vm.$nextTick()
    expect(item.find('.swipe-toast--closing').exists()).toBe(true)

    // 关闭途中再按下：回到 open，倒计时重新起算
    await item.find('.swipe-toast__card').trigger('pointerdown', { button: 0, clientY: 100, pointerId: 1 })
    await item.find('.swipe-toast__card').trigger('pointerup', { clientY: 100, pointerId: 1 })
    await item.vm.$nextTick()
    expect(item.find('.swipe-toast--closing').exists()).toBe(false)
    vi.advanceTimersByTime(499)
    expect(store.notifications).toHaveLength(1)
    vi.advanceTimersByTime(1)
    await item.vm.$nextTick()
    expect(item.find('.swipe-toast--closing').exists()).toBe(true)
    vi.advanceTimersByTime(340)
    expect(store.notifications).toHaveLength(0)
    item.unmount()
  })

  it('dismisses via the close button', async () => {
    vi.useFakeTimers()
    const store = useNotificationStore()
    store.show('关闭消息', 'info', 30_000)
    const item = mountItem(store.notifications[0])

    await item.get('button').trigger('click')
    vi.advanceTimersByTime(340)
    expect(store.notifications).toHaveLength(0)
    item.unmount()
  })
})

describe('SwipeToastHost', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockState.reduced = true
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.useRealTimers()
    document.body.innerHTML = ''
  })

  it('dismisses the latest toast on Escape when no modal dialog is open', () => {
    const store = useNotificationStore()
    store.show('第一条', 'info', 30_000)
    store.show('第二条', 'info', 30_000)
    const host = mount(SwipeToastHost, { attachTo: document.body })

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(store.notifications.map((item) => item.message)).toEqual(['第一条'])
    // 堆叠右缘对齐：不同长度通知各按内容定宽，不被拉成同宽
    expect(host.find('.swipe-toast-host').classes()).toContain('items-end')
    host.unmount()
  })

  it('yields Escape to modal dialogs', () => {
    const store = useNotificationStore()
    store.show('弹窗在场', 'info', 30_000)
    const dialog = document.createElement('div')
    dialog.setAttribute('role', 'dialog')
    dialog.setAttribute('aria-modal', 'true')
    document.body.appendChild(dialog)
    const host = mount(SwipeToastHost, { attachTo: document.body })

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(store.notifications).toHaveLength(1)
    host.unmount()
    dialog.remove()
  })
})
