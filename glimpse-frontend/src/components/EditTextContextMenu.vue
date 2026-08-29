<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useNotificationStore } from '@/stores/notification'
import { isDesktopShell } from '@/platform/desktop'
import { t } from '@/utils/i18n'

type EditableElement = HTMLInputElement | HTMLTextAreaElement

// 桌面端走 Tauri 原生剪贴板（无网页权限弹窗），网页开发模式退回 navigator API。
const readClipboardText = async (): Promise<string> => {
  if (isDesktopShell()) {
    const { readText } = await import('@tauri-apps/plugin-clipboard-manager')
    return await readText()
  }
  return await navigator.clipboard.readText()
}

const props = defineProps<{
  x: number
  y: number
  target: EditableElement | null
}>()

const emit = defineEmits<{
  (event: 'close'): void
}>()

const notifications = useNotificationStore()
const menuElement = ref<HTMLElement | null>(null)
const current = ref<EditableElement | null>(null)
const ready = ref(false)
const position = ref({ x: 0, y: 0 })

const state = computed(() => {
  const el = current.value
  if (!el) {
    return { hasSelection: false, readonly: true, hasContent: false }
  }
  const start = el.selectionStart ?? 0
  const end = el.selectionEnd ?? 0
  return {
    hasSelection: start !== end,
    readonly: el.readOnly || el.disabled,
    hasContent: el.value.length > 0,
  }
})

const focusTarget = () => {
  current.value?.focus({ preventScroll: true })
}

const close = (options: { restoreFocus?: boolean } = {}) => {
  const el = current.value
  current.value = null
  unbindListeners()
  if (el && options.restoreFocus) el.focus({ preventScroll: true })
  emit('close')
}

const runUndo = () => {
  focusTarget()
  document.execCommand('undo')
  close({ restoreFocus: false })
}

const runCut = () => {
  focusTarget()
  document.execCommand('cut')
  close({ restoreFocus: false })
}

const runCopy = () => {
  focusTarget()
  document.execCommand('copy')
  close({ restoreFocus: false })
}

const runSelectAll = () => {
  focusTarget()
  current.value?.select()
  close({ restoreFocus: false })
}

const runPaste = async () => {
  const el = current.value
  if (!el) return
  el.focus({ preventScroll: true })
  try {
    const text = await readClipboardText()
    if (text) {
      const start = el.selectionStart ?? el.value.length
      const end = el.selectionEnd ?? el.value.length
      el.setRangeText(text, start, end, 'end')
      el.dispatchEvent(new Event('input', { bubbles: true }))
    }
    close({ restoreFocus: false })
  } catch (error) {
    console.error('Paste from clipboard failed:', error)
    notifications.show(t('message.pasteFailed'), 'error', 3200)
    close({ restoreFocus: false })
  }
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
  () => props.target,
  async (target) => {
    if (!target) return
    current.value = target
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
</script>

<template>
  <Teleport to="body">
    <div
      v-if="current"
      ref="menuElement"
      class="edit-text-menu"
      :class="{ 'edit-text-menu--ready': ready }"
      :style="{ left: `${position.x}px`, top: `${position.y}px` }"
      role="menu"
      tabindex="-1"
      @contextmenu.prevent
    >
      <button
        type="button"
        role="menuitem"
        class="edit-text-menu__item"
        :disabled="state.readonly"
        @click="runUndo"
      >
        <span>{{ t('action.undo') }}</span>
        <kbd class="edit-text-menu__shortcut">Ctrl+Z</kbd>
      </button>
      <button
        type="button"
        role="menuitem"
        class="edit-text-menu__item"
        :disabled="!state.hasSelection || state.readonly"
        @click="runCut"
      >
        <span>{{ t('action.cut') }}</span>
        <kbd class="edit-text-menu__shortcut">Ctrl+X</kbd>
      </button>
      <button
        type="button"
        role="menuitem"
        class="edit-text-menu__item"
        :disabled="!state.hasSelection"
        @click="runCopy"
      >
        <span>{{ t('action.copy') }}</span>
        <kbd class="edit-text-menu__shortcut">Ctrl+C</kbd>
      </button>
      <button
        type="button"
        role="menuitem"
        class="edit-text-menu__item"
        :disabled="state.readonly"
        @click="runPaste"
      >
        <span>{{ t('action.paste') }}</span>
        <kbd class="edit-text-menu__shortcut">Ctrl+V</kbd>
      </button>
      <button
        type="button"
        role="menuitem"
        class="edit-text-menu__item"
        :disabled="!state.hasContent"
        @click="runSelectAll"
      >
        <span>{{ t('action.selectAll') }}</span>
        <kbd class="edit-text-menu__shortcut">Ctrl+A</kbd>
      </button>
    </div>
  </Teleport>
</template>

<style scoped>
.edit-text-menu {
  position: fixed;
  z-index: var(--z-toast);
  min-width: 13rem;
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
  animation: edit-text-menu-in 140ms ease-out;
}

.edit-text-menu--ready {
  visibility: visible;
}

.edit-text-menu__item {
  display: flex;
  width: 100%;
  min-height: var(--control-h-md);
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
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

.edit-text-menu__item:hover:not(:disabled),
.edit-text-menu__item:focus-visible:not(:disabled) {
  background: var(--color-surface-hover);
  color: var(--color-text);
  box-shadow: none;
  outline: none;
}

.edit-text-menu__item:disabled {
  color: var(--color-text-muted);
  opacity: 0.55;
  cursor: default;
}

.edit-text-menu__shortcut {
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  font-size: 0.75rem;
  font-weight: 500;
}

:global([data-theme='dark']) .edit-text-menu {
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.5);
}

@keyframes edit-text-menu-in {
  from {
    opacity: 0;
    transform: scale(0.97);
  }
}

@media (prefers-reduced-motion: reduce) {
  .edit-text-menu {
    animation: none;
  }
}
</style>
