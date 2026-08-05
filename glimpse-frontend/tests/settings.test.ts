import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import Settings from '@/views/Settings.vue'

const apiMocks = vi.hoisted(() => ({
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
  indexStatus: vi.fn(),
  ocrStatus: vi.fn(),
}))

const mountSettings = async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/settings', component: Settings },
    ],
  })
  await router.push('/settings')
  await router.isReady()

  const host = mount({ template: '<router-view />' }, {
    global: {
      plugins: [createPinia(), router],
    },
  })
  await flushPromises()
  return host.getComponent(Settings)
}

vi.mock('@/api/client', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/api/client')>()
  return {
    ...original,
    settingsApi: {
      ...original.settingsApi,
      get: apiMocks.getSettings,
      update: apiMocks.updateSettings,
    },
    indexApi: {
      ...original.indexApi,
      status: apiMocks.indexStatus,
    },
    ocrApi: {
      ...original.ocrApi,
      status: apiMocks.ocrStatus,
    },
  }
})

describe('Settings', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMocks.getSettings.mockResolvedValue({
      hotkeys: { screenshot: '<ctrl>+<shift>+g' },
      screenshot: {},
      ai: { api_key: 'secret', base_url: 'https://api.example.com/v1', model: 'vision-model', timeout: 60 },
      ocr: {},
      ui: { theme: 'light', language: 'zh-CN', close_action: 'ask' },
      cluster: {},
    })
    apiMocks.indexStatus.mockResolvedValue({
      task_id: 'index_repair',
      status: 'idle',
      running: false,
      result: null,
      error: null,
    })
    apiMocks.ocrStatus.mockResolvedValue({
      task_id: 'ocr_backfill',
      status: 'idle',
      running: false,
      result: null,
      error: null,
    })
    apiMocks.updateSettings.mockResolvedValue({})
  })

  it('renders the fixed vector and local OCR stack as read-only information', async () => {
    const wrapper = await mountSettings()

    const aiButton = wrapper.findAll('button').find((button) => button.text().includes('AI 服务'))
    expect(aiButton).toBeDefined()
    await aiButton!.trigger('click')

    expect(wrapper.text()).toContain('BAAI/bge-small-zh-v1.5')
    expect(wrapper.text()).toContain('PP-OCRv6-small')
    expect(wrapper.text()).toContain('RapidOCR 3.9.2')
    expect(wrapper.text()).toContain('ONNX Runtime CPU')
    expect(wrapper.find('input[value="BAAI/bge-small-zh-v1.5"]').exists()).toBe(false)
  })

  it('sends an explicit empty API key when the credential is cleared', async () => {
    const wrapper = await mountSettings()

    const aiButton = wrapper.findAll('button').find((button) => button.text().includes('AI 服务'))
    await aiButton!.trigger('click')
    await wrapper.get('#ai-api-key').setValue('')
    const saveButton = wrapper.get('footer .btn-primary')
    expect(saveButton.text()).toContain('保存设置')
    await saveButton.trigger('click')
    await flushPromises()

    expect(apiMocks.updateSettings).toHaveBeenCalledWith(expect.objectContaining({
      ai: expect.objectContaining({ api_key: '' }),
    }))
  })
})
