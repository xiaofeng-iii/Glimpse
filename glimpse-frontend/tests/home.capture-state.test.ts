import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import Home from '@/views/Home.vue'
import { useBackendStatusStore } from '@/stores/backendStatus'
import { useMemoriesStore } from '@/stores/memories'

const mocks = vi.hoisted(() => ({
  getSettings: vi.fn(),
  triggerCapture: vi.fn(),
  whenBackendRuntimeReady: vi.fn(),
}))

vi.mock('@/api/client', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/api/client')>()
  return {
    ...original,
    screenshotApi: {
      ...original.screenshotApi,
      triggerAndAnalyze: mocks.triggerCapture,
    },
    settingsApi: {
      ...original.settingsApi,
      get: mocks.getSettings,
    },
  }
})

vi.mock('@/config/runtime', () => ({
  whenBackendRuntimeReady: mocks.whenBackendRuntimeReady,
}))

vi.mock('@/platform/desktop', () => ({
  getDesktopWindowMinimized: vi.fn(),
  isDesktopShell: () => false,
  minimizeDesktopWindow: vi.fn(),
}))

describe('Home capture state wiring', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.whenBackendRuntimeReady.mockReturnValue(new Promise(() => {}))
    mocks.getSettings.mockResolvedValue({ hotkeys: {}, cluster: {} })
  })

  it('keeps toolbar and empty-state capture actions on the same disabled and busy state', async () => {
    let finishCapture!: (result: { success: boolean; clustered: boolean }) => void
    mocks.triggerCapture.mockReturnValue(new Promise((resolve) => {
      finishCapture = resolve
    }))

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', name: 'home', component: Home }],
    })
    await router.push('/')
    await router.isReady()
    const pinia = createPinia()
    const wrapper = mount({ template: '<router-view />' }, {
      global: {
        plugins: [pinia, router],
        stubs: {
          SearchToolbar: {
            name: 'SearchToolbar',
            props: ['modelValue', 'capturing', 'captureDisabled'],
            emits: ['capture', 'update:modelValue'],
            template: '<div data-testid="search-toolbar" />',
          },
          MemoryWall: {
            name: 'MemoryWall',
            props: ['capturing', 'captureDisabled'],
            emits: ['capture'],
            template: '<div data-testid="memory-wall" />',
          },
          ClusterBar: true,
          MemoryInspector: true,
        },
      },
    })
    const backendStatus = useBackendStatusStore(pinia)
    const toolbar = () => wrapper.findComponent({ name: 'SearchToolbar' })
    const wall = () => wrapper.findComponent({ name: 'MemoryWall' })
    const memoryPane = wrapper.get('.home-memory-pane')

    expect(memoryPane.classes()).toContain('overflow-y-auto')
    expect(memoryPane.find('[data-testid="search-toolbar"]').exists()).toBe(true)
    expect(memoryPane.find('[data-testid="memory-wall"]').exists()).toBe(true)

    expect(toolbar().props('captureDisabled')).toBe(true)
    expect(wall().props('captureDisabled')).toBe(true)
    expect(toolbar().props('capturing')).toBe(false)
    expect(wall().props('capturing')).toBe(false)

    backendStatus.state = 'ready'
    backendStatus.check = vi.fn().mockResolvedValue(true)
    await flushPromises()

    expect(toolbar().props('captureDisabled')).toBe(false)
    expect(wall().props('captureDisabled')).toBe(false)

    toolbar().vm.$emit('capture')
    await flushPromises()

    expect(toolbar().props('capturing')).toBe(true)
    expect(wall().props('capturing')).toBe(true)

    finishCapture({ success: true, clustered: false })
    await flushPromises()

    expect(toolbar().props('capturing')).toBe(false)
    expect(wall().props('capturing')).toBe(false)

    wrapper.unmount()
  })

  it('closes the floating inspector on outside pointerdown and Escape but not on card or titlebar clicks', async () => {
    vi.stubGlobal('innerWidth', 800) // <820 浮层形态
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', name: 'home', component: Home }],
    })
    await router.push('/')
    await router.isReady()
    const pinia = createPinia()
    const wrapper = mount({ template: '<router-view />' }, {
      attachTo: document.body,
      global: {
        plugins: [pinia, router],
        stubs: {
          SearchToolbar: {
            name: 'SearchToolbar',
            props: ['modelValue'],
            template: '<div class="search-toolbar" />',
          },
          MemoryWall: {
            name: 'MemoryWall',
            template: '<div><article class="memory-card"><span>card</span></article></div>',
          },
          ClusterBar: true,
          // 侧栏关闭路径会调 canLeave()；浅 stub 缺该方法会让关闭静默失败。
          MemoryInspector: {
            name: 'MemoryInspector',
            template: '<div />',
            setup: () => ({ canLeave: async () => true }),
          },
        },
      },
    })
    const memoriesStore = useMemoriesStore(pinia)
    const memory = {
      id: 'memory-1',
      created_at: '2026-10-04T09:00:00',
      image_path: '',
      ai_summary: 'A memory',
      app_name: '',
      sync_status: 'SYNCED',
      match_sources: [],
    }
    memoriesStore.upsert(memory as never)
    const select = async () => {
      memoriesStore.select(memory as never)
      await flushPromises()
    }
    const inspectorOpen = () => Boolean(memoriesStore.selectedId)
    const pointerDownOn = async (target: Element) => {
      target.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, button: 0 }))
      await flushPromises()
    }

    await select()
    const panel = document.querySelector('.inspector-panel')!
    await pointerDownOn(panel)
    expect(inspectorOpen()).toBe(true)

    await pointerDownOn(document.querySelector('.memory-card span')!)
    expect(inspectorOpen()).toBe(true)

    const titlebar = document.createElement('div')
    titlebar.className = 'desktop-shell__titlebar'
    document.body.appendChild(titlebar)
    await pointerDownOn(titlebar)
    expect(inspectorOpen()).toBe(true)
    titlebar.remove()

    await pointerDownOn(document.body)
    expect(inspectorOpen()).toBe(false)

    await select()
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushPromises()
    expect(inspectorOpen()).toBe(false)

    wrapper.unmount()
    vi.unstubAllGlobals()
  })

  it('keeps the docked inspector open on outside clicks and shows the decor panel when closed', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', name: 'home', component: Home }],
    })
    await router.push('/')
    await router.isReady()
    const pinia = createPinia()
    const wrapper = mount({ template: '<router-view />' }, {
      attachTo: document.body,
      global: {
        plugins: [pinia, router],
        stubs: {
          SearchToolbar: {
            name: 'SearchToolbar',
            props: ['modelValue'],
            template: '<div class="search-toolbar" />',
          },
          MemoryWall: {
            name: 'MemoryWall',
            template: '<div><article class="memory-card"><span>card</span></article></div>',
          },
          ClusterBar: true,
          MemoryInspector: {
            name: 'MemoryInspector',
            template: '<div />',
            setup: () => ({ canLeave: async () => true }),
          },
        },
      },
    })
    const memoriesStore = useMemoriesStore(pinia)
    const memory = {
      id: 'memory-1',
      created_at: '2026-10-04T09:00:00',
      image_path: '',
      ai_summary: 'A memory',
      app_name: '',
      sync_status: 'SYNCED',
      match_sources: [],
    }
    memoriesStore.upsert(memory as never)
    memoriesStore.select(memory as never)
    await flushPromises()
    const pointerDownOn = async (target: Element) => {
      target.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, button: 0 }))
      await flushPromises()
    }

    // jsdom 默认 1024px，docked 形态：点外与 Esc 都不关闭
    document.body.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, button: 0 }))
    await flushPromises()
    expect(memoriesStore.selectedId).toBe('memory-1')

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushPromises()
    expect(memoriesStore.selectedId).toBe('memory-1')

    // 关闭后：1024px（窄于 docked 边界 1180）不渲染装饰板，墙列数封顶三列
    memoriesStore.select(null)
    await flushPromises()
    expect(document.querySelector('.inspector-panel--decor')).toBeNull()
    expect(wrapper.findComponent({ name: 'MemoryWall' }).attributes('max-columns')).toBe('3')

    // 宽度到达 docked 边界（≥1180px）时关闭侧栏，槽位渲染装饰面板，封顶解除
    vi.stubGlobal('innerWidth', 1280)
    window.dispatchEvent(new Event('resize'))
    await flushPromises()
    expect(wrapper.findComponent({ name: 'MemoryWall' }).attributes('max-columns')).toBeUndefined()
    memoriesStore.select(memory as never)
    await flushPromises()
    memoriesStore.select(null)
    await flushPromises()
    expect(document.querySelector('.inspector-panel--decor')).not.toBeNull()
    expect(document.querySelector('.side-decor__day')?.textContent).toBeTruthy()
    expect(document.querySelector('.side-decor__phrase')?.textContent).toBeTruthy()

    memoriesStore.select(memory as never)
    await flushPromises()
    expect(document.querySelector('.inspector-panel--decor')).toBeNull()
    expect(memoriesStore.selectedId).toBe('memory-1')

    wrapper.unmount()
    vi.unstubAllGlobals()
  })

  it('shows the wall scrollbar only while scrolling and hides it after the idle timeout', async () => {
    vi.useFakeTimers()
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', name: 'home', component: Home }],
    })
    await router.push('/')
    await router.isReady()
    const pinia = createPinia()
    const wrapper = mount({ template: '<router-view />' }, {
      attachTo: document.body,
      global: {
        plugins: [pinia, router],
        stubs: {
          SearchToolbar: { name: 'SearchToolbar', props: ['modelValue'], template: '<div />' },
          MemoryWall: { name: 'MemoryWall', template: '<div />' },
          ClusterBar: true,
          MemoryInspector: {
            name: 'MemoryInspector',
            template: '<div />',
            setup: () => ({ canLeave: async () => true }),
          },
        },
      },
    })
    const pane = wrapper.get('.home-memory-pane')
    expect(pane.classes()).not.toContain('is-scrolling')

    // 滚动进行中：浮现
    await pane.trigger('scroll')
    expect(pane.classes()).toContain('is-scrolling')

    // 持续滚动：保持浮现
    await vi.advanceTimersByTimeAsync(500)
    await pane.trigger('scroll')
    await vi.advanceTimersByTimeAsync(500)
    expect(pane.classes()).toContain('is-scrolling')

    // 停止超过空闲阈值：隐回
    await vi.advanceTimersByTimeAsync(900)
    expect(pane.classes()).not.toContain('is-scrolling')

    wrapper.unmount()
    vi.useRealTimers()
  })
})
