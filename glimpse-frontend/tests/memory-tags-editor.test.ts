import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import type { Memory } from '@/api/client'
import MemoryTagsEditor from '@/components/MemoryTagsEditor.vue'
import { useNotificationStore } from '@/stores/notification'
import { useUnsavedChangesStore } from '@/stores/unsavedChanges'

const apiMocks = vi.hoisted(() => ({
  updateTags: vi.fn(),
  listTags: vi.fn(),
}))

vi.mock('@/api/client', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/api/client')>()
  return {
    ...original,
    memoriesApi: {
      ...original.memoriesApi,
      updateTags: apiMocks.updateTags,
    },
    tagsApi: {
      ...original.tagsApi,
      list: apiMocks.listTags,
    },
  }
})

const createMemory = (overrides: Partial<Memory> = {}): Memory => ({
  id: 'memory-1',
  created_at: '2026-07-30T14:32:00',
  image_path: '',
  ai_summary: 'summary',
  app_name: 'unknown',
  sync_status: 'SYNCED',
  match_sources: [],
  ...overrides,
})

const mountEditor = (memory: Memory) =>
  mount(MemoryTagsEditor, { props: { memory } })

const openInput = async (wrapper: ReturnType<typeof mountEditor>) => {
  if (wrapper.find('.tags-editor__input').exists()) {
    return wrapper.get('.tags-editor__input')
  }
  await wrapper.get('.tags-editor__add').trigger('click')
  await nextTick()
  return wrapper.get('.tags-editor__input')
}

const typeAndEnter = async (
  wrapper: ReturnType<typeof mountEditor>,
  value: string,
) => {
  const input = await openInput(wrapper)
  await input.setValue(value)
  await input.trigger('keydown', { key: 'Enter' })
}

