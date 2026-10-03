import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { createPinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import Settings from '@/views/Settings.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'

const appStyles = readFileSync(resolve(process.cwd(), 'src/styles/main.css'), 'utf8')

const apiMocks = vi.hoisted(() => ({
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
  resetSettings: vi.fn(),
  indexStatus: vi.fn(),
  ocrStatus: vi.fn(),
  invoke: vi.fn(),
  getVersion: vi.fn(),
  fetchIndex: vi.fn(),
  isDesktopShell: vi.fn(),
}))

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
    indexApi: { ...original.indexApi, status: apiMocks.indexStatus },
    ocrApi: { ...original.ocrApi, status: apiMocks.ocrStatus },
  }
})

vi.mock('@tauri-apps/api/core', () => ({ invoke: apiMocks.invoke }))
vi.mock('@tauri-apps/api/app', () => ({ getVersion: apiMocks.getVersion }))
vi.mock('@/platform/desktop', () => ({ isDesktopShell: apiMocks.isDesktopShell }))

const indexEntries = [
  {
    version: '0.3.2',
    preview: false,
    notes: '**新特性**\n- 0.3.2 已有功能\n\n**修复**\n\n**Full Changelog**: x',
    sortKey: [0, 3, 2, 1, 0, 0],
  },
  {
    version: '0.3.3-preview.20261003',
    preview: true,
    notes: '**新特性**\n- 预览新能力\n\n**优化**\n- 预览优化\n\n**修复**\n\n**Full Changelog**: x',
    sortKey: [0, 3, 3, 0, 20261003, 0],
  },
]

const mountedHosts: Array<{ unmount: () => void }> = []
afterEach(() => { mountedHosts.splice(0).forEach((host) => host.unmount()) })

const mountSettings = async () => {
  const { createMemoryHistory, createRouter } = await import('vue-router')
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/settings', component: Settings },
    ],
  })
  await router.push('/settings')
  await router.isReady()
  // attachTo 让 reka-ui PopoverPortal 的 Fragment 在 autoUnmount 前被显式卸载，
  // 否则 jsdom 下 teardown 会因 nextSibling 为 null 崩溃并污染本文件其余用例。
  const host = mount({ template: '<router-view />' }, {
    attachTo: document.body,
    global: { plugins: [createPinia(), router] },
  })
  mountedHosts.push(host)
  await flushPromises()
  return host.getComponent(Settings)
}

const selectSection = async (wrapper: VueWrapper, label: string) => {
  await wrapper.findAll('nav button').find((button) => button.text() === label)!.trigger('click')
}

const openUpdates = async (wrapper: VueWrapper) => {
  await selectSection(wrapper, '软件更新')
  return wrapper
}

const currentVersionButton = (wrapper: VueWrapper) =>
  wrapper.findAll('button').find((button) => button.text() === '0.3.2')!
const checkButton = (wrapper: VueWrapper) =>
  wrapper.findAll('button').find((button) => button.text().includes('检查更新'))!

