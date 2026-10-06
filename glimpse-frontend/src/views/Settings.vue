<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  ArrowPathIcon,
  CameraIcon,
  CheckCircleIcon,
  CircleStackIcon,
  CpuChipIcon,
  EyeIcon,
  EyeSlashIcon,
  CommandLineIcon,
  LockClosedIcon,
  PaintBrushIcon,
  SparklesIcon,
  ArrowDownTrayIcon,
} from '@heroicons/vue/24/outline'
import { onBeforeRouteLeave, useRoute } from 'vue-router'
import {
  indexApi,
  ocrApi,
  type IndexRepairStatus,
  type OcrBackfillStatus,
} from '@/api/client'
import { useNotificationStore } from '@/stores/notification'
import { useSettingsStore } from '@/stores/settings'
import { useUnsavedChangesStore } from '@/stores/unsavedChanges'
import { DEV_UPDATE_CHANNEL, useUpdatesStore } from '@/stores/updates'
import {
  applyThemePreference,
  normalizeThemePreference,
  type ThemePreference,
} from '@/utils/theme'
import {
  normalizeLanguagePreference,
  setLanguagePreference,
  t,
  type LanguagePreference,
} from '@/utils/i18n'
import { createLogger } from '@/utils/logger'
import { isDesktopShell } from '@/platform/desktop'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import AppSelect from '@/components/AppSelect.vue'
import UpdateNotesContent from '@/components/UpdateNotesContent.vue'
import UpdateNotesPopover from '@/components/UpdateNotesPopover.vue'
import { aggregateNotes, createNotesLoader, type Notes } from '@/utils/updateNotes'

const logger = createLogger('views/Settings')
const route = useRoute()
const settingsStore = useSettingsStore()
const notifications = useNotificationStore()
const unsavedChanges = useUnsavedChangesStore()
const updatesStore = useUpdatesStore()

const sections = [
  { id: 'hotkeys', labelKey: 'settings.hotkeys', descriptionKey: 'settings.hotkeysDescription', icon: CommandLineIcon },
  { id: 'screenshot', labelKey: 'settings.screenshot', descriptionKey: 'settings.screenshotDescription', icon: CameraIcon },
  { id: 'ai', labelKey: 'settings.ai', descriptionKey: 'settings.aiDescription', icon: SparklesIcon },
  { id: 'ui', labelKey: 'settings.ui', descriptionKey: 'settings.uiDescription', icon: PaintBrushIcon },
  { id: 'updates', labelKey: 'settings.updates', descriptionKey: 'settings.updatesDescription', icon: ArrowDownTrayIcon },
  { id: 'maintenance', labelKey: 'settings.maintenance', descriptionKey: 'settings.maintenanceDescription', icon: CircleStackIcon },
] as const

const sectionGroups = ([
  { labelKey: 'settings.groupPersonal', ids: ['ui', 'hotkeys', 'screenshot'] },
  { labelKey: 'settings.groupConfiguration', ids: ['ai', 'maintenance'] },
  { labelKey: 'settings.groupApplication', ids: ['updates'] },
] as const).map((group) => ({ ...group, sections: group.ids.map((id) => sections.find((section) => section.id === id)!) }))

type SectionId = typeof sections[number]['id']
type ConfirmAction = 'reset' | 'index' | 'ocr' | null

const isSectionId = (value: unknown): value is SectionId =>
  typeof value === 'string' && sections.some((section) => section.id === value)

const activeSection = ref<SectionId>('ui')

onMounted(() => {
  // 「查看详情」等入口通过 ?section= 直达目标分区；缺省显示导航首项「界面」。
  if (isSectionId(route.query.section)) activeSection.value = route.query.section
})
const loading = ref(true)
const saving = ref(false)
const savedSnapshot = ref('')
const savedAiSnapshot = ref('')
const autoSaveError = ref(false)
const aiSaveError = ref(false)
const resetting = ref(false)
let writeQueue: Promise<unknown> = Promise.resolve()
let autoSavePromise: Promise<boolean> | null = null

// Share one queue across ordinary settings, AI and reset, even after a failure.
const enqueueWrite = <T,>(operation: () => Promise<T>): Promise<T> => {
  const result = writeQueue.then(operation)
  writeQueue = result.catch(() => undefined)
  return result
}
const showApiKey = ref(false)

const screenshotHotkey = ref('')
const recordingHotkey = ref(false)
const captureLimitWindowSeconds = ref(5)
const clusterThreshold = ref(2)
const maxCaptures = ref(10)
const clusterMode = ref(false)
const clusterAutoSubmit = ref(true)
const clusterMaxImages = ref(5)
const clusterTimeout = ref(5)
const aiApiKey = ref('')
const aiBaseUrl = ref('https://api.openai.com/v1')
const aiModel = ref('gpt-4o-mini')
const aiTimeout = ref(60)
const themePreference = ref<ThemePreference>('light')
const language = ref<LanguagePreference>('zh-CN')
const closeAction = ref<'ask' | 'minimize' | 'exit'>('ask')
const updateChannel = ref<'stable' | 'preview' | 'dev-test'>('stable')
const lastRealChannel = ref<'stable' | 'preview'>('stable')
const currentVersion = ref('')
const availableUpdate = ref<{ version: string; notes: string | null } | null>(null)
const checkingUpdate = ref(false)
const updateDialogOpen = ref(false)
const currentNotesOpen = ref(false)
const targetNotesOpen = ref(false)
const updateNotes = computed(() => updatesStore.updateNotes)
const updateNotesLoading = computed(() => updatesStore.updateNotesLoading)
const updateNotesPartial = computed(() => updatesStore.updateNotesPartial)
const installFailed = ref(false)
const loadNotes = createNotesLoader()
// 开发通道用内存里的假索引，真实通道照旧抓 GitHub Pages。
const loadNotesForChannel = async (channel: string) => {
  if (import.meta.env.DEV && channel === DEV_UPDATE_CHANNEL) {
    const { devReleaseNotes } = await import('@/dev/fakeUpdateChannel')
    return devReleaseNotes()
  }
  return loadNotes()
}
// dev-test 按预览语义聚合，再交给 aggregateNotes 的截断规则。
const aggregationChannel = (channel: string): 'stable' | 'preview' =>
  channel === 'stable' ? 'stable' : 'preview'
let updateGeneration = 0
let disposed = false
// 加载/回填设置触发的 updateChannel 变化是程序化的，不代表用户切换通道：
// 此时不得清空启动检测（顶栏）已发现的更新。仅用户手动切换时才清空。
let populatingSettings = false
watch(currentNotesOpen, (open) => {
  if (!open) return
  updatesStore.loadCurrentNotes()
})
// flush: 'sync' 让回调在 updateChannel 赋值时同步触发，populatingSettings 豁免才来得及生效
// （默认 post 会在 populateForm 复位标志后才回调，豁免落空）。
watch(updateChannel, (value) => {
  if (import.meta.env.DEV) {
    updatesStore.setDevChannel(value === DEV_UPDATE_CHANNEL)
    if (value !== DEV_UPDATE_CHANNEL) lastRealChannel.value = value
  }
  if (populatingSettings) return
  updateGeneration++
  availableUpdate.value = null
  updatesStore.availableUpdate = null
  updateDialogOpen.value = false
  targetNotesOpen.value = false
  installFailed.value = false
}, { flush: 'sync' })
watch(activeSection, () => { currentNotesOpen.value = false; targetNotesOpen.value = false })

