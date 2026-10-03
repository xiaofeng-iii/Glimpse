import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { createPinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import Settings from '@/views/Settings.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'

const appStyles = readFileSync(resolve(process.cwd(), 'src/styles/main.css'), 'utf8')

const apiMocks = vi.hoisted(() => ({
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
  resetSettings: vi.fn(),
  indexStatus: vi.fn(),
  ocrStatus: vi.fn(),
}))

const mountedHosts: Array<{ unmount: () => void }> = []
afterEach(() => { mountedHosts.splice(0).forEach((host) => host.unmount()) })

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
  mountedHosts.push(host)
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
      reset: apiMocks.resetSettings,
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

const selectSection = async (wrapper: Awaited<ReturnType<typeof mountSettings>>, label: string) => {
  await wrapper.findAll('nav button').find((button) => button.text() === label)!.trigger('click')
}
const deferred = () => {
  let resolve!: () => void
  const promise = new Promise<void>((done) => { resolve = done })
  return { promise, resolve }
}

describe('Settings', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    apiMocks.resetSettings.mockResolvedValue({})
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

  it('keeps an unchanged save button disabled without presenting it as busy', async () => {
    const wrapper = await mountSettings()
    await selectSection(wrapper, 'AI 服务')
    const saveButton = wrapper.get<HTMLButtonElement>('[data-testid=save-ai]')

    expect(saveButton.element.disabled).toBe(true)
    expect(saveButton.attributes('aria-busy')).toBe('false')
    expect(saveButton.find('.animate-spin').exists()).toBe(false)
    expect(appStyles).toContain(".btn-primary[aria-busy='true']")
    expect(appStyles).toMatch(/\.btn-primary:disabled\s*\{[^}]*cursor:\s*default;/s)
  })

  it('sends an explicit empty API key when the credential is cleared', async () => {
    const wrapper = await mountSettings()

    const aiButton = wrapper.findAll('button').find((button) => button.text().includes('AI 服务'))
    await aiButton!.trigger('click')
    await wrapper.get('#ai-api-key').setValue('')
    const saveButton = wrapper.get('[data-testid=save-ai]')
    expect(saveButton.text()).toContain('保存')
    await saveButton.trigger('click')
    await flushPromises()

    expect(apiMocks.updateSettings).toHaveBeenCalledWith(expect.objectContaining({
      ai: expect.objectContaining({ api_key: '' }),
    }))
  })
  it('groups navigation in the requested order and removes footer actions', async () => {
    const wrapper = await mountSettings()
    expect(wrapper.findAll('nav h3').map((node) => node.text())).toEqual(['个人', '配置', '应用'])
    expect(wrapper.findAll('nav button').map((node) => node.text())).toEqual(['界面', '快捷键', '截图设置', 'AI 服务', '维护', '软件更新'])
    expect(wrapper.find('footer').exists()).toBe(false)
    expect(wrapper.get('.settings-content__footer').text()).toContain('恢复默认')
    expect(apiMocks.updateSettings).not.toHaveBeenCalled()
  })

  it('serializes rapid ordinary edits and preserves unsaved AI drafts', async () => {
    const wrapper = await mountSettings()
    await selectSection(wrapper, 'AI 服务')
    await wrapper.get('#ai-api-key').setValue('draft-secret')
    expect(apiMocks.updateSettings).not.toHaveBeenCalled()
    await selectSection(wrapper, '截图设置')
    const pending = deferred()
    apiMocks.updateSettings.mockReturnValueOnce(pending.promise)
    const input = wrapper.get('input[type=number]')
    await input.setValue(6)
    await flushPromises()
    await input.setValue(7)
    await input.setValue(8)
    expect(apiMocks.updateSettings).toHaveBeenCalledTimes(1)
    pending.resolve()
    await flushPromises()
    expect(apiMocks.updateSettings).toHaveBeenCalledTimes(2)
    expect(apiMocks.updateSettings.mock.calls[1]![0].screenshot.capture_limit_window_seconds).toBe(8)
    expect(apiMocks.updateSettings.mock.calls.every(([payload]) => !('ai' in payload))).toBe(true)
    expect((input.element as HTMLInputElement).value).toBe('8')
    await selectSection(wrapper, 'AI 服务')
    expect((wrapper.get('#ai-api-key').element as HTMLInputElement).value).toBe('draft-secret')
    expect(wrapper.get('[data-testid=save-ai]').attributes('disabled')).toBeUndefined()
  })

  it('waits for auto-save before leaving and blocks departure after failed retries', async () => {
    const wrapper = await mountSettings()
    await selectSection(wrapper, '截图设置')
    const pending = deferred()
    apiMocks.updateSettings.mockReturnValueOnce(pending.promise)
    await wrapper.get('input[type=number]').setValue(6)
    await flushPromises()
    const navigation = wrapper.vm.$router.push('/')
    await flushPromises()
    expect(wrapper.vm.$router.currentRoute.value.path).toBe('/settings')
    pending.resolve()
    await navigation
    expect(wrapper.vm.$router.currentRoute.value.path).toBe('/')

    const failed = await mountSettings()
    await selectSection(failed, '截图设置')
    apiMocks.updateSettings.mockRejectedValue(new Error('offline'))
    await failed.get('input[type=number]').setValue(9)
    await flushPromises()
    expect(failed.get('[role=status]').text()).toContain('设置保存失败')
    await failed.vm.$router.push('/')
    expect(failed.vm.$router.currentRoute.value.path).toBe('/settings')
    apiMocks.updateSettings.mockResolvedValue({})
    await failed.get('[role=status] button').trigger('click')
    await flushPromises()
    expect(failed.find('[role=status]').exists()).toBe(false)
  })

  it('saves AI alone, preserving edits made during an in-flight AI save and its leave guard', async () => {
    const wrapper = await mountSettings()
    await selectSection(wrapper, 'AI 服务')
    await wrapper.get('#ai-api-key').setValue('first')
    const pending = deferred()
    apiMocks.updateSettings.mockReturnValueOnce(pending.promise)
    await wrapper.get('[data-testid=save-ai]').trigger('click')
    await flushPromises()
    await wrapper.get('#ai-api-key').setValue('second')
    pending.resolve()
    await flushPromises()
    expect(Object.keys(apiMocks.updateSettings.mock.calls[0]![0])).toEqual(['ai'])
    expect((wrapper.get('#ai-api-key').element as HTMLInputElement).value).toBe('second')
    const navigation = wrapper.vm.$router.push('/')
    await flushPromises()
    const dialog = wrapper.findAllComponents(ConfirmDialog).find((item) => item.vm.$attrs.id === 'settings-discard')!
    expect(dialog.props('open')).toBe(true)
    dialog.vm.$emit('cancel')
    await navigation
    expect(wrapper.vm.$router.currentRoute.value.path).toBe('/settings')
  })

  it('queues reset after an active save and discards pending edits without a stale write', async () => {
    const wrapper = await mountSettings()
    await selectSection(wrapper, '截图设置')
    const pending = deferred()
    apiMocks.updateSettings.mockReturnValueOnce(pending.promise)
    await wrapper.get('input[type=number]').setValue(6)
    await flushPromises()
    await wrapper.get('input[type=number]').setValue(7)
    await wrapper.get('.settings-reset-link').trigger('click')
    const dialog = wrapper.findAllComponents(ConfirmDialog).find((item) => item.vm.$attrs.id === 'settings-confirm')!
    dialog.vm.$emit('confirm')
    await flushPromises()
    expect(apiMocks.resetSettings).not.toHaveBeenCalled()
    pending.resolve()
    await flushPromises()
    expect(apiMocks.resetSettings).toHaveBeenCalledTimes(1)
    expect(apiMocks.updateSettings).toHaveBeenCalledTimes(1)
    expect((wrapper.get('input[type=number]').element as HTMLInputElement).value).toBe('5')
  })

  it('queues AI behind ordinary writes and retains its draft and retry button on failure', async () => {
    const wrapper = await mountSettings()
    await selectSection(wrapper, '截图设置')
    const pending = deferred()
    apiMocks.updateSettings.mockReturnValueOnce(pending.promise).mockRejectedValueOnce(new Error('AI save failed'))
    await wrapper.get('input[type=number]').setValue(6)
    await flushPromises()
    await selectSection(wrapper, 'AI 服务')
    await wrapper.get('#ai-api-key').setValue('draft')
    await wrapper.get('[data-testid=save-ai]').trigger('click')
    await flushPromises()
    expect(apiMocks.updateSettings).toHaveBeenCalledTimes(1)
    pending.resolve()
    await flushPromises()
    expect(apiMocks.updateSettings).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[role=alert]').text()).toContain('设置保存失败')
    expect((wrapper.get('#ai-api-key').element as HTMLInputElement).value).toBe('draft')
    expect(wrapper.get('[data-testid=save-ai]').attributes('disabled')).toBeUndefined()
    await wrapper.get('[data-testid=save-ai]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid=save-ai]').attributes('disabled')).toBeDefined()
  })

})
