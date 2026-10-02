<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, onUnmounted, ref, watch } from 'vue'
import { CalendarDaysIcon, ChevronDownIcon, FunnelIcon as FunnelOutlineIcon, XMarkIcon } from '@heroicons/vue/24/outline'
import { languagePreference, t } from '@/utils/i18n'
import { describeMemoryPeriod, describeMemoryPeriodParts } from '@/utils/memory-grouping'
import {
  cloneMemoryFilters,
  createEmptyMemoryFilters,
  hasActiveMemoryFilters,
  type MemoryContentType,
  type MemoryFilters,
} from '@/utils/memory-filters'
import MemoryCalendarPicker from './MemoryCalendarPicker.vue'

const props = defineProps<{
  modelValue: MemoryFilters
  loading?: boolean
  compact?: boolean
}>()

const emit = defineEmits<{
  (event: 'apply', filters: MemoryFilters): void
}>()

const root = ref<HTMLElement | null>(null)
const trigger = ref<HTMLButtonElement | null>(null)
const open = ref(false)
const calendarOpen = ref(false)
const draft = ref<MemoryFilters>(cloneMemoryFilters(props.modelValue))
const panelId = 'memory-filter-panel'
const calendarId = `${panelId}-calendar`
const calendarReveal = ref<HTMLElement | null>(null)
const calendarMounted = ref(false)
const calendarHeight = ref(0)
let calendarResizeObserver: ResizeObserver | null = null
let cancelCalendarCollapse: (() => void) | null = null
let calendarAnimation = 0
const dateLabel = computed(() => draft.value.dateFrom || draft.value.dateTo
  ? describeMemoryPeriod(draft.value.dateFrom, draft.value.dateTo, languagePreference.value)
  : t('filter.anyTime'))
const dateParts = computed(() => describeMemoryPeriodParts(
  draft.value.dateFrom,
  draft.value.dateTo,
  languagePreference.value,
))

const contentTypeOptions: Array<{ value: MemoryContentType; label: Parameters<typeof t>[0] }> = [
  { value: 'screenshot', label: 'filter.screenshotMemory' },
  { value: 'text', label: 'filter.textMemory' },
]

const active = computed(() => hasActiveMemoryFilters(props.modelValue))

const close = (restoreFocus = false) => {
  open.value = false
  if (restoreFocus) void nextTick(() => trigger.value?.focus())
}

const show = () => {
  draft.value = cloneMemoryFilters(props.modelValue)
  calendarOpen.value = false
  open.value = true
}

const toggle = () => {
  if (open.value) close()
  else show()
}

const emitDraft = () => {
  emit('apply', cloneMemoryFilters(draft.value))
}

// 日历选中的时段实时生效：写回草稿并向上抛出
const applyCalendar = (next: MemoryFilters) => {
  draft.value = next
  emitDraft()
}

const stopCalendarObservation = () => {
  calendarResizeObserver?.disconnect()
  calendarResizeObserver = null
}

const cancelCalendarAnimation = () => {
  cancelCalendarCollapse?.()
  cancelCalendarCollapse = null
}

