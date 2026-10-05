import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { createPinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import Settings from '@/views/Settings.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { useUpdatesStore } from '@/stores/updates'

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
  openUrl: vi.fn(),
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
vi.mock('@tauri-apps/plugin-opener', () => ({ openUrl: apiMocks.openUrl }))
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

const mountSettings = async (initialPath = '/settings', prepare?: () => Promise<void> | void) => {
  const { createMemoryHistory, createRouter } = await import('vue-router')
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/settings', component: Settings },
    ],
  })
  const pinia = createPinia()
  const { setActivePinia } = await import('pinia')
  setActivePinia(pinia)
  // prepare 在组件挂载前驱动共享 store，模拟启动检测/顶栏已发生的状态。
  if (prepare) await prepare()
  await router.push(initialPath)
  await router.isReady()
  // attachTo 让 reka-ui PopoverPortal 的 Fragment 在 autoUnmount 前被显式卸载，
  // 否则 jsdom 下 teardown 会因 nextSibling 为 null 崩溃并污染本文件其余用例。
  const host = mount({ template: '<router-view />' }, {
    attachTo: document.body,
    global: { plugins: [pinia, router] },
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
  wrapper.findAll('button').find((button) => button.classes().includes('version-notes-trigger'))!
const checkButton = (wrapper: VueWrapper) =>
  wrapper.findAll('button').find((button) => button.text().includes('检查更新'))!

describe('Settings update notes', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.stubGlobal('fetch', apiMocks.fetchIndex)
    window.localStorage.clear()
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

  it('shows the version and repository link below the panel on every section', async () => {
    const wrapper = await mountSettings()
    const meta = wrapper.get('.settings-meta')
    expect(meta.text()).toContain('Glimpse v0.3.2')

    const repositoryLink = meta.get('a')
    expect(repositoryLink.text()).toBe('GitHub')
    expect(repositoryLink.attributes('href')).toBe('https://github.com/xiaofeng-iii/Glimpse')
    expect(repositoryLink.attributes('target')).toBe('_blank')

    await selectSection(wrapper, '软件更新')
    expect(wrapper.get('.settings-meta').text()).toContain('Glimpse v0.3.2')
  })

  it('opens the repository via the desktop opener instead of the webview', async () => {
    const wrapper = await mountSettings()

    await wrapper.get('.settings-meta__link').trigger('click')
    await flushPromises()

    expect(apiMocks.openUrl).toHaveBeenCalledWith('https://github.com/xiaofeng-iii/Glimpse')
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

  it('offers the dev channel and never writes it into settings', async () => {
    window.localStorage.setItem('glimpse.devUpdateChannel', '1')
    const wrapper = await openUpdates(await mountSettings())
    await flushPromises()

    expect(wrapper.get('#settings-update-channel').text()).toContain('开发测试')
    expect(apiMocks.updateSettings).not.toHaveBeenCalled()
    const payloads = apiMocks.updateSettings.mock.calls.map(([payload]) => JSON.stringify(payload))
    expect(payloads.some((payload) => payload.includes('dev-test'))).toBe(false)
  })

  it('checks the dev channel in place: fake 1.0.0 with aggregated notes', async () => {
    window.localStorage.setItem('glimpse.devUpdateChannel', '1')
    const wrapper = await openUpdates(await mountSettings())

    await checkButton(wrapper).trigger('click')
    const dialog = wrapper.findAllComponents(ConfirmDialog).find((item) => item.vm.$attrs.id === 'update-notes')!
    // 开发通道走动态导入，等对话框真正打开再断言内容。
    await vi.waitFor(() => expect(dialog.props('open')).toBe(true))
    await flushPromises()

    expect(apiMocks.invoke).not.toHaveBeenCalled()
    expect(dialog.props('title')).toContain('1.0.0')
    const bodyText = document.body.textContent ?? ''
    expect(bodyText).toContain('记忆墙支持自定义排序')
    expect(bodyText).toContain('新增记忆连拍合并开关')
    expect(bodyText).not.toContain('仅预览版测试条目（聚合时应被剔除）')
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
    // 状态文案在弹窗内只出现一次（标题下方的描述行），不再描述、正文各来一份。
    const dialogPanel = document.querySelector('[role="alertdialog"]')
    expect(dialogPanel?.textContent?.match(/正在下载/g)).toHaveLength(1)

    releaseInstall()
    await flushPromises()
    expect(dialog.props('busy')).toBe(false)
    expect(wrapper.text()).toContain('安装失败，请重新检查更新后再试。')
    // 失败后已取走待安装对象，入口回到"重新检查更新"而不是残留可重复安装的按钮。
    expect(wrapper.find('.settings-panel__card').exists()).toBe(false)
    expect(checkButton(wrapper).attributes('disabled')).toBeUndefined()
  })

  it('installs in place from the card without opening any dialog', async () => {
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
    dialog.vm.$emit('cancel')
    await flushPromises()

    const installButton = wrapper.findAll('button').find((button) => button.text() === '下载并安装')!
    await installButton.trigger('click')
    await flushPromises()

    // 点击后就地进入下载态：不再弹窗，按钮自身变为共享的「正在下载」状态。
    expect(dialog.props('open')).toBe(false)
    expect(wrapper.findAll('button').find((button) => button.text() === '正在下载')).toBeDefined()

    releaseInstall()
    await flushPromises()
    expect(wrapper.text()).toContain('安装失败，请重新检查更新后再试。')
  })

  it('mirrors an install started elsewhere as 正在下载 in the updates section', async () => {
    apiMocks.invoke.mockResolvedValue({ version: '0.3.3-preview.20261003', notes: null })
    // 挂载前模拟启动检测已发现更新、且顶栏浮窗已发起下载。
    const wrapper = await mountSettings('/settings', async () => {
      const store = useUpdatesStore()
      store.recordCurrentVersion('0.3.2')
      await store.checkForUpdate()
      store.installing = true
    })

    await openUpdates(wrapper)
    await flushPromises()

    const dialog = wrapper.findAllComponents(ConfirmDialog).find((item) => item.vm.$attrs.id === 'update-notes')!
    expect(dialog.props('open')).toBe(false)
    expect(wrapper.text()).toContain('发现新版本 0.3.3-preview.20261003')
    const installButton = wrapper.findAll('button').find((button) => button.text() === '正在下载')!
    expect(installButton.attributes('disabled')).toBeDefined()
    expect(checkButton(wrapper).attributes('disabled')).toBeDefined()
  })

  it('does not auto-check on normal entry; detection waits for the manual button', async () => {
    // 普通进入设置页不发起检测，更新卡片不出现，直到用户点「检查更新」。
    apiMocks.invoke.mockResolvedValue({ version: '0.3.3-preview.20261003', notes: null })
    const wrapper = await openUpdates(await mountSettings())
    await flushPromises()

    expect(apiMocks.invoke).not.toHaveBeenCalledWith('check_for_update', expect.anything())
    expect(wrapper.text()).not.toContain('发现新版本')

    await checkButton(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('发现新版本 0.3.3-preview.20261003'))
  })

  it('shows the already-found update directly when entering via 查看详情', async () => {
    // 标题栏「查看详情」带入 ?section=updates，且启动检测已把更新写进共享 store：
    // 直接展示，不重新检测、不弹模态。
    apiMocks.invoke.mockResolvedValue({ version: '0.3.3-preview.20261003', notes: null })
    const wrapper = await mountSettings('/settings?section=updates')
    // 在组件同一个 pinia 实例上模拟启动检测已发现更新。
    const updatesStore = useUpdatesStore()
    updatesStore.recordCurrentVersion('0.3.2')
    await updatesStore.checkForUpdate()
    await vi.waitFor(() => expect(updatesStore.updateNotesLoading).toBe(false))
    // adoptStoreUpdate 在 onMounted 已跑过；这里直接驱动一次同步以验证展示路径。
    ;(wrapper.vm as unknown as { adoptStoreUpdate?: () => void }).adoptStoreUpdate?.()

    await vi.waitFor(() => expect(wrapper.text()).toContain('发现新版本 0.3.3-preview.20261003'))
    const dialog = wrapper.findAllComponents(ConfirmDialog).find((item) => item.vm.$attrs.id === 'update-notes')!
    expect(dialog.props('open')).toBe(false)
  })

  it('stays silent when the manual check finds nothing new', async () => {
    // 手动检测没有新版本时给"已是最新"提示但不弹窗。
    apiMocks.invoke.mockResolvedValue(null)
    const wrapper = await openUpdates(await mountSettings())
    await checkButton(wrapper).trigger('click')
    await flushPromises()

    const dialog = wrapper.findAllComponents(ConfirmDialog).find((item) => item.vm.$attrs.id === 'update-notes')!
    expect(dialog.props('open')).toBe(false)
    expect(wrapper.text()).not.toContain('发现新版本')
  })
})
