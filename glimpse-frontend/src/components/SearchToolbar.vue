<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import {
  AdjustmentsHorizontalIcon,
  MagnifyingGlassIcon,
  QuestionMarkCircleIcon,
  ArrowPathIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline'
import type { SearchOptions } from '@/api/client'
import { useMemoriesStore } from '@/stores/memories'
import { t } from '@/utils/i18n'
import { requestOnboarding } from '@/utils/onboarding'
import AddMemoryButton from './AddMemoryButton.vue'
import CaptureButton from './CaptureButton.vue'

const props = withDefaults(defineProps<{
  modelValue?: string
  shortcutLabel?: string
  captureShortcutLabel?: string
  capturing?: boolean
  captureDisabled?: boolean
  addingMemory?: boolean
  addMemoryDisabled?: boolean
  refreshing?: boolean
}>(), {
  modelValue: '',
  shortcutLabel: 'Ctrl+F',
  captureShortcutLabel: 'Ctrl+Shift+G',
  capturing: false,
  captureDisabled: false,
  addingMemory: false,
  addMemoryDisabled: false,
  refreshing: false,
})

const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void
  (event: 'capture'): void
  (event: 'add-memory'): void
  (event: 'refresh'): void
  (event: 'debug-panel-change', open: boolean): void
}>()

const memoriesStore = useMemoriesStore()
const query = ref(props.modelValue)
const source = ref(memoriesStore.searchSource || 'all')
const searchInput = ref<HTMLInputElement | null>(null)
const debugPanelElement = ref<HTMLDetailsElement | null>(null)
const debugPanelOpen = ref(false)
const isDev = import.meta.env.DEV
const devOptions = ref({
  limit: memoriesStore.searchOptions.limit ?? 20,
  semanticThreshold: memoriesStore.searchOptions.semanticThreshold ?? 1.15,
  candidateMultiplier: memoriesStore.searchOptions.candidateMultiplier ?? 2,
  rrfK: memoriesStore.searchOptions.rrfK ?? 60,
  debug: memoriesStore.searchOptions.debug ?? true,
})

const sources = [
  { value: 'all', labelKey: 'search.all' },
  { value: 'exact', labelKey: 'search.exactOnly' },
  { value: 'semantic', labelKey: 'search.semanticOnly' },
] as const

let debounceTimer: ReturnType<typeof window.setTimeout> | null = null
let composing = false
let clearImmediately = false

const clampNumber = (value: unknown, fallback: number, minimum: number, maximum: number) => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return fallback
  return Math.min(maximum, Math.max(minimum, value))
}

const currentOptions = (): SearchOptions => {
  if (!isDev) return {}
  return {
    limit: clampNumber(devOptions.value.limit, 20, 1, 100),
    semanticThreshold: clampNumber(devOptions.value.semanticThreshold, 1.15, 0, 4),
    candidateMultiplier: clampNumber(devOptions.value.candidateMultiplier, 2, 1, 10),
    rrfK: clampNumber(devOptions.value.rrfK, 60, 1, 200),
    debug: devOptions.value.debug,
  }
}

const executeSearch = () => {
  const normalized = query.value.trim()
  if (normalized) {
    void memoriesStore.search(normalized, source.value, currentOptions())
  } else {
    void memoriesStore.load()
  }
}

const scheduleSearch = () => {
  memoriesStore.invalidatePendingRequests()
  if (debounceTimer) window.clearTimeout(debounceTimer)
  debounceTimer = window.setTimeout(executeSearch, 300)
}

const cancelScheduledSearch = () => {
  memoriesStore.invalidatePendingRequests()
  if (debounceTimer) {
    window.clearTimeout(debounceTimer)
    debounceTimer = null
  }
}

const handleDebugToggle = (event: Event) => {
  const open = (event.currentTarget as HTMLDetailsElement).open
  if (debugPanelOpen.value === open) return
  debugPanelOpen.value = open
  emit('debug-panel-change', open)
}

const handleShowOnboarding = () => {
  debugPanelOpen.value = false
  if (debugPanelElement.value) debugPanelElement.value.open = false
  emit('debug-panel-change', false)
  requestOnboarding()
}