// 展开收起由 watch 驱动而非 Vue Transition：收起完成前保持日历挂载，
// 动画结束后才真正卸载，避免过渡被打断时节点残留或高度卡在中间值
watch(calendarOpen, (isOpen) => {
  const token = ++calendarAnimation
  if (isOpen) {
    cancelCalendarAnimation()
    calendarMounted.value = true
    void nextTick(() => {
      if (token !== calendarAnimation) return
      const picker = calendarReveal.value?.firstElementChild as HTMLElement | null
      calendarHeight.value = picker?.offsetHeight ?? 0
      if (!picker || !('ResizeObserver' in window)) return
      stopCalendarObservation()
      calendarResizeObserver = new ResizeObserver((entries) => {
        const target = entries[0]?.target as HTMLElement | undefined
        calendarHeight.value = target?.offsetHeight ?? calendarHeight.value
      })
      calendarResizeObserver.observe(picker)
    })
    return
  }

  stopCalendarObservation()
  const wrapper = calendarReveal.value
  const startHeight = wrapper?.offsetHeight ?? 0
  if (!wrapper || startHeight < 1 || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    calendarHeight.value = 0
    calendarMounted.value = false
    return
  }
  calendarHeight.value = startHeight
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (token !== calendarAnimation) return
    calendarHeight.value = 0
    const finish = (event: TransitionEvent) => {
      if (event.target !== wrapper || event.propertyName !== 'height') return
      calendarMounted.value = false
    }
    wrapper.addEventListener('transitionend', finish)
    const fallback = window.setTimeout(() => { calendarMounted.value = false }, 260)
    cancelCalendarCollapse = () => {
      wrapper.removeEventListener('transitionend', finish)
      window.clearTimeout(fallback)
      cancelCalendarCollapse = null
    }
  }))
})

onBeforeUnmount(() => {
  cancelCalendarAnimation()
  stopCalendarObservation()
})

const toggleContentType = (contentType: MemoryContentType) => {
  const selected = new Set(draft.value.contentTypes)
  if (selected.has(contentType)) selected.delete(contentType)
  else selected.add(contentType)

  draft.value = {
    ...draft.value,
    contentTypes: contentTypeOptions
      .map((option) => option.value)
      .filter((value) => selected.has(value)),
  }
  emitDraft()
}

const apply = () => {
  emitDraft()
  close(true)
}

const clear = () => {
  emit('apply', createEmptyMemoryFilters())
  close(true)
}

const handlePointerDown = (event: MouseEvent) => {
  if (open.value && !root.value?.contains(event.target as Node)) close()
}

const handleKeydown = (event: KeyboardEvent) => {
  if (open.value && event.key === 'Escape') {
    event.preventDefault()
    close(true)
  }
}

const handleScroll = (event: Event) => {
  if (open.value && !root.value?.contains(event.target as Node)) close()
}

onMounted(() => {
  document.addEventListener('mousedown', handlePointerDown)
  document.addEventListener('keydown', handleKeydown)
  document.addEventListener('scroll', handleScroll, true)
})

onUnmounted(() => {
  document.removeEventListener('mousedown', handlePointerDown)
  document.removeEventListener('keydown', handleKeydown)
  document.removeEventListener('scroll', handleScroll, true)
})
</script>

