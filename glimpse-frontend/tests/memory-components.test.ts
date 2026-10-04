import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import type { Memory } from '@/api/client'
import MemoryCard from '@/components/MemoryCard.vue'
import MemoryInspector from '@/components/MemoryInspector.vue'
import MemoryWall from '@/components/MemoryWall.vue'
import MemoryFilters from '@/components/MemoryFilters.vue'
import MediaGallery from '@/components/MediaGallery.vue'
import ImagePreviewModal from '@/components/ImagePreviewModal.vue'
import SearchToolbar from '@/components/SearchToolbar.vue'
import SummaryEditor from '@/components/SummaryEditor.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import OcrText from '@/components/OcrText.vue'
import MemoryAnalysisState from '@/components/MemoryAnalysisState.vue'
import MemoryDetail from '@/views/MemoryDetail.vue'
import memoryAnalysisStateSource from '@/components/MemoryAnalysisState.vue?raw'
import { useImagePreviewStore } from '@/stores/imagePreview'
import { useNotificationStore } from '@/stores/notification'
import { useUnsavedChangesStore } from '@/stores/unsavedChanges'
import { useDevStateStore } from '@/stores/devState'
import { setLanguagePreference } from '@/utils/i18n'
import { ONBOARDING_REQUEST_EVENT } from '@/utils/onboarding'
import { createEmptyMemoryFilters } from '@/utils/memory-filters'

const apiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  updateSummary: vi.fn(),
  updateUserText: vi.fn(),
}))

vi.mock('@/api/client', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/api/client')>()
  return {
    ...original,
    memoriesApi: {
      ...original.memoriesApi,
      get: apiMocks.get,
      updateSummary: apiMocks.updateSummary,
      updateUserText: apiMocks.updateUserText,
    },
  }
})

