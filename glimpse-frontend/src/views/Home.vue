<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import type { Memory } from '@/api/client'
import { clusterApi, memoriesApi, screenshotApi, searchApi, settingsApi } from '@/api/client'
import { whenBackendRuntimeReady } from '@/config/runtime'
import {
  getDesktopWindowMinimized,
  isDesktopShell,
  minimizeDesktopWindow,
} from '@/platform/desktop'
import { useBackendStatusStore } from '@/stores/backendStatus'
import { useClusterStore } from '@/stores/cluster'
import { useMemoriesStore } from '@/stores/memories'
import { useNotificationStore } from '@/stores/notification'
import { createLogger } from '@/utils/logger'
import { memoryMatchesFilters, type MemoryFilters } from '@/utils/memory-filters'
import { getMemoryImageUrls } from '@/utils/memory-images'
import { t } from '@/utils/i18n'
import AddTextMemoryDialog from '@/components/AddTextMemoryDialog.vue'
import ClusterBar from '@/components/ClusterBar.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import MemoryContextMenu from '@/components/MemoryContextMenu.vue'
import MemoryInspector from '@/components/MemoryInspector.vue'
import MemoryWall from '@/components/MemoryWall.vue'
import SearchToolbar from '@/components/SearchToolbar.vue'

type SearchToolbarExpose = {
  focus: () => void
  clear: () => void
}

type MemoryInspectorExpose = {
  canLeave: () => Promise<boolean>
}

const router = useRouter()
const memoriesStore = useMemoriesStore()
const clusterStore = useClusterStore()
const notifications = useNotificationStore()
const backendStatus = useBackendStatusStore()
const logger = createLogger('views/Home')

const searchToolbar = ref<SearchToolbarExpose | null>(null)
const memoryInspector = ref<MemoryInspectorExpose | null>(null)
const query = ref(memoriesStore.searchQuery)
const isCapturing = ref(false)
const isRefreshing = ref(false)
const textMemoryDialogOpen = ref(false)
const isAddingTextMemory = ref(false)
const textMemoryError = ref('')
const contextMenu = ref<{ x: number; y: number; memory: Memory | null }>({ x: 0, y: 0, memory: null })
const deleteDialogOpen = ref(false)
const deleteTarget = ref<Memory | null>(null)
const deletingMemory = ref(false)
const showSearchDebug = ref(false)
const clusterModeEnabled = ref(false)
const screenshotShortcutLabel = ref('Ctrl+Shift+G')
const wideLayout = ref(window.innerWidth >= 1180)
const isDesktop = isDesktopShell()
let semanticWarmupTimer: ReturnType<typeof window.setTimeout> | null = null
let unmounted = false

const selectedMemory = computed(() => memoriesStore.selectedMemory)

const wait = (milliseconds: number) =>
  new Promise<void>((resolve) => window.setTimeout(resolve, milliseconds))

const formatShortcutLabel = (hotkey?: string, fallback = '') => {
  if (!hotkey) return fallback
  const labels: Record<string, string> = {
    ctrl: 'Ctrl',
    shift: 'Shift',
    alt: 'Alt',
    cmd: 'Win',
    escape: 'Esc',
    enter: 'Enter',
    space: 'Space',
    backspace: 'Backspace',
  }
  return hotkey
    .split('+')
    .map((part) => {
      const normalized = part.trim().replace(/^<|>$/g, '').toLowerCase()
      return labels[normalized] ?? (normalized.length === 1 ? normalized.toUpperCase() : normalized)
    })
    .join('+')
}

const focusSearch = async () => {
  await nextTick()
  searchToolbar.value?.focus()
}

const scheduleSemanticWarmup = () => {
  if (semanticWarmupTimer) return
  semanticWarmupTimer = window.setTimeout(() => {
    semanticWarmupTimer = null
    void searchApi.warmup().catch((error) => logger.warn('Semantic warmup failed: %s', error))
  }, 2000)
}

const loadUiSettings = async () => {
  try {
    const settings = await settingsApi.get()
    screenshotShortcutLabel.value = formatShortcutLabel(
      settings.hotkeys?.screenshot,
      'Ctrl+Shift+G',
    )
    clusterModeEnabled.value = Boolean(settings.cluster?.cluster_mode)
  } catch (error) {
    logger.error('Failed to load UI settings: %s', error)
  }
}

const waitForBackend = async (timeout = 30_000) => {
  const deadline = Date.now() + timeout
  while (!unmounted && Date.now() < deadline) {
    if (await backendStatus.check()) return true
    await wait(500)
  }
  return false
}

