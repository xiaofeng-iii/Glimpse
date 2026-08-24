import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import Home from '@/views/Home.vue'
import { useBackendStatusStore } from '@/stores/backendStatus'

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
})