const themeOptions = [
  { value: 'light', labelKey: 'settings.themeLight' },
  { value: 'dark', labelKey: 'settings.themeDark' },
  { value: 'system', labelKey: 'settings.themeSystem' },
] as const
const activeThemeIndex = computed(() => {
  const index = themeOptions.findIndex((o) => o.value === themePreference.value)
  return index >= 0 ? index : 0
})

const THEME_SLIDE_BASE_MS = 100
const THEME_SLIDE_MS_PER_STEP = 100
const themeSlideDurationMs = ref(THEME_SLIDE_BASE_MS + THEME_SLIDE_MS_PER_STEP)
let previousThemeIndex = activeThemeIndex.value
watch(activeThemeIndex, (next) => {
  themeSlideDurationMs.value =
    THEME_SLIDE_BASE_MS + Math.max(1, Math.abs(next - previousThemeIndex)) * THEME_SLIDE_MS_PER_STEP
  previousThemeIndex = next
})

const updateChannelOptions = computed(() => {
  const options = [
    { value: 'stable', label: t('settings.updateStable') },
    { value: 'preview', label: t('settings.updatePreview') },
  ]
  if (import.meta.env.DEV) {
    options.push({
      value: DEV_UPDATE_CHANNEL,
      label: language.value === 'en-US' ? 'Dev test' : '开发测试',
    })
  }
  return options
})

const testingAi = ref(false)
const aiTestResult = ref<{ success: boolean; message: string } | null>(null)
const indexStatus = ref<IndexRepairStatus | null>(null)
const ocrStatus = ref<OcrBackfillStatus | null>(null)
const confirmAction = ref<ConfirmAction>(null)
const confirmBusy = ref(false)
const discardDialogOpen = ref(false)
let discardResolver: ((confirmed: boolean) => void) | null = null
let pendingDiscardPromise: Promise<boolean> | null = null
let unregisterGuard: (() => boolean) | null = null
let maintenanceTimer: ReturnType<typeof window.setTimeout> | null = null

const currentSection = computed(() => sections.find((section) => section.id === activeSection.value) ?? sections[0])
const maintenanceRunning = computed(() => Boolean(indexStatus.value?.running || ocrStatus.value?.running))
// 开发通道不写进 settings.json：后端只接受 stable/preview。
const persistedUpdateChannel = computed(() =>
  import.meta.env.DEV && updateChannel.value === DEV_UPDATE_CHANNEL
    ? lastRealChannel.value
    : updateChannel.value === 'preview' ? 'preview' : 'stable',
)
const ordinarySettings = computed(() => ({
  hotkeys: { screenshot: screenshotHotkey.value },
  screenshot: {
    capture_limit_window_seconds: captureLimitWindowSeconds.value,
    cluster_threshold: clusterThreshold.value,
    max_captures_per_window: maxCaptures.value,
  },
  cluster: {
    cluster_mode: clusterMode.value,
    cluster_auto_submit: clusterAutoSubmit.value,
    cluster_max_images: clusterMaxImages.value,
    cluster_timeout: clusterTimeout.value,
  },
  ui: {
    theme: themePreference.value,
    language: language.value,
    close_action: closeAction.value,
    update_channel: persistedUpdateChannel.value,
  },
}))
const aiSettings = computed(() => ({
  api_key: aiApiKey.value,
  base_url: aiBaseUrl.value,
  model: aiModel.value,
  timeout: aiTimeout.value,
}))
const formSnapshot = computed(() => JSON.stringify(ordinarySettings.value))
const aiSnapshot = computed(() => JSON.stringify(aiSettings.value))
const dirty = computed(() => Boolean(savedSnapshot.value && formSnapshot.value !== savedSnapshot.value))
const aiDirty = computed(() => Boolean(savedAiSnapshot.value && aiSnapshot.value !== savedAiSnapshot.value))
const ocrSucceeded = computed(() =>
  ocrStatus.value?.result?.succeeded ?? ocrStatus.value?.result?.updated ?? 0,
)

const hotkeyLabels: Record<string, string> = {
  ctrl: 'Ctrl',
  shift: 'Shift',
  alt: 'Alt',
  cmd: 'Win',
  escape: 'Esc',
  enter: 'Enter',
  tab: 'Tab',
  space: 'Space',
  backspace: 'Backspace',
  delete: 'Delete',
  insert: 'Insert',
  home: 'Home',
  end: 'End',
  page_up: 'Page Up',
  page_down: 'Page Down',
  up: 'Up',
  down: 'Down',
  left: 'Left',
  right: 'Right',
}
const specialKeys: Record<string, string> = {
  Escape: 'escape',
  Enter: 'enter',
  Tab: 'tab',
  ' ': 'space',
  Spacebar: 'space',
  Backspace: 'backspace',
  Delete: 'delete',
  Insert: 'insert',
  Home: 'home',
  End: 'end',
  PageUp: 'page_up',
  PageDown: 'page_down',
  ArrowUp: 'up',
  ArrowDown: 'down',
  ArrowLeft: 'left',
  ArrowRight: 'right',
}
const modifierKeys = new Set(['Control', 'Shift', 'Alt', 'Meta'])

const formatHotkey = (hotkey: string) => {
  if (!hotkey) return t('settings.emptyHotkey')
  return hotkey.split('+').map((part) => {
    const normalized = part.trim().replace(/^<|>$/g, '').toLowerCase()
    return hotkeyLabels[normalized] ?? (normalized.length === 1 ? normalized.toUpperCase() : normalized)
  }).join(' + ')
}

const recordHotkey = (event: KeyboardEvent) => {
  event.preventDefault()
  event.stopPropagation()
  if (event.key === 'Escape') {
    recordingHotkey.value = false
    return
  }
  const noModifier = !event.ctrlKey && !event.shiftKey && !event.altKey && !event.metaKey
  if (noModifier && (event.key === 'Backspace' || event.key === 'Delete')) {
    screenshotHotkey.value = ''
    recordingHotkey.value = false
    return
  }

  if (modifierKeys.has(event.key)) return
  const mainKey = specialKeys[event.key]
    ?? (/^F([1-9]|1[0-9]|2[0-4])$/.test(event.key) ? event.key.toLowerCase() : event.key.length === 1 ? event.key.toLowerCase() : '')
  if (!mainKey || mainKey === '+') return

  const parts: string[] = []
  if (event.ctrlKey) parts.push('<ctrl>')
  if (event.shiftKey) parts.push('<shift>')
  if (event.altKey) parts.push('<alt>')
  if (event.metaKey) parts.push('<cmd>')
  parts.push(mainKey.length === 1 ? mainKey : `<${mainKey}>`)
  screenshotHotkey.value = parts.join('+')
  recordingHotkey.value = false
}

