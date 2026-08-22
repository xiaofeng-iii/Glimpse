import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import type { Memory } from '@/api/client'
import MemoryCard from '@/components/MemoryCard.vue'
import MediaGallery from '@/components/MediaGallery.vue'
import ImagePreviewModal from '@/components/ImagePreviewModal.vue'
import SearchToolbar from '@/components/SearchToolbar.vue'
import SummaryEditor from '@/components/SummaryEditor.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { useImagePreviewStore } from '@/stores/imagePreview'
import { useNotificationStore } from '@/stores/notification'
import { useUnsavedChangesStore } from '@/stores/unsavedChanges'
import { ONBOARDING_REQUEST_EVENT } from '@/utils/onboarding'

const apiMocks = vi.hoisted(() => ({
  updateSummary: vi.fn(),
}))

vi.mock('@/api/client', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/api/client')>()
  return {
    ...original,
    memoriesApi: {
      ...original.memoriesApi,
      updateSummary: apiMocks.updateSummary,
    },
  }
})

const createMemory = (overrides: Partial<Memory> = {}): Memory => ({
  id: 'memory-1',
  created_at: '2026-07-30T14:32:00',
  image_path: 'C:\\captures\\memory.png',
  ai_summary: 'A payment screen',
  app_name: 'Design Tool',
  text_content: 'Payment failed',
  extra_images: '[]',
  sync_status: 'SYNCED',
  match_sources: ['精确', '语义'],
  ...overrides,
})

