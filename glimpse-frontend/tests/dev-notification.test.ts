import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import SearchToolbar from '@/components/SearchToolbar.vue'
import { useNotificationStore } from '@/stores/notification'

describe('DEV 面板测试通知', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('fires a notification of the chosen type with its tiered duration', async () => {
    const wrapper = mount(SearchToolbar)
    const store = useNotificationStore()

    const buttons = wrapper.findAll('button').filter((button) => ['成功', '提示', '警告', '错误'].includes(button.text()))
    expect(buttons).toHaveLength(4)

    await buttons.find((button) => button.text() === '成功')!.trigger('click')
    await buttons.find((button) => button.text() === '错误')!.trigger('click')

    expect(store.notifications.map((item) => item.type)).toEqual(['success', 'error'])
    expect(store.notifications[0].duration).toBe(1800)
    expect(store.notifications[1].duration).toBe(4200)
    expect(store.notifications[0].message).toContain('测试通知')
  })
})