watch(
  () => props.modelValue,
  (value) => {
    if (value !== query.value) query.value = value
  },
)

watch(query, (value) => {
  emit('update:modelValue', value)
  if (clearImmediately) {
    clearImmediately = false
    cancelScheduledSearch()
    void memoriesStore.load()
    return
  }
  if (composing) {
    cancelScheduledSearch()
    return
  }
  scheduleSearch()
})

watch(source, () => {
  if (query.value.trim()) scheduleSearch()
})

if (isDev) {
  watch(devOptions, () => {
    if (query.value.trim()) scheduleSearch()
  }, { deep: true })
}

const clear = () => {
  if (debounceTimer) {
    window.clearTimeout(debounceTimer)
    debounceTimer = null
  }
  if (query.value) clearImmediately = true
  query.value = ''
  searchInput.value?.focus()
}

const handleCompositionStart = () => {
  composing = true
  cancelScheduledSearch()
}

const handleCompositionEnd = () => {
  composing = false
  scheduleSearch()
}

const focus = () => {
  searchInput.value?.focus()
  searchInput.value?.select()
}

onBeforeUnmount(() => {
  if (debounceTimer) window.clearTimeout(debounceTimer)
  if (debugPanelOpen.value) emit('debug-panel-change', false)
})

defineExpose({ focus, clear })
</script>

