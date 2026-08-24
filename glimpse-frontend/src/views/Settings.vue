<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
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
  ServerStackIcon,
  SparklesIcon,
} from '@heroicons/vue/24/outline'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import {
  indexApi,
  ocrApi,
  type IndexRepairStatus,
  type OcrBackfillStatus,
} from '@/api/client'
import { useNotificationStore } from '@/stores/notification'
import { useSettingsStore } from '@/stores/settings'
import { useUnsavedChangesStore } from '@/stores/unsavedChanges'
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
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import AppSelect from '@/components/AppSelect.vue'

const logger = createLogger('views/Settings')
const router = useRouter()
const settingsStore = useSettingsStore()
const notifications = useNotificationStore()
const unsavedChanges = useUnsavedChangesStore()

const sections = [
  { id: 'hotkeys', labelKey: 'settings.hotkeys', descriptionKey: 'settings.hotkeysDescription', icon: CommandLineIcon },
  { id: 'screenshot', labelKey: 'settings.screenshot', descriptionKey: 'settings.screenshotDescription', icon: CameraIcon },
  { id: 'ai', labelKey: 'settings.ai', descriptionKey: 'settings.aiDescription', icon: SparklesIcon },
  { id: 'ui', labelKey: 'settings.ui', descriptionKey: 'settings.uiDescription', icon: PaintBrushIcon },
  { id: 'maintenance', labelKey: 'settings.maintenance', descriptionKey: 'settings.maintenanceDescription', icon: CircleStackIcon },
] as const

type SectionId = typeof sections[number]['id']
type ConfirmAction = 'reset' | 'index' | 'ocr' | null

const activeSection = ref<SectionId>('hotkeys')
const loading = ref(true)
const saving = ref(false)
const savedSnapshot = ref('')
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
const formSnapshot = computed(() => JSON.stringify({
  screenshotHotkey: screenshotHotkey.value,
  captureLimitWindowSeconds: captureLimitWindowSeconds.value,
  clusterThreshold: clusterThreshold.value,
  maxCaptures: maxCaptures.value,
  clusterMode: clusterMode.value,
  clusterAutoSubmit: clusterAutoSubmit.value,
  clusterMaxImages: clusterMaxImages.value,
  clusterTimeout: clusterTimeout.value,
  aiApiKey: aiApiKey.value,
  aiBaseUrl: aiBaseUrl.value,
  aiModel: aiModel.value,
  aiTimeout: aiTimeout.value,
  themePreference: themePreference.value,
  language: language.value,
  closeAction: closeAction.value,
}))
const dirty = computed(() => Boolean(savedSnapshot.value && formSnapshot.value !== savedSnapshot.value))
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
  savedSnapshot.value = formSnapshot.value
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

