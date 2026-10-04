<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
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
import { getMemoryImagePaths } from '@/utils/memory-images'
import { getMemoryDisplayText } from '@/utils/memory-types'
import { copyImageFileToClipboard } from '@/platform/clipboard'
import { t } from '@/utils/i18n'
import AddTextMemoryDialog from '@/components/AddTextMemoryDialog.vue'
import ClusterBar from '@/components/ClusterBar.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import MemoryContextMenu from '@/components/MemoryContextMenu.vue'
import MemoryInspector from '@/components/MemoryInspector.vue'
import SideDecorPanel from '@/components/SideDecorPanel.vue'
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
const inspectorPanelElement = ref<HTMLElement | null>(null)
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
const dockedLayout = ref(window.innerWidth >= 820)
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

const handleAddTextMemory = async (payload: { content: string; images: File[] }) => {
  if (isAddingTextMemory.value) return
  isAddingTextMemory.value = true
  textMemoryError.value = ''
  try {
    if (!(await backendStatus.check())) {
      textMemoryError.value = t('addMemory.backendUnavailable')
      return
    }

    const withImages = payload.images.length > 0
    const memory = withImages
      ? await memoriesApi.createWithImages(payload.images, payload.content)
      : await memoriesApi.createText(payload.content)
    if (query.value.trim()) {
      searchToolbar.value?.clear()
      await nextTick()
    }
    memoriesStore.upsert(memory)
    if (memoryMatchesFilters(memory, memoriesStore.activeFilters)) {
      memoriesStore.select(memory)
    }
    textMemoryDialogOpen.value = false
    const messageKey = memory.sync_status === 'FAILED'
      ? (withImages ? 'message.imageMemoryCreatedIndexFailed' : 'message.textMemoryCreatedIndexFailed')
      : (withImages ? 'message.imageMemoryCreated' : 'message.textMemoryCreated')
    notifications.show(
      t(messageKey),
      memory.sync_status === 'FAILED' ? 'warning' : 'success',
      memory.sync_status === 'FAILED' ? 3600 : 2200,
    )
  } catch (error) {
    logger.error('Memory creation failed: %s', error)
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
    await navigator.clipboard.writeText(getMemoryDisplayText(memory))
    notifications.show(t('message.copied'), 'success', 1800)
  } catch {
    notifications.show(t('message.copyFailed'), 'error', 2800)
  }
}

const handleMenuCopyImage = async (memory: Memory) => {
  closeContextMenu()
  const path = getMemoryImagePaths(memory)[0]
  if (!path) return
  try {
    await copyImageFileToClipboard(path)
    notifications.show(t('message.copied'), 'success', 1800)
  } catch (error) {
    logger.warn('Copy image to clipboard failed: %s', error)
    const detail = error instanceof Error ? error.message : String(error)
    notifications.show(
      `${t('message.copyImageFailed')}（${detail.slice(0, 120)}）`,
      'error',
      4200,
    )
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
  wideLayout.value = window.innerWidth >= 1180
  // 侧栏关闭交互跟随视觉形态：≥820px 侧栏是排版内的内容块（docked），点外/Esc 不关闭；
  // <820px 侧栏浮于内容之上，才有关闭语义。分界与 .inspector-panel 的媒体查询保持一致。
  dockedLayout.value = window.innerWidth >= 820
}

// 记忆墙滚动条仅在滚动进行时浮现，停止片刻即隐回（详见 .home-memory-pane 样式注释）。
const SCROLLBAR_IDLE_MS = 800
const paneScrollbarActive = ref(false)
let scrollbarIdleTimer: ReturnType<typeof window.setTimeout> | null = null

const markPaneScrollbarActive = () => {
  paneScrollbarActive.value = true
  if (scrollbarIdleTimer) window.clearTimeout(scrollbarIdleTimer)
  scrollbarIdleTimer = window.setTimeout(() => {
    paneScrollbarActive.value = false
    scrollbarIdleTimer = null
  }, SCROLLBAR_IDLE_MS)
}

// 浮层形态（<820px）下，点击面板以外（记忆卡片除外）即关闭；docked 形态是排版内
// 的内容块，点外不关闭。拖动标题栏是窗口操作，任何形态都不视为关闭意图。走
// handleCloseInspector 以保留未保存草稿确认。模态对话框打开时不参与关闭。
const handleDocumentPointerDown = (event: PointerEvent) => {
  if (!memoriesStore.selectedId || event.button !== 0) return
  if (dockedLayout.value) return
  if (!(event.target instanceof Node)) return
  if (document.querySelector('[role="dialog"][aria-modal="true"]')) return
  if (event.target instanceof Element && event.target.closest('.desktop-shell__titlebar')) return
  const panel = inspectorPanelElement.value
  if (panel?.contains(event.target)) return
  if (event.target instanceof Element && event.target.closest('.memory-card')) return
  void handleCloseInspector()
}

watch(selectedMemory, (value) => {
  if (value) {
    document.addEventListener('pointerdown', handleDocumentPointerDown, true)
  } else {
    document.removeEventListener('pointerdown', handleDocumentPointerDown, true)
  }
})

const handleKeydown = (event: KeyboardEvent) => {
  const key = event.key.toLowerCase()
  const target = event.target as HTMLElement | null
  const dialogOpen = Boolean(document.querySelector('[role="dialog"][aria-modal="true"]'))
  const editingText = target instanceof HTMLTextAreaElement || Boolean(target?.isContentEditable)

  if (dialogOpen) return

  // 浮层形态且焦点不在搜索工具栏时，Esc 优先关闭侧栏；docked 形态与搜索栏内保持既有语义。
  if (
    key === 'escape'
    && selectedMemory.value
    && !dockedLayout.value
    && !editingText
    && !(target instanceof Element && target.closest('.search-toolbar'))
  ) {
    event.preventDefault()
    void handleCloseInspector()
    return
  }

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
  if (scrollbarIdleTimer) window.clearTimeout(scrollbarIdleTimer)
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('keydown', handleKeydown)
  window.removeEventListener('glimpse:focus-search', handleFocusSearchEvent)
  window.removeEventListener('glimpse:shortcut-screenshot', handleShortcutCapture)
  document.removeEventListener('pointerdown', handleDocumentPointerDown, true)
})
</script>