const populateForm = () => {
  const settings = settingsStore.settings
  if (!settings) return
  populatingSettings = true
  try {
    screenshotHotkey.value = settings.hotkeys?.screenshot ?? ''
    captureLimitWindowSeconds.value = settings.screenshot?.capture_limit_window_seconds
      ?? settings.screenshot?.debounce_interval
      ?? 5
    clusterThreshold.value = settings.screenshot?.cluster_threshold ?? 2
    maxCaptures.value = settings.screenshot?.max_captures_per_window ?? 10
    clusterMode.value = Boolean(settings.cluster?.cluster_mode)
    clusterAutoSubmit.value = settings.cluster?.cluster_auto_submit ?? true
    clusterMaxImages.value = settings.cluster?.cluster_max_images ?? 10
    clusterTimeout.value = settings.cluster?.cluster_timeout ?? 10
    aiApiKey.value = settings.ai?.api_key ?? ''
    aiBaseUrl.value = settings.ai?.base_url ?? 'https://api.openai.com/v1'
    aiModel.value = settings.ai?.model ?? 'gpt-4o-mini'
    aiTimeout.value = settings.ai?.timeout ?? 60
    themePreference.value = normalizeThemePreference(settings.ui?.theme)
    language.value = normalizeLanguagePreference(settings.ui?.language)
    closeAction.value = settings.ui?.close_action ?? 'ask'
    lastRealChannel.value = settings.ui?.update_channel === 'preview' ? 'preview' : 'stable'
    updateChannel.value = import.meta.env.DEV && updatesStore.devChannel
      ? DEV_UPDATE_CHANNEL
      : lastRealChannel.value
    availableUpdate.value = null
    savedSnapshot.value = formSnapshot.value
    savedAiSnapshot.value = aiSnapshot.value
  } finally {
    populatingSettings = false
  }
}

const loadSettings = async () => {
  loading.value = true
  await settingsStore.load()
  populateForm()
  loading.value = false
}

const refreshMaintenance = async () => {
  const [nextIndex, nextOcr] = await Promise.allSettled([indexApi.status(), ocrApi.status()])
  if (nextIndex.status === 'fulfilled') indexStatus.value = nextIndex.value
  if (nextOcr.status === 'fulfilled') ocrStatus.value = nextOcr.value
}

const scheduleMaintenancePoll = () => {
  if (maintenanceTimer) window.clearTimeout(maintenanceTimer)
  if (!maintenanceRunning.value) return
  maintenanceTimer = window.setTimeout(async () => {
    await refreshMaintenance()
    scheduleMaintenancePoll()
  }, 1500)
}

// Acknowledge only the submitted snapshot; never overwrite newer edits or AI drafts.
const flushAutoSave = (): Promise<boolean> => {
  if (autoSavePromise) return autoSavePromise
  if (loading.value || resetting.value || !dirty.value) return Promise.resolve(!dirty.value)
  autoSaveError.value = false
  autoSavePromise = enqueueWrite(async () => {
    while (dirty.value && !resetting.value) {
      const snapshot = formSnapshot.value
      const payload = JSON.parse(snapshot) as typeof ordinarySettings.value
      try {
        await settingsStore.update(payload)
        savedSnapshot.value = snapshot
        applyThemePreference(payload.ui.theme)
        setLanguagePreference(payload.ui.language)
      } catch (error) {
        logger.error('Failed to auto-save settings: %s', error)
        autoSaveError.value = true
        notifications.show(t('settings.saveFailed'), 'error', 2800)
        return false
      }
    }
    return !dirty.value
  }).finally(() => { autoSavePromise = null })
  return autoSavePromise
}

watch(formSnapshot, () => {
  if (!loading.value && !resetting.value) void flushAutoSave()
})

const handleSaveAi = async () => {
  if (saving.value || resetting.value || !aiDirty.value) return
  const snapshot = aiSnapshot.value
  const draft = { ...aiSettings.value }
  saving.value = true
  aiSaveError.value = false
  try {
    await enqueueWrite(() => settingsStore.update({ ai: {
      ...draft,
      api_key: draft.api_key.trim(),
      base_url: draft.base_url.trim(),
      model: draft.model.trim(),
    } }))
    savedAiSnapshot.value = snapshot
    notifications.show(t('settings.saved'), 'success', 1800)
  } catch (error) {
    logger.error('Failed to save AI settings: %s', error)
    aiSaveError.value = true
    notifications.show(t('settings.saveFailed'), 'error', 2800)
  } finally {
    saving.value = false
  }
}

// 检查更新的核心流程，手动点击与进入设置页自动检测共用。
// notify/silent 控制反馈：手动点击要给"已是最新/失败"提示并弹窗，自动检测静默、只把卡片摆上。
const runUpdateCheck = async ({ silent }: { silent: boolean }) => {
  if (!isDesktopShell() || checkingUpdate.value || updatesStore.installing) return
  checkingUpdate.value = true
  availableUpdate.value = null
  installFailed.value = false
  targetNotesOpen.value = false
  const generation = ++updateGeneration
  const channel = updateChannel.value
  try {
    let target: { version: string; notes: string | null } | null
    if (import.meta.env.DEV && channel === DEV_UPDATE_CHANNEL) {
      const { devCheckForUpdate } = await import('@/dev/fakeUpdateChannel')
      target = devCheckForUpdate(currentVersion.value)
    } else {
      const { invoke } = await import('@tauri-apps/api/core')
      target = await invoke<{ version: string; notes: string | null } | null>('check_for_update', { channel })
    }
    if (disposed || generation !== updateGeneration) return
    availableUpdate.value = target
    updatesStore.availableUpdate = target
    if (target) updatesStore.refreshUpdateNotes(target.version)
    if (!target) {
      if (!silent) notifications.show(t('settings.updateCurrent'), 'info')
      return
    }
    currentNotesOpen.value = false
    if (!silent) updateDialogOpen.value = true
  } catch (error) {
    logger.error('Failed to check for updates: %s', error)
    if (!silent && !disposed && generation === updateGeneration) notifications.show(t('settings.updateCheckFailed'), 'error')
  } finally {
    checkingUpdate.value = false
  }
}

// 把共享 store 已发现的更新同步到本地展示：不重新检测，任何进入路径都执行，
// 这样顶栏发起的下载在进行中时，设置页也能读到同一份 installing 状态。
const adoptStoreUpdate = () => {
  if (!updatesStore.availableUpdate) return
  availableUpdate.value = updatesStore.availableUpdate
}

const checkForUpdate = () => runUpdateCheck({ silent: false })

// 安装状态统一存放在共享 store：设置页卡片、更新弹窗与顶栏浮窗读同一份 installing，
// 任何一处发起下载，其余位置同步显示「正在下载」。这里只负责失败后的页面内收尾。
const installUpdate = async () => {
  if (!availableUpdate.value || updatesStore.installing || updatesStore.checking) return
  targetNotesOpen.value = false
  currentNotesOpen.value = false
  const ok = await updatesStore.installUpdate()
  if (!ok) {
    updateDialogOpen.value = false
    notifications.show(t('settings.updateInstallFailed'), 'error')
    availableUpdate.value = null
    installFailed.value = true
  }
}

const repositoryUrl = 'https://github.com/xiaofeng-iii/Glimpse'

// 桌面壳的 WebView 会吞掉 target="_blank" 的新窗口请求，改交系统浏览器打开；浏览器端保留原生链接行为。
const openRepository = async (event: MouseEvent) => {
  if (!isDesktopShell()) return
  event.preventDefault()
  try {
    const { openUrl } = await import('@tauri-apps/plugin-opener')
    await openUrl(repositoryUrl)
  } catch (error) {
    logger.error('Failed to open repository link: %s', error)
  }
}