vi.mock('vue-router', async (importOriginal) => {
  const original = await importOriginal<typeof import('vue-router')>()
  return {
    ...original,
    useRoute: () => ({ params: { id: 'memory-1' } }),
    useRouter: () => ({ push: vi.fn() }),
    onBeforeRouteLeave: () => {},
    onBeforeRouteUpdate: () => {},
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
    window.localStorage.clear()
    setActivePinia(createPinia())
    setLanguagePreference('zh-CN')
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

    expect(group.classes()).toEqual(expect.arrayContaining([
      'search-toolbar__control',
      'search-toolbar__source-switcher',
      'inline-grid',
      'auto-cols-fr',
    ]))
    expect(buttons).toHaveLength(3)
    expect(buttons.map((button) => button.attributes('aria-pressed'))).toEqual(['true', 'false', 'false'])
    for (const button of buttons) {
      expect(button.classes()).toEqual(expect.arrayContaining(['h-7', 'min-h-0']))
    }
  })

  it('keeps a processing screenshot card clickable and exposes the same wait state in details', async () => {
    const processingMemory = createMemory({
      ai_summary: '',
      text_content: '',
      analysis_status: 'PROCESSING',
    })
    vi.useFakeTimers()
    try {
      const card = mount(MemoryCard, {
        props: { memory: processingMemory },
      })

      expect(card.get('.memory-card').attributes('aria-busy')).toBe('true')
      expect(card.text()).toContain('正在分析图片内容')
      expect(card.find('.memory-analysis-state__row').exists()).toBe(true)
      expect(card.find('.memory-analysis-state__bar').exists()).toBe(false)
      expect(card.findComponent(MemoryAnalysisState).exists()).toBe(true)

      await card.get('.memory-card').trigger('click')
      expect(card.emitted('select')).toBeUndefined()
      await vi.advanceTimersByTimeAsync(250)
      await card.get('.memory-card').trigger('keydown', { key: 'Enter' })
      expect(card.emitted('select')?.[0]?.[0]).toEqual(processingMemory)
      expect(card.emitted('open')?.[0]?.[0]).toEqual(processingMemory)
    } finally {
      vi.useRealTimers()
    }

    const inspector = mount(MemoryInspector, {
      props: { memory: processingMemory },
    })
    expect(inspector.findComponent(MediaGallery).exists()).toBe(true)
    expect(inspector.findComponent(MemoryAnalysisState).exists()).toBe(true)
    expect(inspector.findComponent(SummaryEditor).exists()).toBe(false)
    expect(inspector.text()).toContain('正在分析图片内容')
    expect(inspector.find('.memory-analysis-state__bar').exists()).toBe(false)
    expect(inspector.text()).toContain('查看详情')
    expect(inspector.text()).not.toContain('删除')
  })

  it('shows every image while a submitted cluster memory is still processing', () => {
    const inspector = mount(MemoryInspector, {
      props: {
        memory: createMemory({
          ai_summary: '',
          text_content: '',
          image_path: 'C:\\captures\\first.png',
          extra_images: JSON.stringify(['C:\\captures\\second.png']),
          analysis_status: 'PROCESSING',
        }),
      },
    })

    expect(inspector.findComponent(MemoryAnalysisState).exists()).toBe(true)
    expect(inspector.text()).toContain('1 / 2')
    expect(inspector.findAll('.media-gallery__thumbnail')).toHaveLength(2)
  })

  it('shows user text with an analyzing flag instead of the wait block for user-added images', () => {
    const memory = createMemory({
      ai_summary: '',
      text_content: '',
      user_text: '用户输入的说明',
      analysis_status: 'PROCESSING',
      sync_status: 'PENDING',
    })

    const card = mount(MemoryCard, { props: { memory } })
    expect(card.get('.memory-card').attributes('aria-busy')).toBe('true')
    expect(card.text()).toContain('用户输入的说明')
    expect(card.text()).toContain('正在分析图片内容')
    expect(card.findComponent(MemoryAnalysisState).exists()).toBe(true)

    const inspector = mount(MemoryInspector, { props: { memory } })
    expect(inspector.text()).toContain('用户输入的说明')
    expect(inspector.text()).toContain('正在分析图片内容')
    expect(inspector.findComponent(MemoryAnalysisState).exists()).toBe(true)
    expect(inspector.findComponent(SummaryEditor).exists()).toBe(false)
    expect(inspector.text()).toContain('复制内容')
  })

  it('flags failed analysis on user-note memories without hiding the content', () => {
    const memory = createMemory({
      ai_summary: '',
      user_text: '用户输入的说明',
      analysis_status: 'FAILED',
    })

    const card = mount(MemoryCard, { props: { memory } })
    expect(card.text()).toContain('用户输入的说明')
    expect(card.text()).toContain('图片内容分析失败')
    expect(card.find('.memory-analysis-state__row--failed').exists()).toBe(true)
    expect(card.findComponent(MemoryAnalysisState).exists()).toBe(true)

    const inspector = mount(MemoryInspector, { props: { memory } })
    expect(inspector.text()).toContain('用户输入的说明')
    expect(inspector.text()).toContain('图片内容分析失败')
    expect(inspector.findComponent(MemoryAnalysisState).exists()).toBe(true)
  })

  it('drives every analysis progress bar from the shared wall-clock phase', () => {
    expect(memoryAnalysisStateSource).toContain('startSynchronizedProgress')
    expect(memoryAnalysisStateSource).toContain('ref="progressBar"')
    expect(memoryAnalysisStateSource).not.toMatch(/\.memory-analysis-state__bar\s*\{[^}]*animation:/s)
  })

  it('renders the inline state row without a progress bar and keeps the block panel bar', () => {
    const inline = mount(MemoryAnalysisState, { props: { variant: 'inline' } })
    expect(inline.find('.memory-analysis-state__row').exists()).toBe(true)
    expect(inline.find('.memory-analysis-state__bar').exists()).toBe(false)
    expect(inline.text()).toContain('正在分析图片内容')

    const failedInline = mount(MemoryAnalysisState, { props: { variant: 'inline', status: 'FAILED' } })
    expect(failedInline.find('.memory-analysis-state__row--failed').exists()).toBe(true)
    expect(failedInline.text()).toContain('图片内容分析失败')

    const block = mount(MemoryAnalysisState)
    expect(block.find('.memory-analysis-state__bar').exists()).toBe(true)
    expect(block.text()).toContain('正在分析图片内容')
    expect(block.text()).toContain('等待AI摘要和OCR识别')
  })

  it('labels a card image that fails to load with the shared preview message', async () => {
    const card = mount(MemoryCard, { props: { memory: createMemory() } })
    await card.get('.memory-card__media img').trigger('error')
    expect(card.text()).toContain('图片预览加载失败')
    expect(card.findComponent(MemoryAnalysisState).exists()).toBe(false)
  })

  it('keeps user text visible on the detail page while analysis is running', async () => {
    apiMocks.get.mockResolvedValue(
      createMemory({
        ai_summary: '',
        user_text: '用户输入的说明',
        analysis_status: 'PROCESSING',
      }),
    )

    const wrapper = mount(MemoryDetail)
    await flushPromises()

    expect(wrapper.text()).toContain('用户输入的说明')
    expect(wrapper.text()).toContain('正在分析图片内容')
    expect(wrapper.find('.memory-analysis-state__row').exists()).toBe(false)
    expect(wrapper.find('.memory-analysis-state__bar').exists()).toBe(true)
    expect(wrapper.findComponent(SummaryEditor).exists()).toBe(false)
  })

  it('presents the compact search modes as one group before separated actions', () => {
    const wrapper = mount(SearchToolbar)
    const layout = wrapper.get('.search-toolbar__layout')
    const group = wrapper.get('.search-toolbar__source-switcher')
    const actions = wrapper.get('.search-toolbar__actions')
    const labels = group.findAll('.search-toolbar__source-button').map((button) => button.text())

    expect(layout.exists()).toBe(true)
    expect(group.attributes('aria-label')).toBe('搜索模式')
    expect(labels).toEqual(['综合', '精确', '语义'])
    expect(actions.element.previousElementSibling).toBe(group.element)
    expect(actions.get('.capture-button').element.nextElementSibling)
      .toBe(actions.get('.add-memory-button').element)
    expect(actions.element.lastElementChild).toBe(actions.get('.add-memory-button').element)
  })

  it('renders a text memory as content instead of a missing-image placeholder', () => {
    const wrapper = mount(MemoryCard, {
      props: {
        memory: createMemory({
          memory_type: 'text',
          image_path: '',
          ai_summary: '下周二和产品团队复盘搜索体验',
          text_content: undefined,
        }),
        selected: true,
      },
    })

    expect(wrapper.text()).toContain('下周二和产品团队复盘搜索体验')
    expect(wrapper.text()).not.toContain('文本记忆')
    expect(wrapper.text()).not.toContain('手动添加')
    expect(wrapper.get('.memory-card').classes()).toContain('memory-card--text')
    expect(wrapper.get('.memory-card__text-body').classes()).toContain('memory-card__text-body')
    expect(wrapper.get('.memory-card__text-content').classes()).toContain('memory-card__text-content')
    expect(wrapper.get('.memory-card__tag-area').text()).toBe('')
    expect(wrapper.get('.memory-card__text-footer time').text()).toBeTruthy()
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('svg').exists()).toBe(false)
  })

  it('omits media and OCR modules from the text-memory inspector', () => {
    const wrapper = mount(MemoryInspector, {
      props: {
        memory: createMemory({
          memory_type: 'text',
          image_path: '',
          ai_summary: '一条手动录入内容',
          text_content: undefined,
        }),
      },
    })

    expect(wrapper.text()).not.toContain('文本记忆')
    expect(wrapper.text()).toContain('记忆内容')
    expect(wrapper.text()).toContain('复制内容')
    expect(wrapper.findComponent(MediaGallery).exists()).toBe(false)
    expect(wrapper.findComponent(OcrText).exists()).toBe(false)
  })

  it('keeps compact search modes clear in English', () => {
    setLanguagePreference('en-US')
    const wrapper = mount(SearchToolbar)
    const group = wrapper.get('.search-toolbar__source-switcher')

    expect(group.attributes('aria-label')).toBe('Search mode')
    expect(group.findAll('.search-toolbar__source-button').map((button) => button.text()))
      .toEqual(['All', 'Exact', 'Semantic'])
  })

  it('shares capture styling and disabled or busy state across toolbar and empty wall', async () => {
    const toolbar = mount(SearchToolbar, {
      props: { capturing: true, captureDisabled: false },
    })
    const toolbarCapture = toolbar.get<HTMLButtonElement>('.capture-button')
    const busyToolbarText = toolbarCapture.text()

    expect(toolbarCapture.attributes('aria-busy')).toBe('true')
    expect(toolbarCapture.attributes('aria-label')).toBe('截图，处理中...')
    expect(toolbarCapture.element.disabled).toBe(true)
    expect(toolbarCapture.find('.animate-spin').exists()).toBe(true)
    expect(toolbarCapture.classes()).toEqual(expect.arrayContaining(['h-8']))
    expect(busyToolbarText).toContain('截图')

    await toolbar.setProps({ capturing: false })
    expect(toolbarCapture.attributes('aria-busy')).toBe('false')
    expect(toolbarCapture.attributes('aria-label')).toBeUndefined()
    expect(toolbarCapture.element.disabled).toBe(false)
    expect(toolbarCapture.text()).toBe(busyToolbarText)

    const wall = mount(MemoryWall, {
      props: {
        memories: [],
        total: 0,
        capturing: true,
        captureDisabled: false,
      },
    })
    const emptyCapture = wall.get<HTMLButtonElement>('.capture-button')

    expect(wall.get('.memory-wall__capture-icon').exists()).toBe(true)
    expect(emptyCapture.attributes('aria-busy')).toBe('true')
    expect(emptyCapture.attributes('aria-label')).toBe('截图，处理中...')
    expect(emptyCapture.element.disabled).toBe(true)
    expect(emptyCapture.find('.animate-spin').exists()).toBe(true)
    expect(emptyCapture.classes()).toContain('h-10')

    await wall.setProps({ capturing: false, captureDisabled: true })
    expect(emptyCapture.attributes('aria-busy')).toBe('false')
    expect(emptyCapture.element.disabled).toBe(true)
    expect(emptyCapture.text()).toContain('截图')
  })

  it('compacts the filter as soon as the memory wall scrolls upward', async () => {
    const pane = document.createElement('div')
    pane.className = 'home-memory-pane'
    const toolbar = document.createElement('div')
    toolbar.className = 'search-toolbar'
    const host = document.createElement('div')
    pane.append(toolbar, host)
    document.body.append(pane)

    const wrapper = mount(MemoryWall, {
      props: { memories: [], total: 0 },
      attachTo: host,
    })
    await wrapper.vm.$nextTick()
    const header = wrapper.get('.memory-wall__header').element
    vi.spyOn(toolbar, 'getBoundingClientRect').mockReturnValue(DOMRect.fromRect({ height: 80 }))
    vi.spyOn(pane, 'getBoundingClientRect').mockReturnValue(DOMRect.fromRect({ height: 600 }))
    vi.spyOn(header, 'getBoundingClientRect').mockReturnValue(DOMRect.fromRect({ y: 160, height: 32 }))

    pane.scrollTop = 24
    pane.dispatchEvent(new Event('scroll'))
    await wrapper.vm.$nextTick()

    expect(wrapper.get('.memory-wall__header').classes()).toContain('memory-wall__header--compact')
    expect(wrapper.get('.memory-filters').classes()).toContain('memory-filters--compact')
  })

  it('applies a calendar day through the extensible memory filter panel', async () => {
    const wrapper = mount(MemoryFilters, {
      props: { modelValue: createEmptyMemoryFilters() },
      attachTo: document.body,
    })

    await wrapper.get('.memory-filters__trigger').trigger('click')
    expect(wrapper.find('.memory-calendar').exists()).toBe(false)
    await wrapper.get('.memory-filters__date-toggle').trigger('click')
    const now = new Date()
    const pad = (value: number) => String(value).padStart(2, '0')
    const today = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
    await wrapper.get(`[data-date="${today}"]`).trigger('pointerdown')
    window.dispatchEvent(new Event('pointerup'))
    await flushPromises()

    const applied = wrapper.emitted('apply')?.[0]?.[0]
    expect(applied).toMatchObject({
      datePreset: 'custom',
      dateFrom: today,
      dateTo: today,
      sourceChannels: [],
      contentTypes: [],
    })
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)

    await wrapper.get('.memory-filters__actions .btn-primary').trigger('click')
    expect(wrapper.emitted('apply')).toHaveLength(2)
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('collapses dates by default and preserves the selected period across reopening', async () => {
    const filters = {
      ...createEmptyMemoryFilters(),
      datePreset: 'custom' as const,
      dateFrom: '2026-09-10',
      dateTo: '2026-09-12',
    }
    const wrapper = mount(MemoryFilters, {
      props: { modelValue: filters },
      attachTo: document.body,
    })

    await wrapper.get('.memory-filters__trigger').trigger('click')
    const toggle = wrapper.get('.memory-filters__date-toggle')
    const summary = toggle.text()
    expect(summary).toContain('2026')
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(wrapper.find('.memory-calendar').exists()).toBe(false)

    await toggle.trigger('click')
    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(wrapper.get(`#${toggle.attributes('aria-controls')}`).isVisible()).toBe(true)
    expect(wrapper.get('[data-date="2026-09-10"]').classes()).toContain('memory-calendar__day--endpoint')
    await toggle.trigger('click')
    expect(toggle.text()).toBe(summary)
    expect(wrapper.find('.memory-calendar').exists()).toBe(false)
    expect(wrapper.emitted('apply')).toBeUndefined()

    await toggle.trigger('click')
    await wrapper.get('.memory-filters__close').trigger('click')
    await wrapper.get('.memory-filters__trigger').trigger('click')
    expect(wrapper.get('.memory-filters__date-toggle').attributes('aria-expanded')).toBe('false')
    expect(wrapper.get('.memory-filters__date-toggle').text()).toBe(summary)
    expect(wrapper.find('.memory-calendar').exists()).toBe(false)
    wrapper.unmount()
  })

  it('applies a content type through the shared memory filter panel', async () => {
    const wrapper = mount(MemoryFilters, {
      props: { modelValue: createEmptyMemoryFilters() },
      attachTo: document.body,
    })

    await wrapper.get('.memory-filters__trigger').trigger('click')
    const contentTypes = wrapper.findAll<HTMLInputElement>('.memory-filters__content-type')
    expect(contentTypes.map((input) => input.attributes('type'))).toEqual(['checkbox', 'checkbox'])
    expect(contentTypes.map((input) => input.element.value)).toEqual(['screenshot', 'text'])
    await contentTypes[0].trigger('click')
    expect(wrapper.emitted('apply')?.[0]?.[0]).toMatchObject({ contentTypes: ['screenshot'] })
    await contentTypes[1].trigger('click')
    expect(wrapper.emitted('apply')?.[1]?.[0]).toMatchObject({ contentTypes: ['screenshot', 'text'] })
    await wrapper.get('.memory-filters__actions .btn-primary').trigger('click')

    expect(wrapper.emitted('apply')?.[2]?.[0]).toMatchObject({
      datePreset: 'all',
      dateFrom: '',
      dateTo: '',
      contentTypes: ['screenshot', 'text'],
    })
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
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

  it('closes the DEV panel on outside pointerdown and Escape regardless of focus', async () => {
    const wrapper = mount(SearchToolbar, { attachTo: document.body })
    const panel = wrapper.get('details')

    ;(panel.element as HTMLDetailsElement).open = true
    await panel.trigger('toggle')
    expect(wrapper.emitted('debug-panel-change')?.at(-1)).toEqual([true])

    // 点击面板外（不触发 focusout 的空白场景）：全局 pointerdown 捕获应关闭。
    // jsdom 无 PointerEvent 构造器，用 MouseEvent 但保持 type 为 pointerdown。
    document.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, composed: true }))
    await nextTick()
    expect((panel.element as HTMLDetailsElement).open).toBe(false)
    expect(wrapper.emitted('debug-panel-change')?.at(-1)).toEqual([false])

    // 重新打开后按 ESC（document 级捕获）：面板内外的焦点位置都不影响关闭。
    ;(panel.element as HTMLDetailsElement).open = true
    await panel.trigger('toggle')
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await nextTick()
    expect((panel.element as HTMLDetailsElement).open).toBe(false)
    expect(wrapper.emitted('debug-panel-change')?.at(-1)).toEqual([false])

    wrapper.unmount()
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
    expect(editButton.classes()).toEqual(expect.arrayContaining(['h-8', 'w-28', 'text-sm', 'font-semibold']))

    await editButton.trigger('click')
    await flushPromises()

    const frame = wrapper.get('.summary-editor__compact-frame')
    expect(frame.attributes('style')).toContain('height: 220px')
    expect(document.activeElement).toBe(originalControl)
    for (const button of wrapper.findAll('.summary-editor__edit-action')) {
      expect(button.classes()).toEqual(expect.arrayContaining(['h-8', 'w-28', 'text-sm', 'font-semibold']))
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

  it('shows the user note instead of the AI summary and saves through user_text', async () => {
    apiMocks.updateUserText.mockResolvedValue(
      createMemory({ user_text: 'Revised note' }),
    )
    const wrapper = mount(SummaryEditor, {
      props: {
        memory: createMemory({ user_text: '我的原始说明' }),
      },
    })

    expect(wrapper.text()).toContain('记忆内容')
    expect(wrapper.text()).toContain('编辑内容')
    expect(wrapper.text()).toContain('我的原始说明')
    expect(wrapper.text()).not.toContain('A payment screen')

    await wrapper.get('.summary-editor__edit-action').trigger('click')
    await wrapper.get('textarea').setValue('Revised note')
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter', ctrlKey: true })
    await flushPromises()

    expect(apiMocks.updateUserText).toHaveBeenCalledWith('memory-1', 'Revised note')
    expect(apiMocks.updateSummary).not.toHaveBeenCalled()
    expect(wrapper.find('textarea').exists()).toBe(false)
  })

  it('renders the user note on wall cards in place of the AI summary', () => {
    const wrapper = mount(MemoryCard, {
      props: {
        memory: createMemory({ user_text: '卡片上的用户说明' }),
        selected: true,
      },
    })

    expect(wrapper.text()).toContain('卡片上的用户说明')
    expect(wrapper.text()).not.toContain('A payment screen')
  })

  it('stays quiet when the index is synced and flags only unsynced states', () => {
    const synced = mount(SummaryEditor, {
      props: { memory: createMemory({ sync_status: 'SYNCED' }) },
    })
    expect(synced.text()).not.toContain('已同步')
    expect(synced.text()).not.toContain('语义索引')

    const pending = mount(SummaryEditor, {
      props: { memory: createMemory({ user_text: '我的说明', sync_status: 'PENDING' }) },
    })
    expect(pending.text()).toContain('正在更新语义索引')
  })

  it('overrides displayed analysis and sync states from the dev panel store', async () => {
    const devState = useDevStateStore()
    const memory = createMemory({ user_text: '用户输入的说明' })

    const card = mount(MemoryCard, { props: { memory } })
    expect(card.text()).not.toContain('正在分析图片内容')
    expect(card.text()).not.toContain('图片内容分析失败')

    devState.setAnalysisOverride('processing')
    await nextTick()
    expect(card.text()).toContain('正在分析图片内容')
    expect(card.findComponent(MemoryAnalysisState).exists()).toBe(true)

    devState.setAnalysisOverride('failed')
    await nextTick()
    expect(card.text()).toContain('图片内容分析失败')

    devState.setAnalysisOverride('none')
    devState.setSyncOverride('pending')
    await nextTick()
    const editor = mount(SummaryEditor, { props: { memory } })
    expect(editor.text()).toContain('正在更新语义索引')

    devState.setSyncOverride('none')
    await nextTick()
    expect(editor.text()).not.toContain('语义索引')
    expect(window.localStorage.getItem('glimpse.devMemoryStateOverride')).toBeNull()
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