<template>
  <main class="relative flex h-full min-h-0 flex-col overflow-hidden bg-[var(--shell-window-bg)]">
    <div class="relative flex min-h-0 flex-1 overflow-hidden">
      <div
        class="home-memory-pane min-w-0 flex-1 overflow-y-auto"
        :class="{
          'is-scrolling': paneScrollbarActive,
          'home-memory-pane--wall-capped': !wideLayout,
        }"
        @scroll.passive="markPaneScrollbarActive"
      >
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
          :query="memoriesStore.searchQuery"
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
          key="inspector"
          ref="inspectorPanelElement"
          class="inspector-panel z-30"
        >
          <MemoryInspector
            ref="memoryInspector"
            :memory="selectedMemory"
            @close="handleCloseInspector"
            @open="handleOpenMemory"
          />
        </div>
      </Transition>
      <!-- 装饰板不参与 Transition：普通条件渲染瞬时挂载/卸载，永远在流内占位，
           不存在离场中间态。只在 wideLayout（≥1180px，与侧栏 docked 边界一致）
           下渲染——更窄时媒体查询会把 .inspector-panel 变成右侧浮层，装饰板
           在该区间会悬浮在墙上，且预留槽位后墙面不足三列。 -->
      <div
        v-if="!selectedMemory && wideLayout"
        class="inspector-panel inspector-panel--decor"
      >
        <SideDecorPanel />
      </div>
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
  /* 墙到底/到顶后过滚就地截住，不再链给根视口——否则根视口弹性回弹会
     连同吸顶的搜索浮条一起位移。 */
  overscroll-behavior-y: contain;
  scrollbar-gutter: stable;
  container-name: memory-pane;
  container-type: inline-size;
}

/* 装饰板出现前（宽度 < 1180px）墙列数封顶三列：宽度先攒着，等够
   「三列 + 装饰板」时整体切换，避免「四列满宽 → 三列 + 装饰板」的回退跳动。
   装饰板出现后该限宽移除，随宽度正常增列。 */
.home-memory-pane--wall-capped :deep(.memory-grid) {
  max-width: calc(3 * 239px + 2 * 12px);
}

/* 记忆墙滚动条仅在滚动进行时浮现，停止约 0.8 秒后隐回：常驻拇指会在记忆墙与
   右侧装饰板/侧栏之间形成一条分割线，而悬停墙面本身不应视为滚动意图。 */
.home-memory-pane::-webkit-scrollbar-thumb {
  background: transparent;
}

.home-memory-pane.is-scrolling::-webkit-scrollbar-thumb {
  background: var(--shell-scrollbar-thumb);
}

.home-memory-pane.is-scrolling::-webkit-scrollbar-thumb:hover {
  background: var(--shell-scrollbar-thumb-hover);
}

/* Firefox/Chromium 标准属性兜底（设置 scrollbar-color 后 webkit 伪元素被忽略） */
.home-memory-pane {
  scrollbar-color: transparent transparent;
}

.home-memory-pane.is-scrolling {
  scrollbar-color: var(--shell-scrollbar-thumb) transparent;
}

/* 详情侧栏是浮在墙侧的内容块：白底、圆角与卡片阴影成块；边缘不加描边。 */
.inspector-panel {
  width: 380px;
  flex: 0 0 380px;
  min-height: 0;
  overflow: hidden;
  margin: 0.5rem 0.75rem 0.75rem 0.25rem;
  border-radius: var(--radius-xl);
  background: var(--color-surface);
  box-shadow: var(--shadow-card);
}

/* 装饰面板与记忆墙背景一体：无底色、无圆角、无阴影，仅借用槽位宽度。 */
.inspector-panel--decor {
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

/* Transition 双分支切换时，离场面板立即脱离 flex 流（原地绝对定位播完动画），
   否则两个面板短暂同占一行，内容区先压扁再弹回，吸顶搜索浮条随之闪现。 */
.inspector-leave-active {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
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
    margin: 0;
    border-radius: 0;
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
