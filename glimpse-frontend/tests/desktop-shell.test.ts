import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import DesktopShell from '@/components/DesktopShell.vue'
import { useBackendStatusStore } from '@/stores/backendStatus'
import { setLanguagePreference } from '@/utils/i18n'

const mocks = vi.hoisted(() => ({
  checkHealth: vi.fn(),
  getSettings: vi.fn(),
  whenBackendRuntimeReady: vi.fn(),
}))

vi.mock('@/api/client', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/api/client')>()
  return {
    ...original,
    healthApi: {
      check: mocks.checkHealth,
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
  closeDesktopWindow: vi.fn(),
  focusDesktopWindow: vi.fn(),
  getDesktopWindowMaximized: vi.fn().mockResolvedValue(false),
  hideDesktopWindow: vi.fn(),
  isDesktopShell: () => false,
  listenForDesktopCloseRequests: vi.fn(),
  minimizeDesktopWindow: vi.fn(),
  toggleDesktopMaximize: vi.fn(),
}))

const connectionFailure = () => Object.assign(new Error('Network Error'), {
  isAxiosError: true,
  response: undefined,
})

describe('DesktopShell service status', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setLanguagePreference('zh-CN')
    mocks.whenBackendRuntimeReady.mockResolvedValue(undefined)
    mocks.getSettings.mockResolvedValue({
      hotkeys: {},
      screenshot: {},
      ai: {},
      ocr: {},
      ui: { close_action: 'ask' },
      cluster: {},
    })
  })

  it('renders starting, ready, and runtime error as distinct states', async () => {
    let resolveHealth!: (value: { status: string }) => void
    mocks.checkHealth.mockReturnValueOnce(new Promise((resolve) => {
      resolveHealth = resolve
    }))

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', name: 'home', component: { template: '<div />' } }],
    })
    await router.push('/')
    await router.isReady()
    const pinia = createPinia()
    const wrapper = mount(DesktopShell, {
      slots: { default: '<div />' },
      global: {
        plugins: [pinia, router],
        stubs: { CloseActionDialog: true },
      },
    })
    await flushPromises()

    const status = () => wrapper.get('[role="status"]')
    expect(status().text()).toBe('服务启动中')
    expect(status().classes()).toContain('service-status--starting')
    expect(status().find('.animate-spin').exists()).toBe(true)

    resolveHealth({ status: 'healthy' })
    await flushPromises()
    expect(status().text()).toBe('服务正常')
    expect(status().classes()).toContain('service-status--ready')

    mocks.checkHealth.mockRejectedValueOnce(connectionFailure())
    const backendStatus = useBackendStatusStore(pinia)
    await backendStatus.check()
    await flushPromises()
    expect(status().text()).toBe('服务异常')
    expect(status().classes()).toContain('service-status--offline')
  })
})
