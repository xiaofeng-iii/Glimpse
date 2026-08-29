<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import {
  ArrowTopRightOnSquareIcon,
  ClipboardDocumentIcon,
  PhotoIcon,
} from '@heroicons/vue/24/outline'
import { useImagePreviewStore } from '@/stores/imagePreview'
import { useNotificationStore } from '@/stores/notification'
import { copyImageFileToClipboard, copyImageFilesToClipboard } from '@/platform/clipboard'
import { isDesktopShell } from '@/platform/desktop'
import { t } from '@/utils/i18n'

const props = defineProps<{
  x: number
  y: number
  /** 相对后端数据根目录的图片路径（用于整组复制为文件列表）。 */
  paths: string[]
  /** 各图片的可访问 URL（与 paths 一一对应）。 */
  urls: string[]
  index: number
  /** 递增令牌：父组件每次右键都 +1，驱动菜单重新打开（同图同位置也生效）。 */
  openToken: number
  /** 是否提供“查看图片”入口（详情画廊场景）。 */
  showOpen?: boolean
}>()

const emit = defineEmits<{
  (event: 'close'): void
}>()

const imagePreview = useImagePreviewStore()
const menuElement = ref<HTMLElement | null>(null)
const ready = ref(false)
const position = ref({ x: 0, y: 0 })
// 快照打开瞬间的状态，避免菜单期间上游变化导致错位。
const snapshot = ref<{ urls: string[]; paths: string[]; index: number } | null>(null)

const canCopyFiles = computed(() => Boolean(isDesktopShell() && (snapshot.value?.paths.length ?? 0) > 1))

const close = (options: { restoreFocus?: boolean } = {}) => {
  snapshot.value = null
  unbindListeners()
  if (options.restoreFocus) {
    document.activeElement instanceof HTMLElement && document.activeElement.focus({ preventScroll: true })
  }
  emit('close')
}

const handleDocumentContextmenu = (event: MouseEvent) => {
  event.preventDefault()
  const el = menuElement.value
  if (!el || !(event.target instanceof Node) || !el.contains(event.target)) close()
}

const handleDocumentPointerDown = (event: PointerEvent) => {
  const el = menuElement.value
  if (!el || !(event.target instanceof Node) || !el.contains(event.target)) close()
}

const handleDocumentKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape') {
    event.preventDefault()
    event.stopPropagation()
    close()
  } else if (event.key === 'Tab') {
    event.preventDefault()
    close()
  }
}

const handleViewportChange = () => close({ restoreFocus: false })

const bindListeners = () => {
  document.addEventListener('contextmenu', handleDocumentContextmenu, true)
  document.addEventListener('pointerdown', handleDocumentPointerDown, true)
  document.addEventListener('keydown', handleDocumentKeydown, true)
  document.addEventListener('scroll', handleViewportChange, true)
  window.addEventListener('resize', handleViewportChange)
}

const unbindListeners = () => {
  document.removeEventListener('contextmenu', handleDocumentContextmenu, true)
  document.removeEventListener('pointerdown', handleDocumentPointerDown, true)
  document.removeEventListener('keydown', handleDocumentKeydown, true)
  document.removeEventListener('scroll', handleViewportChange, true)
  window.removeEventListener('resize', handleViewportChange)
}

watch(
  () => props.openToken,
  async (token) => {
    if (!token || !props.urls.length) return
    snapshot.value = { urls: [...props.urls], paths: [...props.paths], index: props.index }
    ready.value = false
    position.value = { x: props.x, y: props.y }
    bindListeners()
    await nextTick()
    const el = menuElement.value
    if (el) {
      const rect = el.getBoundingClientRect()
      position.value = {
        x: Math.max(8, Math.min(props.x, window.innerWidth - rect.width - 8)),
        y: Math.max(8, Math.min(props.y, window.innerHeight - rect.height - 8)),
      }
    }
    ready.value = true
  },
)

onBeforeUnmount(unbindListeners)

const finish = () => {
  snapshot.value = null
  unbindListeners()
  emit('close')
}