<template>
  <section class="search-toolbar">
    <div class="search-toolbar__surface">
      <div class="search-toolbar__layout">
        <div class="search-toolbar__input relative min-w-0">
          <MagnifyingGlassIcon
            class="pointer-events-none absolute left-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-[var(--shell-muted)]"
            aria-hidden="true"
          />
          <input
            ref="searchInput"
            v-model="query"
            type="search"
            class="search-toolbar__control h-9 w-full border border-[var(--shell-line)] bg-[var(--shell-control-bg)] pl-11 pr-24 text-sm text-[var(--shell-ink)] outline-none transition placeholder:text-[var(--shell-muted)] [&::-webkit-search-cancel-button]:appearance-none [&::-webkit-search-cancel-button]:hidden [&::-webkit-search-cancel-button]:[display:none]"
            :placeholder="t('search.placeholder')"
            @keydown.esc.stop.prevent="clear"
            @compositionstart="handleCompositionStart"
            @compositionend="handleCompositionEnd"
          />
          <div class="absolute right-3 top-1/2 flex -translate-y-1/2 items-center gap-2">
            <button
              v-if="query"
              type="button"
              class="search-toolbar__detail-control flex h-[22px] min-h-0 w-[22px] flex-none items-center justify-center text-[var(--shell-muted)] transition hover:bg-[var(--shell-control-hover)]"
              :aria-label="t('search.clear')"
              @click="clear"
            >
              <XMarkIcon class="h-3 w-3" aria-hidden="true" />
            </button>
            <kbd class="search-toolbar__detail-control border border-[var(--shell-line)] px-1.5 py-0.5 text-xs text-[var(--shell-muted)]">
              {{ shortcutLabel }}
            </kbd>
          </div>
        </div>

        <div
          class="search-toolbar__control search-toolbar__source-switcher inline-grid h-9 grid-flow-col auto-cols-fr items-center border border-[var(--shell-line)] bg-[var(--shell-control-bg)]"
          role="group"
          :aria-label="t('search.sourceLabel')"
        >
          <button
            v-for="item in sources"
            :key="item.value"
            type="button"
            class="search-toolbar__source-button h-7 min-h-0 px-3 text-sm font-medium transition"
            :class="source === item.value
              ? 'bg-[var(--color-primary)] text-white shadow-sm'
              : 'text-[var(--shell-ink)] hover:bg-[var(--shell-control-hover)]'"
            :aria-pressed="source === item.value"
            @click="source = item.value"
          >
            {{ t(item.labelKey) }}
          </button>
        </div>

        <div class="search-toolbar__actions flex shrink-0 items-center gap-2.5">
          <button
            type="button"
            class="search-toolbar__control inline-flex h-9 min-h-0 w-9 items-center justify-center border border-[var(--shell-line)] bg-[var(--shell-control-bg)] text-[var(--shell-muted)] transition hover:bg-[var(--shell-control-hover)] disabled:opacity-50"
            :aria-label="t('action.refresh')"
            :disabled="refreshing"
            @click="emit('refresh')"
          >
            <ArrowPathIcon class="h-5 w-5" :class="{ 'animate-spin': refreshing }" aria-hidden="true" />
          </button>

        <details
          ref="debugPanelElement"
          v-if="isDev"
          class="relative"
          :open="debugPanelOpen"
          @toggle="handleDebugToggle"
        >
          <summary
            class="search-toolbar__control flex h-9 cursor-pointer list-none items-center gap-1.5 border border-amber-200/80 bg-amber-50/75 px-3 text-amber-800 transition hover:bg-amber-100"
            :aria-label="t('search.debugTitle')"
          >
            <AdjustmentsHorizontalIcon class="h-4 w-4 flex-none" aria-hidden="true" />
            <span class="text-[10px] font-bold tracking-wide">DEV</span>
          </summary>
          <div
            class="search-toolbar__debug-panel absolute right-0 top-[calc(100%+.5rem)] w-[min(440px,calc(100vw-2.5rem))] rounded-lg border border-amber-200/80 bg-[var(--shell-card)] p-4 text-left shadow-2xl"
          >
            <div class="flex items-start gap-2 text-xs text-amber-800">
              <AdjustmentsHorizontalIcon class="mt-0.5 h-4 w-4 flex-none" aria-hidden="true" />
              <div>
                <p class="font-semibold">{{ t('search.debugTitle') }}</p>
                <p class="mt-0.5 text-[var(--shell-muted)]">{{ t('search.debugHint') }}</p>
              </div>
            </div>
            <div class="mt-3 grid grid-cols-2 gap-3">
              <label v-for="field in [
                { key: 'limit', label: t('search.resultLimit'), min: 1, max: 100, step: 1 },
                { key: 'semanticThreshold', label: t('search.semanticThreshold'), min: 0, max: 4, step: .05 },
                { key: 'candidateMultiplier', label: t('search.candidateMultiplier'), min: 1, max: 10, step: 1 },
                { key: 'rrfK', label: t('search.rrfK'), min: 1, max: 200, step: 1 },
              ]" :key="field.key" class="text-xs text-[var(--shell-muted)]">
                <span class="mb-1 block">{{ field.label }}</span>
                <input
                  v-model.number="devOptions[field.key as keyof typeof devOptions]"
                  type="number"
                  :min="field.min"
                  :max="field.max"
                  :step="field.step"
                  class="w-full rounded-md border border-[var(--shell-line)] bg-[var(--shell-control-bg)] px-2 py-1.5 text-sm text-[var(--shell-ink)] outline-none focus:border-amber-400"
                />
              </label>
            </div>
            <label class="mt-3 flex cursor-pointer items-center gap-2 text-xs text-amber-800">
              <input v-model="devOptions.debug" type="checkbox" class="h-4 w-4 accent-amber-600" />
              {{ t('search.showScores') }}
            </label>
            <button
              data-testid="show-onboarding"
              type="button"
              class="mt-4 inline-flex min-h-9 w-full items-center justify-center gap-2 rounded-md border border-amber-300/80 bg-amber-50 px-3 text-xs font-semibold text-amber-800 transition hover:bg-amber-100"
              @click="handleShowOnboarding"
            >
              <QuestionMarkCircleIcon class="h-4 w-4" aria-hidden="true" />
              {{ t('search.showOnboarding') }}
            </button>
          </div>
        </details>

        <CaptureButton
          class="search-toolbar__capture"
          :capturing="capturing"
          :disabled="captureDisabled"
          :shortcut-label="captureShortcutLabel"
          density="toolbar"
          show-shortcut
          @capture="emit('capture')"
        />
        <AddMemoryButton
          class="search-toolbar__add-memory"
          :busy="addingMemory"
          :disabled="addMemoryDisabled"
          density="toolbar"
          @add="emit('add-memory')"
        />
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.search-toolbar {
  --search-toolbar-surface-radius: var(--radius-xl);
  --search-toolbar-surface-inset: 0.75rem;
  --search-toolbar-control-radius: var(--radius-sm);
  --search-toolbar-segment-inset: 3px;
  --search-toolbar-segment-radius: max(
    1px,
    calc(var(--search-toolbar-control-radius) - var(--search-toolbar-segment-inset))
  );
  --search-toolbar-detail-radius: var(--search-toolbar-control-radius);
  --search-toolbar-surface-shadow:
    0 1px 2px rgba(26, 38, 64, 0.04),
    0 2px 6px rgba(26, 38, 64, 0.035);

  position: sticky;
  z-index: var(--z-sticky);
  top: 0;
  isolation: isolate;
  padding: 0.625rem 1.25rem 0.5rem;
  background: transparent;
}