const testAi = async () => {
  testingAi.value = true
  aiTestResult.value = null
  try {
    aiTestResult.value = await settingsStore.testAi(
      aiApiKey.value,
      aiBaseUrl.value,
      aiModel.value,
    )
  } catch {
    aiTestResult.value = { success: false, message: t('settings.testFailed') }
  } finally {
    testingAi.value = false
  }
}

const openConfirmation = (action: Exclude<ConfirmAction, null>) => {
  confirmAction.value = action
}

const confirmationCopy = computed(() => {
  if (confirmAction.value === 'reset') {
    return {
      title: t('settings.resetTitle'),
      description: t('settings.resetConfirm'),
      confirm: t('action.reset'),
      destructive: true,
    }
  }
  if (confirmAction.value === 'index') {
    return {
      title: t('settings.repairIndex'),
      description: t('settings.indexRepairConfirm'),
      confirm: t('settings.startRepair'),
      destructive: false,
    }
  }
  return {
    title: t('settings.ocrBackfill'),
    description: t('settings.ocrBackfillConfirm'),
    confirm: t('settings.startBackfill'),
    destructive: false,
  }
})

const runConfirmedAction = async () => {
  const action = confirmAction.value
  if (!action || confirmBusy.value) return
  confirmBusy.value = true
  if (action === 'reset') resetting.value = true
  try {
    if (action === 'reset') {
      await enqueueWrite(async () => {
        await settingsStore.reset()
        populateForm()
        autoSaveError.value = false
        aiSaveError.value = false
      })
      applyThemePreference(themePreference.value)
      setLanguagePreference(language.value)
      notifications.show(t('settings.resetDone'), 'success', 1800)
    } else if (action === 'index') {
      indexStatus.value = await indexApi.repair()
      notifications.show(t('message.indexRepairStarted'), 'success', 1800)
      scheduleMaintenancePoll()
    } else {
      ocrStatus.value = await ocrApi.backfill()
      notifications.show(t('message.ocrBackfillStarted'), 'success', 1800)
      scheduleMaintenancePoll()
    }
    confirmAction.value = null
  } catch (error) {
    logger.error('Maintenance action failed: %s', error)
    notifications.show(
      maintenanceRunning.value ? t('message.maintenanceConflict') : t('message.maintenanceFailed'),
      'error',
      3000,
    )
  } finally {
    confirmBusy.value = false
    resetting.value = false
  }
}

const resolveDiscard = (confirmed: boolean) => {
  discardDialogOpen.value = false
  if (confirmed) {
    const saved = JSON.parse(savedAiSnapshot.value) as typeof aiSettings.value
    aiApiKey.value = saved.api_key
    aiBaseUrl.value = saved.base_url
    aiModel.value = saved.model
    aiTimeout.value = saved.timeout
  }
  discardResolver?.(confirmed)
  discardResolver = null
  pendingDiscardPromise = null
}

const canLeave = async () => {
  await writeQueue
  if (!await flushAutoSave()) return false
  if (!aiDirty.value) return true
  if (pendingDiscardPromise) return pendingDiscardPromise
  discardDialogOpen.value = true
  pendingDiscardPromise = new Promise<boolean>((resolve) => {
    discardResolver = resolve
  })
  return pendingDiscardPromise
}

// 下载安装由全局 store 承载、完成时会整体重启应用，不依赖设置页存续，
// 因此安装期间不再拦截离开页面（与顶栏发起下载后可自由导航保持一致）。
onBeforeRouteLeave(async () => canLeave())

onMounted(async () => {
  unregisterGuard = unsavedChanges.register(canLeave)
  await Promise.all([loadSettings(), refreshMaintenance()])
  if (isDesktopShell()) {
    try {
      const { getVersion } = await import('@tauri-apps/api/app')
      currentVersion.value = await getVersion()
    } catch (error) {
      logger.error('Failed to read app version: %s', error)
    }
  }
  // 当前版本笔记从共享 store 读取；这里兜底记录版本，避免启动检测未完成时查询落空。
  if (currentVersion.value) {
    updatesStore.recordCurrentVersion(currentVersion.value)
  }
  // 默认进入不自动检测：检测由用户点「检查更新」或启动流程触发；
  // 但共享 store 里已发现的更新（含进行中的下载）总是同步进来展示。
  adoptStoreUpdate()
  scheduleMaintenancePoll()
})

onUnmounted(() => {
  disposed = true
  updateGeneration++
  if (maintenanceTimer) window.clearTimeout(maintenanceTimer)
  unregisterGuard?.()
  discardResolver?.(false)
})
</script>

