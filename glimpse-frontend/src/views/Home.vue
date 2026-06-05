<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMemoriesStore } from '@/stores/memories'
import { useClusterStore } from '@/stores/cluster'
import { useNotificationStore } from '@/stores/notification'
import { screenshotApi, clusterApi, healthApi, settingsApi, type Memory } from '@/api/client'
import {
  closeDesktopWindow,
  getDesktopWindowMaximized,
  focusDesktopWindow,
  hideDesktopWindow,
  isDesktopShell,
  listenForDesktopCloseRequests,
  minimizeDesktopWindow,
  toggleDesktopMaximize,
} from '@/platform/desktop'
import SearchBar from '@/components/SearchBar.vue'
import MemoryList from '@/components/MemoryList.vue'
import DetailPanel from '@/components/DetailPanel.vue'
import ClusterBar from '@/components/ClusterBar.vue'
import CloseActionDialog from '@/components/CloseActionDialog.vue'
import glimpseLogo from '@/assets/glimpse.svg'

type SearchBarExpose = {
  focus: () => void
}

type CloseAction = 'ask' | 'minimize' | 'exit'

const router = useRouter()
const memoriesStore = useMemoriesStore()
const clusterStore = useClusterStore()
const notificationStore = useNotificationStore()

const selectedMemory = computed(() => memoriesStore.selectedMemory)
const searchBar = ref<SearchBarExpose | null>(null)
const isCapturing = ref(false)
const backendReady = ref(false)
const isCheckingBackend = ref(false)
const deletingMemoryId = ref<string | null>(null)
const closeAction = ref<CloseAction>('ask')
const closeDialogOpen = ref(false)
const isDesktop = isDesktopShell()
const isWindowMaximized = ref(false)
const screenshotShortcutLabel = ref('Ctrl+Shift+G')
const searchShortcutLabel = ref('Ctrl+F')
const clusterModeEnabled = ref(false)
let removeDesktopCloseListener: (() => void) | null = null

type ScreenshotTriggerOptions = {
  initiatedByHotkey?: boolean
}

const wait = (ms: number) =>
  new Promise<void>((resolve) => {
    window.setTimeout(resolve, ms)
  })

