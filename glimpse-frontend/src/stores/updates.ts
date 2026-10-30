import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { isDesktopShell } from '@/platform/desktop'
import { createLogger } from '@/utils/logger'
import {
  createNotesLoader,
  NotesLoaderError,
  parseNotes,
  type Notes,
} from '@/utils/updateNotes'

const logger = createLogger('stores/updates')

// 开发假通道的标识，与 @/dev/fakeUpdateChannel 配套；生产构建里所有引用都会被 DEV 常量折叠掉。
export const DEV_UPDATE_CHANNEL = 'dev-test'
export const DEV_UPDATE_CHANNEL_STORAGE_KEY = 'glimpse.devUpdateChannel'

function newOperationId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

function describeNotesError(error: unknown): { kind: string; detail?: string; status?: number } {
  if (error instanceof NotesLoaderError) {
    return { kind: error.kind, detail: error.detail, status: error.status }
  }
  return { kind: 'unknown' }
}

function isMainlandChina(): boolean {
  try {
    const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone
    if (timeZone === 'Asia/Shanghai') return true
  } catch {
    // Intl API 不可用时继续按语言判断。
  }
  return navigator.language.startsWith('zh-CN')
}

export type UpdateMirrorMode = 'auto' | 'direct' | 'mirror'

export interface UpdateDownloadProgress {
  downloaded: number
  total: number | null
}

export type UpdatePhase = 'idle' | 'downloading' | 'cancelling' | 'installing' | 'installed' | 'cancelled' | 'failed'

export interface UpdateOperation {
  phase: UpdatePhase
  version: string | null
  progress: UpdateDownloadProgress | null
  error: string | null
}

export type UpdateInstallResult = 'installed' | 'cancelled' | 'running'

export interface InstallUpdateOptions {
  mirrorMode?: UpdateMirrorMode
}

function resolvePreferMirror(mode: UpdateMirrorMode): boolean {
  if (mode === 'direct') return false
  if (mode === 'mirror') return true
  return isMainlandChina()
}

