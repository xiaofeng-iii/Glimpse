import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { isDesktopShell } from '@/platform/desktop'
import { createLogger } from '@/utils/logger'
import {
  aggregateNotes,
  createNotesLoader,
  parseNotes,
  type Notes,
} from '@/utils/updateNotes'

const logger = createLogger('stores/updates')

export const LAST_RUN_VERSION_STORAGE_KEY = 'glimpse.lastRunVersion'
// 开发假通道的标识，与 @/dev/fakeUpdateChannel 配套；生产构建里所有引用都会被 DEV 常量折叠掉。
export const DEV_UPDATE_CHANNEL = 'dev-test'
export const DEV_UPDATE_CHANNEL_STORAGE_KEY = 'glimpse.devUpdateChannel'

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

const readLastRunVersion = () => {
  try {
    return window.localStorage.getItem(LAST_RUN_VERSION_STORAGE_KEY)
  } catch {
    return null
  }
}

const writeLastRunVersion = (version: string) => {
  try {
    window.localStorage.setItem(LAST_RUN_VERSION_STORAGE_KEY, version)
  } catch {
    // localStorage 不可用时本次会话仍提示，下次启动再试。
  }
}

export const useUpdatesStore = defineStore('updates', () => {
  const settingsStore = useSettingsStore()

  const currentVersion = ref('')
  const availableUpdate = ref<AvailableUpdate | null>(null)
  const checking = ref(false)
  const installing = ref(false)
  const installFailed = ref(false)
  const justUpdated = ref(false)
  const justUpdatedNotesSeen = ref(false)

  const updateNotes = ref<Notes | null>(null)
  const updateNotesLoading = ref(false)
  const updateNotesPartial = ref(false)
  const currentNotes = ref<Notes | null>(null)
  const currentNotesError = ref<'' | 'settings.notesMissing' | 'settings.notesNetwork'>('')
  const currentNotesLoading = ref(false)

  const loadNotes = createNotesLoader()
  let notesGeneration = 0
  let currentNotesRequested = false

  const showAvailableBadge = computed(() => Boolean(availableUpdate.value))
  const showJustUpdatedBadge = computed(
    () => !availableUpdate.value && justUpdated.value && !justUpdatedNotesSeen.value,
  )

  const devChannel = ref(readDevChannelEnabled())

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

  // 开发通道用内存里的假索引，真实通道照旧抓 GitHub Pages。
  const loadNotesFor = async (targetChannel: string) => {
    if (import.meta.env.DEV && targetChannel === DEV_UPDATE_CHANNEL) {
      const { devReleaseNotes } = await import('@/dev/fakeUpdateChannel')
      return devReleaseNotes()
    }
    return loadNotes()
  }

  // dev-test 按预览语义聚合，再交给 aggregateNotes 的截断规则。
  const aggregationChannel = (targetChannel: string): 'stable' | 'preview' =>
    targetChannel === 'stable' ? 'stable' : 'preview'

  const recordCurrentVersion = (version: string) => {
    if (!version) return
    currentVersion.value = version
    const lastRun = readLastRunVersion()
    if (lastRun === version) return
    // 首次启动不写回：lastRun 为空不算"刚更新"，只建立基线。
    if (lastRun) justUpdated.value = true
    writeLastRunVersion(version)
  }

  const checkForUpdate = async (): Promise<AvailableUpdate | null> => {
    if (!isDesktopShell() || checking.value || installing.value) return null
    checking.value = true
    installFailed.value = false
    const requestedChannel = channel.value
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
      availableUpdate.value = target
      if (target) {
        const generation = ++notesGeneration
        updateNotes.value = null
        updateNotesPartial.value = false
        updateNotesLoading.value = true
        void loadNotesFor(requestedChannel).then((entries) => {
          if (generation !== notesGeneration) return
          updateNotes.value = aggregateNotes(entries, currentVersion.value, target.version, aggregationChannel(requestedChannel))
          updateNotesPartial.value = !updateNotes.value
        }).catch(() => {
          if (generation === notesGeneration) updateNotesPartial.value = true
        }).finally(() => {
          if (generation === notesGeneration) updateNotesLoading.value = false
        })
      }
      return target
    } catch (error) {
      // 启动静默检测失败不打扰用户；手动检查由调用方决定是否提示。
      logger.error('Failed to check for updates: %s', error)
      return null
    } finally {
      checking.value = false
    }
  }

  const installUpdate = async (): Promise<boolean> => {
    if (!availableUpdate.value || installing.value || checking.value) return false
    installing.value = true
    try {
      if (import.meta.env.DEV && channel.value === DEV_UPDATE_CHANNEL) {
        const { devInstallUpdate } = await import('@/dev/fakeUpdateChannel')
        await devInstallUpdate()
      } else {
        const { invoke } = await import('@tauri-apps/api/core')
        await invoke('install_checked_update')
      }
      return true
    } catch (error) {
      logger.error('Failed to install update: %s', error)
      availableUpdate.value = null
      installFailed.value = true
      return false
    } finally {
      installing.value = false
    }
  }

  const loadCurrentNotes = async () => {
    if (currentNotesRequested) return
    currentNotesRequested = true
    currentNotesLoading.value = true
    try {
      const entries = await loadNotes()
      const entry = entries.find((release) => release.version === currentVersion.value)
      if (entry) currentNotes.value = parseNotes(entry.notes)
      else currentNotesError.value = 'settings.notesMissing'
    } catch {
      currentNotesError.value = 'settings.notesNetwork'
    } finally {
      currentNotesLoading.value = false
    }
  }

  // 手动重新检查到新版本后调用，让顶栏浮窗展示同一份聚合说明。
  const refreshUpdateNotes = (version: string) => {
    const generation = ++notesGeneration
    const requestedChannel = channel.value
    updateNotes.value = null
    updateNotesPartial.value = false
    updateNotesLoading.value = true
    void loadNotesFor(requestedChannel).then((entries) => {
      if (generation !== notesGeneration) return
      updateNotes.value = aggregateNotes(entries, currentVersion.value, version, aggregationChannel(requestedChannel))
      updateNotesPartial.value = !updateNotes.value
    }).catch(() => {
      if (generation === notesGeneration) updateNotesPartial.value = true
    }).finally(() => {
      if (generation === notesGeneration) updateNotesLoading.value = false
    })
  }

  const dismissJustUpdated = () => {
    justUpdatedNotesSeen.value = true
  }

  return {
    currentVersion,
    availableUpdate,
    checking,
    installing,
    installFailed,
    justUpdated,
    showAvailableBadge,
    showJustUpdatedBadge,
    updateNotes,
    updateNotesLoading,
    updateNotesPartial,
    currentNotes,
    currentNotesError,
    currentNotesLoading,
    devChannel,
    setDevChannel,
    recordCurrentVersion,
    checkForUpdate,
    installUpdate,
    loadCurrentNotes,
    dismissJustUpdated,
    refreshUpdateNotes,
  }
})