describe('Settings update notes', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.stubGlobal('fetch', apiMocks.fetchIndex)
    apiMocks.getSettings.mockResolvedValue({
      hotkeys: { screenshot: '<ctrl>+<shift>+g' },
      screenshot: {},
      ai: {},
      ocr: {},
      ui: { theme: 'light', language: 'zh-CN', close_action: 'ask', update_channel: 'preview' },
      cluster: {},
    })
    apiMocks.indexStatus.mockResolvedValue({ task_id: 'x', status: 'idle', running: false, result: null, error: null })
    apiMocks.ocrStatus.mockResolvedValue({ task_id: 'y', status: 'idle', running: false, result: null, error: null })
    apiMocks.updateSettings.mockResolvedValue({})
    apiMocks.isDesktopShell.mockReturnValue(true)
    apiMocks.getVersion.mockResolvedValue('0.3.2')
    apiMocks.fetchIndex.mockResolvedValue({
      json: async () => ({ schemaVersion: 1, releases: indexEntries }),
      ok: true,
    })
  })

  it('opens current-version notes in an anchored popover and keeps plain styling', async () => {
    const wrapper = await openUpdates(await mountSettings())
    const trigger = currentVersionButton(wrapper)
    expect(trigger.classes()).toContain('version-notes-trigger')

    await trigger.trigger('click')
    await flushPromises()

    expect(apiMocks.fetchIndex).toHaveBeenCalledTimes(1)
    const popoverText = document.body.textContent ?? ''
    expect(popoverText).toContain('0.3.2 已有功能')
    expect(popoverText).toContain('新特性')
    expect(popoverText).not.toContain('**新特性**')
    expect(popoverText).not.toContain('Full Changelog')
    // 没有条目的分类仍保留标题，不编造内容。
    const fixHeading = [...document.querySelectorAll('h3')].find((node) => node.textContent === '修复')
    expect(fixHeading).toBeDefined()
    expect(fixHeading!.parentElement!.querySelector('li')).toBeNull()
  })

  it('shows a network-specific error when the notes index cannot be loaded', async () => {
    apiMocks.fetchIndex.mockRejectedValue(new TypeError('offline'))
    const wrapper = await openUpdates(await mountSettings())

    await currentVersionButton(wrapper).trigger('click')
    await flushPromises()

    expect(document.body.textContent).toContain('更新说明获取失败，请稍后重试')
  })

  it('opens the update dialog with aggregated notes after finding a new version', async () => {
    apiMocks.invoke.mockResolvedValue({ version: '0.3.3-preview.20261003', notes: '预览正文' })
    const wrapper = await openUpdates(await mountSettings())

    await checkButton(wrapper).trigger('click')
    await flushPromises()
    await flushPromises()

    const dialog = wrapper.findAllComponents(ConfirmDialog).find((item) => item.vm.$attrs.id === 'update-notes')!
    expect(dialog.props('open')).toBe(true)
    expect(dialog.props('title')).toContain('0.3.3-preview.20261003')
    const bodyText = document.body.textContent ?? ''
    expect(bodyText).toContain('预览新能力')
    expect(bodyText).toContain('优化')
    expect(bodyText).not.toContain('0.3.2 已有功能')
  })

  it('falls back to raw target notes when the index load fails', async () => {
    apiMocks.invoke.mockResolvedValue({ version: '0.3.3-preview.20261003', notes: '单版正文' })
    apiMocks.fetchIndex.mockRejectedValue(new TypeError('offline'))
    const wrapper = await openUpdates(await mountSettings())

    await checkButton(wrapper).trigger('click')
    await flushPromises()
    await flushPromises()

    expect(document.body.textContent).toContain('部分版本说明获取失败')
    expect(document.body.textContent).toContain('单版正文')
  })

  it('keeps the discovered update available after dismissing the dialog', async () => {
    apiMocks.invoke.mockResolvedValue({ version: '0.3.3-preview.20261003', notes: null })
    const wrapper = await openUpdates(await mountSettings())

    await checkButton(wrapper).trigger('click')
    await flushPromises()
    await flushPromises()

    const dialog = wrapper.findAllComponents(ConfirmDialog).find((item) => item.vm.$attrs.id === 'update-notes')!
    dialog.vm.$emit('cancel')
    await flushPromises()
    expect(dialog.props('open')).toBe(false)
    expect(wrapper.text()).toContain('发现新版本 0.3.3-preview.20261003')

    // 箭头浮层复用同一份聚合内容并可以再次打开。
    const arrow = wrapper.findAll('button').find((button) => button.attributes('aria-label') === '查看更新说明')!
    await arrow.trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('预览新能力')
  })

  it('turns the dialog busy in place when installing and resets after failure', async () => {
    let releaseInstall!: (value?: unknown) => void
    apiMocks.invoke.mockImplementation(async (command: string) => {
      if (command === 'check_for_update') {
        return { version: '0.3.3-preview.20261003', notes: null }
      }
      if (command === 'install_checked_update') {
        await new Promise<void>((resolve) => { releaseInstall = resolve })
        throw new Error('download failed')
      }
      throw new Error(`unexpected command ${command}`)
    })
    const wrapper = await openUpdates(await mountSettings())

    await checkButton(wrapper).trigger('click')
    await flushPromises()
    const dialog = wrapper.findAllComponents(ConfirmDialog).find((item) => item.vm.$attrs.id === 'update-notes')!

    dialog.vm.$emit('confirm')
    await flushPromises()
    expect(dialog.props('busy')).toBe(true)
    expect(document.body.textContent).toContain('正在下载并验证更新')

    releaseInstall()
    await flushPromises()
    expect(dialog.props('busy')).toBe(false)
    expect(wrapper.text()).toContain('安装失败，请重新检查更新后再试。')
    // 失败后已取走待安装对象，入口回到"重新检查更新"而不是残留可重复安装的按钮。
    expect(wrapper.find('.maintenance-card .btn-primary').exists()).toBe(false)
    expect(checkButton(wrapper).attributes('disabled')).toBeUndefined()
  })
})