describe('MemoryTagsEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    apiMocks.listTags.mockResolvedValue({ tags: [] })
    // 默认回声：服务端按提交名单返回规范化后的标签对象
    apiMocks.updateTags.mockImplementation(async (id: string, tags: string[]) => ({
      ...createMemory({ id }),
      tags: tags.map((name, index) => ({ id: index + 1, name })),
    }))
  })

  it('renders chips without persistent remove controls and the tail add square', () => {
    const wrapper = mountEditor(createMemory({
      tags: [{ id: 1, name: '工作' }, { id: 2, name: '灵感' }],
    }))

    const chips = wrapper.findAll('.tags-editor__chip')
    expect(chips.map((chip) => chip.text())).toEqual(['工作', '灵感'])
    expect(wrapper.findAll('.tags-editor__chip-remove')).toHaveLength(0)
    expect(wrapper.get('.tags-editor__add').attributes('aria-label')).toBe('添加标签')
    expect(apiMocks.updateTags).not.toHaveBeenCalled()
  })

  it('shows only the add square when untagged', () => {
    const wrapper = mountEditor(createMemory())

    expect(wrapper.find('.tags-editor__chip').exists()).toBe(false)
    expect(wrapper.find('.tags-editor__add').exists()).toBe(true)
  })

  it('opens the input directly from + and collapses on empty blur without saving', async () => {
    const wrapper = mountEditor(createMemory())

    expect(wrapper.find('.tags-editor__input').exists()).toBe(false)
    await wrapper.get('.tags-editor__add').trigger('click')
    await nextTick()
    expect(wrapper.find('.tags-editor__input').exists()).toBe(true)

    await wrapper.get('.tags-editor__input').trigger('blur')
    await nextTick()
    expect(wrapper.find('.tags-editor__input').exists()).toBe(false)
    expect(wrapper.find('.tags-editor__add').exists()).toBe(true)
    expect(apiMocks.updateTags).not.toHaveBeenCalled()
  })

  it('saves immediately on Enter and keeps the input active for rapid entry', async () => {
    const wrapper = mountEditor(createMemory())
    await typeAndEnter(wrapper, '第一个')

    expect(apiMocks.updateTags).toHaveBeenCalledWith('memory-1', ['第一个'])
    expect(wrapper.find('.tags-editor__input').exists()).toBe(true)

    await typeAndEnter(wrapper, '第二个')
    expect(apiMocks.updateTags).toHaveBeenLastCalledWith('memory-1', ['第一个', '第二个'])
    await flushPromises()
    expect(
      wrapper.findAll('.tags-editor__chip').map((chip) => chip.text()),
    ).toEqual(['第一个', '第二个'])
  })

  it('commits pending input on blur and collapses back to +', async () => {
    const wrapper = mountEditor(createMemory())
    const input = await openInput(wrapper)
    await input.setValue('未回车的标签')

    await input.trigger('blur')
    await flushPromises()

    expect(apiMocks.updateTags).toHaveBeenCalledWith('memory-1', ['未回车的标签'])
    expect(wrapper.find('.tags-editor__input').exists()).toBe(false)
    expect(wrapper.get('.tags-editor__add').exists()).toBe(true)
  })

  it('keeps the input open when blur commits an invalid name', async () => {
    const wrapper = mountEditor(createMemory())
    const input = await openInput(wrapper)
    await input.setValue('x'.repeat(25))

    await input.trigger('blur')

    expect(apiMocks.updateTags).not.toHaveBeenCalled()
    expect(wrapper.find('.tags-editor__input').exists()).toBe(true)
    expect(wrapper.text()).toContain('标签最长 24 个字符')
  })

  it('discards pending input on Escape without saving', async () => {
    const wrapper = mountEditor(createMemory())
    const input = await openInput(wrapper)
    await input.setValue('不要了')

    await input.trigger('keydown', { key: 'Escape' })
    await nextTick()

    expect(apiMocks.updateTags).not.toHaveBeenCalled()
    expect(wrapper.find('.tags-editor__input').exists()).toBe(false)
    expect(wrapper.find('.tags-editor__chip').exists()).toBe(false)
  })

  it('does not submit while an IME composition is active', async () => {
    const wrapper = mountEditor(createMemory())
    const input = await openInput(wrapper)

    await input.setValue('会议')
    await input.trigger('compositionstart')
    await input.trigger('keydown', { key: 'Enter' })
    expect(apiMocks.updateTags).not.toHaveBeenCalled()

    await input.trigger('compositionend')
    await input.trigger('keydown', { key: 'Enter' })
    expect(apiMocks.updateTags).toHaveBeenCalledWith('memory-1', ['会议'])
  })

  it('rejects duplicates case-insensitively and overlong names inline', async () => {
    const wrapper = mountEditor(createMemory({ tags: [{ id: 1, name: 'Work' }] }))
    await typeAndEnter(wrapper, 'work')
    expect(wrapper.text()).toContain('标签已存在')
    expect(apiMocks.updateTags).not.toHaveBeenCalled()

    await typeAndEnter(wrapper, 'x'.repeat(25))
    expect(wrapper.text()).toContain('标签最长 24 个字符')
    expect(apiMocks.updateTags).not.toHaveBeenCalled()
  })

  it('enforces the 10-tags-per-memory limit', async () => {
    const wrapper = mountEditor(createMemory({
      tags: Array.from({ length: 10 }, (_, index) => ({
        id: index + 1,
        name: `tag-${index}`,
      })),
    }))

    await typeAndEnter(wrapper, 'overflow')

    expect(wrapper.text()).toContain('每条记忆最多 10 个标签')
    expect(apiMocks.updateTags).not.toHaveBeenCalled()
  })

  it('adds from suggestions without losing input focus and excludes selected', async () => {
    apiMocks.listTags.mockResolvedValue({
      tags: [
        { id: 1, name: '工作', memory_count: 3 },
        { id: 2, name: '灵感', memory_count: 1 },
      ],
    })
    const wrapper = mountEditor(createMemory({ tags: [{ id: 1, name: '工作' }] }))
    await openInput(wrapper)
    await flushPromises()

    const suggestions = wrapper.findAll('.tags-editor__suggestion')
    expect(suggestions.map((button) => button.text())).toEqual(['灵感'])

    await suggestions[0].trigger('click')
    expect(apiMocks.updateTags).toHaveBeenCalledWith('memory-1', ['工作', '灵感'])
    // 点击建议不清输入框：焦点仍在，可继续输入
    expect(wrapper.find('.tags-editor__input').exists()).toBe(true)
  })

  it('opens a right-click delete action and removes the tag immediately', async () => {
    const wrapper = mount(MemoryTagsEditor, {
      attachTo: document.body,
      props: { memory: createMemory({ tags: [{ id: 1, name: '工作' }] }) },
    })

    await wrapper.get('.tags-editor__chip').trigger('contextmenu', { clientX: 40, clientY: 40 })
    await nextTick()

    const deleteItem = document.querySelector<HTMLElement>('[role="menuitem"]')
    expect(deleteItem?.textContent).toContain('删除标签')
    deleteItem?.click()
    await flushPromises()

    expect(apiMocks.updateTags).toHaveBeenCalledWith('memory-1', [])
    expect(wrapper.find('.tags-editor__chip').exists()).toBe(false)
    expect(wrapper.find('.tags-editor__add').exists()).toBe(true)
    expect(document.querySelector('.tag-context-menu')).toBeNull()
    wrapper.unmount()
  })

  it('reverts to the server state and toasts when a save fails', async () => {
    apiMocks.updateTags.mockRejectedValue(new Error('offline'))
    const wrapper = mountEditor(createMemory({ tags: [{ id: 1, name: '工作' }] }))
    const notifications = useNotificationStore()

    await typeAndEnter(wrapper, '灵感')
    // 乐观更新先上屏
    expect(wrapper.findAll('.tags-editor__chip').map((chip) => chip.text()))
      .toEqual(['工作', '灵感'])
    await flushPromises()

    expect(notifications.notifications).toHaveLength(1)
    expect(wrapper.findAll('.tags-editor__chip').map((chip) => chip.text()))
      .toEqual(['工作'])
  })

  it('adopts server-normalized names after saving', async () => {
    apiMocks.updateTags.mockResolvedValue({
      ...createMemory(),
      tags: [{ id: 9, name: 'Work' }],
    })
    const wrapper = mountEditor(createMemory())
    await typeAndEnter(wrapper, 'work')
    await flushPromises()

    expect(apiMocks.updateTags).toHaveBeenCalledWith('memory-1', ['work'])
    expect(wrapper.findAll('.tags-editor__chip').map((chip) => chip.text()))
      .toEqual(['Work'])
  })

  it('resets when switching to another memory', async () => {
    const wrapper = mountEditor(createMemory({ tags: [{ id: 1, name: '工作' }] }))
    await openInput(wrapper)

    await wrapper.setProps({
      memory: createMemory({ id: 'memory-2', tags: [{ id: 3, name: '其它' }] }),
    })

    expect(wrapper.find('.tags-editor__input').exists()).toBe(false)
    expect(wrapper.findAll('.tags-editor__chip').map((chip) => chip.text()))
      .toEqual(['其它'])
  })

  it('commits pending input on leave without a discard dialog', async () => {
    const wrapper = mountEditor(createMemory())
    const unsavedChanges = useUnsavedChangesStore()
    await openInput(wrapper)
    await wrapper.get('.tags-editor__input').setValue('离开前')

    await expect(unsavedChanges.canLeave()).resolves.toBe(true)

    expect(apiMocks.updateTags).toHaveBeenCalledWith('memory-1', ['离开前'])
    expect(document.querySelector('[role="alertdialog"]')).toBeNull()
    expect(wrapper.find('.tags-editor__input').exists()).toBe(false)
  })
})
