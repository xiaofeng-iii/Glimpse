import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useUpdatesStore } from '@/stores/updates'
import { useSettingsStore } from '@/stores/settings'

const apiMocks = vi.hoisted(() => ({
  invoke: vi.fn(),
  fetchIndex: vi.fn(),
  isDesktopShell: vi.fn(),
}))

vi.mock('@tauri-apps/api/core', () => ({ invoke: apiMocks.invoke }))
vi.mock('@/platform/desktop', () => ({ isDesktopShell: apiMocks.isDesktopShell }))

const indexEntries = [
  {
    version: '0.3.2',
    preview: false,
    notes: '**新特性**\n- 0.3.2 已有功能\n\n**修复**\n\n**Full Changelog**: x',
    sortKey: [0, 3, 2, 1, 0, 0],
  },
  {
    version: '0.3.3',
    preview: false,
    notes: '**新特性**\n- 0.3.3 新能力\n\n**优化**\n\n**修复**\n\n**Full Changelog**: x',
    sortKey: [0, 3, 3, 1, 0, 0],
  },
]

describe('updates store', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.stubGlobal('fetch', apiMocks.fetchIndex)
    window.localStorage.clear()
    setActivePinia(createPinia())
    apiMocks.isDesktopShell.mockReturnValue(true)
    apiMocks.fetchIndex.mockResolvedValue({
      json: async () => ({ schemaVersion: 1, releases: indexEntries }),
      ok: true,
    })
    const settings = useSettingsStore()
    settings.settings = {
      hotkeys: {},
      screenshot: {},
      ai: {},
      ocr: {},
      ui: { update_channel: 'stable' },
      cluster: {},
    } as never
  })

  it('marks just updated only when the stored version differs', () => {
    const store = useUpdatesStore()

    store.recordCurrentVersion('0.3.2')
    expect(store.justUpdated).toBe(false)

    store.recordCurrentVersion('0.3.3')
    expect(store.justUpdated).toBe(true)
    expect(store.showJustUpdatedBadge).toBe(true)

    store.dismissJustUpdated()
    expect(store.showJustUpdatedBadge).toBe(false)
  })

  it('does not treat the very first launch as an update', () => {
    const store = useUpdatesStore()
    store.recordCurrentVersion('0.3.2')
    expect(store.justUpdated).toBe(false)
    expect(window.localStorage.getItem('glimpse.lastRunVersion')).toBe('0.3.2')
  })

  it('stores the available update and aggregates its notes', async () => {
    const store = useUpdatesStore()
    store.recordCurrentVersion('0.3.2')
    apiMocks.invoke.mockResolvedValue({ version: '0.3.3', notes: '单版正文' })

    const target = await store.checkForUpdate()

    expect(apiMocks.invoke).toHaveBeenCalledWith('check_for_update', { channel: 'stable' })
    expect(target?.version).toBe('0.3.3')
    expect(store.showAvailableBadge).toBe(true)
    // 有新版本时不再同时显示"刚升级"徽章。
    expect(store.showJustUpdatedBadge).toBe(false)

    await vi.waitFor(() => expect(store.updateNotesLoading).toBe(false))
    expect(store.updateNotes?.sections.features).toContain('0.3.3 新能力')
    expect(store.updateNotes?.sections.features).not.toContain('0.3.2 已有功能')
  })

  it('stays silent when the startup check fails', async () => {
    const store = useUpdatesStore()
    apiMocks.invoke.mockRejectedValue(new Error('offline'))

    const target = await store.checkForUpdate()

    expect(target).toBeNull()
    expect(store.availableUpdate).toBeNull()
    expect(store.checking).toBe(false)
  })

  it('serves the fake dev-channel update without calling the desktop shell', async () => {
    const store = useUpdatesStore()
    store.recordCurrentVersion('0.4.1')
    store.setDevChannel(true)

    const target = await store.checkForUpdate()

    expect(apiMocks.invoke).not.toHaveBeenCalled()
    expect(target?.version).toBe('1.0.0')
    expect(store.showAvailableBadge).toBe(true)
    await vi.waitFor(() => expect(store.updateNotesLoading).toBe(false))
    expect(store.updateNotes?.sections.features).toContain('记忆墙支持自定义排序')
    expect(store.updateNotes?.sections.features).toContain('新增记忆连拍合并开关')
    // 被 1.0.0 正式版覆盖的预览条目按截断规则剔除，不该混进聚合结果。
    expect(store.updateNotes?.sections.features).not.toContain('仅预览版测试条目（聚合时应被剔除）')
  })

  it('fails the simulated dev-channel install without touching the updater', async () => {
    const store = useUpdatesStore()
    store.recordCurrentVersion('0.4.1')
    store.setDevChannel(true)
    await store.checkForUpdate()

    const installed = await store.installUpdate()

    expect(installed).toBe(false)
    expect(apiMocks.invoke).not.toHaveBeenCalled()
    expect(store.installFailed).toBe(true)
    expect(store.availableUpdate).toBeNull()
  })
})
