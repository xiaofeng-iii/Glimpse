<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import {
  AdjustmentsHorizontalIcon,
  CameraIcon,
  MagnifyingGlassIcon,
  QuestionMarkCircleIcon,
  ArrowPathIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline'
import type { SearchOptions } from '@/api/client'
import { useMemoriesStore } from '@/stores/memories'
import { t } from '@/utils/i18n'
import { requestOnboarding } from '@/utils/onboarding'

const props = withDefaults(defineProps<{
  modelValue?: string
  shortcutLabel?: string
  captureShortcutLabel?: string
  capturing?: boolean
  captureDisabled?: boolean
  refreshing?: boolean
}>(), {
  modelValue: '',
  shortcutLabel: 'Ctrl+F',
  captureShortcutLabel: 'Ctrl+Shift+G',
  capturing: false,
  captureDisabled: false,
  refreshing: false,
})

const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void
  (event: 'capture'): void
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
  query.value = ''
  searchInput.value?.focus()
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
  <section class="border-b border-[var(--shell-line)] bg-[var(--shell-frame-bg)] px-5 py-3">
    <div class="flex flex-wrap items-center gap-2.5">
      <div class="relative min-w-[260px] flex-1">
        <MagnifyingGlassIcon
          class="pointer-events-none absolute left-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-[var(--shell-muted)]"
          aria-hidden="true"
        />
        <input
          ref="searchInput"
          v-model="query"
          type="search"
          class="h-11 w-full rounded-lg border border-[var(--shell-line)] bg-[var(--shell-control-bg)] pl-11 pr-24 text-sm text-[var(--shell-ink)] outline-none transition placeholder:text-[var(--shell-muted)] [&::-webkit-search-cancel-button]:appearance-none [&::-webkit-search-cancel-button]:hidden [&::-webkit-search-cancel-button]:[display:none]"
          :placeholder="t('search.placeholder')"
          @keydown.esc.stop.prevent="clear"
        />
        <div class="absolute right-3 top-1/2 flex -translate-y-1/2 items-center gap-2">
          <button
            v-if="query"
            type="button"
            class="flex h-[22px] min-h-0 w-[22px] flex-none items-center justify-center rounded-md text-[var(--shell-muted)] transition hover:bg-[var(--shell-control-hover)]"
            :aria-label="t('search.clear')"
            @click="clear"
          >
            <XMarkIcon class="h-3 w-3" aria-hidden="true" />
          </button>
          <kbd class="rounded-md border border-[var(--shell-line)] px-1.5 py-0.5 text-xs text-[var(--shell-muted)]">
            {{ shortcutLabel }}
          </kbd>
        </div>
      </div>

      <div
        class="search-toolbar__source-switcher inline-grid h-11 grid-flow-col auto-cols-fr items-center rounded-lg border border-[var(--shell-line)] bg-[var(--shell-control-bg)] p-[3px]"
        role="group"
        :aria-label="t('search.sourceLabel')"
      >
        <button
          v-for="item in sources"
          :key="item.value"
          type="button"
          class="search-toolbar__source-button h-9 min-h-0 rounded-md px-3.5 text-sm font-medium transition"
          :class="source === item.value
            ? 'bg-[var(--color-primary)] text-white shadow-sm'
            : 'text-[var(--shell-ink)] hover:bg-[var(--shell-control-hover)]'"
          :aria-pressed="source === item.value"
          @click="source = item.value"
        >
          {{ t(item.labelKey) }}
        </button>
      </div>

      <div class="toolbar-actions flex shrink-0 items-center gap-2.5">
        <button
          type="button"
          class="inline-flex h-11 w-11 items-center justify-center rounded-lg border border-[var(--shell-line)] bg-[var(--shell-control-bg)] text-[var(--shell-muted)] transition hover:bg-[var(--shell-control-hover)] disabled:opacity-50"
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
            class="flex h-11 cursor-pointer list-none items-center gap-1.5 rounded-lg border border-amber-200/80 bg-amber-50/75 px-3 text-amber-800 transition hover:bg-amber-100"
            :aria-label="t('search.debugTitle')"
          >
            <AdjustmentsHorizontalIcon class="h-4 w-4 flex-none" aria-hidden="true" />
            <span class="text-[10px] font-bold tracking-wide">DEV</span>
          </summary>
          <div
            class="absolute right-0 top-[calc(100%+.5rem)] z-50 w-[min(440px,calc(100vw-2.5rem))] rounded-lg border border-amber-200/80 bg-[var(--shell-card)] p-4 text-left shadow-2xl"
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

        <button
          type="button"
          class="capture-button inline-flex h-11 items-center gap-2 rounded-lg px-4 font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-55"
          :disabled="capturing || captureDisabled"
          @click="emit('capture')"
        >
          <CameraIcon class="h-5 w-5" aria-hidden="true" />
          {{ capturing ? t('action.processing') : t('action.capture') }}
          <kbd class="capture-shortcut rounded-md bg-white/18 px-1.5 py-0.5 text-xs">{{ captureShortcutLabel }}</kbd>
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
@media (max-width: 1024px) {
  .capture-button {
    padding-inline: 1rem;
  }

  .capture-shortcut {
    display: none;
  }
}
</style>
