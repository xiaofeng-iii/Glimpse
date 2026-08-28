<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { FunnelIcon as FunnelOutlineIcon, XMarkIcon } from '@heroicons/vue/24/outline'
import { FunnelIcon as FunnelSolidIcon } from '@heroicons/vue/24/solid'
import { t } from '@/utils/i18n'
import {
  cloneMemoryFilters,
  createEmptyMemoryFilters,
  hasActiveMemoryFilters,
  resolveMemoryDatePreset,
  type MemoryContentType,
  type MemoryDatePreset,
  type MemoryFilters,
} from '@/utils/memory-filters'

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
const draft = ref<MemoryFilters>(cloneMemoryFilters(props.modelValue))
const error = ref('')
const panelId = 'memory-filter-panel'

const presets: Array<{ value: MemoryDatePreset; label: Parameters<typeof t>[0] }> = [
  { value: 'today', label: 'filter.today' },
  { value: 'last7Days', label: 'filter.last7Days' },
  { value: 'last30Days', label: 'filter.last30Days' },
  { value: 'all', label: 'filter.allTime' },
  { value: 'custom', label: 'filter.custom' },
]

const contentTypeOptions: Array<{ value: MemoryContentType; label: Parameters<typeof t>[0] }> = [
  { value: 'screenshot', label: 'filter.screenshotMemory' },
  { value: 'text', label: 'filter.textMemory' },
]

const active = computed(() => hasActiveMemoryFilters(props.modelValue))

const close = (restoreFocus = false) => {
  open.value = false
  error.value = ''
  if (restoreFocus) void nextTick(() => trigger.value?.focus())
}

const show = () => {
  draft.value = cloneMemoryFilters(props.modelValue)
  error.value = ''
  open.value = true
}

const toggle = () => {
  if (open.value) close()
  else show()
}

const draftValidationError = () => {
  if (draft.value.datePreset === 'custom' && (!draft.value.dateFrom || !draft.value.dateTo)) {
    return 'filter.dateRequired' as const
  }
  if (draft.value.dateFrom && draft.value.dateTo && draft.value.dateFrom > draft.value.dateTo) {
    return 'filter.dateOrder' as const
  }
  return null
}

const emitDraft = () => {
  emit('apply', cloneMemoryFilters(draft.value))
}

const emitDraftIfValid = () => {
  error.value = ''
  if (draftValidationError()) return
  emitDraft()
}

const choosePreset = (preset: MemoryDatePreset) => {
  error.value = ''
  if (preset === 'custom') {
    draft.value = {
      ...draft.value,
      datePreset: preset,
    }
    emitDraftIfValid()
    return
  }
  draft.value = {
    ...draft.value,
    ...resolveMemoryDatePreset(preset),
  }
  emitDraft()
}

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
  emitDraftIfValid()
}

const apply = () => {
  const validationError = draftValidationError()
  if (validationError) {
    error.value = t(validationError)
    return
  }
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
      <FunnelSolidIcon v-if="active" class="memory-filters__trigger-icon" aria-hidden="true" />
      <FunnelOutlineIcon v-else class="memory-filters__trigger-icon" aria-hidden="true" />
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
            <div class="memory-filters__presets">
              <label v-for="preset in presets" :key="preset.value" class="memory-filters__preset-row">
                <input
                  :checked="draft.datePreset === preset.value"
                  :value="preset.value"
                  class="memory-filters__preset"
                  name="memory-date-preset"
                  type="radio"
                  @change="choosePreset(preset.value)"
                />
                <span class="memory-filters__preset-indicator" aria-hidden="true"></span>
                <span>{{ t(preset.label) }}</span>
              </label>
            </div>

            <div v-if="draft.datePreset === 'custom'" class="memory-filters__dates">
              <label>
                <span>{{ t('filter.dateFrom') }}</span>
                <input
                  v-model="draft.dateFrom"
                  type="date"
                  :aria-invalid="Boolean(error)"
                  @change="emitDraftIfValid"
                />
              </label>
              <span class="memory-filters__date-separator" aria-hidden="true">{{ t('filter.dateSeparator') }}</span>
              <label>
                <span>{{ t('filter.dateTo') }}</span>
                <input
                  v-model="draft.dateTo"
                  type="date"
                  :aria-invalid="Boolean(error)"
                  @change="emitDraftIfValid"
                />
              </label>
            </div>
            <p v-if="error" class="memory-filters__error" role="alert">{{ error }}</p>
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
  --memory-filter-option-height: 1.375rem;

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
  color: var(--color-primary);
  background: transparent;
  cursor: pointer;
  font-size: 0.8125rem;
  font-weight: 600;
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

.memory-filters__trigger--active .memory-filters__trigger-icon {
  color: var(--color-primary-hover);
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
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-lg);
  color: var(--color-text);
  background: var(--color-surface-subtle);
  box-shadow: var(--shadow-card);
}