<template>
  <ConfirmDialog id="update-notes" :open="updateDialogOpen" :title="t('settings.updateAvailable', { version: availableUpdate?.version ?? '' })" :description="updatesStore.installing ? t('settings.updateInstalling') : ''" :confirm-label="t('settings.updateNow')" :cancel-label="t('settings.updateLater')" :busy="updatesStore.installing" hide-icon @cancel="updateDialogOpen = false" @confirm="installUpdate">
    <UpdateNotesContent v-if="!updatesStore.installing" :notes="updateNotes" :loading="updateNotesLoading" :partial="updateNotesPartial" :raw="updateNotesPartial ? availableUpdate?.notes ?? '' : undefined" />
  </ConfirmDialog>
  <main class="settings-page h-full min-h-0 bg-[var(--shell-window-bg)] p-4 sm:p-5">
    <div class="mx-auto flex h-full min-h-0 w-full max-w-[1020px] flex-col">
      <header class="mb-4 flex-none">
        <h1 class="text-xl font-semibold tracking-[-0.01em] text-[var(--shell-ink)]">{{ t('settings.title') }}</h1>
      </header>

      <div v-if="loading" class="flex min-h-[65vh] items-center justify-center">
        <ArrowPathIcon class="h-8 w-8 animate-spin text-[var(--color-primary)]" :aria-label="t('settings.loading')" />
      </div>

      <div v-else class="settings-layout min-h-0 flex-1">
        <nav class="settings-nav min-h-0 overflow-y-auto" :aria-label="t('settings.sectionNavigation')">
          <div v-for="group in sectionGroups" :key="group.labelKey" class="settings-nav__group flex flex-col">
            <h3 class="px-3 pb-0.5 pt-1 text-xs font-medium text-[var(--shell-muted)]">{{ t(group.labelKey) }}</h3>
            <button
              v-for="section in group.sections"
              :key="section.id"
              type="button"
              class="flex h-[var(--control-h-md)] min-h-[var(--control-h-md)] w-full items-center gap-2.5 rounded-[var(--radius-md)] px-3 text-left text-[0.8125rem] font-normal transition"
              :class="activeSection === section.id
                ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-hover)]'
                : 'text-[var(--shell-ink)] hover:bg-[var(--shell-control-hover)]'"
              :aria-current="activeSection === section.id ? 'page' : undefined"
              @click="activeSection = section.id"
            >
              <component :is="section.icon" class="h-4 w-4 flex-none" aria-hidden="true" />
              {{ t(section.labelKey) }}
            </button>
          </div>
        </nav>

        <section class="settings-content min-h-0">
          <header class="settings-content__header flex-none">
            <div class="settings-content__header-inner">
              <h2 class="text-base font-semibold tracking-[-0.01em] text-[var(--shell-ink)]">{{ t(currentSection.labelKey) }}</h2>
              <p class="mt-1 text-sm text-[var(--shell-muted)]">{{ t(currentSection.descriptionKey) }}</p>
              <div v-if="autoSaveError" class="mt-1 flex items-center gap-2 text-xs text-red-600" role="status" aria-live="polite">
                <span>{{ t('settings.saveFailed') }}</span>
                <button type="button" class="underline" :disabled="resetting" @click="flushAutoSave">{{ t('settings.retrySave') }}</button>
              </div>
            </div>
            <div class="settings-content__header-divider"></div>
          </header>

          <div :inert="resetting || discardDialogOpen" class="settings-content__body min-h-0 flex-1 overflow-y-auto px-7 py-5">
            <div class="settings-panel">
              <template v-if="activeSection === 'hotkeys'">
              <div class="setting-row">
                <div>
                  <label class="setting-label">{{ t('settings.screenshotHotkey') }}</label>
                  <p class="setting-help">{{ t('settings.recordHelp') }}</p>
                </div>
                <button
                  type="button"
                  class="setting-input flex min-h-[1.875rem] items-center justify-between text-left"
                  :class="{ 'setting-input--recording': recordingHotkey }"
                  @click="recordingHotkey = true"
                  @keydown="recordHotkey"
                >
                  <span>{{ recordingHotkey ? t('settings.recording') : formatHotkey(screenshotHotkey) }}</span>
                  <CommandLineIcon class="h-5 w-5 flex-none text-[var(--shell-muted)]" aria-hidden="true" />
                </button>
              </div>
              <div class="setting-row">
                <div>
                  <span class="setting-label">{{ t('settings.searchHotkey') }}</span>
                  <p class="setting-help">{{ t('settings.searchHotkeyFixed') }}</p>
                </div>
                <div class="setting-readonly">Ctrl + F</div>
              </div>
            </template>

            <template v-else-if="activeSection === 'screenshot'">
              <label class="setting-row">
                <span class="setting-label">{{ t('settings.captureLimitWindow') }}</span>
                <input v-model.number="captureLimitWindowSeconds" class="setting-input" type="number" min="1" max="120" />
              </label>
              <label class="setting-row">
                <span class="setting-label">{{ t('settings.maxCaptures') }}</span>
                <input v-model.number="maxCaptures" class="setting-input" type="number" min="1" max="100" />
              </label>
              <label class="setting-row">
                <span class="setting-label">{{ t('settings.clusterThreshold') }}</span>
                <input v-model.number="clusterThreshold" class="setting-input" type="number" min="1" max="20" />
              </label>

              <div>
                <label class="flex cursor-pointer items-center justify-between gap-4">
                  <span>
                    <span class="setting-label">{{ t('settings.enableCluster') }}</span>
                    <span class="setting-help">{{ t('settings.clusterScreenshotHint') }}</span>
                  </span>
                  <input v-model="clusterMode" type="checkbox" class="h-5 w-5 accent-[var(--color-primary)]" />
                </label>
                <div class="mt-3.5 grid gap-3 sm:grid-cols-3" :class="{ 'opacity-50': !clusterMode }">
                  <label>
                    <span class="setting-label">{{ t('settings.maxImages') }}</span>
                    <input v-model.number="clusterMaxImages" class="setting-input mt-1.5" type="number" min="2" max="20" :disabled="!clusterMode" />
                  </label>
                  <label>
                    <span class="setting-label">{{ t('settings.timeoutSeconds') }}</span>
                    <input v-model.number="clusterTimeout" class="setting-input mt-1.5" type="number" min="1" max="120" :disabled="!clusterMode" />
                  </label>
                  <label class="flex items-center gap-3 pt-8">
                    <input v-model="clusterAutoSubmit" type="checkbox" class="h-5 w-5 accent-[var(--color-primary)]" :disabled="!clusterMode" />
                    <span class="setting-label">{{ t('settings.autoSubmit') }}</span>
                  </label>
                </div>
              </div>
            </template>

            <template v-else-if="activeSection === 'ai'">
              <div class="setting-row">
                <div>
                  <label for="ai-api-key" class="setting-label">API Key</label>
                  <p class="setting-help">{{ t('settings.localOnly') }}</p>
                </div>
                <div class="relative w-full max-w-[320px]">
                  <input
                    id="ai-api-key"
                    v-model="aiApiKey"
                    class="setting-input w-full pr-12"
                    :type="showApiKey ? 'text' : 'password'"
                    autocomplete="off"
                  />
                  <button
                    type="button"
                    class="absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-[var(--shell-muted)] hover:bg-[var(--shell-control-hover)]"
                    :aria-label="showApiKey ? t('settings.hideApiKey') : t('settings.showApiKey')"
                    @click="showApiKey = !showApiKey"
                  >
                    <EyeSlashIcon v-if="showApiKey" class="h-5 w-5" aria-hidden="true" />
                    <EyeIcon v-else class="h-5 w-5" aria-hidden="true" />
                  </button>
                </div>
              </div>
              <label class="setting-row">
                <span class="setting-label">Base URL</span>
                <input v-model="aiBaseUrl" class="setting-input" type="url" />
              </label>
              <label class="setting-row">
                <span class="setting-label">{{ t('settings.visualModel') }}</span>
                <input v-model="aiModel" class="setting-input" type="text" />
              </label>
              <div class="setting-row">
                <div>
                  <span class="setting-label">{{ t('settings.vectorModel') }}</span>
                  <p class="setting-help">{{ t('settings.fixedBuiltin') }}</p>
                </div>
                <div class="setting-readonly flex items-center gap-2">
                  <LockClosedIcon class="h-4 w-4 flex-none" aria-hidden="true" />
                  BAAI/bge-small-zh-v1.5
                </div>
              </div>
              <label class="setting-row">
                <span class="setting-label">{{ t('settings.requestTimeout') }}</span>
                <input v-model.number="aiTimeout" class="setting-input" type="number" min="1" max="600" />
              </label>

              <div class="flex flex-wrap items-center gap-3">
                <button type="button" class="btn-secondary" :disabled="testingAi" @click="testAi">
                  {{ testingAi ? t('settings.testing') : t('settings.test') }}
                </button>
                <button type="button" class="btn-primary" data-testid="save-ai" :disabled="saving || !aiDirty || resetting" :aria-busy="saving" @click="handleSaveAi">
                  {{ saving ? t('settings.saving') : t('action.save') }}
                </button>
                <span v-if="aiSaveError" role="alert" class="text-sm text-red-600">{{ t('settings.saveFailed') }}</span>
                <p
                  v-if="aiTestResult"
                  class="flex items-center gap-2 text-sm"
                  :class="aiTestResult.success ? 'text-emerald-600' : 'text-red-600'"
                >
                  <CheckCircleIcon class="h-5 w-5 flex-none" aria-hidden="true" />
                  {{ aiTestResult.message }}
                </p>
              </div>

              <div class="settings-panel__card bg-[var(--color-primary-soft)]">
                <div class="flex items-center gap-2 text-sm font-semibold text-[var(--color-primary-hover)]">
                  <CpuChipIcon class="h-5 w-5 flex-none" aria-hidden="true" />
                  {{ t('settings.localOcr') }}
                </div>
                <dl class="mt-3 grid gap-2.5 text-sm sm:grid-cols-2">
                  <div><dt class="text-[var(--shell-muted)]">{{ t('settings.ocrModel') }}</dt><dd class="mt-0.5 font-medium text-[var(--shell-ink)]">PP-OCRv6-small</dd></div>
                  <div><dt class="text-[var(--shell-muted)]">{{ t('settings.ocrFramework') }}</dt><dd class="mt-0.5 font-medium text-[var(--shell-ink)]">RapidOCR 3.9.2</dd></div>
                  <div><dt class="text-[var(--shell-muted)]">{{ t('settings.ocrRuntime') }}</dt><dd class="mt-0.5 font-medium text-[var(--shell-ink)]">ONNX Runtime CPU</dd></div>
                  <div><dt class="text-[var(--shell-muted)]">{{ t('settings.dataPrivacy') }}</dt><dd class="mt-0.5 font-medium text-[var(--shell-ink)]">{{ t('settings.localNoUpload') }}</dd></div>
                </dl>
              </div>
            </template>

            <template v-else-if="activeSection === 'ui'">
              <div class="setting-row">
                <span class="setting-label">{{ t('settings.theme') }}</span>
                <div
                  class="theme-switcher inline-grid grid-flow-col auto-cols-fr items-center"
                  role="radiogroup"
                  :aria-label="t('settings.theme')"
                  :style="{ '--segment-slide-duration': `${themeSlideDurationMs}ms` }"
                >
                  <span
                    class="theme-switcher__thumb"
                    :style="{ transform: `translateX(calc(${activeThemeIndex} * (100% + var(--theme-segment-inset))))` }"
                    aria-hidden="true"
                  ></span>
                  <button
                    v-for="option in themeOptions"
                    :key="option.value"
                    type="button"
                    class="theme-switcher__button text-xs font-medium text-[var(--shell-muted)] hover:text-[var(--shell-ink)]"
                    :aria-pressed="themePreference === option.value"
                    @click="themePreference = option.value"
                  >
                    {{ t(option.labelKey) }}
                  </button>
                  <span
                    class="theme-switcher__ink"
                    :style="{ transform: `translateX(calc(${activeThemeIndex} * (100% + var(--theme-segment-inset))))` }"
                    aria-hidden="true"
                  >
                    <span
                      class="theme-switcher__ink-row"
                      :style="{ transform: `translateX(calc(${-activeThemeIndex} * ((100% + var(--theme-segment-inset)) / 3)))` }"
                    >
                      <span
                        v-for="option in themeOptions"
                        :key="option.value"
                        class="theme-switcher__ink-label text-xs font-medium"
                      >
                        {{ t(option.labelKey) }}
                      </span>
                    </span>
                  </span>
                </div>
              </div>
              <div class="setting-row">
                <label id="settings-language-label" for="settings-language" class="setting-label">{{ t('settings.language') }}</label>
                <AppSelect
                  id="settings-language"
                  v-model="language"
                  aria-labelledby="settings-language-label"
                  :options="[
                    { value: 'zh-CN', label: t('settings.languageZh') },
                    { value: 'en-US', label: t('settings.languageEn') },
                  ]"
                />
              </div>
              <div class="setting-row">
                <label id="settings-close-action-label" for="settings-close-action" class="setting-label">{{ t('settings.closeAction') }}</label>
                <AppSelect
                  id="settings-close-action"
                  v-model="closeAction"
                  aria-labelledby="settings-close-action-label"
                  :options="[
                    { value: 'ask', label: t('settings.closeAsk') },
                    { value: 'minimize', label: t('settings.closeMinimize') },
                    { value: 'exit', label: t('settings.closeExit') },
                  ]"
                />
              </div>
            </template>

            <template v-else-if="activeSection === 'updates'">
              <div class="setting-row">
                <div>
                  <label id="settings-update-channel-label" for="settings-update-channel" class="setting-label">{{ t('settings.updateChannel') }}</label>
                  <p class="setting-help">{{ t('settings.updateChannelHint') }}</p>
                </div>
                <AppSelect
                  id="settings-update-channel"
                  v-model="updateChannel"
                  aria-labelledby="settings-update-channel-label"
                  :options="updateChannelOptions"
                  :disabled="updatesStore.installing"
                />
              </div>
              <div class="setting-row">
                <div>
                  <span class="setting-label">{{ t('settings.updateCheckLabel') }}</span>
                  <p v-if="!isDesktopShell()" class="setting-help">{{ t('settings.updateDesktopOnly') }}</p>
                </div>
                <div class="flex flex-wrap items-center justify-end gap-3">
                  <p v-if="installFailed" role="alert" class="text-sm text-[var(--shell-muted)]">{{ t('settings.updateRetryCheck') }}</p>
                  <button type="button" class="btn-secondary" :disabled="!isDesktopShell() || checkingUpdate || updatesStore.installing" @click="checkForUpdate">
                    {{ checkingUpdate ? t('settings.updateChecking') : t('settings.updateCheck') }}
                  </button>
                </div>
              </div>
              <div v-if="availableUpdate" class="settings-panel__card bg-[var(--color-surface-subtle)]">
                <div class="flex items-center gap-2">
                  <p class="setting-label">{{ t('settings.updateAvailable', { version: availableUpdate.version }) }}</p>
                  <UpdateNotesPopover v-model:open="targetNotesOpen" :label="t('settings.updateAvailable', { version: availableUpdate.version })">
                    <template #trigger><button type="button" class="inline-flex h-7 w-7 items-center justify-center rounded text-[var(--shell-muted)]" :aria-label="t('settings.notesView')" :disabled="updatesStore.installing"><span aria-hidden="true">›</span></button></template>
                    <UpdateNotesContent :notes="updateNotes" :loading="updateNotesLoading" :partial="updateNotesPartial" :raw="updateNotesPartial ? availableUpdate.notes ?? '' : undefined" />
                  </UpdateNotesPopover>
                </div>
                <button type="button" class="btn-primary mt-3" :disabled="updatesStore.installing || checkingUpdate" @click="installUpdate">
                  {{ updatesStore.installing ? t('settings.updateInstalling') : t('settings.updateInstall') }}
                </button>
              </div>
            </template>

            <template v-else>
              <div class="maintenance-card">
                <div class="flex items-start gap-3.5">
                  <CircleStackIcon class="mt-1 h-6 w-6 flex-none text-[var(--color-primary)]" aria-hidden="true" />
                  <div class="min-w-0 flex-1">
                    <h3 class="setting-label">{{ t('settings.semanticIndex') }}</h3>
                    <p class="setting-help">{{ t('settings.semanticIndexHint') }}</p>
                    <p v-if="indexStatus?.running" class="mt-3 text-sm text-[var(--color-primary)]">{{ t('settings.indexRepairRunning') }}</p>
                    <p v-else-if="indexStatus?.result" class="mt-3 text-sm text-[var(--shell-muted)]">
                      {{ t('settings.indexRepairLastResult', {
                        processed: indexStatus.result.processed,
                        indexed: indexStatus.result.indexed,
                        failed: indexStatus.result.failed,
                      }) }}
                    </p>
                    <p v-else-if="indexStatus" class="mt-3 text-sm text-[var(--shell-muted)]">
                      {{ t('settings.indexRepairIdle', {
                        sqlite: indexStatus.sqlite_count ?? 0,
                        chroma: indexStatus.chroma_count ?? 0,
                      }) }}
                    </p>
                  </div>
                  <button
                    type="button"
                    class="btn-secondary"
                    :disabled="maintenanceRunning"
                    @click="openConfirmation('index')"
                  >
                    {{ indexStatus?.running ? t('settings.repairingIndex') : t('settings.repairIndex') }}
                  </button>
                </div>
              </div>

              <div class="maintenance-card">
                <div class="flex items-start gap-3.5">
                  <CpuChipIcon class="mt-1 h-6 w-6 flex-none text-[var(--color-primary)]" aria-hidden="true" />
                  <div class="min-w-0 flex-1">
                    <h3 class="setting-label">{{ t('settings.ocrBackfill') }}</h3>
                    <p class="setting-help">{{ t('settings.ocrBackfillHint') }}</p>
                    <p v-if="ocrStatus?.running" class="mt-3 text-sm text-[var(--color-primary)]">
                      {{ t('settings.ocrBackfillRunning', {
                        processed: ocrStatus.result?.processed ?? 0,
                        total: ocrStatus.result?.total ?? 0,
                      }) }}
                    </p>
                    <p v-else-if="ocrStatus?.result" class="mt-3 text-sm text-[var(--shell-muted)]">
                      {{ t('settings.ocrBackfillResult', {
                        processed: ocrStatus.result.processed,
                        succeeded: ocrSucceeded,
                        skipped: ocrStatus.result.skipped,
                        failed: ocrStatus.result.failed,
                      }) }}
                    </p>
                  </div>
                  <button
                    type="button"
                    class="btn-secondary"
                    :disabled="maintenanceRunning"
                    @click="openConfirmation('ocr')"
                  >
                    {{ ocrStatus?.running ? t('settings.backfillingOcr') : t('settings.startBackfill') }}
                  </button>
                </div>
              </div>
            </template>
            </div>
            <div class="settings-meta">
              <UpdateNotesPopover v-if="currentVersion" v-model:open="currentNotesOpen" :label="`${t('settings.updateVersion')} ${currentVersion}`">
                <template #trigger><button type="button" class="version-notes-trigger">Glimpse v{{ currentVersion }}</button></template>
                <UpdateNotesContent :notes="updatesStore.currentNotes" :loading="updatesStore.currentNotesLoading" :error="updatesStore.currentNotesError ? t(updatesStore.currentNotesError) : ''" />
              </UpdateNotesPopover>
              <span v-else class="settings-meta__version">Glimpse</span>
              <span class="settings-meta__dot" aria-hidden="true">·</span>
              <a class="settings-meta__link" :href="repositoryUrl" target="_blank" rel="noreferrer" @click="openRepository">GitHub</a>
            </div>
          </div>

          <div class="settings-content__footer flex-none px-7 py-3">
            <button
              type="button"
              class="settings-reset-link text-xs text-[var(--shell-muted)] hover:text-red-600 transition"
              :disabled="resetting"
              @click="openConfirmation('reset')"
            >
              {{ t('action.reset') }}
            </button>
          </div>
        </section>
      </div>
    </div>

    <ConfirmDialog
      id="settings-confirm"
      :open="Boolean(confirmAction)"
      :title="confirmationCopy.title"
      :description="confirmationCopy.description"
      :confirm-label="confirmationCopy.confirm"
      :cancel-label="t('action.cancel')"
      :destructive="confirmationCopy.destructive"
      :busy="confirmBusy"
      @confirm="runConfirmedAction"
      @cancel="confirmAction = null"
    />
    <ConfirmDialog
      id="settings-discard"
      :open="discardDialogOpen"
      :title="t('settings.discardTitle')"
      :description="t('settings.discardDescription')"
      :confirm-label="t('settings.discard')"
      :cancel-label="t('settings.keepEditing')"
      destructive
      @confirm="resolveDiscard(true)"
      @cancel="resolveDiscard(false)"
    />
  </main>