const handleSave = async () => {
  const current = settingsStore.settings
  if (!current || saving.value) return
  saving.value = true
  try {
    const ai = {
      ...current.ai,
      api_key: aiApiKey.value.trim(),
      base_url: aiBaseUrl.value.trim(),
      model: aiModel.value.trim(),
      timeout: aiTimeout.value,
    }
    await settingsStore.update({
      hotkeys: { ...current.hotkeys, screenshot: screenshotHotkey.value },
      screenshot: {
        ...current.screenshot,
        capture_limit_window_seconds: captureLimitWindowSeconds.value,
        cluster_threshold: clusterThreshold.value,
        max_captures_per_window: maxCaptures.value,
      },
      ai,
      ui: {
        ...current.ui,
        theme: themePreference.value,
        language: language.value,
        close_action: closeAction.value,
      },
      cluster: {
        ...current.cluster,
        cluster_mode: clusterMode.value,
        cluster_auto_submit: clusterAutoSubmit.value,
        cluster_max_images: clusterMaxImages.value,
        cluster_timeout: clusterTimeout.value,
      },
    })
    populateForm()
    applyThemePreference(themePreference.value)
    setLanguagePreference(language.value)
    notifications.show(t('settings.saved'), 'success', 1800)
  } catch (error) {
    logger.error('Failed to save settings: %s', error)
    notifications.show(t('settings.saveFailed'), 'error', 2800)
  } finally {
    saving.value = false
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
  if (!action) return
  confirmBusy.value = true
  try {
    if (action === 'reset') {
      await settingsStore.reset()
      populateForm()
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
  }
}

const resolveDiscard = (confirmed: boolean) => {
  discardDialogOpen.value = false
  if (confirmed) populateForm()
  discardResolver?.(confirmed)
  discardResolver = null
  pendingDiscardPromise = null
}

const canLeave = async () => {
  if (!dirty.value) return true
  if (pendingDiscardPromise) return pendingDiscardPromise
  discardDialogOpen.value = true
  pendingDiscardPromise = new Promise<boolean>((resolve) => {
    discardResolver = resolve
  })
  return pendingDiscardPromise
}

onBeforeRouteLeave(async () => canLeave())

onMounted(async () => {
  unregisterGuard = unsavedChanges.register(canLeave)
  await Promise.all([loadSettings(), refreshMaintenance()])
  scheduleMaintenancePoll()
})

onUnmounted(() => {
  if (maintenanceTimer) window.clearTimeout(maintenanceTimer)
  unregisterGuard?.()
  discardResolver?.(false)
})
</script>

<template>
  <main class="settings-page h-full min-h-0 bg-[var(--shell-window-bg)] p-4 sm:p-5">
    <div class="mx-auto flex h-full min-h-0 max-w-[1420px] flex-col">
      <header class="mb-4 flex-none">
        <h1 class="text-xl font-semibold tracking-[-0.01em] text-[var(--shell-ink)]">{{ t('settings.title') }}</h1>
      </header>

      <div v-if="loading" class="flex min-h-[65vh] items-center justify-center">
        <ArrowPathIcon class="h-8 w-8 animate-spin text-[var(--color-primary)]" :aria-label="t('settings.loading')" />
      </div>

      <div v-else class="settings-layout min-h-0 flex-1">
        <nav class="settings-nav min-h-0 overflow-y-auto" :aria-label="t('settings.sectionNavigation')">
          <button
            v-for="section in sections"
            :key="section.id"
            type="button"
            class="flex min-h-10 w-full items-center gap-2.5 rounded-lg px-3 text-left text-sm font-medium transition"
            :class="activeSection === section.id
              ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-hover)]'
              : 'text-[var(--shell-ink)] hover:bg-[var(--shell-control-hover)]'"
            :aria-current="activeSection === section.id ? 'page' : undefined"
            @click="activeSection = section.id"
          >
            <component :is="section.icon" class="h-5 w-5 flex-none" aria-hidden="true" />
            {{ t(section.labelKey) }}
          </button>
        </nav>

        <section class="settings-content min-h-0">
          <header class="flex-none border-b border-[var(--shell-line)] px-5 py-3.5 sm:px-6">
            <h2 class="text-xl font-semibold tracking-[-0.01em] text-[var(--shell-ink)]">{{ t(currentSection.labelKey) }}</h2>
            <p class="mt-1.5 text-sm leading-6 text-[var(--shell-muted)]">{{ t(currentSection.descriptionKey) }}</p>
          </header>

          <div class="settings-content__body min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4 sm:px-6">
            <template v-if="activeSection === 'hotkeys'">
              <div class="setting-row">
                <div>
                  <label class="setting-label">{{ t('settings.screenshotHotkey') }}</label>
                  <p class="setting-help">{{ t('settings.recordHelp') }}</p>
                </div>
                <button
                  type="button"
                  class="setting-input flex min-h-10 items-center justify-between text-left"
                  :class="{ 'border-[var(--color-primary)] ring-2 ring-[color-mix(in_srgb,var(--color-primary)_15%,transparent)]': recordingHotkey }"
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

              <div class="rounded-lg border border-[var(--shell-line)] p-3.5">
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
                <div class="relative">
                  <input
                    id="ai-api-key"
                    v-model="aiApiKey"
                    class="setting-input pr-12"
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
                <button type="button" class="btn-secondary min-h-10" :disabled="testingAi" @click="testAi">
                  <ArrowPathIcon v-if="testingAi" class="h-5 w-5 flex-none animate-spin" aria-hidden="true" />
                  <ServerStackIcon v-else class="h-5 w-5 flex-none" aria-hidden="true" />
                  {{ testingAi ? t('settings.testing') : t('settings.test') }}
                </button>
                <p
                  v-if="aiTestResult"
                  class="flex items-center gap-2 text-sm"
                  :class="aiTestResult.success ? 'text-emerald-600' : 'text-red-600'"
                >
                  <CheckCircleIcon class="h-5 w-5 flex-none" aria-hidden="true" />
                  {{ aiTestResult.message }}
                </p>
              </div>

              <div class="rounded-lg border border-[color-mix(in_srgb,var(--color-primary)_20%,transparent)] bg-[var(--color-primary-soft)] p-3.5">
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
              <fieldset>
                <legend class="setting-label">{{ t('settings.theme') }}</legend>
                <div class="mt-2.5 grid grid-cols-3 gap-2.5">
                  <label
                    v-for="option in [
                      { value: 'light', label: t('settings.themeLight') },
                      { value: 'dark', label: t('settings.themeDark') },
                      { value: 'system', label: t('settings.themeSystem') },
                    ]"
                    :key="option.value"
                    class="cursor-pointer rounded-lg border p-2.5 text-center text-sm font-medium transition"
                    :class="themePreference === option.value ? 'border-[var(--color-primary)] bg-[var(--color-primary-soft)] text-[var(--color-primary-hover)]' : 'border-[var(--shell-line)]'"
                  >
                    <input v-model="themePreference" class="sr-only" type="radio" :value="option.value" />
                    {{ option.label }}
                  </label>
                </div>
              </fieldset>
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
                    class="btn-secondary min-h-10"
                    :disabled="maintenanceRunning"
                    @click="openConfirmation('index')"
                  >
                    <ArrowPathIcon class="h-5 w-5 flex-none" :class="{ 'animate-spin': indexStatus?.running }" aria-hidden="true" />
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
                    class="btn-secondary min-h-10"
                    :disabled="maintenanceRunning"
                    @click="openConfirmation('ocr')"
                  >
                    <ArrowPathIcon class="h-5 w-5 flex-none" :class="{ 'animate-spin': ocrStatus?.running }" aria-hidden="true" />
                    {{ ocrStatus?.running ? t('settings.backfillingOcr') : t('settings.startBackfill') }}
                  </button>
                </div>
              </div>
            </template>
          </div>

          <footer class="flex flex-none flex-wrap items-center justify-between gap-2.5 border-t border-[var(--shell-line)] px-5 py-2.5 sm:px-6">
            <button type="button" class="min-h-10 rounded-md px-3 text-sm font-medium text-red-600 hover:bg-red-50" @click="openConfirmation('reset')">
              {{ t('action.reset') }}
            </button>
            <div class="flex gap-2.5">
              <button type="button" class="btn-secondary min-h-10 px-4" @click="router.push('/')">{{ t('action.cancel') }}</button>
              <button type="button" class="btn-primary min-h-10 px-4" :disabled="saving || !dirty" @click="handleSave">
                <ArrowPathIcon v-if="saving" class="h-5 w-5 flex-none animate-spin" aria-hidden="true" />
                {{ saving ? t('settings.saving') : t('settings.saveChanges') }}
              </button>
            </div>
          </footer>
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
.settings-layout {
  display: grid;
  min-height: 0;
  grid-template-columns: 250px minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr);
  gap: 1rem;
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
  padding: .5rem;
}

