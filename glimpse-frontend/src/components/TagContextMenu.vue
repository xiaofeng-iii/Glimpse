<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { TrashIcon } from '@heroicons/vue/24/outline'
import { t } from '@/utils/i18n'

const props = defineProps<{
  tagName: string | null
  x: number
  y: number
}>()

const emit = defineEmits<{
  (event: 'close'): void
  (event: 'delete', name: string): void
}>()

const menuElement = ref<HTMLElement | null>(null)
const current = ref<string | null>(null)
const ready = ref(false)
const position = ref({ x: 0, y: 0 })

const close = () => {
  if (!current.value) return
  current.value = null
  unbindListeners()
  emit('close')
}

const runDelete = () => {
  const name = current.value
  if (!name) return
  emit('delete', name)
  close()
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
  if (event.key !== 'Escape' && event.key !== 'Tab') return
  event.preventDefault()
  if (event.key === 'Escape') event.stopPropagation()
  close()
}

const handleViewportChange = () => close()

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
  () => props.tagName,
  async (tagName) => {
    if (!tagName) return
    current.value = tagName
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
    menuElement.value?.querySelector<HTMLElement>('[role="menuitem"]')?.focus()
  },
)

onBeforeUnmount(unbindListeners)
</script>

<template>
  <Teleport to="body">
    <div
      v-if="current"
      ref="menuElement"
      class="tag-context-menu"
      :class="{ 'tag-context-menu--ready': ready }"
      :style="{ left: `${position.x}px`, top: `${position.y}px` }"
      role="menu"
      :aria-label="t('tags.contextMenu')"
      tabindex="-1"
      @contextmenu.prevent
    >
      <button
        type="button"
        role="menuitem"
        class="tag-context-menu__item tag-context-menu__item--danger"
        @click="runDelete"
      >
        <TrashIcon class="h-4 w-4" aria-hidden="true" />
        <span>{{ t('tags.deleteTag') }}</span>
      </button>
    </div>
  </Teleport>
</template>

<style scoped>
.tag-context-menu {
  position: fixed;
  z-index: var(--z-toast);
  min-width: 10rem;
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
  animation: tag-context-menu-in 140ms ease-out;
}

.tag-context-menu--ready {
  visibility: visible;
}

.tag-context-menu__item {
  display: flex;
  width: 100%;
  min-height: var(--control-h-sm);
  align-items: center;
  gap: 0.5rem;
  padding: 0 0.625rem;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  cursor: pointer;
  font-size: 0.875rem;
  line-height: var(--line-height-14);
  text-align: left;
  transition: background-color 160ms ease, color 160ms ease;
}

.tag-context-menu__item > svg {
  flex: 0 0 auto;
}

.tag-context-menu__item--danger {
  color: var(--color-danger);
}

.tag-context-menu__item--danger:hover,
.tag-context-menu__item--danger:focus-visible {
  background: var(--color-danger-soft);
  color: var(--color-danger);
  box-shadow: none;
  outline: none;
}

:root[data-theme='dark'] .tag-context-menu {
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.5);
}

@keyframes tag-context-menu-in {
  from {
    opacity: 0;
    transform: scale(0.97);
  }
}

@media (prefers-reduced-motion: reduce) {
  .tag-context-menu {
    animation: none;
  }
}
</style>