</template>

<style scoped>
.version-notes-trigger {
  display: inline;
  min-height: 0;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  letter-spacing: inherit;
  text-decoration: underline;
  text-decoration-color: transparent;
  text-underline-offset: 2px;
  cursor: pointer;
  transition: color 400ms ease-out, text-decoration-color 400ms ease-out;
}
.version-notes-trigger:hover {
  color: var(--color-primary-hover);
  text-decoration-color: currentColor;
}
.settings-layout {
  display: grid;
  min-height: 0;
  grid-template-columns: 230px minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr);
  gap: 1.25rem;
  justify-content: center;
}

.settings-page {
  overflow-y: auto;
}

.settings-nav,
.settings-content {
  border: 1px solid var(--shell-line);
  background: var(--shell-card);
  box-shadow: var(--shell-card-shadow);
}

.settings-nav {
  display: flex;
  min-height: 0;
  flex-direction: column;
  gap: .25rem;
  border-radius: var(--radius-xl);
  padding: .375rem;
}

/* 隐藏内容区滚动条：滚动条出现时会占走宽度，让面板与标题分隔线错位。 */
.settings-content__body {
  scrollbar-width: none;
}

.settings-content__body::-webkit-scrollbar {
  display: none;
}

.settings-content__footer {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  padding-top: 0.35rem;
  padding-bottom: 0.85rem;
}