.memory-filters__heading {
  display: flex;
  min-height: 3.75rem;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.75rem 1rem 0.75rem 1.25rem;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface-subtle);
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
  padding: 1rem 1.25rem 1.125rem;
  scrollbar-gutter: stable;
}

.memory-filters__group {
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}

.memory-filters__group + .memory-filters__group {
  margin-top: 1.125rem;
}

.memory-filters__group-label {
  display: block;
  margin: 0 0 0.5rem;
  padding: 0;
  color: var(--color-text-secondary);
  font-size: 0.8125rem;
  font-weight: 700;
  line-height: 1.25rem;
}

.memory-filters__presets {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.memory-filters__preset-row {
  position: relative;
  display: flex;
  min-height: var(--memory-filter-option-height);
  align-items: center;
  gap: 0.5rem;
  margin: 0 -0.375rem;
  padding: 0 0.375rem;
  border-radius: var(--radius-sm);
  color: var(--color-text);
  cursor: pointer;
  font-size: 0.875rem;
  line-height: var(--line-height-14);
}

.memory-filters__preset,
.memory-filters__content-type {
  position: absolute;
  width: 1rem;
  height: 1rem;
  margin: 0;
  opacity: 0;
  pointer-events: none;
}

.memory-filters__preset-indicator {
  display: inline-flex;
  width: 1rem;
  height: 1rem;
  flex: 0 0 1rem;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--color-border-strong);
  border-radius: 50%;
  background: transparent;
}

.memory-filters__preset:checked + .memory-filters__preset-indicator {
  border-color: var(--color-primary);
  background: var(--color-primary);
}

.memory-filters__preset:checked + .memory-filters__preset-indicator::after {
  content: '';
  width: 0.375rem;
  height: 0.375rem;
  border-radius: 50%;
  background: var(--color-on-primary);
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

.memory-filters__preset-row:has(
  .memory-filters__preset:focus-visible,
  .memory-filters__content-type:focus-visible
) {
  background: var(--color-primary-soft);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--color-focus) 26%, transparent);
}

.memory-filters__dates {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: end;
  gap: 0.5rem;
  margin-top: 0.75rem;
}

.memory-filters__dates label {
  display: grid;
  gap: 0.375rem;
  color: var(--color-text-muted);
  font-size: 0.6875rem;
}

.memory-filters__dates input {
  min-width: 0;
  height: 2.25rem;
  padding: 0 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text);
  background: var(--color-surface);
  font-size: 0.75rem;
  line-height: var(--line-height-12);
}

.memory-filters__dates input:focus-visible {
  border-color: var(--color-focus);
  outline: 2px solid color-mix(in srgb, var(--color-focus) 24%, transparent);
  outline-offset: 1px;
}

.memory-filters__date-separator {
  padding-bottom: 0.5rem;
  color: var(--color-text-muted);
  font-size: 0.625rem;
}

.memory-filters__error {
  margin: 0.625rem 0 0;
  color: var(--color-danger);
  font-size: 0.75rem;
  line-height: var(--line-height-12);
}

.memory-filters__actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.5rem;
  padding: 0.75rem 1.25rem;
  border-top: 1px solid var(--color-border);
  background: var(--color-surface-subtle);
}

.memory-filters__actions button {
  height: 2.25rem;
  min-height: 2.25rem;
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
  .memory-filters__trigger-label {
    transition: none;
  }
}
</style>
