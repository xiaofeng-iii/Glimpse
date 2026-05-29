<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useRouter } from 'vue-router'

const settingsStore = useSettingsStore()
const router = useRouter()

// Form refs
const screenshotHotkey = ref('')
const searchHotkey = ref('')
const debounceInterval = ref(5)
const clusterThreshold = ref(2)
const maxCaptures = ref(10)
const aiApiKey = ref('')
const aiBaseUrl = ref('https://api.openai.com/v1')
const aiModel = ref('gpt-4o-mini')
const aiTimeout = ref(60)
const closeAction = ref<'ask' | 'minimize' | 'exit'>('ask')
const clusterMode = ref(false)
const clusterAutoSubmit = ref(true)
const clusterMaxImages = ref(5)
const clusterTimeout = ref(5)

// Test connection state
const isTestingAi = ref(false)
const aiTestResult = ref<{ success: boolean; message: string } | null>(null)
const recordingHotkey = ref<'screenshot' | 'search' | null>(null)

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
  if (!hotkey) return '点击后按下快捷键'
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

const startHotkeyRecording = (target: 'screenshot' | 'search') => {
  recordingHotkey.value = target
}

const clearHotkey = (target: 'screenshot' | 'search') => {
  if (target === 'screenshot') {
    screenshotHotkey.value = ''
  } else {
    searchHotkey.value = ''
  }
}

const handleHotkeyKeydown = (event: KeyboardEvent, target: 'screenshot' | 'search') => {
  event.preventDefault()
  event.stopPropagation()

  if (event.key === 'Escape') {
    recordingHotkey.value = null
    return
  }

  const noModifier = !event.ctrlKey && !event.shiftKey && !event.altKey && !event.metaKey
  if ((event.key === 'Backspace' || event.key === 'Delete') && noModifier) {
    clearHotkey(target)
    recordingHotkey.value = null
    return
  }

  const hotkey = formatHotkeyForPynput(event)
  if (!hotkey) return

  if (target === 'screenshot') {
    screenshotHotkey.value = hotkey
  } else {
    searchHotkey.value = hotkey
  }
  recordingHotkey.value = null
}

const loadSettings = async () => {
  await settingsStore.load()
  if (settingsStore.settings) {
    const s = settingsStore.settings
    screenshotHotkey.value = s.hotkeys?.screenshot || ''
    searchHotkey.value = s.hotkeys?.search || ''
    debounceInterval.value = s.screenshot?.debounce_interval || 5
    clusterThreshold.value = s.screenshot?.cluster_threshold || 2
    maxCaptures.value = s.screenshot?.max_captures_per_window || 10
    aiApiKey.value = s.ai?.api_key || ''
    aiBaseUrl.value = s.ai?.base_url || 'https://api.openai.com/v1'
    aiModel.value = s.ai?.model || 'gpt-4o-mini'
    aiTimeout.value = s.ai?.timeout || 60
    closeAction.value = s.ui?.close_action || 'ask'
    clusterMode.value = s.cluster?.cluster_mode || false
    clusterAutoSubmit.value = s.cluster?.cluster_auto_submit ?? true
    clusterMaxImages.value = s.cluster?.cluster_max_images || 5
    clusterTimeout.value = s.cluster?.cluster_timeout || 5
  }
}

onMounted(async () => {
  await loadSettings()
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
        search: searchHotkey.value,
      },
      screenshot: {
        debounce_interval: debounceInterval.value,
        cluster_threshold: clusterThreshold.value,
        max_captures_per_window: maxCaptures.value,
      },
      ai: aiSettings,
      ui: {
        close_action: closeAction.value,
      },
      cluster: {
        cluster_mode: clusterMode.value,
        cluster_auto_submit: clusterAutoSubmit.value,
        cluster_max_images: clusterMaxImages.value,
        cluster_timeout: clusterTimeout.value,
      },
    })
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
    aiTestResult.value = { success: false, message: '测试失败' }
  } finally {
    isTestingAi.value = false
  }
}

const handleReset = async () => {
  if (confirm('确定要恢复所有设置为默认值吗？')) {
    await settingsStore.reset()
    await loadSettings()
  }
}

const handleCancel = () => {
  router.push('/')
}
</script>