.settings-content {
  display: flex;
  min-height: 500px;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
  border-radius: var(--radius-xl);
}

.setting-row {
  display: grid;
  grid-template-columns: minmax(180px, 240px) minmax(260px, 1fr);
  align-items: center;
  gap: 1rem;
}

.setting-label {
  display: block;
  font-size: .875rem;
  font-weight: 600;
  color: var(--shell-ink);
}

.setting-help {
  display: block;
  margin-top: .25rem;
  font-size: .75rem;
  line-height: 1.125rem;
  color: var(--shell-muted);
}

.setting-input,
.setting-readonly {
  width: 100%;
  min-height: 2.5rem;
  border: 1px solid var(--shell-line);
  border-radius: var(--radius-md);
  background: var(--shell-control-bg);
  padding: .45rem .75rem;
  color: var(--shell-ink);
  outline: none;
  transition: border-color 160ms ease, box-shadow 160ms ease;
}

.setting-input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-primary) 14%, transparent);
}

.setting-readonly {
  color: var(--shell-muted);
  cursor: default;
}

.maintenance-card {
  border: 1px solid var(--shell-line);
  border-radius: var(--radius-lg);
  padding: .875rem;
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
    grid-template-columns: repeat(5, minmax(115px, 1fr));
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
}
</style>