.settings-reset-link {
  background: transparent;
  border: none;
  padding: 0;
  cursor: pointer;
  opacity: .65;
  outline: none;
  font-size: .75rem;
  color: var(--shell-muted);
}

.settings-reset-link:hover:not(:disabled) {
  opacity: 1;
  color: var(--color-danger);
  text-decoration: underline;
}

/* 面板下方的版本与仓库元信息行：居中低对比，悬浮缓慢亮起，所有分区共用。 */
.settings-meta {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: .5rem;
  margin-top: 1rem;
  font-size: .75rem;
  line-height: var(--line-height-12);
  color: color-mix(in srgb, var(--shell-muted) 65%, transparent);
}

.settings-meta__dot {
  opacity: .7;
}

.settings-meta__link {
  color: inherit;
  text-decoration: underline;
  text-decoration-color: transparent;
  text-underline-offset: 2px;
  transition: color 400ms ease-out, text-decoration-color 400ms ease-out;
}

.settings-meta__link:hover {
  color: var(--color-primary-hover);
  text-decoration-color: currentColor;
}

.settings-reset-link:disabled {
  opacity: .35;
  cursor: not-allowed;
}

.settings-nav__group {
  display: flex;
  flex-direction: column;
  gap: .25rem;
}

.settings-content {
  display: flex;
  min-height: 500px;
  flex-direction: column;
  min-width: 0;
  max-width: 720px;
  width: 100%;
  overflow: hidden;
  border-radius: var(--radius-xl);
}

.settings-content__header {
  display: flex;
  flex-direction: column;
}

