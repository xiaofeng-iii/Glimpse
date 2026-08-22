import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import App from '@/App.vue'
import FirstRunGuide from '@/components/FirstRunGuide.vue'
import { setLanguagePreference } from '@/utils/i18n'
import {
  completeOnboarding,
  CURRENT_ONBOARDING_VERSION,
  ONBOARDING_VERSION_STORAGE_KEY,
  requestOnboarding,
  shouldShowOnboarding,
} from '@/utils/onboarding'

const appMocks = vi.hoisted(() => ({
  connectWebSocket: vi.fn(),
  startKeepalive: vi.fn(),
  loadSettings: vi.fn(),
  whenBackendRuntimeReady: vi.fn(),
  applyThemePreference: vi.fn(),
  watchSystemTheme: vi.fn(),
}))

vi.mock('@/api/websocket', () => ({
  useWebSocket: () => ({
    connect: appMocks.connectWebSocket,
    startKeepalive: appMocks.startKeepalive,
  }),
}))

vi.mock('@/stores/settings', () => ({
  useSettingsStore: () => ({
    settings: null,
    load: appMocks.loadSettings,
  }),
}))

vi.mock('@/config/runtime', () => ({
  whenBackendRuntimeReady: appMocks.whenBackendRuntimeReady,
}))

vi.mock('@/utils/theme', () => ({
  applyThemePreference: appMocks.applyThemePreference,
  watchSystemTheme: appMocks.watchSystemTheme,
}))

const mountApp = () => mount(App, {
  global: {
    stubs: {
      RouterView: true,
      DesktopShell: { template: '<div><slot /></div>' },
      ImagePreviewModal: true,
      NotificationToast: true,
      Teleport: true,
    },
  },
})

describe('first-run onboarding', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    setLanguagePreference('zh-CN')
    appMocks.loadSettings.mockResolvedValue(undefined)
    appMocks.whenBackendRuntimeReady.mockResolvedValue(undefined)
    appMocks.watchSystemTheme.mockReturnValue(vi.fn())
  })

  it('uses a versioned completion marker', () => {
    expect(shouldShowOnboarding()).toBe(true)

    window.localStorage.setItem(ONBOARDING_VERSION_STORAGE_KEY, 'invalid')
    expect(shouldShowOnboarding()).toBe(true)

    window.localStorage.setItem(
      ONBOARDING_VERSION_STORAGE_KEY,
      String(CURRENT_ONBOARDING_VERSION - 1),
    )
    expect(shouldShowOnboarding()).toBe(true)

    completeOnboarding()
    expect(window.localStorage.getItem(ONBOARDING_VERSION_STORAGE_KEY)).toBe(
      String(CURRENT_ONBOARDING_VERSION),
    )
    expect(shouldShowOnboarding()).toBe(false)
  })

  it('shows immediately on first entry, persists completion, and stays hidden next time', async () => {
    const firstMount = mountApp()
    await flushPromises()

    const dialog = firstMount.get('[role="dialog"]')
    expect(dialog.attributes('aria-modal')).toBe('true')
    expect(dialog.text()).toContain('三步开始使用 Glimpse')
    expect(dialog.text()).toContain('Ctrl + Shift + G')
    expect(dialog.text()).toContain('Ctrl + F')

    await firstMount.get('[data-testid="first-run-complete"]').trigger('click')
    await flushPromises()
    expect(firstMount.find('[role="dialog"]').exists()).toBe(false)
    expect(window.localStorage.getItem(ONBOARDING_VERSION_STORAGE_KEY)).toBe('1')

    firstMount.unmount()
    const secondMount = mountApp()
    await flushPromises()
    expect(secondMount.find('[role="dialog"]').exists()).toBe(false)
  })

  it('does not wait for backend readiness before showing the guide', async () => {
    appMocks.whenBackendRuntimeReady.mockReturnValueOnce(new Promise(() => {}))
    const wrapper = mountApp()
    await flushPromises()

    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
  })

  it('reopens the guide when the development UI requests it', async () => {
    completeOnboarding()
    const wrapper = mountApp()
    await flushPromises()
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)

    requestOnboarding()
    await flushPromises()

    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    expect(window.localStorage.getItem(ONBOARDING_VERSION_STORAGE_KEY)).toBe('1')
  })

  it('focuses the primary action and supports Escape dismissal', async () => {
    const wrapper = mount(FirstRunGuide, {
      props: { open: true },
      attachTo: document.body,
      global: { stubs: { Teleport: true } },
    })
    await flushPromises()

    expect(document.activeElement).toBe(wrapper.get('[data-testid="first-run-complete"]').element)
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    expect(wrapper.emitted('complete')).toHaveLength(1)
  })
})
