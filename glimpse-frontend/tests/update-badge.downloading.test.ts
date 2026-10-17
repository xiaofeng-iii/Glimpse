import { describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { useUpdatesStore } from '@/stores/updates'
import UpdateBadge from '@/components/UpdateBadge.vue'

vi.mock('@/platform/desktop', () => ({ isDesktopShell: () => true }))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

const mountBadge = async (installing: boolean) => {
  setActivePinia(createPinia())
  const updates = useUpdatesStore()
  updates.availableUpdate = { version: '1.0.0', notes: '' }
  updates.installing = installing
  const wrapper = mount(UpdateBadge, { attachTo: document.body })
  await flushPromises()
  const trigger = wrapper.find('.update-badge--available')
  expect(trigger.exists()).toBe(true)
  await trigger.trigger('pointerdown')
  await trigger.trigger('click')
  await flushPromises()
  return wrapper
}

const footerStates = () =>
  Array.from(document.querySelectorAll('.notes-popover__footer button')).map((b) => ({
    text: b.textContent?.trim(),
    disabled: (b as HTMLButtonElement).disabled,
  }))

describe('UpdateBadge 下载中按钮状态', () => {
  it('下载中：查看详情保持可点（仅跳转设置页），立即更新禁用并显示正在下载', async () => {
    const wrapper = await mountBadge(true)
    const states = footerStates()
    expect(states).toEqual([
      { text: '查看详情', disabled: false },
      { text: '正在下载', disabled: true },
    ])
    wrapper.unmount()
  })

  it('非下载中：两个按钮都可点', async () => {
    const wrapper = await mountBadge(false)
    expect(footerStates()).toEqual([
      { text: '查看详情', disabled: false },
      { text: '立即更新', disabled: false },
    ])
    wrapper.unmount()
  })
})