const loadMemories = async () => {
  await memoriesStore.load()
  if (wideLayout.value && !memoriesStore.selectedMemory && memoriesStore.memories.length) {
    memoriesStore.select(memoriesStore.memories[0])
  }
}

const handleScreenshot = async (initiatedByHotkey = false) => {
  if (isCapturing.value) {
    if (initiatedByHotkey) notifications.show(t('message.busyCapture'), 'warning', 2800)
    return
  }

  if (!(await backendStatus.check())) {
    const messageKey = backendStatus.isStarting
      ? initiatedByHotkey ? 'message.backendStartingHotkey' : 'message.backendStarting'
      : initiatedByHotkey ? 'message.backendOfflineHotkey' : 'message.backendOffline'
    notifications.show(
      t(messageKey),
      backendStatus.isStarting ? 'info' : 'error',
      4200,
    )
    return
  }

  await loadUiSettings()

  if (isDesktop) {
    const wasMinimized = await getDesktopWindowMinimized()
    if (!wasMinimized) {
      await minimizeDesktopWindow()
      await wait(300)
    }
  }

  if (isCapturing.value) {
    if (initiatedByHotkey) notifications.show(t('message.busyCapture'), 'warning', 2800)
    return
  }
  isCapturing.value = true
  // 锁只保护发送截图请求本身；最小化与等待不在锁内，连按可快速进入下一次截图。
  if (!clusterModeEnabled.value) {
    notifications.show(
      initiatedByHotkey ? t('message.captureStartedHotkey') : t('message.captureStarted'),
      'info',
      1800,
    )
  }

  try {
    const result = await screenshotApi.triggerAndAnalyze()
    if (!result.success) {
      notifications.show(result.message || t('message.captureFailed'), 'error', 4200)
    } else if (!result.clustered && !clusterModeEnabled.value) {
      if (result.memory) {
        memoriesStore.upsert(result.memory)
      }
      notifications.show(result.message || t('message.captureSubmitted'), 'success', 2200)
    }
  } catch (error) {
    logger.error('Screenshot failed: %s', error)
    notifications.show(t('message.checkBackendLogs'), 'error', 4200)
  } finally {
    isCapturing.value = false
  }
}

const confirmInspectorLeave = () =>
  memoryInspector.value?.canLeave() ?? Promise.resolve(true)

const handleSelectMemory = async (memory: Memory) => {
  if (memory.id === memoriesStore.selectedId) return
  if (!(await confirmInspectorLeave())) return
  memoriesStore.select(memory)
}

const handleCloseInspector = async () => {
  if (!(await confirmInspectorLeave())) return
  memoriesStore.select(null)
}

const handleOpenMemory = async (memory: Memory | string) => {
  if (!(await confirmInspectorLeave())) return
  const id = typeof memory === 'string' ? memory : memory.id
  await router.push(`/memory/${id}`)
}

const handleRefresh = async () => {
  if (!(await backendStatus.check())) return
  isRefreshing.value = true
  try {
    scheduleSemanticWarmup()
    await memoriesStore.refresh()
  } finally {
    isRefreshing.value = false
  }
}

const openTextMemoryDialog = async () => {
  if (!(await backendStatus.check())) {
    notifications.show(t('addMemory.backendUnavailable'), 'error', 3200)
    return
  }
  textMemoryError.value = ''
  textMemoryDialogOpen.value = true
}

const closeTextMemoryDialog = () => {
  if (isAddingTextMemory.value) return
  textMemoryDialogOpen.value = false
  textMemoryError.value = ''
}

const handleAddTextMemory = async (content: string) => {
  if (isAddingTextMemory.value) return
  isAddingTextMemory.value = true
  textMemoryError.value = ''
  try {
    if (!(await backendStatus.check())) {
      textMemoryError.value = t('addMemory.backendUnavailable')
      return
    }

    const memory = await memoriesApi.createText(content)
    if (query.value.trim()) {
      searchToolbar.value?.clear()
      await nextTick()
    }
    memoriesStore.upsert(memory)
    if (memoryMatchesFilters(memory, memoriesStore.activeFilters)) {
      memoriesStore.select(memory)
    }
    textMemoryDialogOpen.value = false
    notifications.show(
      t(memory.sync_status === 'FAILED'
        ? 'message.textMemoryCreatedIndexFailed'
        : 'message.textMemoryCreated'),
      memory.sync_status === 'FAILED' ? 'warning' : 'success',
      memory.sync_status === 'FAILED' ? 3600 : 2200,
    )
  } catch (error) {
    logger.error('Text memory creation failed: %s', error)
    textMemoryError.value = t('addMemory.saveFailed')
  } finally {
    isAddingTextMemory.value = false
  }
}

