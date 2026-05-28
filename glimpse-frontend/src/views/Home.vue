<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMemoriesStore } from '@/stores/memories'
import { useClusterStore } from '@/stores/cluster'
import { useNotificationStore } from '@/stores/notification'
import { screenshotApi, clusterApi, healthApi, settingsApi, type Memory } from '@/api/client'
import {
  closeDesktopWindow,
  focusDesktopWindow,
  hideDesktopWindow,
  isDesktopShell,
} from '@/platform/desktop'
import SearchBar from '@/components/SearchBar.vue'
import MemoryList from '@/components/MemoryList.vue'
import DetailPanel from '@/components/DetailPanel.vue'
import ClusterBar from '@/components/ClusterBar.vue'

type SearchBarExpose = {
  focus: () => void
}

const router = useRouter()
const memoriesStore = useMemoriesStore()
const clusterStore = useClusterStore()
const notificationStore = useNotificationStore()

const selectedMemory = computed(() => memoriesStore.selectedMemory)
const searchBar = ref<SearchBarExpose | null>(null)
const isCapturing = ref(false)
const backendReady = ref(false)
const isCheckingBackend = ref(false)
const isDesktop = isDesktopShell()

const wait = (ms: number) =>
  new Promise<void>((resolve) => {
    window.setTimeout(resolve, ms)
  })

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

const handleScreenshot = async () => {
  if (isCapturing.value) {
    return
  }

  const healthy = await checkBackendHealth()
  if (!healthy) {
    notificationStore.show('后端未连接，请先启动 Python API 服务。', 'error', 4500)
    return
  }

  isCapturing.value = true
  notificationStore.show('正在截图并提交分析...', 'info', 0)

  try {
    if (isDesktop) {
      await hideDesktopWindow()
      await wait(180)
    }

    // API now blocks until memory is fully created (mirrors main-branch Qt flow)
    const result = await screenshotApi.triggerAndAnalyze(true)
    if (!result.success) {
      notificationStore.show(result.message || '截图请求失败。', 'error', 4500)
      return
    }

    // Memory is already created — refresh list and select the new memory
    await loadMemories()
    if (result.memory_id) {
      const created = memoriesStore.memories.find(m => m.id === result.memory_id)
      if (created) {
        memoriesStore.select(created)
      }
    }
    notificationStore.show('记忆分析完成', 'success', 2200)
  } catch (error) {
    console.error('Screenshot failed:', error)
    notificationStore.show('截图请求失败，请检查后端日志。', 'error', 4500)
  } finally {
    if (isDesktop) {
      await focusDesktopWindow()
    }
    isCapturing.value = false
  }
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

const handleCloseWindow = async () => {
  let closeAction = 'ask'
  try {
    const settings = await settingsApi.get()
    closeAction = settings.ui?.close_action || 'ask'
  } catch (error) {
    closeAction = 'ask'
  }

  if (closeAction === 'minimize') {
    await hideDesktopWindow()
    return
  }

  if (closeAction === 'exit') {
    await closeDesktopWindow()
    return
  }

  const shouldExit = window.confirm('关闭 Glimpse？\n\n确定：退出应用\n取消：最小化到托盘')
  if (shouldExit) {
    await closeDesktopWindow()
  } else {
    await hideDesktopWindow()
  }
}

const handleRefresh = async () => {
  await checkBackendHealth()
  await memoriesStore.refresh()
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

onMounted(async () => {
  if (isDesktop) {
    await focusDesktopWindow()
  }

  window.addEventListener('keydown', handleKeydown)
  window.addEventListener('glimpse:focus-search', handleFocusSearchEvent)
  await checkBackendHealth()
  await loadMemories()
  await focusSearch()
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  window.removeEventListener('glimpse:focus-search', handleFocusSearchEvent)
})
</script>

<template>
  <div class="min-h-screen shell-frame p-4">
    <div class="shell-card mx-auto flex min-h-[calc(100vh-2rem)] max-w-6xl flex-col overflow-hidden rounded-[28px]">
      <header class="shell-header flex items-center justify-between gap-4 px-5 py-4">
        <div class="flex items-center gap-3" data-tauri-drag-region>
          <div class="logo-badge flex h-11 w-11 items-center justify-center rounded-2xl text-lg font-bold text-white">
            G
          </div>
          <div data-tauri-drag-region>
            <h1 class="text-lg font-semibold text-slate-900">Glimpse</h1>
            <p class="text-xs text-slate-500">
              桌面记忆弹窗
              <span class="mx-2 text-slate-300">·</span>
              Ctrl+Shift+G 截图
            </p>
          </div>
        </div>

        <div class="flex items-center gap-2">
          <span
            :class="[
              'status-pill',
              backendReady ? 'status-pill-ready' : 'status-pill-offline',
            ]"
          >
            {{ backendReady ? '后端已连接' : '后端未连接' }}
          </span>

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
            @click="handleScreenshot"
          >
            <svg v-if="!isCapturing" class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span v-else class="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/35 border-t-white"></span>
            <span>{{ isCapturing ? '处理中...' : '截图' }}</span>
            <kbd>Ctrl+Shift+G</kbd>
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
            @click="handleHideWindow"
            title="隐藏"
          >
            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4" />
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

      <main class="min-h-0 flex-1 overflow-y-auto px-5 pb-5">
        <div class="mx-auto flex min-h-full max-w-6xl flex-col gap-4">
          <SearchBar ref="searchBar" />

          <ClusterBar
            v-if="clusterStore.state === 'COLLECTING'"
            @submit="handleClusterSubmit"
            @cancel="handleClusterCancel"
          />

          <div class="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(360px,5fr)]">
            <MemoryList
              :memories="memoriesStore.memories"
              :is-loading="memoriesStore.isLoading"
              :selected-id="selectedMemory?.id"
              @select="handleSelectMemory"
              @open="handleOpenMemoryDetail($event.id)"
            />

            <DetailPanel
              v-if="selectedMemory"
              :memory="selectedMemory"
              @close="memoriesStore.select(null)"
              @open="handleOpenMemoryDetail"
            />
            <div v-else class="card flex items-center justify-center p-8 text-sm text-slate-500">
              选择一条记忆后，可在这里查看摘要与精确文本。
            </div>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>
