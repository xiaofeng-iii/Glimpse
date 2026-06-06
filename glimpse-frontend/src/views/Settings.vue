<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useNotificationStore } from '@/stores/notification'
import { useRouter } from 'vue-router'
import { indexApi, type IndexRepairStatus } from '@/api/client'
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

const settingsStore = useSettingsStore()
const notificationStore = useNotificationStore()
const router = useRouter()

const sections = [
  { id: 'hotkeys', labelKey: 'settings.hotkeys', icon: 'M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z' },
  { id: 'screenshot', labelKey: 'settings.screenshot', icon: 'M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z M15 13a3 3 0 11-6 0 3 3 0 016 0z' },
  { id: 'ai', labelKey: 'settings.ai', icon: 'M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z' },
  { id: 'ui', labelKey: 'settings.ui', icon: 'M2.25 12l8.954-8.955a1.126 1.126 0 011.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25' },
  { id: 'maintenance', labelKey: 'settings.maintenance', icon: 'M4 6c0-1.657 3.582-3 8-3s8 1.343 8 3-3.582 3-8 3-8-1.343-8-3z M4 6v6c0 1.657 3.582 3 8 3s8-1.343 8-3V6 M4 12v6c0 1.657 3.582 3 8 3s8-1.343 8-3v-6' },
] as const

type SectionId = typeof sections[number]['id']
const activeSection = ref<SectionId>('hotkeys')

// Form refs
const screenshotHotkey = ref('')
const debounceInterval = ref(5)
const clusterThreshold = ref(2)
const maxCaptures = ref(10)
const aiApiKey = ref('')
const aiBaseUrl = ref('https://api.openai.com/v1')
const aiModel = ref('gpt-4o-mini')
const aiTimeout = ref(60)
const themePreference = ref<ThemePreference>('light')
const language = ref<LanguagePreference>('zh-CN')
const closeAction = ref<'ask' | 'minimize' | 'exit'>('ask')
const clusterMode = ref(false)
const clusterAutoSubmit = ref(true)
const clusterMaxImages = ref(5)
const clusterTimeout = ref(5)

// Test connection state
const isTestingAi = ref(false)
const aiTestResult = ref<{ success: boolean; message: string } | null>(null)
const recordingHotkey = ref<'screenshot' | null>(null)
const isRepairingIndex = ref(false)
const indexRepairStatus = ref<IndexRepairStatus | null>(null)
let indexRepairPollTimer: ReturnType<typeof setTimeout> | null = null

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