.search-toolbar::before {
  position: absolute;
  z-index: 0;
  inset: 0 0 -0.75rem;
  pointer-events: none;
  background: linear-gradient(
    to bottom,
    color-mix(in srgb, var(--shell-window-bg) 78%, transparent) 0%,
    color-mix(in srgb, var(--shell-window-bg) 28%, transparent) 62%,
    transparent 100%
  );
  content: '';
}

.search-toolbar::after {
  position: absolute;
  z-index: 0;
  inset: 0 0 -0.75rem;
  pointer-events: none;
  background: color-mix(in srgb, var(--shell-window-bg) 1%, transparent);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  mask-image: linear-gradient(to bottom, #000 0%, rgb(0 0 0 / 72%) 46%, transparent 100%);
  -webkit-mask-image: linear-gradient(to bottom, #000 0%, rgb(0 0 0 / 72%) 46%, transparent 100%);
  content: '';
}

.search-toolbar__surface {
  position: relative;
  z-index: 1;
  padding: var(--search-toolbar-surface-inset);
  border: 1px solid var(--shell-card-border);
  border-radius: var(--search-toolbar-surface-radius);
  background: var(--shell-card);
  box-shadow: var(--search-toolbar-surface-shadow);
}

.search-toolbar__layout {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) 13.5rem auto;
  align-items: center;
  gap: 0.625rem;
}

.search-toolbar__source-switcher {
  width: 13.5rem;
  gap: var(--search-toolbar-segment-inset);
  padding: var(--search-toolbar-segment-inset);
}

.search-toolbar__control,
.search-toolbar__capture,
.search-toolbar__add-memory {
  border-radius: var(--search-toolbar-control-radius);
}

.search-toolbar__source-button {
  border-radius: var(--search-toolbar-segment-radius);
}

.search-toolbar__detail-control {
  border-radius: var(--search-toolbar-detail-radius);
}

.search-toolbar__actions {
  padding-left: 0.75rem;
  border-left: 1px solid var(--shell-line);
}

.search-toolbar__debug-panel {
  z-index: var(--z-popover);
}

:global(:root[data-theme='dark']) .search-toolbar {
  --search-toolbar-surface-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
}


@container memory-pane (max-width: 960px) {
  .search-toolbar {
    padding-inline: 1rem;
  }

  .search-toolbar__layout {
    grid-template-columns: minmax(0, 1fr) auto;
  }

  .search-toolbar__input {
    grid-column: 1 / -1;
  }

  .search-toolbar__source-switcher {
    grid-column: 1;
    width: 12rem;
  }

  .search-toolbar__actions {
    grid-column: 2;
    grid-row: 2;
    justify-self: end;
    padding-left: 0.625rem;
  }
}

@container memory-pane (max-width: 640px) {
  .search-toolbar {
    padding-inline: 0.75rem;
  }

  .search-toolbar__layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .search-toolbar__source-switcher {
    grid-column: 1;
    width: 100%;
  }

  .search-toolbar__actions {
    grid-column: 1;
    grid-row: 3;
    justify-self: end;
    padding-left: 0;
    border-left: 0;
  }
}
</style>