// 开发通道的选择只留在 localStorage：后端会拒绝 settings.json 里的未知通道值。
const readDevChannelEnabled = () => {
  if (!import.meta.env.DEV) return false
  try {
    return window.localStorage.getItem(DEV_UPDATE_CHANNEL_STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

export interface AvailableUpdate {
  version: string
  notes: string | null
}

export const useUpdatesStore = defineStore('updates', () => {
  const settingsStore = useSettingsStore()

  const currentVersion = ref('')
  const availableUpdate = ref<AvailableUpdate | null>(null)
  const checking = ref(false)
  const checkFailed = ref(false)
  const installing = ref(false)
  const cancelling = ref(false)
  const installFailed = ref(false)
  const downloadProgress = ref<UpdateDownloadProgress | null>(null)

  const updateNotes = ref<Notes | null>(null)
  const currentNotes = ref<Notes | null>(null)
  const currentNotesError = ref<'' | 'settings.notesMissing' | 'settings.notesNetwork'>('')
  const currentNotesLoading = ref(false)

  const loadNotes = createNotesLoader((event) => {
    logger.child({ event: 'updates.notes.loader' }).debug(`notes index ${event.phase}`)
  })
  let currentNotesRequested = false
  let currentNotesVersion = ''
  let pendingCheck: Promise<AvailableUpdate | null> | null = null
  let operationListenerReady: Promise<void> | null = null
  let installPending = false

  const showAvailableBadge = computed(() => Boolean(availableUpdate.value))

  const devChannel = ref(readDevChannelEnabled())
  const activePhase = ref<UpdatePhase>('idle')

  const channel = computed<'stable' | 'preview' | 'dev-test'>(() => {
    if (import.meta.env.DEV && devChannel.value) return DEV_UPDATE_CHANNEL
    return settingsStore.settings?.ui?.update_channel === 'preview' ? 'preview' : 'stable'
  })

  const setDevChannel = (enabled: boolean) => {
    if (!import.meta.env.DEV) return
    devChannel.value = enabled
    try {
      if (enabled) window.localStorage.setItem(DEV_UPDATE_CHANNEL_STORAGE_KEY, '1')
      else window.localStorage.removeItem(DEV_UPDATE_CHANNEL_STORAGE_KEY)
    } catch {
      // localStorage 不可用时仅本次会话生效。
    }
  }

  const recordCurrentVersion = (version: string) => {
    if (!version) return
    currentVersion.value = version
  }

  const checkForUpdate = async (): Promise<AvailableUpdate | null> => {
    if (!isDesktopShell() || installing.value) return null
    if (pendingCheck) return pendingCheck
    checking.value = true
    checkFailed.value = false
    installFailed.value = false
    const requestedChannel = channel.value
    const operationId = newOperationId()
    const op = logger.child({ operationId, event: 'updates.check' })
    pendingCheck = (async () => {
      try {
        let target: AvailableUpdate | null
        if (import.meta.env.DEV && requestedChannel === DEV_UPDATE_CHANNEL) {
          const { devCheckForUpdate } = await import('@/dev/fakeUpdateChannel')
          target = devCheckForUpdate(currentVersion.value)
        } else {
          const { invoke } = await import('@tauri-apps/api/core')
          target = await invoke<AvailableUpdate | null>('check_for_update', {
            channel: requestedChannel,
          })
        }
        // 通道在检测期间被切换时，旧响应只代表旧通道，不得写回共享状态。
        if (channel.value !== requestedChannel) {
          op.child({ outcome: 'dropped_stale' }).debug('channel changed during check, dropping result')
          return null
        }
        availableUpdate.value = target
        op
          .child({
            outcome: target ? 'available' : 'up_to_date',
            data: { target: target?.version ?? null, channel: requestedChannel },
          })
          .info(target ? `update available: ${target.version}` : 'up to date')
        if (target) {
          // 更新弹窗直接渲染 updater manifest 带回的目标版正文：与版本检测
          // 同一次响应，不存在第二数据源的陈旧/缺录问题（原 index 聚合路径
          // 会被 WebView/CDN 缓存打穿，表现为发布后检查更新只见裸 markdown）。
          updateNotes.value = target.notes ? parseNotes(target.notes) : null
        }
        return target
      } catch (error) {
        // 启动静默检测失败不打扰用户；手动检查由设置页按 checkFailed 提示。
        op.child({ outcome: 'failed' }).error('Failed to check for updates: %s', error)
        checkFailed.value = true
        return null
      } finally {
        checking.value = false
        pendingCheck = null
      }
    })()
    return pendingCheck
  }

  const applyOperation = (operation: UpdateOperation) => {
    // 安装启动前的旧 idle 快照不能覆盖本次调用的下载中状态。
    if (installPending && operation.phase === 'idle') return
    activePhase.value = operation.phase
    const running = ['downloading', 'cancelling', 'installing'].includes(operation.phase)
    installing.value = running
    cancelling.value = operation.phase === 'cancelling'
    downloadProgress.value = operation.progress
    if (operation.phase === 'failed') {
      installFailed.value = true
    }
    if (operation.phase === 'cancelled') {
      installFailed.value = false
    }
    if (operation.version && !availableUpdate.value) {
      availableUpdate.value = { version: operation.version, notes: null }
    }
    if (operation.phase === 'idle') {
      cancelling.value = false
    }
  }

  const syncUpdateOperation = async () => {
    if (!isDesktopShell()) return
    if (!operationListenerReady) {
      operationListenerReady = (async () => {
        const [{ listen }, { invoke }] = await Promise.all([
          import('@tauri-apps/api/event'),
          import('@tauri-apps/api/core'),
        ])
        await listen<UpdateOperation>(
          'glimpse://update-operation',
          (event) => applyOperation(event.payload),
        )
        applyOperation(await invoke<UpdateOperation>('get_update_install_status'))
      })().catch((error) => {
        operationListenerReady = null
        throw error
      })
    }
    await operationListenerReady
  }

  const installUpdate = async (options: InstallUpdateOptions = {}): Promise<boolean> => {
    if (!availableUpdate.value || installing.value || checking.value) return false
    const op = logger.child({ event: 'updates.install' })
    installing.value = true
    installPending = true
    cancelling.value = false
    installFailed.value = false
    downloadProgress.value = null
    let localTerminal = false
    try {
      if (import.meta.env.DEV && channel.value === DEV_UPDATE_CHANNEL) {
        const { devInstallUpdate } = await import('@/dev/fakeUpdateChannel')
        await devInstallUpdate()
      } else {
        await syncUpdateOperation()
        // 只有"运行中"三态才代表已有任务在跑（双击/多入口触发）；cancelled/
        // failed/installed 是终态——Rust 侧终结后不会回到 idle，若按
        // "非 idle 即拦截"，取消后重新下载会被误判为已在下载而直接短路，
        // 表现为无进度且取消秒回。
        const phase = activePhase.value
        const alreadyRunning = phase === 'downloading' || phase === 'cancelling' || phase === 'installing'
        if (alreadyRunning && installing.value) return true
        const [{ listen }, { invoke }] = await Promise.all([
          import('@tauri-apps/api/event'),
          import('@tauri-apps/api/core'),
        ])
        const unlistenProgress = await listen<UpdateDownloadProgress>(
          'glimpse://update-download-progress',
          (event) => {
            if (installing.value && !cancelling.value) downloadProgress.value = event.payload
          },
        )
        try {
          const mirrorMode = options.mirrorMode
            ?? settingsStore.settings?.ui?.update_mirror_mode
            ?? 'auto'
          const result = await invoke<UpdateInstallResult>('install_checked_update', {
            preferMirror: resolvePreferMirror(mirrorMode),
          })
          applyOperation(await invoke<UpdateOperation>('get_update_install_status'))
          if (result === 'running') return true
          if (result === 'cancelled') {
            op.child({ outcome: 'cancelled' }).info('update download cancelled')
            installFailed.value = false
            return true
          }
        } finally {
          unlistenProgress()
        }
      }
      op.child({ outcome: 'success' }).info('update install finished')
      localTerminal = true
      return true
    } catch (error) {
      try {
        const { invoke } = await import('@tauri-apps/api/core')
        const operation = await invoke<UpdateOperation>('get_update_install_status')
        applyOperation(operation)
        if (installing.value || operation.phase === 'cancelled') {
          if (!(import.meta.env.DEV && channel.value === DEV_UPDATE_CHANNEL)) return true
        }
      } catch {
        if (installing.value && activePhase.value !== 'idle') return true
      }
      op.child({ outcome: 'failed' }).error('Failed to install update: %s', error)
      installFailed.value = true
      localTerminal = true
      return false
    } finally {
      installPending = false
      if (localTerminal || activePhase.value === 'idle') {
        installing.value = false
        cancelling.value = false
        downloadProgress.value = null
      }
    }
  }

  const cancelUpdateDownload = async () => {
    if (!installing.value || cancelling.value) return
    cancelling.value = true
    try {
      const { invoke } = await import('@tauri-apps/api/core')
      await invoke('cancel_update_download')
      applyOperation(await invoke<UpdateOperation>('get_update_install_status'))
    } catch (error) {
      cancelling.value = false
      logger.child({ event: 'updates.install', outcome: 'cancel_failed' }).error('Failed to cancel update download: %s', error)
    }
  }

  const loadCurrentNotes = async () => {
    const version = currentVersion.value
    if (currentNotesRequested && currentNotesVersion === version) return
    currentNotesRequested = true
    currentNotesVersion = version
    currentNotesLoading.value = true
    const op = logger.child({ event: 'updates.current_notes', operationId: newOperationId() })
    try {
      const entries = await loadNotes()
      // 等待期间当前版本变了：旧结果作废并放开门闩，下一次调用按新版本加载。
      if (currentVersion.value !== version) {
        currentNotesRequested = false
        op.child({ outcome: 'superseded' }).debug('current version changed during load, discarding result')
        return
      }
      const entry = entries.find((release) => release.version === version)
      if (entry) {
        currentNotes.value = parseNotes(entry.notes)
        // 上一次失败残留的错误在正文里优先渲染，成功后必须清掉。
        currentNotesError.value = ''
        op.child({ outcome: 'ready' }).info('current notes loaded')
      } else {
        currentNotesError.value = 'settings.notesMissing'
        op.child({ outcome: 'missing', data: { version } }).warn('current version missing from notes index')
      }
    } catch (error) {
      // 放开门闩，让下次打开浮窗/重进设置页时还能再试；成功路径保持会话级缓存不变。
      currentNotesRequested = false
      currentNotesError.value = 'settings.notesNetwork'
      op.child({ outcome: 'failed', data: describeNotesError(error) }).warn('failed to load notes index: %s', error)
    } finally {
      currentNotesLoading.value = false
    }
  }

  // 手动重新检查到新版本后调用，让顶栏浮窗展示同一份说明。
  const refreshUpdateNotes = (notes: string | null) => {
    updateNotes.value = notes ? parseNotes(notes) : null
  }

  return {
    currentVersion,
    availableUpdate,
    checking,
    checkFailed,
    installing,
    cancelling,
    installFailed,
    downloadProgress,
    showAvailableBadge,
    updateNotes,
    currentNotes,
    currentNotesError,
    currentNotesLoading,
    devChannel,
    setDevChannel,
    recordCurrentVersion,
    checkForUpdate,
    installUpdate,
    cancelUpdateDownload,
    loadCurrentNotes,
    refreshUpdateNotes,
    syncUpdateOperation,
  }
})
