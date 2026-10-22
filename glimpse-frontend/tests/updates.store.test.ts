import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useUpdatesStore } from '@/stores/updates'
import { useSettingsStore } from '@/stores/settings'
import { setDiagnosticsSink, type DiagnosticsSinkEvent } from '@/utils/logger'

const apiMocks = vi.hoisted(() => ({
  invoke: vi.fn(),
  listen: vi.fn(),
  fetchIndex: vi.fn(),
  isDesktopShell: vi.fn(),
}))

vi.mock('@tauri-apps/api/core', () => ({ invoke: apiMocks.invoke }))
vi.mock('@tauri-apps/api/event', () => ({ listen: apiMocks.listen }))
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
    apiMocks.listen.mockResolvedValue(vi.fn())
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

  it('stores the available update and parses its manifest notes inline', async () => {
    const store = useUpdatesStore()
    store.recordCurrentVersion('0.3.2')
    apiMocks.invoke.mockResolvedValue({
      version: '0.3.3',
      notes: '**新特性**\n- 0.3.3 新能力',
    })

    const target = await store.checkForUpdate()

    expect(apiMocks.invoke).toHaveBeenCalledWith('check_for_update', { channel: 'stable' })
    expect(target?.version).toBe('0.3.3')
    expect(store.showAvailableBadge).toBe(true)
    // 说明正文来自版本检测的同一份 manifest 返回值，不再单独拉 index
    expect(apiMocks.fetchIndex).not.toHaveBeenCalled()
    expect(store.updateNotes?.sections.features).toEqual(['0.3.3 新能力'])
  })

  it('shares one pending check instead of issuing duplicate update checks', async () => {
    const store = useUpdatesStore()
    store.recordCurrentVersion('0.3.2')
    let releaseCheck!: (value: { version: string; notes: string | null }) => void
    apiMocks.invoke.mockReturnValue(new Promise((resolve) => { releaseCheck = resolve }))

    const first = store.checkForUpdate()
    const second = store.checkForUpdate()
    releaseCheck({ version: '0.3.3', notes: null })
    const [firstResult, secondResult] = await Promise.all([first, second])

    expect(apiMocks.invoke).toHaveBeenCalledTimes(1)
    expect(firstResult?.version).toBe('0.3.3')
    expect(secondResult).toBe(firstResult)
  })

  it('passes the selected mirror mode directly when installing', async () => {
    const store = useUpdatesStore()
    store.recordCurrentVersion('0.3.2')
    apiMocks.invoke.mockImplementation(async (command: string) => {
      if (command === 'check_for_update') return { version: '0.3.3', notes: null }
      if (command === 'install_checked_update') return 'installed'
      throw new Error(`unexpected command ${command}`)
    })

    await store.checkForUpdate()
    apiMocks.invoke.mockClear()
    await store.installUpdate({ mirrorMode: 'direct' })

    expect(apiMocks.invoke).toHaveBeenCalledWith('install_checked_update', { preferMirror: false })
    expect(apiMocks.listen).toHaveBeenCalledWith(
      'glimpse://update-download-progress',
      expect.any(Function),
    )
  })

  it('falls back to the persisted mirror mode outside the settings page', async () => {
    const settings = useSettingsStore()
    settings.settings = {
      ...settings.settings,
      ui: { update_channel: 'stable', update_mirror_mode: 'mirror' },
    } as never
    const store = useUpdatesStore()
    store.recordCurrentVersion('0.3.2')
    apiMocks.invoke.mockImplementation(async (command: string) => {
      if (command === 'check_for_update') return { version: '0.3.3', notes: null }
      if (command === 'install_checked_update') return 'installed'
      throw new Error(`unexpected command ${command}`)
    })

    await store.checkForUpdate()
    apiMocks.invoke.mockClear()
    await store.installUpdate()

    expect(apiMocks.invoke).toHaveBeenCalledWith('install_checked_update', { preferMirror: true })
  })

  it('tracks download progress from the Rust event', async () => {
    const store = useUpdatesStore()
    store.recordCurrentVersion('0.3.2')
    let progressHandler: ((event: { payload: { downloaded: number; total: number | null } }) => void) | null = null
    apiMocks.listen.mockImplementation(async (_event: string, handler: typeof progressHandler) => {
      progressHandler = handler
      return vi.fn()
    })
    let releaseInstall!: (value: 'installed') => void
    apiMocks.invoke.mockImplementation(async (command: string) => {
      if (command === 'check_for_update') return { version: '0.3.3', notes: null }
      if (command === 'install_checked_update') {
        return new Promise((resolve) => { releaseInstall = resolve })
      }
      throw new Error(`unexpected command ${command}`)
    })

    await store.checkForUpdate()
    const install = store.installUpdate({ mirrorMode: 'direct' })
    await vi.waitFor(() => expect(progressHandler).not.toBeNull())
    progressHandler!({ payload: { downloaded: 1024, total: 4096 } })
    expect(store.downloadProgress).toEqual({ downloaded: 1024, total: 4096 })

    releaseInstall('installed')
    expect(await install).toBe(true)
    expect(store.downloadProgress).toBeNull()
  })

  it('cancels without presenting cancellation as an installation failure', async () => {
    const store = useUpdatesStore()
    store.recordCurrentVersion('0.3.2')
    let releaseInstall!: (value: 'cancelled') => void
    apiMocks.invoke.mockImplementation(async (command: string) => {
      if (command === 'check_for_update') return { version: '0.3.3', notes: null }
      if (command === 'install_checked_update') {
        return new Promise((resolve) => { releaseInstall = resolve })
      }
      if (command === 'cancel_update_download') return null
      throw new Error(`unexpected command ${command}`)
    })

    await store.checkForUpdate()
    const install = store.installUpdate({ mirrorMode: 'mirror' })
    await vi.waitFor(() => expect(store.installing).toBe(true))
    await store.cancelUpdateDownload()
    releaseInstall('cancelled')
    expect(await install).toBe(true)
    expect(store.installFailed).toBe(false)
    expect(store.availableUpdate?.version).toBe('0.3.3')
    expect(store.installing).toBe(false)
    expect(apiMocks.invoke).toHaveBeenCalledWith('cancel_update_download')
  })

  it('stays silent when the startup check fails', async () => {
    const store = useUpdatesStore()
    apiMocks.invoke.mockRejectedValue(new Error('offline'))

    const target = await store.checkForUpdate()

    expect(target).toBeNull()
    expect(store.availableUpdate).toBeNull()
    expect(store.checking).toBe(false)
  })

  it('serves the fake dev-channel beta update without calling the desktop shell', async () => {
    const store = useUpdatesStore()
    store.recordCurrentVersion('0.4.1')
    store.setDevChannel(true)

    const target = await store.checkForUpdate()

    expect(apiMocks.invoke).not.toHaveBeenCalled()
    expect(apiMocks.fetchIndex).not.toHaveBeenCalled()
    expect(target?.version).toBe('1.0.0-beta.1')
    expect(store.showAvailableBadge).toBe(true)
    expect(store.updateNotes?.sections.features).toContain('记忆墙支持自定义排序')
    expect(store.updateNotes?.sections.fixes.length).toBeGreaterThan(0)
  })

  it.each(['1.0.0-beta.1', '1.0.0-beta.2', '1.0.0'])('does not offer the dev beta when already running %s', async (version) => {
    const store = useUpdatesStore()
    store.recordCurrentVersion(version)
    store.setDevChannel(true)

    expect(await store.checkForUpdate()).toBeNull()
    expect(store.showAvailableBadge).toBe(false)
    expect(apiMocks.invoke).not.toHaveBeenCalled()
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

  it('recovers current notes when a failed load is retried', async () => {
    const store = useUpdatesStore()
    store.recordCurrentVersion('0.3.2')

    apiMocks.fetchIndex.mockRejectedValueOnce(new TypeError('offline'))
    await store.loadCurrentNotes()
    expect(store.currentNotesError).toBe('settings.notesNetwork')
    expect(store.currentNotes).toBeNull()

    // 同一会话第二次调用重新发请求（不再是死锁的 rejected promise 缓存）。
    await store.loadCurrentNotes()
    expect(apiMocks.fetchIndex).toHaveBeenCalledTimes(2)
    expect(store.currentNotes?.sections.features).toContain('0.3.2 已有功能')
    expect(store.currentNotesError).toBe('')
    // 成功后恢复会话级缓存：第三次调用不再请求。
    await store.loadCurrentNotes()
    expect(apiMocks.fetchIndex).toHaveBeenCalledTimes(2)
  })

  describe('diagnostics events', () => {
    let events: DiagnosticsSinkEvent[]

    beforeEach(() => {
      events = []
      setDiagnosticsSink((event) => events.push(event))
    })

    afterEach(() => {
      setDiagnosticsSink(null)
    })

    it('records missing_target when the target version is absent from the index', async () => {
      const store = useUpdatesStore()
      store.recordCurrentVersion('0.3.2')
      apiMocks.invoke.mockResolvedValue({ version: '9.9.9', notes: null })

      await store.checkForUpdate()
      await vi.waitFor(() => expect(store.updateNotesLoading).toBe(false))

      expect(store.updateNotesPartial).toBe(true)
      const partial = events.find((event) => event.event === 'updates.notes' && event.outcome === 'partial')
      expect(partial?.data?.reason).toBe('missing_target')
    })

    it('records unsupported_current when the running version cannot be parsed', async () => {
      const store = useUpdatesStore()
      store.recordCurrentVersion('0.3.2-weird')
      apiMocks.invoke.mockResolvedValue({ version: '0.3.3', notes: null })

      await store.checkForUpdate()
      await vi.waitFor(() => expect(store.updateNotesLoading).toBe(false))

      expect(store.updateNotesPartial).toBe(true)
      const partial = events.find((event) => event.event === 'updates.notes' && event.outcome === 'partial')
      expect(partial?.data?.reason).toBe('unsupported_current')
    })

    it('records the failure kind when the notes index cannot be fetched', async () => {
      const store = useUpdatesStore()
      store.recordCurrentVersion('0.3.2')
      apiMocks.invoke.mockResolvedValue({ version: '0.3.3', notes: null })
      apiMocks.fetchIndex.mockRejectedValue(new TypeError('offline'))

      await store.checkForUpdate()
      await vi.waitFor(() => expect(store.updateNotesLoading).toBe(false))

      const failed = events.find((event) => event.event === 'updates.notes' && event.outcome === 'fetch_failed')
      expect(failed?.data?.kind).toBe('network')
      expect(store.updateNotesPartial).toBe(true)
    })

    it('distinguishes a missing current version from a network failure', async () => {
      const store = useUpdatesStore()
      store.recordCurrentVersion('0.3.9')

      await store.loadCurrentNotes()
      expect(store.currentNotesError).toBe('settings.notesMissing')
      expect(events.some((event) => event.event === 'updates.current_notes' && event.outcome === 'missing')).toBe(true)
      expect(events.some((event) => event.event === 'updates.current_notes' && event.outcome === 'failed')).toBe(false)
    })

    it('reloads current notes when the recorded version changes', async () => {
      const store = useUpdatesStore()
      store.recordCurrentVersion('0.3.2')

      await store.loadCurrentNotes()
      expect(store.currentNotes?.sections.features).toContain('0.3.2 已有功能')

      store.recordCurrentVersion('0.3.3')
      await store.loadCurrentNotes()
      // 索引成功后是会话级缓存：不再发请求，但按新版本重新解析。
      expect(apiMocks.fetchIndex).toHaveBeenCalledTimes(1)
      expect(store.currentNotes?.sections.features).toContain('0.3.3 新能力')
      expect(store.currentNotesError).toBe('')
    })
  })
})
