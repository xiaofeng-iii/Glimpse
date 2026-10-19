import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import type { Memory } from '@/api/client'
import MemoryTagsEditor from '@/components/MemoryTagsEditor.vue'
import { useMemoriesStore } from '@/stores/memories'
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

const enterEditing = async (wrapper: ReturnType<typeof mountEditor>) => {
  await wrapper.get('.tags-editor__edit-action').trigger('click')
  await nextTick()
}

const typeAndEnter = async (
  wrapper: ReturnType<typeof mountEditor>,
  value: string,
) => {
  await wrapper.get('.tags-editor__input').setValue(value)
  await wrapper.get('.tags-editor__input').trigger('keydown', { key: 'Enter' })
}

describe('MemoryTagsEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    apiMocks.listTags.mockResolvedValue({ tags: [] })
    apiMocks.updateTags.mockImplementation(async (id: string, tags: string[]) => ({
      ...createMemory({ id }),
      tags: tags.map((name, index) => ({ id: index + 1, name })),
    }))
  })

  it('shows existing tags read-only and an empty hint when untagged', async () => {
    const tagged = mountEditor(createMemory({
      tags: [{ id: 1, name: '工作' }, { id: 2, name: '灵感' }],
    }))
    expect(tagged.get('[data-testid="tags-readonly"]').text()).toContain('工作')
    expect(tagged.get('[data-testid="tags-readonly"]').text()).toContain('灵感')

    const untagged = mountEditor(createMemory())
    expect(untagged.text()).toContain('未设置标签')
  })

  it('loads the tag catalog when entering edit mode', async () => {
    apiMocks.listTags.mockResolvedValue({
      tags: [{ id: 1, name: '工作', memory_count: 3 }],
    })
    const wrapper = mountEditor(createMemory())
    await enterEditing(wrapper)

    expect(apiMocks.listTags).toHaveBeenCalledTimes(1)
    await flushPromises()
    expect(wrapper.text()).toContain('已有标签')
    expect(wrapper.get('.tags-editor__suggestion').text()).toBe('工作')
  })

  it('adds a tag on Enter and renders it as a removable chip', async () => {
    const wrapper = mountEditor(createMemory())
    await enterEditing(wrapper)
    await typeAndEnter(wrapper, '  工作  ')

    expect(wrapper.get('.tags-editor__chip--editable').text()).toContain('工作')
    expect(wrapper.get<HTMLInputElement>('.tags-editor__input').element.value).toBe('')

    await wrapper.get('.tags-editor__chip-remove').trigger('click')
    expect(wrapper.find('.tags-editor__chip--editable').exists()).toBe(false)
  })

  it('does not submit while an IME composition is active', async () => {
    const wrapper = mountEditor(createMemory())
    await enterEditing(wrapper)

    const input = wrapper.get('.tags-editor__input')
    await input.setValue('会议')
    await input.trigger('compositionstart')
    await input.trigger('keydown', { key: 'Enter' })
    expect(wrapper.find('.tags-editor__chip--editable').exists()).toBe(false)

    await input.trigger('compositionend')
    await input.trigger('keydown', { key: 'Enter' })
    expect(wrapper.get('.tags-editor__chip--editable').text()).toContain('会议')
  })

  it('rejects duplicates case-insensitively and overlong names inline', async () => {
    const wrapper = mountEditor(createMemory({ tags: [{ id: 1, name: 'Work' }] }))
    await enterEditing(wrapper)

    await typeAndEnter(wrapper, 'work')
    expect(wrapper.text()).toContain('标签已存在')
    expect(wrapper.findAll('.tags-editor__chip--editable')).toHaveLength(1)

    await typeAndEnter(wrapper, 'x'.repeat(25))
    expect(wrapper.text()).toContain('标签最长 24 个字符')
  })

  it('enforces the 10-tags-per-memory limit', async () => {
    const wrapper = mountEditor(createMemory({
      tags: Array.from({ length: 10 }, (_, index) => ({
        id: index + 1,
        name: `tag-${index}`,
      })),
    }))
    await enterEditing(wrapper)

    await typeAndEnter(wrapper, 'overflow')
    expect(wrapper.text()).toContain('每条记忆最多 10 个标签')
    expect(wrapper.findAll('.tags-editor__chip--editable')).toHaveLength(10)
  })

  it('excludes already-selected tags from suggestions', async () => {
    apiMocks.listTags.mockResolvedValue({
      tags: [
        { id: 1, name: '工作', memory_count: 3 },
        { id: 2, name: '灵感', memory_count: 1 },
      ],
    })
    const wrapper = mountEditor(createMemory({ tags: [{ id: 1, name: '工作' }] }))
    await enterEditing(wrapper)
    await flushPromises()

    const suggestions = wrapper.findAll('.tags-editor__suggestion')
    expect(suggestions).toHaveLength(1)
    expect(suggestions[0].text()).toBe('灵感')

    await suggestions[0].trigger('click')
    expect(wrapper.findAll('.tags-editor__chip--editable')).toHaveLength(2)
    expect(wrapper.findAll('.tags-editor__suggestion')).toHaveLength(0)
  })

  it('saves the full replacement and adopts server-normalized tags', async () => {
    const serverMemory = {
      ...createMemory(),
      tags: [{ id: 9, name: 'Work' }],
    }
    apiMocks.updateTags.mockResolvedValue(serverMemory)
    const wrapper = mountEditor(createMemory())
    await enterEditing(wrapper)
    await typeAndEnter(wrapper, 'work')

    const saveButton = wrapper
      .findAll('.tags-editor__edit-actions button')
      .find((button) => button.text() === '保存')
    await saveButton!.trigger('click')
    await flushPromises()

    expect(apiMocks.updateTags).toHaveBeenCalledWith('memory-1', ['work'])
    expect(wrapper.find('.tags-editor__input').exists()).toBe(false)
    // 真实界面里父级绑定的是 store 实体：保存后 prop 换成服务端返回值。
    await wrapper.setProps({ memory: serverMemory })
    expect(wrapper.get('[data-testid="tags-readonly"]').text()).toContain('Work')
  })

  it('saves an empty list to clear all tags', async () => {
    const wrapper = mountEditor(createMemory({ tags: [{ id: 1, name: '工作' }] }))
    await enterEditing(wrapper)
    await wrapper.get('.tags-editor__chip-remove').trigger('click')

    const saveButton = wrapper
      .findAll('.tags-editor__edit-actions button')
      .find((button) => button.text() === '保存')
    await saveButton!.trigger('click')
    await flushPromises()

    expect(apiMocks.updateTags).toHaveBeenCalledWith('memory-1', [])
  })

  it('keeps the draft and reports failure when saving fails', async () => {
    apiMocks.updateTags.mockRejectedValue(new Error('offline'))
    const wrapper = mountEditor(createMemory())
    const notifications = useNotificationStore()
    await enterEditing(wrapper)
    await typeAndEnter(wrapper, '工作')

    const saveButton = wrapper
      .findAll('.tags-editor__edit-actions button')
      .find((button) => button.text() === '保存')
    await saveButton!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('保存失败')
    expect(wrapper.get('.tags-editor__chip--editable').text()).toContain('工作')
    expect(notifications.notifications.length).toBeGreaterThan(0)
  })

  it('commits pending input on save instead of silently dropping it', async () => {
    const wrapper = mountEditor(createMemory())
    await enterEditing(wrapper)
    await wrapper.get('.tags-editor__input').setValue('未回车的标签')

    const saveButton = wrapper
      .findAll('.tags-editor__edit-actions button')
      .find((button) => button.text() === '保存')
    await saveButton!.trigger('click')
    await flushPromises()

    expect(apiMocks.updateTags).toHaveBeenCalledWith('memory-1', ['未回车的标签'])
  })

  it('resets editing state when switching to another memory', async () => {
    const wrapper = mountEditor(createMemory())
    await enterEditing(wrapper)
    await typeAndEnter(wrapper, '草稿标签')

    await wrapper.setProps({
      memory: createMemory({ id: 'memory-2', tags: [{ id: 3, name: '其它' }] }),
    })

    expect(wrapper.find('.tags-editor__input').exists()).toBe(false)
    expect(wrapper.get('[data-testid="tags-readonly"]').text()).toContain('其它')
  })

  it('asks before leaving with a dirty draft and resolves both choices', async () => {
    const wrapper = mountEditor(createMemory())
    const unsavedChanges = useUnsavedChangesStore()
    await enterEditing(wrapper)
    await typeAndEnter(wrapper, '未保存')

    const keepEditing = unsavedChanges.canLeave()
    await flushPromises()
    const firstDialog = document.querySelector<HTMLElement>('[role="alertdialog"]')
    expect(firstDialog).not.toBeNull()
    const keepButton = [...firstDialog!.querySelectorAll('button')]
      .find((button) => button.textContent?.includes('继续编辑'))
    keepButton!.click()
    await expect(keepEditing).resolves.toBe(false)
    expect(wrapper.get('.tags-editor__chip--editable').text()).toContain('未保存')

    const discardChanges = unsavedChanges.canLeave()
    await flushPromises()
    const secondDialog = document.querySelector<HTMLElement>('[role="alertdialog"]')
    const discardButton = [...secondDialog!.querySelectorAll('button')]
      .find((button) => button.textContent?.includes('放弃修改'))
    discardButton!.click()
    await expect(discardChanges).resolves.toBe(true)
    expect(wrapper.find('.tags-editor__input').exists()).toBe(false)
  })

  it('leaves immediately when there is nothing to save', async () => {
    const wrapper = mountEditor(createMemory())
    const unsavedChanges = useUnsavedChangesStore()
    await enterEditing(wrapper)

    await expect(unsavedChanges.canLeave()).resolves.toBe(true)
  })
})