const notify = (message: string, type: 'success' | 'error', duration: number) => {
  useNotificationStore().show(message, type, duration)
}

const runOpen = () => {
  const shot = snapshot.value
  if (!shot) return
  imagePreview.open(shot.urls, shot.index)
  finish()
}

const runCopyImage = async () => {
  const shot = snapshot.value
  if (!shot) return
  const path = shot.paths[shot.index]
  finish()
  if (!path) {
    notify(t('message.copyImageFailed'), 'error', 2800)
    return
  }
  try {
    await copyImageFileToClipboard(path)
    notify(t('message.copied'), 'success', 1800)
  } catch (error) {
    console.error('Copy image to clipboard failed:', error)
    const detail = error instanceof Error ? error.message : String(error)
    notify(`${t('message.copyImageFailed')}（${detail.slice(0, 120)}）`, 'error', 4200)
  }
}

const runCopyAllImages = async () => {
  const shot = snapshot.value
  if (!shot) return
  const paths = shot.paths
  finish()
  try {
    await copyImageFilesToClipboard(paths)
    notify(t('message.copiedImageFiles', { count: paths.length }), 'success', 2200)
  } catch (error) {
    console.error('Copy image files to clipboard failed:', error)
    const detail = error instanceof Error ? error.message : String(error)
    notify(`${t('message.copyImageFailed')}（${detail.slice(0, 120)}）`, 'error', 4200)
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="snapshot"
      ref="menuElement"
      class="image-context-menu"
      :class="{ 'image-context-menu--ready': ready }"
      :style="{ left: `${position.x}px`, top: `${position.y}px` }"
      role="menu"
      :aria-label="t('contextMenu.label')"
      tabindex="-1"
      @contextmenu.prevent
    >
      <button
        v-if="showOpen"
        type="button"
        role="menuitem"
        class="image-context-menu__item"
        @click="runOpen"
      >
        <ArrowTopRightOnSquareIcon class="h-4 w-4" aria-hidden="true" />
        <span>{{ t('action.viewImage') }}</span>
      </button>
      <button
        type="button"
        role="menuitem"
        class="image-context-menu__item"
        @click="runCopyImage"
      >
        <ClipboardDocumentIcon class="h-4 w-4" aria-hidden="true" />
        <span>{{ t('action.copyImage') }}</span>
      </button>
      <button
        v-if="canCopyFiles"
        type="button"
        role="menuitem"
        class="image-context-menu__item"
        @click="runCopyAllImages"
      >
        <PhotoIcon class="h-4 w-4" aria-hidden="true" />
        <span>{{ t('action.copyAllImages', { count: snapshot.paths.length }) }}</span>
      </button>
    </div>
  </Teleport>
</template>

<style scoped>
.image-context-menu {
  position: fixed;
  z-index: var(--z-toast);
  min-width: 12rem;
  padding: 0.375rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface-raised);
  box-shadow:
    0 4px 16px rgba(24, 34, 56, 0.14),
    0 12px 36px rgba(24, 34, 56, 0.18);
  outline: none;
  visibility: hidden;
  transform-origin: top left;
  animation: image-context-menu-in 140ms ease-out;
}

.image-context-menu--ready {
  visibility: visible;
}

.image-context-menu__item {
  display: flex;
  width: 100%;
  min-height: var(--control-h-md);
  align-items: center;
  gap: 0.5rem;
  padding: 0 0.625rem;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  line-height: var(--line-height-14);
  text-align: left;
  transition: background-color 140ms ease, color 140ms ease;
}

.image-context-menu__item > svg {
  flex: 0 0 auto;
}

.image-context-menu__item:hover,
.image-context-menu__item:focus-visible {
  background: var(--color-surface-hover);
  color: var(--color-text);
  box-shadow: none;
  outline: none;
}

:global([data-theme='dark']) .image-context-menu {
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.5);
}

@keyframes image-context-menu-in {
  from {
    opacity: 0;
    transform: scale(0.97);
  }
}

@media (prefers-reduced-motion: reduce) {
  .image-context-menu {
    animation: none;
  }
}
</style>