const handleApplyFilters = async (filters: MemoryFilters) => {
  if (!(await confirmInspectorLeave())) return
  const results = await memoriesStore.applyFilters(filters)
  memoriesStore.select(wideLayout.value ? results[0] ?? null : null)
}

const openContextMenu = (payload: { memory: Memory; x: number; y: number }) => {
  contextMenu.value = payload
}

const closeContextMenu = () => {
  contextMenu.value = { x: 0, y: 0, memory: null }
}

const handleMenuOpen = (memory: Memory) => {
  closeContextMenu()
  void handleOpenMemory(memory)
}

const handleMenuCopy = async (memory: Memory) => {
  closeContextMenu()
  try {
    await navigator.clipboard.writeText(memory.ai_summary)
    notifications.show(t('message.copied'), 'success', 1800)
  } catch {
    notifications.show(t('message.copyFailed'), 'error', 2800)
  }
}

const handleMenuCopyImage = async (memory: Memory) => {
  closeContextMenu()
  const url = getMemoryImageUrls(memory)[0]
  if (!url) return
  try {
    let blob = await (await fetch(url)).blob()
    if (blob.type !== 'image/png') {
      const bitmap = await createImageBitmap(blob)
      const canvas = document.createElement('canvas')
      canvas.width = bitmap.width
      canvas.height = bitmap.height
      canvas.getContext('2d')?.drawImage(bitmap, 0, 0)
      const converted = await new Promise<Blob | null>((resolve) =>
        canvas.toBlob(resolve, 'image/png'),
      )
      bitmap.close()
      if (!converted) throw new Error('canvas toBlob returned null')
      blob = converted
    }
    await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })])
    notifications.show(t('message.copied'), 'success', 1800)
  } catch (error) {
    logger.warn('Copy image to clipboard failed: %s', error)
    notifications.show(t('message.copyImageFailed'), 'error', 2800)
  }
}

const handleMenuDelete = (memory: Memory) => {
  closeContextMenu()
  deleteTarget.value = memory
  deleteDialogOpen.value = true
}

const confirmContextDelete = async () => {
  const target = deleteTarget.value
  if (!target || deletingMemory.value) return
  deletingMemory.value = true
  try {
    await memoriesStore.remove(target.id)
    notifications.show(t('message.deleted'), 'success', 1800)
    deleteDialogOpen.value = false
    if (memoriesStore.selectedId === target.id) {
      memoriesStore.select(null)
    }
  } catch (error) {
    logger.error('Delete memory failed: %s', error)
    notifications.show(t('message.deleteFailed'), 'error', 2800)
  } finally {
    deletingMemory.value = false
  }
}

const handleResize = () => {
  const wasWide = wideLayout.value
  wideLayout.value = window.innerWidth >= 1180
  if (!wasWide && wideLayout.value && !memoriesStore.selectedMemory && memoriesStore.memories.length) {
    memoriesStore.select(memoriesStore.memories[0])
  }
}

const handleKeydown = (event: KeyboardEvent) => {
  const key = event.key.toLowerCase()
  const target = event.target as HTMLElement | null
  const dialogOpen = Boolean(document.querySelector('[role="dialog"][aria-modal="true"]'))
  const editingText = target instanceof HTMLTextAreaElement || Boolean(target?.isContentEditable)

  if (dialogOpen) return

  if (key === 'escape' && query.value && !editingText) {
    event.preventDefault()
    searchToolbar.value?.clear()
  } else if (event.ctrlKey && event.shiftKey && key === 'g' && !isDesktop) {
    event.preventDefault()
    void handleScreenshot()
  } else if (event.ctrlKey && key === 'f') {
    event.preventDefault()
    void focusSearch()
  }
}

const handleFocusSearchEvent = () => void focusSearch()
const handleShortcutCapture = () => {
  if (isDesktop) void handleScreenshot(true)
}

onBeforeRouteLeave(async () => confirmInspectorLeave())

onMounted(async () => {
  unmounted = false
  window.addEventListener('resize', handleResize)
  window.addEventListener('keydown', handleKeydown)
  window.addEventListener('glimpse:focus-search', handleFocusSearchEvent)
  window.addEventListener('glimpse:shortcut-screenshot', handleShortcutCapture)

  await whenBackendRuntimeReady()
  if (!(await waitForBackend())) return
  await Promise.all([loadUiSettings(), loadMemories()])
  scheduleSemanticWarmup()
  await focusSearch()
})