.settings-content__header-inner {
  padding: 1.375rem 1.75rem 1rem 1.75rem;
}

.settings-content__header-divider {
  margin: 0 1.75rem;
  border-bottom: 1px solid var(--shell-line);
}

.setting-row {
  display: grid;
  grid-template-columns: minmax(160px, 200px) minmax(0, 1fr);
  align-items: center;
  gap: 1rem;
}

/* 右侧操作元素统一贴到行右缘，对齐靠结构（固定标签列 + 统一右缘）而非分隔线，
   避免行底线与控件描边撞色造成的"满屏是线"。 */
.setting-row > :last-child {
  justify-self: end;
}

/* 设置项容器：低对比度细线包裹整组设置项，项间用内缩分隔线分开。
   分隔线不贯通容器两端，靠容器左右内边距实现。 */
.settings-panel {
  --settings-panel-line: color-mix(in srgb, var(--shell-line) 55%, transparent);
  border: 1px solid var(--settings-panel-line);
  border-radius: var(--radius-xl);
  padding-inline: 1rem;
}

.settings-panel > * {
  padding-block: .75rem;
}

.settings-panel > * + * {
  border-top: 1px solid var(--settings-panel-line);
}

/* 面板内的有色信息块：留出与相邻行及容器边缘的呼吸距离，不参与行分隔线。 */
.settings-panel > .settings-panel__card {
  margin-block: .75rem;
  border-top: 0;
  border-radius: var(--radius-lg);
  padding: .875rem 1rem;
}

.setting-label {
  display: block;
  font-size: .8125rem;
  font-weight: 600;
  line-height: var(--line-height-14);
  color: var(--shell-ink);
}

.setting-help {
  display: block;
  margin-top: 2px;
  font-size: .75rem;
  line-height: var(--line-height-12);
  color: var(--shell-muted);
}

.setting-input,
.setting-readonly {
  width: 100%;
  max-width: 320px;
  height: var(--control-h-md);
  min-height: var(--control-h-md);
  border: 1px solid var(--shell-line);
  border-radius: var(--radius-md);
  background: var(--shell-control-bg);
  padding: 0 .65rem;
  font-size: .8125rem;
  color: var(--shell-ink);
  outline: none;
  transition: border-color 140ms ease, background-color 140ms ease;
}

.setting-input[type='number'] {
  max-width: 120px;
}

.setting-input:focus {
  border-color: var(--color-primary);
  box-shadow: none;
  background: var(--shell-control-bg);
}

.setting-input--recording {
  border-color: var(--color-primary);
  background: var(--shell-control-bg);
  box-shadow: none;
}

.setting-readonly {
  display: flex;
  align-items: center;
  color: var(--shell-muted);
  cursor: default;
}

/* 扁平化三段式主题切换器：保持线框浅底外观 + 独立平移滑块动效与遮罩文字变色 */
.theme-switcher {
  --theme-segment-inset: 2px;
  --theme-segment-radius: calc(var(--radius-md) - var(--theme-segment-inset));
  --segment-slide-easing: cubic-bezier(0.33, 1, 0.68, 1);
  position: relative;
  width: 10.5rem;
  height: var(--control-h-md);
  gap: var(--theme-segment-inset);
  padding: var(--theme-segment-inset);
  border: 1px solid var(--shell-line);
  border-radius: var(--radius-md);
  background: var(--color-surface-subtle);
}

.theme-switcher__thumb {
  position: absolute;
  top: var(--theme-segment-inset);
  bottom: var(--theme-segment-inset);
  left: var(--theme-segment-inset);
  width: calc((100% - var(--theme-segment-inset) * 4) / 3);
  border-radius: var(--theme-segment-radius);
  background: var(--color-surface-raised, var(--shell-card));
  box-shadow: 0 0 6px rgba(0, 0, 0, .14);
  will-change: transform;
  transition: transform var(--segment-slide-duration, 300ms) var(--segment-slide-easing);
}

.theme-switcher__button {
  position: relative;
  height: 100%;
  border-radius: var(--theme-segment-radius);
  user-select: none;
  cursor: pointer;
  outline: none;
}

.theme-switcher__button:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 1px;
}

/* 遮罩窗：与滑块同几何同平移，窗口内是选中文字副本；
   反向平移保持与底层文字完全对齐，滑动中文字随滑块边缘即时切变颜色。 */
.theme-switcher__ink {
  position: absolute;
  top: var(--theme-segment-inset);
  bottom: var(--theme-segment-inset);
  left: var(--theme-segment-inset);
  width: calc((100% - var(--theme-segment-inset) * 4) / 3);
  overflow: hidden;
  border-radius: var(--theme-segment-radius);
  pointer-events: none;
  will-change: transform;
  transition: transform var(--segment-slide-duration, 300ms) var(--segment-slide-easing);
}

.theme-switcher__ink-row {
  position: absolute;
  top: 0;
  left: 0;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--theme-segment-inset);
  width: calc(300% + var(--theme-segment-inset) * 2);
  height: 100%;
  will-change: transform;
  transition: transform var(--segment-slide-duration, 300ms) var(--segment-slide-easing);
}

.theme-switcher__ink-label {
  display: flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  color: var(--shell-ink);
}

@media (prefers-reduced-motion: reduce) {
  .theme-switcher__thumb,
  .theme-switcher__ink,
  .theme-switcher__ink-row {
    transition: none;
  }
}

:root[data-theme='dark'] .theme-switcher__thumb {
  background: var(--color-surface-hover);
  box-shadow: 0 0 8px rgba(0, 0, 0, .45);
}

.settings-content :deep(.btn-primary) {
  min-height: var(--control-h-md);
  height: var(--control-h-md);
  padding: 0 .75rem;
  font-size: .8125rem;
  font-weight: 400;
  line-height: var(--line-height-14);
  color: #ffffff;
  text-shadow: none;
}

.settings-content :deep(.btn-ghost-danger) {
  min-height: var(--control-h-md);
  height: var(--control-h-md);
  padding: 0 .75rem;
  font-size: .8125rem;
  font-weight: 400;
  line-height: var(--line-height-14);
  text-shadow: none;
}

:root[data-theme='dark'] .settings-content :deep(.btn-primary) {
  color: #ffffff;
  text-shadow: none;
}

/* 维护分区条目：作为 .settings-panel 的直接子项，视觉分组由容器与分隔线承担。 */
.maintenance-card {
  min-width: 0;
}

.updates-panel__card {
  border-radius: var(--radius-lg);
  background: var(--color-surface-subtle);
  padding: .875rem 1rem;
}

@media (max-width: 900px) {
  .settings-page {
    overflow-y: auto;
  }

  .settings-layout {
    flex: none;
    grid-template-columns: 1fr;
    grid-template-rows: auto auto;
  }

  .settings-nav {
    display: grid;
    align-self: auto;
    grid-template-columns: repeat(4, minmax(130px, 1fr));
    overflow-x: auto;
  }

  .settings-content {
    overflow: visible;
  }

  .settings-content__body {
    flex: none;
    overflow: visible;
  }
}

@media (max-width: 720px) {
  .setting-row {
    grid-template-columns: 1fr;
    gap: .75rem;
  }

  .setting-row > :last-child {
    justify-self: start;
  }
}
</style>