<template>
  <div
    ref="root"
    class="memory-filters relative"
    :class="{ 'memory-filters--compact': compact }"
  >
    <button
      ref="trigger"
      type="button"
      class="memory-filters__trigger"
      :class="{ 'memory-filters__trigger--active': active }"
      :aria-expanded="open"
      :aria-controls="panelId"
      :aria-label="t('filter.open')"
      :disabled="loading"
      @click="toggle"
    >
      <FunnelOutlineIcon class="memory-filters__trigger-icon" aria-hidden="true" />
      <span class="memory-filters__trigger-label">{{ t('filter.open') }}</span>
      <span v-if="active" class="sr-only">{{ t('filter.active') }}</span>
    </button>

    <Transition name="filter-popover">
      <div
        v-if="open"
        :id="panelId"
        class="memory-filters__panel"
        role="dialog"
        aria-modal="false"
        :aria-label="t('filter.title')"
      >
        <div class="memory-filters__heading">
          <h2>{{ t('filter.open') }}</h2>
          <button
            type="button"
            class="memory-filters__close"
            :aria-label="t('action.close')"
            @click="close(true)"
          >
            <XMarkIcon class="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        <div class="memory-filters__body">
          <fieldset class="memory-filters__group">
            <legend class="memory-filters__group-label">{{ t('filter.timeRange') }}</legend>
            <button
              type="button"
              class="memory-filters__date-toggle"
              :class="{ 'memory-filters__date-toggle--active': draft.dateFrom || draft.dateTo }"
              :aria-expanded="calendarOpen"
              :aria-controls="calendarId"
              :title="dateLabel"
              @click="calendarOpen = !calendarOpen"
            >
              <CalendarDaysIcon class="h-4 w-4 shrink-0" aria-hidden="true" />
              <span class="memory-filters__date-text" :title="dateLabel">
                <template v-if="draft.dateFrom || draft.dateTo">
                  <span class="memory-filters__date-seg">{{ dateParts.head }}</span><span v-if="dateParts.tail" class="memory-filters__date-seg memory-filters__date-seg--tail">{{ ` ${dateParts.tail}` }}</span>
                </template>
                <template v-else>{{ dateLabel }}</template>
              </span>
              <ChevronDownIcon
                class="memory-filters__date-chevron h-4 w-4 shrink-0"
                :class="{ 'memory-filters__date-chevron--open': calendarOpen }"
                aria-hidden="true"
              />
            </button>
            <div
              :id="calendarId"
              ref="calendarReveal"
              class="memory-filters__calendar-reveal"
              :style="{ height: `${calendarHeight}px` }"
            >
              <MemoryCalendarPicker v-if="calendarMounted" class="memory-filters__calendar" :filters="draft" @apply="applyCalendar" />
            </div>
          </fieldset>

          <fieldset class="memory-filters__group">
            <legend class="memory-filters__group-label">{{ t('filter.contentType') }}</legend>
            <div class="memory-filters__presets">
              <label
                v-for="contentType in contentTypeOptions"
                :key="contentType.value"
                class="memory-filters__preset-row"
              >
                <input
                  :checked="draft.contentTypes.includes(contentType.value)"
                  :value="contentType.value"
                  class="memory-filters__content-type"
                  type="checkbox"
                  @change="toggleContentType(contentType.value)"
                />
                <span class="memory-filters__checkbox-indicator" aria-hidden="true"></span>
                <span>{{ t(contentType.label) }}</span>
              </label>
            </div>
          </fieldset>
        </div>

        <div class="memory-filters__actions">
          <button type="button" class="btn-primary" @click="apply">
            {{ t('filter.apply') }}
          </button>
          <button type="button" class="btn-secondary" @click="clear">
            {{ t('filter.clear') }}
          </button>
        </div>
      </div>
    </Transition>

  </div>
</template>