onUnmounted(() => {
  unmounted = true
  if (semanticWarmupTimer) window.clearTimeout(semanticWarmupTimer)
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('keydown', handleKeydown)
  window.removeEventListener('glimpse:focus-search', handleFocusSearchEvent)
  window.removeEventListener('glimpse:shortcut-screenshot', handleShortcutCapture)
})
</script>

<template>
  <main class="relative flex h-full min-h-0 flex-col overflow-hidden bg-[var(--shell-window-bg)]">
    <div class="relative flex min-h-0 flex-1 overflow-hidden">
      <div class="home-memory-pane min-w-0 flex-1 overflow-y-auto">
        <SearchToolbar
          ref="searchToolbar"
          v-model="query"
          shortcut-label="Ctrl+F"
          :capture-shortcut-label="screenshotShortcutLabel"
          :capturing="isCapturing"
          :capture-disabled="!backendStatus.isReady"
          :adding-memory="isAddingTextMemory"
          :add-memory-disabled="!backendStatus.isReady"
          :refreshing="isRefreshing"
          @capture="handleScreenshot()"
          @add-memory="openTextMemoryDialog"
          @refresh="handleRefresh"
          @debug-panel-change="showSearchDebug = $event"
        />

        <ClusterBar
          v-if="clusterStore.isCollecting"
          class="mx-5 mt-3"
          @submit="clusterApi.submit()"
          @cancel="clusterApi.cancel()"
        />

        <MemoryWall
          :memories="memoriesStore.memories"
          :total="memoriesStore.total"
          :loading="memoriesStore.isLoading"
          :selected-id="memoriesStore.selectedId"
          :query="query"
          :show-search-debug="showSearchDebug"
          :capturing="isCapturing"
          :capture-disabled="!backendStatus.isReady"
          :adding-memory="isAddingTextMemory"
          :add-memory-disabled="!backendStatus.isReady"
          :filters="memoriesStore.activeFilters"
          @select="handleSelectMemory"
          @open="handleOpenMemory"
          @contextmenu="openContextMenu"
          @capture="handleScreenshot()"
          @add-memory="openTextMemoryDialog"
          @apply-filters="handleApplyFilters"
        />
      </div>

      <Transition name="inspector">
        <div
          v-if="selectedMemory"
          class="inspector-panel z-30 border-l border-[var(--shell-line)] shadow-[-12px_0_28px_rgba(15,23,42,.06)]"
        >
          <MemoryInspector
            ref="memoryInspector"
            :memory="selectedMemory"
            @close="handleCloseInspector"
            @open="handleOpenMemory"
          />
        </div>
      </Transition>
    </div>

    <AddTextMemoryDialog
      :open="textMemoryDialogOpen"
      :busy="isAddingTextMemory"
      :error-message="textMemoryError"
      @cancel="closeTextMemoryDialog"
      @submit="handleAddTextMemory"
    />

    <MemoryContextMenu
      :x="contextMenu.x"
      :y="contextMenu.y"
      :memory="contextMenu.memory"
      @close="closeContextMenu"
      @open="handleMenuOpen"
      @copy="handleMenuCopy"
      @copy-image="handleMenuCopyImage"
      @delete="handleMenuDelete"
    />

    <ConfirmDialog
      id="wall-delete-memory"
      :open="deleteDialogOpen"
      :title="t('delete.title')"
      :description="t('message.deleteConfirmIrreversible')"
      :confirm-label="t('action.delete')"
      :cancel-label="t('action.cancel')"
      :busy="deletingMemory"
      destructive
      @confirm="confirmContextDelete"
      @cancel="deleteDialogOpen = false"
    />
  </main>
</template>

<style scoped>
.home-memory-pane {
  position: relative;
  isolation: isolate;
  overflow-x: clip;
  scrollbar-gutter: stable;
  container-name: memory-pane;
  container-type: inline-size;
}

.inspector-panel {
  width: 380px;
  flex: 0 0 380px;
  min-height: 0;
}

@media (max-width: 1179px) {
  .inspector-panel {
    position: absolute;
    inset: 0 0 0 auto;
    width: min(420px, 100%);
  }
}

@media (max-width: 819px) {
  .inspector-panel {
    inset: 0;
    width: 100%;
  }
}

.inspector-enter-active,
.inspector-leave-active {
  transition: transform 180ms ease, opacity 180ms ease;
}

.inspector-enter-from,
.inspector-leave-to {
  transform: translateX(24px);
  opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
  .inspector-enter-active,
  .inspector-leave-active {
    transition: none;
  }
}
</style>
