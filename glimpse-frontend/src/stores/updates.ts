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

  const channel = computed<'stable' | 'preview'>(() =>
    settingsStore.settings?.ui?.update_channel === 'preview' ? 'preview' : 'stable',
  )

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
    try {
      const { invoke } = await import('@tauri-apps/api/core')
      const target = await invoke<AvailableUpdate | null>('check_for_update', {
        channel: channel.value,
      })
      availableUpdate.value = target
      if (target) {
        const generation = ++notesGeneration
        updateNotes.value = null
        updateNotesPartial.value = false
        updateNotesLoading.value = true
        void loadNotes().then((entries) => {
          if (generation !== notesGeneration) return
          updateNotes.value = aggregateNotes(entries, currentVersion.value, target.version, channel.value)
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
      const { invoke } = await import('@tauri-apps/api/core')
      await invoke('install_checked_update')
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
    updateNotes.value = null
    updateNotesPartial.value = false
    updateNotesLoading.value = true
    void loadNotes().then((entries) => {
      if (generation !== notesGeneration) return
      updateNotes.value = aggregateNotes(entries, currentVersion.value, version, channel.value)
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
    recordCurrentVersion,
    checkForUpdate,
    installUpdate,
    loadCurrentNotes,
    dismissJustUpdated,
    refreshUpdateNotes,
  }
})
