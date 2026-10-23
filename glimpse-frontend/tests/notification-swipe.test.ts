import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useNotificationStore, MAX_VISIBLE_NOTIFICATIONS } from '@/stores/notification'
import {
  pushSample,
  rubberband,
  shouldDismiss,
  velocityOf,
} from '@/utils/swipe-gesture'

describe('notification store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('queues notifications with their duration and returns ids', () => {
    const store = useNotificationStore()
    const first = store.show('已保存', 'success', 1800)
    const second = store.show('失败', 'error', 2800)

    expect(first).not.toBe(second)
    expect(store.notifications.map((item) => item.message)).toEqual(['已保存', '失败'])
    expect(store.notifications[0].duration).toBe(1800)
    expect(store.notifications[1].duration).toBe(2800)
  })

  it('deduplicates identical message and type within 1200ms', () => {
    const store = useNotificationStore()
    store.show('同一条', 'info')
    expect(store.show('同一条', 'info')).toBe(-1)
    expect(store.notifications).toHaveLength(1)
  })

  it('drops the oldest notification beyond the stacking cap', () => {
    const store = useNotificationStore()
    for (let index = 0; index < MAX_VISIBLE_NOTIFICATIONS + 2; index += 1) {
      store.show(`第 ${index} 条`, 'info')
    }

    expect(store.notifications).toHaveLength(MAX_VISIBLE_NOTIFICATIONS)
    expect(store.notifications[0].message).toBe('第 2 条')
    expect(store.notifications[MAX_VISIBLE_NOTIFICATIONS - 1].message).toBe('第 4 条')
  })

  it('dismiss removes only the targeted notification', () => {
    const store = useNotificationStore()
    const first = store.show('一', 'info')
    store.show('二', 'info')
    store.dismiss(first)

    expect(store.notifications.map((item) => item.message)).toEqual(['二'])
    store.dismiss(first)
    expect(store.notifications).toHaveLength(1)
  })
})

describe('swipe gesture math', () => {
  it('passes downward displacement through and damps upward with rational rubberband', () => {
    expect(rubberband(30)).toBe(30)
    // 有理阻尼：小位移段比指数曲线更软
    expect(rubberband(-10)).toBeCloseTo(-4.47, 2)
    // 渐近 -24 但永不越过
    expect(rubberband(-500)).toBeCloseTo(-22.07, 2)
    expect(rubberband(-500)).toBeGreaterThan(-24)
  })

  it('dismisses only when overall downward and either flicking fast or far enough', () => {
    expect(shouldDismiss(40, 0)).toBe(true)
    expect(shouldDismiss(45, 0)).toBe(true)
    expect(shouldDismiss(10, 0.5)).toBe(true)
    expect(shouldDismiss(10, 0.05)).toBe(false)
    // 整体不在向下（dy <= 0）时任何速度都不关
    expect(shouldDismiss(0, 5)).toBe(false)
    expect(shouldDismiss(-30, 5)).toBe(false)
  })

  it('computes velocity from first and last samples', () => {
    expect(velocityOf([[1000, 0], [1050, 15]], 1100)).toBeCloseTo(0.3)
    // 单样本无速度
    expect(velocityOf([[1000, 0]], 1100)).toBe(0)
    // 向上位移速度为负
    expect(velocityOf([[1000, 50], [1050, 30]], 1100)).toBeCloseTo(-0.4)
  })

  it('treats a stale last sample as zero velocity', () => {
    // 末样本距 now 超过 100ms：手势已停滞
    expect(velocityOf([[1000, 0], [1050, 15]], 1200)).toBe(0)
  })

  it('keeps at most the latest four samples', () => {
    const samples: Array<[number, number]> = []
    for (let index = 0; index < 6; index += 1) pushSample(samples, 1000 + index * 10, index * 5)
    expect(samples).toHaveLength(4)
    expect(samples[0][0]).toBe(1000 + 20)
  })
})
