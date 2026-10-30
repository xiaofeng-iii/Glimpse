import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import App from '@/App.vue'
import GuidedTour from '@/components/GuidedTour.vue'
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
  showNotification: vi.fn(),
  routePush: vi.fn(),
}))

vi.mock('vue-router', () => ({
  RouterView: { template: '<div />' },
  useRoute: () => ({ name: 'home', fullPath: '/', query: {} }),
  useRouter: () => ({ push: appMocks.routePush }),
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

vi.mock('@/stores/notification', () => ({
  useNotificationStore: () => ({
    show: appMocks.showNotification,
  }),
}))

vi.mock('@/stores/hotkeyRegistration', () => ({
  useHotkeyRegistrationStore: () => ({
    hotkey: null,
    error: null,
    reportSuccess: vi.fn(),
    reportFailure: vi.fn(),
  }),
}))

vi.mock('@/platform/global-shortcut', () => ({
  applyScreenshotShortcut: vi.fn().mockResolvedValue({ ok: true }),
}))

vi.mock('@/config/runtime', () => ({
  whenBackendRuntimeReady: appMocks.whenBackendRuntimeReady,
}))

vi.mock('@/utils/theme', () => ({
  applyThemePreference: appMocks.applyThemePreference,
  watchSystemTheme: appMocks.watchSystemTheme,
}))

vi.mock('@/utils/tour-samples', () => ({
  injectTourSamples: vi.fn().mockResolvedValue(undefined),
  removeTourSamples: vi.fn().mockResolvedValue(undefined),
  sweepTourSamples: vi.fn().mockResolvedValue(undefined),
}))

const mountApp = () => mount(App, {
  global: {
    stubs: {
      RouterView: true,
      DesktopShell: { template: '<div><slot /></div>' },
      ImagePreviewModal: true,
      SwipeToastHost: true,
      Teleport: true,
    },
  },
})

describe('first-run guided tour', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    setLanguagePreference('zh-CN')
    appMocks.loadSettings.mockResolvedValue(undefined)
    appMocks.whenBackendRuntimeReady.mockResolvedValue(undefined)
    appMocks.watchSystemTheme.mockReturnValue(vi.fn())
    appMocks.routePush.mockResolvedValue(undefined)
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

  it('shows the tour immediately on first entry, persists completion, and stays hidden next time', async () => {
    const firstMount = mountApp()
    await flushPromises()

    const dialog = firstMount.get('[role="dialog"]')
    expect(dialog.attributes('aria-modal')).toBe('true')
    expect(dialog.text()).toContain('欢迎使用 Glimpse')
    expect(firstMount.get('[data-testid="tour-next"]').attributes('aria-label')).toBe('开始引导')

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await flushPromises()
    expect(firstMount.find('[role="dialog"]').exists()).toBe(false)
    expect(window.localStorage.getItem(ONBOARDING_VERSION_STORAGE_KEY)).toBe(
      String(CURRENT_ONBOARDING_VERSION),
    )

    firstMount.unmount()
    const secondMount = mountApp()
    await flushPromises()
    expect(secondMount.find('[role="dialog"]').exists()).toBe(false)
  })

  it('does not wait for backend readiness before showing the tour', async () => {
    appMocks.whenBackendRuntimeReady.mockReturnValueOnce(new Promise(() => {}))
    const wrapper = mountApp()
    await flushPromises()

    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
  })

  it('reopens the tour when the toolbar requests it', async () => {
    completeOnboarding()
    const wrapper = mountApp()
    await flushPromises()
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)

    requestOnboarding()
    await flushPromises()

    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    expect(wrapper.get('[role="dialog"]').text()).toContain('欢迎使用 Glimpse')
  })

  it('focuses the primary action and supports Escape dismissal', async () => {
    const wrapper = mount(GuidedTour, {
      props: { open: true },
      attachTo: document.body,
      global: { stubs: { Teleport: true } },
    })
    await flushPromises()

    expect(document.activeElement).toBe(wrapper.get('[data-testid="tour-next"]').element)
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await flushPromises()
    expect(wrapper.emitted('complete')).toHaveLength(1)
  })
})