<style scoped>
.memory-filters {
  --memory-filter-panel-width: 18.125rem;
  --memory-filter-option-height: 2rem;

  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.memory-filters__trigger {
  display: inline-flex;
  height: 2rem;
  min-height: 0;
  align-items: center;
  gap: 0.35rem;
  padding: 0 0.55rem;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  color: var(--shell-ink);
  background: transparent;
  cursor: pointer;
  font-size: 0.8125rem;
  font-weight: 400;
  transition:
    gap 160ms ease,
    padding 160ms ease,
    color 160ms ease,
    background-color 160ms ease,
    border-color 160ms ease,
    box-shadow 160ms ease;
}

.memory-filters__trigger-label {
  display: inline-block;
  max-width: 4rem;
  flex: 0 1 auto;
  overflow: hidden;
  opacity: 1;
  white-space: nowrap;
  transform: translateX(0);
  transition: max-width 160ms ease, opacity 120ms ease, transform 160ms ease;
}

.memory-filters--compact .memory-filters__trigger {
  gap: 0;
  padding-inline: 0.5rem;
  border-color: color-mix(in srgb, var(--shell-line) 70%, transparent);
  background: color-mix(in srgb, var(--shell-window-bg) 70%, transparent);
  box-shadow: var(--shadow-card);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

.memory-filters--compact .memory-filters__trigger-label {
  max-width: 0;
  opacity: 0;
  transform: translateX(0.25rem);
}

.memory-filters__trigger:hover {
  border-color: color-mix(in srgb, var(--color-primary) 20%, transparent);
  background: var(--color-primary-soft);
}

.memory-filters--compact .memory-filters__trigger:hover {
  border-color: color-mix(in srgb, var(--color-primary) 24%, transparent);
  background: color-mix(in srgb, var(--shell-window-bg) 70%, transparent);
}

.memory-filters__trigger-icon {
  width: 0.9375rem;
  height: 0.9375rem;
  flex: 0 0 0.9375rem;
}

.memory-filters__trigger--active {
  color: var(--color-primary);
  font-weight: 600;
}

.memory-filters__trigger:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.memory-filters__panel {
  position: absolute;
  z-index: var(--z-popover);
  top: calc(100% + 0.5rem);
  right: 0;
  display: flex;
  width: min(var(--memory-filter-panel-width), calc(100vw - 2.5rem));
  max-height: min(35rem, calc(100vh - 12rem));
  flex-direction: column;
  overflow: hidden;
  border-radius: var(--radius-xl);
  color: var(--color-text);
  background: var(--color-surface-raised);
  /* 浮层用分层中性投影（含 1px 描边环）承担边界与高度，替代实线边框和卡片级弱阴影 */
  box-shadow:
    0 0 0 1px rgba(0, 0, 0, 0.05),
    0 1px 1px -0.5px rgba(0, 0, 0, 0.06),
    0 3px 3px -1.5px rgba(0, 0, 0, 0.06),
    0 6px 6px -3px rgba(0, 0, 0, 0.06),
    0 12px 12px -6px rgba(0, 0, 0, 0.06),
    0 24px 24px -12px rgba(0, 0, 0, 0.06);
}

:global(:root[data-theme='dark']) .memory-filters__panel {
  box-shadow:
    0 0 0 1px rgba(226, 232, 240, 0.09),
    0 2px 4px rgba(0, 0, 0, 0.3),
    0 8px 16px rgba(0, 0, 0, 0.28),
    0 16px 40px rgba(0, 0, 0, 0.4);
}

.memory-filters__heading {
  display: flex;
  min-height: 2.75rem;
  flex-shrink: 0;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.375rem 0.5rem 0.125rem 0.875rem;
}

.memory-filters__heading h2 {
  margin: 0;
  color: var(--color-text);
  font-size: 1rem;
  font-weight: 700;
  letter-spacing: -0.01em;
  line-height: var(--line-height-16);
}

.memory-filters__close {
  display: inline-flex;
  width: 2rem;
  height: 2rem;
  min-height: 0;
  align-items: center;
  justify-content: center;
  flex: 0 0 2rem;
  padding: 0;
  border: 0;
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  background: transparent;
  cursor: pointer;
}

.memory-filters__close:hover {
  color: var(--color-text);
  background: var(--color-surface-hover);
}

.memory-filters__close:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}

.memory-filters__body {
  min-height: 0;
  overflow-y: auto;
  padding: 0.25rem 0.875rem 0.75rem;
  /* 内容超高出现滚动条时预留槽位，日历多一行也不会压缩内容宽度 */
  scrollbar-gutter: stable;
}

.memory-filters__group {
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}

.memory-filters__group + .memory-filters__group {
  margin-top: 0.75rem;
}

.memory-filters__group-label {
  display: block;
  margin: 0 0 0.25rem;
  padding: 0;
  color: var(--color-text-secondary);
  font-size: 0.8125rem;
  font-weight: 700;
  line-height: 1.25rem;
}

.memory-filters__date-toggle {
  display: flex;
  width: 100%;
  min-height: 2rem;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.375rem;
  border: 0;
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  background: var(--color-surface-subtle);
  cursor: pointer;
  text-align: left;
  font-size: 0.8125rem;
  line-height: 1.25rem;
}

.memory-filters__date-text {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  font-variant-numeric: tabular-nums;
}

.memory-filters__date-seg {
  white-space: nowrap;
}

.memory-filters__date-seg--tail {
  display: inline-block;
}

.memory-filters__date-toggle--active {
  color: var(--color-primary-hover);
  background: var(--color-primary-soft);
}

.memory-filters__date-toggle:hover {
  background: var(--color-surface-hover);
}

.memory-filters__date-toggle:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}