<template>
  <div class="h-screen overflow-y-auto overflow-x-hidden p-4 sm:p-6">
    <div class="max-w-2xl mx-auto pb-10">
      <!-- Header -->
      <div class="flex items-center justify-between mb-8">
        <h1 class="text-2xl font-bold text-gray-900">设置</h1>
        <button
          @click="handleCancel"
          class="btn-secondary"
        >
          返回
        </button>
      </div>

      <!-- Settings Form -->
      <div class="space-y-6">
        <!-- Hotkeys -->
        <div class="card p-6">
          <h2 class="text-lg font-semibold text-gray-900 mb-4">快捷键</h2>
          <div class="space-y-4">
            <div>
              <label class="block text-sm text-gray-600 mb-2">截图快捷键</label>
              <button
                type="button"
                :class="[
                  'w-full min-h-11 px-4 py-2 rounded-lg border text-left outline-none transition-colors',
                  recordingHotkey === 'screenshot'
                    ? 'border-violet-500 bg-violet-50 text-violet-700 ring-2 ring-violet-100'
                    : 'border-gray-200 bg-white text-gray-800 hover:border-violet-300 focus:border-violet-400',
                ]"
                @click="startHotkeyRecording('screenshot')"
                @keydown="handleHotkeyKeydown($event, 'screenshot')"
                @blur="recordingHotkey = null"
              >
                <span class="font-medium">
                  {{ recordingHotkey === 'screenshot' ? '请按下快捷键...' : formatHotkeyForDisplay(screenshotHotkey) }}
                </span>
                <span class="ml-2 text-xs text-gray-400">
                  {{ recordingHotkey === 'screenshot' ? 'Esc 取消，Backspace 清空' : '点击录入' }}
                </span>
              </button>
            </div>
            <div>
              <label class="block text-sm text-gray-600 mb-2">搜索快捷键</label>
              <button
                type="button"
                :class="[
                  'w-full min-h-11 px-4 py-2 rounded-lg border text-left outline-none transition-colors',
                  recordingHotkey === 'search'
                    ? 'border-violet-500 bg-violet-50 text-violet-700 ring-2 ring-violet-100'
                    : 'border-gray-200 bg-white text-gray-800 hover:border-violet-300 focus:border-violet-400',
                ]"
                @click="startHotkeyRecording('search')"
                @keydown="handleHotkeyKeydown($event, 'search')"
                @blur="recordingHotkey = null"
              >
                <span class="font-medium">
                  {{ recordingHotkey === 'search' ? '请按下快捷键...' : formatHotkeyForDisplay(searchHotkey) }}
                </span>
                <span class="ml-2 text-xs text-gray-400">
                  {{ recordingHotkey === 'search' ? 'Esc 取消，Backspace 清空' : '点击录入' }}
                </span>
              </button>
            </div>
          </div>
        </div>

        <!-- Screenshot Settings -->
        <div class="card p-6">
          <h2 class="text-lg font-semibold text-gray-900 mb-4">截图设置</h2>
          <div class="space-y-4">
            <div>
              <label class="block text-sm text-gray-600 mb-2">防抖间隔 (秒)</label>
              <input v-model.number="debounceInterval" type="number" step="0.5" class="w-full px-4 py-2 rounded-lg border border-gray-200 focus:border-violet-400 outline-none" />
            </div>
            <div>
              <label class="block text-sm text-gray-600 mb-2">最大截图数</label>
              <input v-model.number="maxCaptures" type="number" class="w-full px-4 py-2 rounded-lg border border-gray-200 focus:border-violet-400 outline-none" />
            </div>
          </div>
        </div>

        <!-- AI Settings -->
        <div class="card p-6">
          <h2 class="text-lg font-semibold text-gray-900 mb-4">AI 服务</h2>
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
              <label class="block text-sm text-gray-600 mb-2">模型</label>
              <input v-model="aiModel" placeholder="gpt-4o-mini" class="w-full px-4 py-2 rounded-lg border border-gray-200 focus:border-violet-400 outline-none" />
            </div>
            <div>
              <label class="block text-sm text-gray-600 mb-2">超时时间 (秒)</label>
              <input v-model.number="aiTimeout" type="number" class="w-full px-4 py-2 rounded-lg border border-gray-200 focus:border-violet-400 outline-none" />
            </div>
            <div class="flex items-center gap-4">
              <button @click="handleTestAi" :disabled="isTestingAi" class="btn-secondary">
                {{ isTestingAi ? '测试中...' : '测试连接' }}
              </button>
              <span v-if="aiTestResult" :class="['text-sm', aiTestResult.success ? 'text-green-600' : 'text-red-600']">
                {{ aiTestResult.message }}
              </span>
            </div>
          </div>
        </div>

        <!-- UI Settings -->
        <div class="card p-6">
          <h2 class="text-lg font-semibold text-gray-900 mb-4">界面</h2>
          <div class="space-y-4">
            <div>
              <label class="block text-sm text-gray-600 mb-2">关闭窗口时</label>
              <select v-model="closeAction" class="w-full px-4 py-2 rounded-lg border border-gray-200 focus:border-violet-400 outline-none">
                <option value="ask">每次询问</option>
                <option value="minimize">最小化到托盘</option>
                <option value="exit">退出应用</option>
              </select>
            </div>
          </div>
        </div>

        <!-- Cluster Settings -->
        <div class="card p-6">
          <h2 class="text-lg font-semibold text-gray-900 mb-4">集群截图</h2>
          <div class="space-y-4">
            <label class="flex items-center gap-3">
              <input v-model="clusterMode" type="checkbox" class="w-5 h-5 rounded border-gray-300 text-violet-600 focus:ring-violet-500" />
              <span class="text-gray-700">启用集群模式</span>
            </label>
            <label class="flex items-center gap-3">
              <input v-model="clusterAutoSubmit" type="checkbox" class="w-5 h-5 rounded border-gray-300 text-violet-600 focus:ring-violet-500" />
              <span class="text-gray-700">自动提交</span>
            </label>
            <div>
              <label class="block text-sm text-gray-600 mb-2">最大图片数</label>
              <input v-model.number="clusterMaxImages" type="number" class="w-full px-4 py-2 rounded-lg border border-gray-200 focus:border-violet-400 outline-none" />
            </div>
            <div>
              <label class="block text-sm text-gray-600 mb-2">超时时间 (秒)</label>
              <input v-model.number="clusterTimeout" type="number" class="w-full px-4 py-2 rounded-lg border border-gray-200 focus:border-violet-400 outline-none" />
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex justify-between">
          <button @click="handleReset" class="px-4 py-2 text-red-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors">
            恢复默认
          </button>
          <div class="flex gap-3">
            <button @click="handleCancel" class="btn-secondary">取消</button>
            <button @click="handleSave" class="btn-primary">保存</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
