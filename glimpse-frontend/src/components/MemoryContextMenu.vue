<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import {
  ArrowTopRightOnSquareIcon,
  ClipboardDocumentIcon,
  PhotoIcon,
  TrashIcon,
} from '@heroicons/vue/24/outline'
import type { Memory } from '@/api/client'
import { getMemoryImageUrls } from '@/utils/memory-images'
import { isTextMemory } from '@/utils/memory-types'
import { t } from '@/utils/i18n'

const props = defineProps<{
  x: number
  y: number
  memory: Memory | null
}>()

const emit = defineEmits<{
  (event: 'close'): void
  (event: 'open', memory: Memory): void
  (event: 'copy', memory: Memory): void
  (event: 'copy-image', memory: Memory): void
  (event: 'delete', memory: Memory): void
}>()

const menuElement = ref<HTMLElement | null>(null)
const current = ref<Memory | null>(null)
const ready = ref(false)
const position = ref({ x: 0, y: 0 })

const isText = computed(() => (current.value ? isTextMemory(current.value) : false))
const hasImage = computed(() => Boolean(current.value && getMemoryImageUrls(current.value).length))

const focusableItems = () =>
  Array.from(
    menuElement.value?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [],
  )

const focusItemAt = (index: number) => {
  const items = focusableItems()
  if (items.length) items[Math.max(0, Math.min(index, items.length - 1))]?.focus()
}

const moveFocus = (delta: number) => {
  const items = focusableItems()
  const activeIndex = items.findIndex((item) => item === document.activeElement)
  const nextIndex = activeIndex < 0 ? 0 : (activeIndex + delta + items.length) % items.length
  items[nextIndex]?.focus()
}

const restoreFocus = (memory: Memory) => {
  document
    .querySelector<HTMLElement>(`[data-memory-id="${memory.id}"]`)
    ?.focus({ preventScroll: true })
}

const close = (options: { restoreFocus?: boolean } = {}) => {
  const memory = current.value
  current.value = null
  unbindListeners()
  if (memory && options.restoreFocus) restoreFocus(memory)
  emit('close')
}

const run = (action: 'open' | 'copy' | 'copy-image' | 'delete') => {
  const memory = current.value
  if (!memory) return
  current.value = null
  unbindListeners()
  emit('close')
  if (action === 'open') emit('open', memory)
  else if (action === 'copy') emit('copy', memory)
  else if (action === 'copy-image') emit('copy-image', memory)
  else emit('delete', memory)
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
  } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault()
    moveFocus(event.key === 'ArrowDown' ? 1 : -1)
  } else if (event.key === 'Home') {
    event.preventDefault()
    focusItemAt(0)
  } else if (event.key === 'End') {
    event.preventDefault()
    focusItemAt(focusableItems().length - 1)
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
  () => props.memory,
  async (memory) => {
    if (!memory) return
    current.value = memory
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
    await nextTick()
    focusItemAt(0)
  },
)

onBeforeUnmount(unbindListeners)
</script>

<template>
  <Teleport to="body">
    <div
      v-if="current"
      ref="menuElement"
      class="memory-context-menu"
      :class="{ 'memory-context-menu--ready': ready }"
      :style="{ left: `${position.x}px`, top: `${position.y}px` }"
      role="menu"
      :aria-label="t('contextMenu.label')"
      tabindex="-1"
      @contextmenu.prevent
    >
      <button
        type="button"
        role="menuitem"
        class="memory-context-menu__item"
        @click="run('open')"
      >
        <ArrowTopRightOnSquareIcon class="h-4 w-4" aria-hidden="true" />
        <span>{{ t('action.viewDetail') }}</span>
      </button>
      <button
        type="button"
        role="menuitem"
        class="memory-context-menu__item"
        @click="run('copy')"
      >
        <ClipboardDocumentIcon class="h-4 w-4" aria-hidden="true" />
        <span>{{ isText ? t('action.copyContent') : t('action.copySummary') }}</span>
      </button>
      <button
        v-if="hasImage"
        type="button"
        role="menuitem"
        class="memory-context-menu__item"
        @click="run('copy-image')"
      >
        <PhotoIcon class="h-4 w-4" aria-hidden="true" />
        <span>{{ t('action.copyImage') }}</span>
      </button>

      <div class="memory-context-menu__divider" role="separator"></div>

      <button
        type="button"
        role="menuitem"
        class="memory-context-menu__item memory-context-menu__item--danger"
        @click="run('delete')"
      >
        <TrashIcon class="h-4 w-4" aria-hidden="true" />
        <span>{{ t('action.delete') }}</span>
      </button>
    </div>
  </Teleport>
</template>

<style scoped>
.memory-context-menu {
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
  animation: memory-context-menu-in 140ms ease-out;
}

.memory-context-menu--ready {
  visibility: visible;
}

.memory-context-menu__item {
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

.memory-context-menu__item > svg {
  flex: 0 0 auto;
}

.memory-context-menu__item:hover,
.memory-context-menu__item:focus-visible {
  background: var(--color-surface-hover);
  color: var(--color-text);
  box-shadow: none;
  outline: none;
}

.memory-context-menu__item--danger {
  color: var(--color-danger);
}

.memory-context-menu__item--danger:hover,
.memory-context-menu__item--danger:focus-visible {
  background: var(--color-danger-soft);
  color: var(--color-danger);
}

.memory-context-menu__divider {
  height: 1px;
  margin: 0.375rem -0.375rem;
  background: var(--color-border);
}

:global([data-theme='dark']) .memory-context-menu {
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.5);
}

@keyframes memory-context-menu-in {
  from {
    opacity: 0;
    transform: scale(0.97);
  }
}

@media (prefers-reduced-motion: reduce) {
  .memory-context-menu {
    animation: none;
  }
}
</style>