.memory-filters__date-chevron--open {
  transform: rotate(180deg);
}

.memory-filters__calendar-reveal {
  overflow: hidden;
  transition: height 180ms cubic-bezier(0.32, 0.72, 0, 1);
}

.memory-filters__calendar-reveal > * {
  min-height: 0;
  overflow: hidden;
}

.memory-filters__calendar {
  padding-top: 0.5rem;
}

.memory-filters__calendar :deep(.memory-calendar__block) {
  padding: 0.5rem;
  border: 0;
  background: var(--color-surface-subtle);
}

.memory-filters__calendar :deep(.memory-calendar__nav) {
  margin-bottom: 0.25rem;
}

.memory-filters__presets {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.5rem;
}

.memory-filters__preset-row {
  position: relative;
  display: flex;
  min-height: var(--memory-filter-option-height);
  align-items: center;
  gap: 0.5rem;
  margin: 0;
  padding: 0 0.5rem;
  border-radius: var(--radius-sm);
  color: var(--color-text);
  cursor: pointer;
  font-size: 0.875rem;
  line-height: var(--line-height-14);
  transition: background-color 120ms ease;
}

.memory-filters__preset-row:hover {
  background: var(--color-surface-subtle);
}

.memory-filters__content-type {
  position: absolute;
  width: 1rem;
  height: 1rem;
  margin: 0;
  opacity: 0;
  pointer-events: none;
}

.memory-filters__checkbox-indicator {
  display: inline-flex;
  width: 1rem;
  height: 1rem;
  flex: 0 0 1rem;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--color-border-strong);
  border-radius: 0.1875rem;
  background: transparent;
}

.memory-filters__content-type:checked + .memory-filters__checkbox-indicator {
  border-color: var(--color-primary);
  background: var(--color-primary);
}

.memory-filters__content-type:checked + .memory-filters__checkbox-indicator::after {
  content: '';
  width: 0.4375rem;
  height: 0.25rem;
  border-bottom: 2px solid var(--color-on-primary);
  border-left: 2px solid var(--color-on-primary);
  transform: translateY(-0.0625rem) rotate(-45deg);
}

.memory-filters__preset-row:has(.memory-filters__content-type:focus-visible) {
  background: var(--color-primary-soft);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--color-focus) 26%, transparent);
}

.memory-filters__actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.5rem;
  padding: 0 0.875rem 0.75rem;
  flex-shrink: 0;
}

.memory-filters__actions button {
  height: 2rem;
  min-height: 2rem;
  padding: 0 0.75rem;
  border-radius: var(--radius-sm);
  font-size: 0.8125rem;
}

.memory-filters__actions .btn-primary {
  box-shadow: none;
}

.memory-filters__actions .btn-secondary {
  border-color: transparent;
  background: var(--color-surface-hover);
}

.memory-filters__actions .btn-secondary:hover {
  border-color: var(--color-border);
  background: color-mix(in srgb, var(--color-surface-hover) 82%, var(--color-border));
}

.filter-popover-enter-active,
.filter-popover-leave-active {
  transition: opacity 140ms ease, transform 140ms ease;
}

.filter-popover-enter-from,
.filter-popover-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

@media (max-width: 520px) {
  .memory-filters__panel {
    position: fixed;
    top: 4.5rem;
    right: 0.75rem;
    left: 0.75rem;
    width: auto;
    max-height: calc(100vh - 5.25rem);
  }
}

@media (prefers-reduced-motion: reduce) {
  .memory-filters__trigger,
  .memory-filters__trigger-label,
  .memory-filters__preset-row,
  .memory-filters__calendar-reveal,
  .filter-popover-enter-active,
  .filter-popover-leave-active {
    transition: none;
  }
}
</style>