const formatShortcutLabel = (hotkey?: string, fallback = '') => {
  if (!hotkey) {
    return fallback
  }

  const labels: Record<string, string> = {
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

  return hotkey
    .split('+')
    .map((part) => {
      const normalized = part.trim().replace(/^<|>$/g, '').toLowerCase()
      if (labels[normalized]) {
        return labels[normalized]
      }
      if (/^f([1-9]|1[0-9]|2[0-4])$/.test(normalized)) {
        return normalized.toUpperCase()
      }
      return normalized.length === 1 ? normalized.toUpperCase() : normalized
    })
    .join('+')
}

const focusSearch = async () => {
  await nextTick()
  searchBar.value?.focus()
}

const loadMemories = async () => {
  await memoriesStore.load()
  if (!memoriesStore.selectedMemory && memoriesStore.memories.length > 0) {
    memoriesStore.select(memoriesStore.memories[0])
  }
}

const loadUiSettings = async () => {
  try {
    const settings = await settingsApi.get()
    const configuredCloseAction = settings.ui?.close_action
    if (configuredCloseAction === 'ask' || configuredCloseAction === 'minimize' || configuredCloseAction === 'exit') {
      closeAction.value = configuredCloseAction
    }

    screenshotShortcutLabel.value = formatShortcutLabel(
      settings.hotkeys?.screenshot,
      'Ctrl+Shift+G',
    )
    searchShortcutLabel.value = formatShortcutLabel(
      settings.hotkeys?.search,
      'Ctrl+F',
    )
    clusterModeEnabled.value = Boolean(settings.cluster?.cluster_mode)
  } catch (error) {
    console.error('Failed to load UI settings:', error)
  }
}

const checkBackendHealth = async () => {
  if (isCheckingBackend.value) {
    return backendReady.value
  }

  isCheckingBackend.value = true
  try {
    const result = await healthApi.check()
    backendReady.value = result.status === 'healthy'
  } catch (error) {
    backendReady.value = false
  } finally {
    isCheckingBackend.value = false
  }

  return backendReady.value
}

const handleScreenshot = async (options: ScreenshotTriggerOptions = {}) => {
  if (isCapturing.value) {
    if (options.initiatedByHotkey) {
      notificationStore.show('快捷键截图失败：当前已有截图任务正在处理中。', 'warning', 2800)
    }
    return
  }

  const healthy = await checkBackendHealth()
  if (!healthy) {
      notificationStore.show(
      options.initiatedByHotkey
        ? '快捷键截图失败：后端未连接，请先启动 Python API 服务。'
        : '后端未连接，请先启动 Python API 服务。',
      'error',
      4500,
    )
    return
  }

  await loadUiSettings()
  isCapturing.value = true
  if (!clusterModeEnabled.value) {
  notificationStore.show(
    options.initiatedByHotkey
      ? '快捷键已触发，正在截图并提交分析...'
      : '正在截图并提交分析...',
    'info',
    1800,
  )
  }

  try {
    if (isDesktop) {
      await minimizeDesktopWindow()
      await wait(300)
    }

    const result = await screenshotApi.triggerAndAnalyze(true)
    if (!result.success) {
      notificationStore.show(
        options.initiatedByHotkey
          ? `快捷键截图失败：${result.message || '截图请求失败。'}`
          : result.message || '截图请求失败。',
        'error',
        4500,
      )
      return
    }

    if (!result.clustered && !clusterModeEnabled.value) {
      notificationStore.show(
      options.initiatedByHotkey
        ? `快捷键截图成功：${result.message || '已提交分析请求，等待结果。'}`
        : '截图已提交，等待分析完成。',
      'success',
        2400,
      )
    }
  } catch (error) {
    console.error('Screenshot failed:', error)
    notificationStore.show(
      options.initiatedByHotkey
        ? '快捷键截图失败：请检查后端日志。'
        : '截图请求失败，请检查后端日志。',
      'error',
      4500,
    )
  } finally {
    if (isDesktop) {
      await focusDesktopWindow()
    }
    isCapturing.value = false
  }
}

const handleCaptureButtonClick = () => {
  void handleScreenshot()
}

const handleSelectMemory = (memory: Memory) => {
  memoriesStore.select(memory)
}

const handleOpenMemoryDetail = (memoryId: string) => {
  router.push(`/memory/${memoryId}`)
}

const handleOpenSettings = () => {
  router.push('/settings')
}

const handleClusterSubmit = async () => {
  await clusterApi.submit()
}

const handleClusterCancel = async () => {
  await clusterApi.cancel()
}

const handleHideWindow = async () => {
  await hideDesktopWindow()
}

const handleMinimizeWindow = async () => {
  await minimizeDesktopWindow()
}

const syncDesktopWindowState = async () => {
  if (!isDesktop) {
    isWindowMaximized.value = false
    return
  }

  isWindowMaximized.value = await getDesktopWindowMaximized()
}

const handleToggleMaximizeWindow = async () => {
  await toggleDesktopMaximize()
  await syncDesktopWindowState()
}

const performCloseAction = async (action: Exclude<CloseAction, 'ask'>) => {
  if (action === 'minimize') {
    await hideDesktopWindow()
    return
  }

  await closeDesktopWindow()
}

const requestWindowClose = async () => {
  if (closeDialogOpen.value) {
    return
  }

  if (closeAction.value === 'ask') {
    closeDialogOpen.value = true
    return
  }

  try {
    await performCloseAction(closeAction.value)
  } catch (error) {
    console.error('Close window failed:', error)
    notificationStore.show('退出失败，请查看日志。', 'error', 3200)
  }
}

const handleCloseWindow = async () => {
  await requestWindowClose()
}

const handleCloseDialogChoice = async (payload: {
  action: 'minimize' | 'exit'
  remember: boolean
}) => {
  closeDialogOpen.value = false

  try {
    if (payload.remember) {
      try {
        await settingsApi.update({
          ui: {
            close_action: payload.action,
          },
        })
        closeAction.value = payload.action
      } catch (error) {
        console.error('Saving close action failed:', error)
        notificationStore.show('关闭偏好保存失败，但本次操作会继续执行。', 'warning', 3200)
      }
    }

    await performCloseAction(payload.action)
  } catch (error) {
    console.error('Applying close action failed:', error)
    notificationStore.show('关闭操作失败，请查看日志。', 'error', 3200)
  }
}

const handleRefresh = async () => {
  await checkBackendHealth()
  await memoriesStore.refresh()
}

const handleDeleteMemory = async (memory: Memory) => {
  if (deletingMemoryId.value) {
    return
  }

  const confirmed = window.confirm('确定要删除这条记忆吗？')
  if (!confirmed) {
    return
  }

  deletingMemoryId.value = memory.id
  try {
    await memoriesStore.remove(memory.id)
    notificationStore.show('记忆已删除', 'success', 2200)
  } catch (error) {
    console.error('Delete memory failed:', error)
    notificationStore.show('删除失败，请稍后重试。', 'error', 3200)
  } finally {
    deletingMemoryId.value = null
  }
}

const handleKeydown = (event: KeyboardEvent) => {
  const key = event.key.toLowerCase()
  if (event.ctrlKey && event.shiftKey && key === 'g') {
    if (isDesktop) {
      return
    }
    event.preventDefault()
    void handleScreenshot()
    return
  }

  if (event.ctrlKey && key === 'f') {
    event.preventDefault()
    void focusSearch()
    return
  }

  if (key === 'escape' && isDesktop) {
    event.preventDefault()
    void handleHideWindow()
  }
}

const handleFocusSearchEvent = async () => {
  await focusSearch()
}

const handleShortcutScreenshotEvent = async () => {
  if (!isDesktop) {
    return
  }

  await handleScreenshot({
    initiatedByHotkey: true,
  })
}

onMounted(async () => {
  if (isDesktop) {
    await focusDesktopWindow()
    await syncDesktopWindowState()
    removeDesktopCloseListener = await listenForDesktopCloseRequests(() => {
      void requestWindowClose()
    })
  }

  window.addEventListener('keydown', handleKeydown)
  window.addEventListener('glimpse:focus-search', handleFocusSearchEvent)
  window.addEventListener('glimpse:shortcut-screenshot', handleShortcutScreenshotEvent)
  await loadUiSettings()
  await checkBackendHealth()
  await loadMemories()
  await focusSearch()
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  window.removeEventListener('glimpse:focus-search', handleFocusSearchEvent)
  window.removeEventListener('glimpse:shortcut-screenshot', handleShortcutScreenshotEvent)
  removeDesktopCloseListener?.()
  removeDesktopCloseListener = null
})
</script>

<template>
  <div class="shell-frame flex h-screen min-h-0 flex-col overflow-hidden">
    <div class="shell-card flex h-full min-h-0 w-full flex-col overflow-hidden">
      <header class="shell-header relative flex items-center justify-between gap-4 px-5 py-4">
        <div class="shell-titlebar-drag-layer" data-tauri-drag-region></div>
        <div class="shell-drag-zone flex items-center gap-3" data-tauri-drag-region>
          <div class="logo-badge flex h-11 w-11 items-center justify-center overflow-hidden rounded-2xl">
            <img class="h-full w-full object-cover" :src="glimpseLogo" alt="Glimpse" draggable="false" />
          </div>
          <div data-tauri-drag-region>
            <h1 class="text-lg font-semibold text-slate-900">Glimpse</h1>
            <p class="text-xs text-slate-500">桌面记忆弹窗</p>
          </div>
        </div>

        <div class="flex items-center gap-2">
          <span
            data-tauri-drag-region
            :class="[
              'status-pill',
              backendReady ? 'status-pill-ready' : 'status-pill-offline',
            ]"
          >
            {{ backendReady ? '服务正常' : '服务异常' }}
          </span>
        </div>

        <div class="shell-window-controls flex items-center gap-2">
          <button
            class="shell-icon-button"
            :disabled="isCheckingBackend || memoriesStore.isLoading"
            @click="handleRefresh"
            title="刷新"
          >
            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582M20 20v-5h-.581M5.59 9A7.97 7.97 0 0112 6c2.075 0 3.963.79 5.375 2.083L20 11M4 13l2.625 2.917A7.965 7.965 0 0012 18a7.97 7.97 0 005.41-2.1" />
            </svg>
          </button>

          <button
            class="capture-button"
            :disabled="isCapturing"
            @click="handleCaptureButtonClick"
          >
            <svg v-if="!isCapturing" class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span v-else class="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/35 border-t-white"></span>
            <span>{{ isCapturing ? '处理中...' : '截图' }}</span>
            <kbd>{{ screenshotShortcutLabel }}</kbd>
          </button>

          <button
            class="shell-icon-button"
            @click="handleOpenSettings"
            title="设置"
          >
            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </button>

          <button
            v-if="isDesktop"
            class="shell-icon-button"
            @click="handleMinimizeWindow"
            title="最小化"
          >
            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4" />
            </svg>
          </button>

          <button
            v-if="isDesktop"
            class="shell-icon-button"
            @click="handleToggleMaximizeWindow"
            :title="isWindowMaximized ? '恢复' : '最大化'"
          >
            <svg
              v-if="!isWindowMaximized"
              class="h-4 w-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <rect x="5" y="5" width="14" height="14" rx="1.5" stroke-width="2" />
            </svg>
            <svg
              v-else
              class="h-4 w-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 9h10v10H9z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15V5h10" />
            </svg>
          </button>

          <button
            v-if="isDesktop"
            class="shell-icon-button shell-icon-button-danger"
            @click="handleCloseWindow"
            title="关闭"
          >
            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </header>

      <main class="min-h-0 flex-1 overflow-hidden px-5 pb-5 pt-3">
        <div class="mx-auto flex h-full min-h-0 max-w-6xl flex-col gap-4">
          <SearchBar ref="searchBar" :shortcut-label="searchShortcutLabel" />

          <ClusterBar
            v-if="clusterStore.state === 'COLLECTING'"
            @submit="handleClusterSubmit"
            @cancel="handleClusterCancel"
          />

          <div class="grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-hidden md:grid-cols-[minmax(300px,3fr)_minmax(0,5fr)]">
            <MemoryList
              :memories="memoriesStore.memories"
              :is-loading="memoriesStore.isLoading"
              :selected-id="selectedMemory?.id"
              :deleting-id="deletingMemoryId"
              :shortcut-label="screenshotShortcutLabel"
              @select="handleSelectMemory"
              @open="handleOpenMemoryDetail($event.id)"
              @delete="handleDeleteMemory"
            />

            <DetailPanel
              v-if="selectedMemory"
              :memory="selectedMemory"
              @close="memoriesStore.select(null)"
              @open="handleOpenMemoryDetail"
            />
            <div v-else class="card flex h-full min-h-0 items-center justify-center p-8 text-sm text-slate-500">
              选择一条记忆后，可在这里查看摘要与识别文本。
            </div>
          </div>
        </div>
      </main>
    </div>

    <CloseActionDialog
      :open="closeDialogOpen"
      @close="closeDialogOpen = false"
      @choose="handleCloseDialogChoice"
    />
  </div>
</template>