const specialKeyMap: Record<string, string> = {
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

const normalizeMainKey = (event: KeyboardEvent) => {
  if (modifierKeys.has(event.key)) return ''
  if (specialKeyMap[event.key]) return specialKeyMap[event.key]
  if (/^F([1-9]|1[0-9]|2[0-4])$/.test(event.key)) return event.key.toLowerCase()
  if (event.key.length === 1 && event.key !== '+') return event.key.toLowerCase()
  return ''
}

const formatHotkeyForPynput = (event: KeyboardEvent) => {
  const mainKey = normalizeMainKey(event)
  if (!mainKey) return ''

  const parts: string[] = []
  if (event.ctrlKey) parts.push('<ctrl>')
  if (event.shiftKey) parts.push('<shift>')
  if (event.altKey) parts.push('<alt>')
  if (event.metaKey) parts.push('<cmd>')

  const wrappedKey = mainKey.length === 1 ? mainKey : `<${mainKey}>`
  return [...parts, wrappedKey].join('+')
}

const formatHotkeyForDisplay = (hotkey: string) => {
  if (!hotkey) return t('settings.emptyHotkey')
  return hotkey
    .split('+')
    .map((part) => {
      const normalized = part.trim().replace(/^<|>$/g, '').toLowerCase()
      if (hotkeyLabels[normalized]) return hotkeyLabels[normalized]
      if (/^f([1-9]|1[0-9]|2[0-4])$/.test(normalized)) return normalized.toUpperCase()
      return normalized.length === 1 ? normalized.toUpperCase() : normalized
    })
    .join(' + ')
}

const startHotkeyRecording = () => {
  recordingHotkey.value = 'screenshot'
}

const clearHotkey = () => {
  screenshotHotkey.value = ''
}

const handleHotkeyKeydown = (event: KeyboardEvent) => {
  event.preventDefault()
  event.stopPropagation()

  if (event.key === 'Escape') {
    recordingHotkey.value = null
    return
  }

  const noModifier = !event.ctrlKey && !event.shiftKey && !event.altKey && !event.metaKey
  if ((event.key === 'Backspace' || event.key === 'Delete') && noModifier) {
    clearHotkey()
    recordingHotkey.value = null
    return
  }

  const hotkey = formatHotkeyForPynput(event)
  if (!hotkey) return

  screenshotHotkey.value = hotkey
  recordingHotkey.value = null
}

const loadSettings = async () => {
  await settingsStore.load()
  if (settingsStore.settings) {
    const s = settingsStore.settings
    screenshotHotkey.value = s.hotkeys?.screenshot || ''
    debounceInterval.value = s.screenshot?.debounce_interval || 5
    clusterThreshold.value = s.screenshot?.cluster_threshold || 2
    maxCaptures.value = s.screenshot?.max_captures_per_window || 10
    aiApiKey.value = s.ai?.api_key || ''
    aiBaseUrl.value = s.ai?.base_url || 'https://api.openai.com/v1'
    aiModel.value = s.ai?.model || 'gpt-4o-mini'
    aiTimeout.value = s.ai?.timeout || 60
    themePreference.value = normalizeThemePreference(s.ui?.theme)
    language.value = normalizeLanguagePreference(s.ui?.language)
    setLanguagePreference(language.value)
    closeAction.value = s.ui?.close_action || 'ask'
    clusterMode.value = s.cluster?.cluster_mode || false
    clusterAutoSubmit.value = s.cluster?.cluster_auto_submit ?? true
    clusterMaxImages.value = s.cluster?.cluster_max_images || 5
    clusterTimeout.value = s.cluster?.cluster_timeout || 5
  }
}

const clearIndexRepairPoll = () => {
  if (indexRepairPollTimer) {
    clearTimeout(indexRepairPollTimer)
    indexRepairPollTimer = null
  }
}

const indexRepairFailed = (status: IndexRepairStatus) => {
  return Boolean(
    status.error ||
    status.status === 'failed' ||
    status.result?.status === 'failed' ||
    status.result?.status === 'unavailable'
  )
}

const handleIndexRepairFinished = (status: IndexRepairStatus) => {
  isRepairingIndex.value = false

  if (indexRepairFailed(status)) {
    notificationStore.show(t('message.indexRepairFailed'), 'error')
    return
  }

  const failed = status.result?.failed ?? 0
  notificationStore.show(
    failed > 0 ? t('message.indexRepairPartial') : t('message.indexRepairDone'),
    failed > 0 ? 'warning' : 'success',
  )
}

const refreshIndexRepairStatus = async () => {
  const status = await indexApi.status()
  indexRepairStatus.value = status
  isRepairingIndex.value = status.running
  return status
}

const pollIndexRepairStatus = () => {
  clearIndexRepairPoll()
  indexRepairPollTimer = setTimeout(async () => {
    try {
      const status = await refreshIndexRepairStatus()
      if (status.running) {
        pollIndexRepairStatus()
      } else {
        handleIndexRepairFinished(status)
      }
    } catch (error) {
      isRepairingIndex.value = false
      notificationStore.show(t('message.indexRepairFailed'), 'error')
    }
  }, 1500)
}

const handleRepairIndex = async () => {
  if (isRepairingIndex.value) return
  if (!confirm(t('settings.indexRepairConfirm'))) return

  try {
    isRepairingIndex.value = true
    indexRepairStatus.value = await indexApi.repair()
    notificationStore.show(t('message.indexRepairStarted'), 'info')

    if (indexRepairStatus.value.running) {
      pollIndexRepairStatus()
    } else {
      handleIndexRepairFinished(indexRepairStatus.value)
    }
  } catch (error) {
    isRepairingIndex.value = false
    notificationStore.show(t('message.indexRepairFailed'), 'error')
  }
}

const indexRepairStatusText = () => {
  if (isRepairingIndex.value || indexRepairStatus.value?.running) {
    return t('settings.indexRepairRunning')
  }

  const result = indexRepairStatus.value?.result
  if (result) {
    return t('settings.indexRepairLastResult', {
      processed: result.processed,
      indexed: result.indexed,
      failed: result.failed,
    })
  }

  return t('settings.indexRepairIdle', {
    sqlite: indexRepairStatus.value?.sqlite_count ?? 0,
    chroma: indexRepairStatus.value?.chroma_count ?? 0,
  })
}

onMounted(async () => {
  await loadSettings()
  try {
    const status = await refreshIndexRepairStatus()
    if (status.running) {
      pollIndexRepairStatus()
    }
  } catch (error) {
    // Settings remain usable even if maintenance status is temporarily unavailable.
  }
})

onUnmounted(() => {
  clearIndexRepairPoll()
})

const handleSave = async () => {
  try {
    const aiSettings: Record<string, string | number> = {
      base_url: aiBaseUrl.value,
      model: aiModel.value,
      timeout: aiTimeout.value,
    }
    if (aiApiKey.value.trim()) {
      aiSettings.api_key = aiApiKey.value
    }

    await settingsStore.update({
      hotkeys: {
        screenshot: screenshotHotkey.value,
      },
      screenshot: {
        debounce_interval: debounceInterval.value,
        cluster_threshold: clusterThreshold.value,
        max_captures_per_window: maxCaptures.value,
      },
      ai: aiSettings,
      ui: {
        theme: themePreference.value,
        language: language.value,
        close_action: closeAction.value,
      },
      cluster: {
        cluster_mode: clusterMode.value,
        cluster_auto_submit: clusterAutoSubmit.value,
        cluster_max_images: clusterMaxImages.value,
        cluster_timeout: clusterTimeout.value,
      },
    })
    applyThemePreference(themePreference.value)
    setLanguagePreference(language.value)
    router.push('/')
  } catch (error) {
    console.error('Failed to save settings:', error)
  }
}

const handleTestAi = async () => {
  isTestingAi.value = true
  aiTestResult.value = null
  try {
    aiTestResult.value = await settingsStore.testAi(
      aiApiKey.value,
      aiBaseUrl.value,
      aiModel.value
    )
  } catch (error) {
    aiTestResult.value = { success: false, message: t('settings.testFailed') }
  } finally {
    isTestingAi.value = false
  }
}

const handleReset = async () => {
  if (confirm(t('settings.resetConfirm'))) {
    await settingsStore.reset()
    await loadSettings()
    applyThemePreference(themePreference.value)
    setLanguagePreference(language.value)
  }
}

const handleCancel = () => {
  router.push('/')
}
</script>

<template>
  <div class="h-screen p-4 sm:p-6" style="background: radial-gradient(circle at top left, rgba(217, 107, 49, 0.12), transparent 28%), radial-gradient(circle at top right, rgba(35, 93, 103, 0.10), transparent 22%), linear-gradient(135deg, var(--shell-bg-a), var(--shell-bg-b) 50%, var(--shell-bg-c))">
    <div class="flex h-full min-h-0 gap-4">
      <!-- Left Sidebar -->
      <aside class="card flex w-56 flex-shrink-0 flex-col overflow-hidden p-4">
        <div data-tauri-drag-region class="mb-5">
          <h1 class="text-lg font-bold text-gray-900">{{ t('settings.title') }}</h1>
        </div>
        <nav class="flex-1 space-y-1">
          <button
            v-for="section in sections"
            :key="section.id"
            @click="activeSection = section.id"
            :class="[
              'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
              activeSection === section.id
                ? 'bg-violet-50 text-violet-700'
                : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900',
            ]"
          >
            <svg class="h-5 w-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" :d="section.icon" />
            </svg>
            {{ t(section.labelKey) }}
          </button>
        </nav>
        <button @click="handleCancel" class="btn-secondary mt-4 w-full text-center">
          {{ t('action.back') }}
        </button>
      </aside>

      <!-- Right Content -->
      <div class="flex min-h-0 flex-1 flex-col gap-4">
        <main class="card flex-1 overflow-y-auto p-6">
          <div class="max-w-xl">
            <!-- Hotkeys -->
            <div v-if="activeSection === 'hotkeys'">
              <h2 class="text-lg font-semibold text-gray-900 mb-4">{{ t('settings.hotkeys') }}</h2>
              <div class="space-y-4">
                <div>
                  <label class="block text-sm text-gray-600 mb-2">{{ t('settings.screenshotHotkey') }}</label>
                  <button
                    type="button"
                    :class="[
                      'w-full min-h-11 px-4 py-2 rounded-lg border text-left outline-none transition-colors',
                      recordingHotkey === 'screenshot'
                        ? 'border-violet-500 bg-violet-50 text-violet-700 ring-2 ring-violet-100'
                        : 'border-gray-200 bg-white text-gray-800 hover:border-violet-300 focus:border-violet-400',
                    ]"
                    @click="startHotkeyRecording"
                    @keydown="handleHotkeyKeydown"
                    @blur="recordingHotkey = null"
                  >
                    <span class="font-medium">
                      {{ recordingHotkey === 'screenshot' ? t('settings.recording') : formatHotkeyForDisplay(screenshotHotkey) }}
                    </span>
                    <span class="ml-2 text-xs text-gray-400">
                      {{ recordingHotkey === 'screenshot' ? t('settings.recordHelp') : t('settings.recordHint') }}
                    </span>
                  </button>
                </div>
              </div>
            </div>

            <!-- Screenshot -->
            <div v-if="activeSection === 'screenshot'">
              <h2 class="text-lg font-semibold text-gray-900 mb-4">{{ t('settings.screenshot') }}</h2>
              <div class="space-y-4">
                <div>
                  <label class="block text-sm text-gray-600 mb-2">{{ t('settings.debounce') }}</label>
                  <input v-model.number="debounceInterval" type="number" step="0.5" class="w-full px-4 py-2 rounded-lg border border-gray-200 focus:border-violet-400 outline-none" />
                </div>
                <div>
                  <label class="block text-sm text-gray-600 mb-2">{{ t('settings.maxCaptures') }}</label>
                  <input v-model.number="maxCaptures" type="number" class="w-full px-4 py-2 rounded-lg border border-gray-200 focus:border-violet-400 outline-none" />
                </div>
              </div>

              <h3 class="text-lg font-semibold text-gray-900 mt-6 mb-4">{{ t('settings.clusterScreenshot') }}</h3>
              <div class="space-y-4">
                <label class="flex items-center gap-3">
                  <input v-model="clusterMode" type="checkbox" class="w-5 h-5 rounded border-gray-300 text-violet-600 focus:ring-violet-500" />
                  <span class="text-gray-700">{{ t('settings.enableCluster') }}</span>
                </label>
                <label class="flex items-center gap-3">
                  <input v-model="clusterAutoSubmit" type="checkbox" class="w-5 h-5 rounded border-gray-300 text-violet-600 focus:ring-violet-500" />
                  <span class="text-gray-700">{{ t('settings.autoSubmit') }}</span>
                </label>
                <div>
                  <label class="block text-sm text-gray-600 mb-2">{{ t('settings.maxImages') }}</label>
                  <input v-model.number="clusterMaxImages" type="number" class="w-full px-4 py-2 rounded-lg border border-gray-200 focus:border-violet-400 outline-none" />
                </div>
                <div>
                  <label class="block text-sm text-gray-600 mb-2">{{ t('settings.timeoutSeconds') }}</label>
                  <input v-model.number="clusterTimeout" type="number" class="w-full px-4 py-2 rounded-lg border border-gray-200 focus:border-violet-400 outline-none" />
                </div>
              </div>
            </div>

            <!-- AI -->
            <div v-if="activeSection === 'ai'">
              <h2 class="text-lg font-semibold text-gray-900 mb-4">{{ t('settings.ai') }}</h2>
              <div class="space-y-4">
                <div>
                  <label class="block text-sm text-gray-600 mb-2">API Key</label>
                  <input v-model="aiApiKey" type="password" placeholder="sk-..." class="w-full px-4 py-2 rounded-lg border border-gray-200 focus:border-violet-400 outline-none" />
                </div>
                <div>
                  <label class="block text-sm text-gray-600 mb-2">Base URL</label>
                  <input v-model="aiBaseUrl" placeholder="https://api.openai.com/v1" class="w-full px-4 py-2 rounded-lg border border-gray-200 focus:border-violet-400 outline-none" />
                </div>
                <div>
                  <label class="block text-sm text-gray-600 mb-2">{{ t('settings.model') }}</label>
                  <input v-model="aiModel" placeholder="gpt-4o-mini" class="w-full px-4 py-2 rounded-lg border border-gray-200 focus:border-violet-400 outline-none" />
                </div>
                <div>
                  <label class="block text-sm text-gray-600 mb-2">{{ t('settings.timeoutSeconds') }}</label>
                  <input v-model.number="aiTimeout" type="number" class="w-full px-4 py-2 rounded-lg border border-gray-200 focus:border-violet-400 outline-none" />
                </div>
                <div class="flex items-center gap-4">
                  <button @click="handleTestAi" :disabled="isTestingAi" class="btn-secondary">
                    {{ isTestingAi ? t('settings.testing') : t('settings.test') }}
                  </button>
                  <span v-if="aiTestResult" :class="['text-sm', aiTestResult.success ? 'text-green-600' : 'text-red-600']">
                    {{ aiTestResult.message }}
                  </span>
                </div>
              </div>
            </div>

            <!-- UI -->
            <div v-if="activeSection === 'ui'">
              <h2 class="text-lg font-semibold text-gray-900 mb-4">{{ t('settings.ui') }}</h2>
              <div class="space-y-4">
                <div>
                  <label class="block text-sm text-gray-600 mb-2">{{ t('settings.theme') }}</label>
                  <select v-model="themePreference" class="w-full px-4 py-2 rounded-lg border border-gray-200 focus:border-violet-400 outline-none">
                    <option value="light">{{ t('settings.themeLight') }}</option>
                    <option value="dark">{{ t('settings.themeDark') }}</option>
                    <option value="system">{{ t('settings.themeSystem') }}</option>
                  </select>
                </div>
                <div>
                  <label class="block text-sm text-gray-600 mb-2">{{ t('settings.language') }}</label>
                  <select v-model="language" class="w-full px-4 py-2 rounded-lg border border-gray-200 focus:border-violet-400 outline-none" @change="setLanguagePreference(language)">
                    <option value="zh-CN">{{ t('settings.languageZh') }}</option>
                    <option value="en-US">{{ t('settings.languageEn') }}</option>
                  </select>
                </div>
                <div>
                  <label class="block text-sm text-gray-600 mb-2">{{ t('settings.closeAction') }}</label>
                  <select v-model="closeAction" class="w-full px-4 py-2 rounded-lg border border-gray-200 focus:border-violet-400 outline-none">
                    <option value="ask">{{ t('settings.closeAsk') }}</option>
                    <option value="minimize">{{ t('settings.closeMinimize') }}</option>
                    <option value="exit">{{ t('settings.closeExit') }}</option>
                  </select>
                </div>
              </div>
            </div>

            <!-- Maintenance -->
            <div v-if="activeSection === 'maintenance'">
              <h2 class="text-lg font-semibold text-gray-900 mb-4">{{ t('settings.maintenance') }}</h2>
              <div class="space-y-4">
                <div class="flex items-center justify-between gap-4 border-b border-gray-100 py-3">
                  <div class="min-w-0">
                    <div class="text-sm font-medium text-gray-900">{{ t('settings.repairIndex') }}</div>
                    <div class="mt-1 text-xs text-gray-500">{{ indexRepairStatusText() }}</div>
                  </div>
                  <button
                    @click="handleRepairIndex"
                    :disabled="isRepairingIndex"
                    class="btn-secondary whitespace-nowrap disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {{ isRepairingIndex ? t('settings.repairingIndex') : t('settings.repairIndex') }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </main>

        <!-- Footer -->
        <footer class="card flex items-center justify-between p-4">
          <button @click="handleReset" class="px-4 py-2 text-red-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors">
            {{ t('action.reset') }}
          </button>
          <div class="flex gap-3">
            <button @click="handleCancel" class="btn-secondary">{{ t('action.cancel') }}</button>
            <button @click="handleSave" class="btn-primary">{{ t('action.save') }}</button>
          </div>
        </footer>
      </div>
    </div>
  </div>
</template>
