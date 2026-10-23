import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { isDesktopShell } from '@/platform/desktop'
import { createLogger } from '@/utils/logger'
import {
  createNotesLoader,
  parseNotes,
  type Notes,
} from '@/utils/updateNotes'

const logger = createLogger('stores/updates')

// 开发假通道的标识，与 @/dev/fakeUpdateChannel 配套；生产构建里所有引用都会被 DEV 常量折叠掉。
export const DEV_UPDATE_CHANNEL = 'dev-test'
export const DEV_UPDATE_CHANNEL_STORAGE_KEY = 'glimpse.devUpdateChannel'

function isMainlandChina(): boolean {
  try {
    const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone
    if (timeZone === 'Asia/Shanghai') return true
  } catch {
    // Intl API 不可用时继续按语言判断。
  }
  return navigator.language.startsWith('zh-CN')
}

function resolvePreferMirror(mode: 'auto' | 'direct' | 'mirror'): boolean {
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
  const installing = ref(false)
  const installFailed = ref(false)

  const updateNotes = ref<Notes | null>(null)
  const currentNotes = ref<Notes | null>(null)
  const currentNotesError = ref<'' | 'settings.notesMissing' | 'settings.notesNetwork'>('')
  const currentNotesLoading = ref(false)

  const loadNotes = createNotesLoader()
  let currentNotesRequested = false

  const showAvailableBadge = computed(() => Boolean(availableUpdate.value))

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

  const recordCurrentVersion = (version: string) => {
    if (!version) return
    currentVersion.value = version
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
        // 仅真实通道同步镜像模式；dev-test 通道没有 Rust 侧下载，不需要。
        if (!(import.meta.env.DEV && requestedChannel === DEV_UPDATE_CHANNEL)) {
          const mirrorMode = settingsStore.settings?.ui?.update_mirror_mode ?? 'auto'
          const preferMirror = resolvePreferMirror(mirrorMode)
          const { invoke } = await import('@tauri-apps/api/core')
          void invoke('set_update_mirror_mode', { preferMirror }).catch((error) => {
            logger.error('Failed to sync update mirror mode: %s', error)
          })
        }
        // 更新弹窗直接渲染 updater manifest 带回的目标版正文：与版本检测
        // 同一次响应，不存在第二数据源的陈旧/缺录问题（原 index 聚合路径
        // 会被 WebView/CDN 缓存打穿，表现为发布后检查更新只见裸 markdown）。
        updateNotes.value = target.notes ? parseNotes(target.notes) : null
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
      if (entry) {
        currentNotes.value = parseNotes(entry.notes)
        // 上一次失败残留的错误在正文里优先渲染，成功后必须清掉。
        currentNotesError.value = ''
      } else {
        currentNotesError.value = 'settings.notesMissing'
      }
    } catch {
      // 放开门闩，让下次打开浮窗/重进设置页时还能再试；成功路径保持会话级缓存不变。
      currentNotesRequested = false
      currentNotesError.value = 'settings.notesNetwork'
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
    installing,
    installFailed,
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
    loadCurrentNotes,
    refreshUpdateNotes,
  }
})