describe('memory components', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('shows exact and semantic badges for each search match combination only', async () => {
    const wrapper = mount(MemoryCard, {
      props: {
        memory: createMemory({ match_sources: ['精确'] }),
        searching: true,
      },
    })

    expect(wrapper.text()).toContain('精确')
    expect(wrapper.text()).not.toContain('语义')
    expect(wrapper.text()).not.toContain('Design Tool')

    await wrapper.setProps({ memory: createMemory({ match_sources: ['语义'] }) })
    expect(wrapper.text()).not.toContain('精确')
    expect(wrapper.text()).toContain('语义')

    await wrapper.setProps({ memory: createMemory({ match_sources: ['语义', '精确'] }) })
    expect(wrapper.text().indexOf('精确')).toBeLessThan(wrapper.text().indexOf('语义'))

    await wrapper.setProps({ searching: false })
    expect(wrapper.text()).not.toContain('精确')
    expect(wrapper.text()).not.toContain('语义')
  })

  it('shows search ranking details only while the DEV panel is expanded', async () => {
    const wrapper = mount(MemoryCard, {
      props: {
        memory: createMemory({
          search_debug: { mode: 'hybrid', semantic_distance: 0.1234, rrf_score: 0.56789 },
        }),
        searching: true,
        showDebug: false,
      },
    })

    expect(wrapper.text()).not.toContain('0.1234')
    expect(wrapper.text()).not.toContain('0.56789')

    await wrapper.setProps({ showDebug: true })
    expect(wrapper.text()).toContain('0.1234')
    expect(wrapper.text()).toContain('0.56789')
  })

  it('keeps search source segments equally inset inside their frame', () => {
    const wrapper = mount(SearchToolbar)
    const group = wrapper.get('.search-toolbar__source-switcher')
    const buttons = group.findAll('.search-toolbar__source-button')

    expect(group.classes()).toEqual(expect.arrayContaining(['inline-grid', 'auto-cols-fr', 'p-[3px]']))
    expect(buttons).toHaveLength(3)
    expect(buttons.map((button) => button.attributes('aria-pressed'))).toEqual(['true', 'false', 'false'])
    for (const button of buttons) {
      expect(button.classes()).toEqual(expect.arrayContaining(['h-9', 'min-h-0']))
    }
  })

  it('closes the DEV panel before requesting the onboarding guide', async () => {
    const wrapper = mount(SearchToolbar)
    const panel = wrapper.get('details')
    const requestHandler = vi.fn(() => {
      expect((panel.element as HTMLDetailsElement).open).toBe(false)
    })
    window.addEventListener(ONBOARDING_REQUEST_EVENT, requestHandler)

    try {
      (panel.element as HTMLDetailsElement).open = true
      await panel.trigger('toggle')
      expect(wrapper.emitted('debug-panel-change')?.at(-1)).toEqual([true])

      await wrapper.get('[data-testid="show-onboarding"]').trigger('click')

      expect((panel.element as HTMLDetailsElement).open).toBe(false)
      expect(wrapper.emitted('debug-panel-change')?.at(-1)).toEqual([false])
      expect(requestHandler).toHaveBeenCalledTimes(1)
    } finally {
      window.removeEventListener(ONBOARDING_REQUEST_EVENT, requestHandler)
    }
  })

  it('opens the shared in-app preview from a double-click', async () => {
    const wrapper = mount(MediaGallery, {
      props: { memory: createMemory() },
    })
    const previewStore = useImagePreviewStore()

    await wrapper.get('[role="button"]').trigger('dblclick')

    expect(previewStore.isOpen).toBe(true)
    expect(previewStore.images).toHaveLength(1)
  })

  it('opens the shared in-app preview from Enter and Space', async () => {
    const wrapper = mount(MediaGallery, {
      props: { memory: createMemory() },
    })
    const previewStore = useImagePreviewStore()
    const target = wrapper.get('[role="button"]')

    await target.trigger('keydown', { key: 'Enter' })
    expect(previewStore.isOpen).toBe(true)

    previewStore.close()
    await target.trigger('keydown', { key: ' ' })
    expect(previewStore.isOpen).toBe(true)
  })

  it('supports arrow navigation, Escape, scroll lock, and focus restoration in the preview modal', async () => {
    mount(ImagePreviewModal)
    const previewStore = useImagePreviewStore()
    const origin = document.createElement('button')
    document.body.appendChild(origin)
    origin.focus()

    previewStore.open(['image-1.png', 'image-2.png', 'image-3.png'], 0, origin)
    await flushPromises()

    expect(document.querySelector('[role="dialog"][aria-modal="true"]')).not.toBeNull()
    expect(document.body.style.overflow).toBe('hidden')
    expect(document.documentElement.style.overflow).toBe('hidden')

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }))
    expect(previewStore.currentIndex).toBe(1)
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft', bubbles: true }))
    expect(previewStore.currentIndex).toBe(0)

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await flushPromises()
    expect(previewStore.isOpen).toBe(false)
    expect(document.activeElement).toBe(origin)
    expect(document.body.style.overflow).toBe('')
    expect(document.documentElement.style.overflow).toBe('')

    origin.remove()
  })

  it('keeps one compact summary text node and identical text geometry classes across edit state', async () => {
    const wrapper = mount(SummaryEditor, {
      props: { memory: createMemory(), compact: true },
    })
    const originalControl = wrapper.get('textarea').element as HTMLTextAreaElement
    const originalClassName = originalControl.className

    expect(originalControl.readOnly).toBe(true)
    await wrapper.get('.summary-editor__edit-action').trigger('click')
    await flushPromises()

    const editingControl = wrapper.get('textarea').element as HTMLTextAreaElement
    expect(editingControl).toBe(originalControl)
    expect(editingControl.readOnly).toBe(false)
    expect(editingControl.className).toBe(originalClassName)

    await wrapper.get('textarea').trigger('keydown', { key: 'Escape' })
    const cancelledControl = wrapper.get('textarea').element as HTMLTextAreaElement
    expect(cancelledControl).toBe(originalControl)
    expect(cancelledControl.readOnly).toBe(true)
  })

  it('grows a compact summary within its reading cap and keeps all header actions proportionate', async () => {
    const wrapper = mount(SummaryEditor, {
      props: { memory: createMemory({ ai_summary: 'A longer summary' }), compact: true },
      attachTo: document.body,
    })
    const originalControl = wrapper.get('textarea').element as HTMLTextAreaElement
    let measuredHeight = 220
    Object.defineProperty(originalControl, 'scrollHeight', {
      configurable: true,
      get: () => measuredHeight,
    })

    const editButton = wrapper.get('.summary-editor__edit-action')
    expect(editButton.classes()).toEqual(expect.arrayContaining(['h-10', 'w-28', 'text-sm', 'font-semibold', 'leading-5']))

    await editButton.trigger('click')
    await flushPromises()

    const frame = wrapper.get('.summary-editor__compact-frame')
    expect(frame.attributes('style')).toContain('height: 220px')
    expect(document.activeElement).toBe(originalControl)
    for (const button of wrapper.findAll('.summary-editor__edit-action')) {
      expect(button.classes()).toEqual(expect.arrayContaining(['h-10', 'w-28', 'text-sm', 'font-semibold', 'leading-5']))
    }

    measuredHeight = 600
    await wrapper.get('textarea').setValue('A much longer summary that needs more room')
    await flushPromises()

    expect(frame.attributes('style')).toContain('height: 256px')
    expect(wrapper.get('textarea').classes()).toContain('overflow-y-auto')

    await wrapper.get('textarea').trigger('keydown', { key: 'Escape' })
    await flushPromises()
    expect(wrapper.get('textarea').element.readOnly).toBe(true)
    expect(wrapper.get('textarea').attributes('tabindex')).toBe('0')
    expect(frame.classes()).toContain('summary-editor__compact-frame--scrollable')
    wrapper.get('textarea').element.focus()
    expect(document.activeElement).toBe(wrapper.get('textarea').element)
  })

  it('validates blank, unchanged, and oversized summaries before saving', async () => {
    const wrapper = mount(SummaryEditor, {
      props: { memory: createMemory() },
    })
    await wrapper.get('.summary-editor__edit-action').trigger('click')
    const textarea = wrapper.get('textarea')
    const saveButton = () => wrapper.findAll('.summary-editor__edit-action')[1]

    await textarea.setValue('   ')
    expect(wrapper.text()).toContain('摘要不能为空')
    expect(saveButton().attributes('disabled')).toBeDefined()

    await textarea.setValue(' A payment screen ')
    expect(saveButton().attributes('disabled')).toBeDefined()

    await textarea.setValue('x'.repeat(4001))
    expect(wrapper.text()).toContain('摘要不能超过 4000 字')
    expect(saveButton().attributes('disabled')).toBeDefined()
    expect(apiMocks.updateSummary).not.toHaveBeenCalled()
  })

  it('saves with Ctrl+Enter and cancels with Escape', async () => {
    apiMocks.updateSummary.mockResolvedValue(createMemory({ ai_summary: 'Revised summary' }))
    const wrapper = mount(SummaryEditor, {
      props: { memory: createMemory() },
    })

    await wrapper.get('.summary-editor__edit-action').trigger('click')
    await wrapper.get('textarea').setValue('Revised summary')
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter', ctrlKey: true })
    await flushPromises()

    expect(apiMocks.updateSummary).toHaveBeenCalledWith('memory-1', 'Revised summary')
    expect(wrapper.find('textarea').exists()).toBe(false)

    await wrapper.get('.summary-editor__edit-action').trigger('click')
    await wrapper.get('textarea').setValue('Discard me')
    await wrapper.get('textarea').trigger('keydown', { key: 'Escape' })
    expect(wrapper.find('textarea').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Discard me')
  })

  it('asks before leaving with a dirty summary and resolves both choices', async () => {
    const wrapper = mount(SummaryEditor, {
      props: { memory: createMemory() },
    })
    const unsavedChanges = useUnsavedChangesStore()

    await wrapper.get('.summary-editor__edit-action').trigger('click')
    await wrapper.get('textarea').setValue('Unsaved summary')

    const keepEditing = unsavedChanges.canLeave()
    await flushPromises()
    const firstDialog = document.querySelector<HTMLElement>('[role="alertdialog"]')
    expect(firstDialog).not.toBeNull()
    const keepButton = [...firstDialog!.querySelectorAll('button')]
      .find((button) => button.textContent?.includes('继续编辑'))
    keepButton!.click()
    await expect(keepEditing).resolves.toBe(false)
    expect(wrapper.get('textarea').element.value).toBe('Unsaved summary')

    const discardChanges = unsavedChanges.canLeave()
    await flushPromises()
    const secondDialog = document.querySelector<HTMLElement>('[role="alertdialog"]')
    const discardButton = [...secondDialog!.querySelectorAll('button')]
      .find((button) => button.textContent?.includes('放弃修改'))
    discardButton!.click()
    await expect(discardChanges).resolves.toBe(true)
    expect(wrapper.find('textarea').exists()).toBe(false)
  })

  it('keeps a failed summary draft and reports the failure inline and as a toast', async () => {
    apiMocks.updateSummary.mockRejectedValue(new Error('offline'))
    const wrapper = mount(SummaryEditor, {
      props: { memory: createMemory() },
    })
    const notifications = useNotificationStore()

    await wrapper.get('button').trigger('click')
    await wrapper.get('textarea').setValue('A revised payment summary')
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter', ctrlKey: true })
    await flushPromises()

    expect(wrapper.get('textarea').element.value).toBe('A revised payment summary')
    expect(wrapper.text()).toContain('草稿已保留')
    expect(notifications.notifications).toHaveLength(1)
  })

  it('focuses the safe dialog action and restores focus after close', async () => {
    const origin = document.createElement('button')
    document.body.appendChild(origin)
    origin.focus()
    const wrapper = mount(ConfirmDialog, {
      attachTo: document.body,
      props: {
        open: false,
        title: 'Discard changes?',
        description: 'Unsaved changes will be lost.',
        confirmLabel: 'Discard',
        cancelLabel: 'Keep editing',
      },
    })

    await wrapper.setProps({ open: true })
    await flushPromises()
    const cancelButton = document.querySelector<HTMLButtonElement>('[role="alertdialog"] .btn-secondary')
    expect(document.activeElement).toBe(cancelButton)

    await wrapper.setProps({ open: false })
    await flushPromises()
    expect(document.activeElement).toBe(origin)

    wrapper.unmount()
    origin.remove()
  })
})
