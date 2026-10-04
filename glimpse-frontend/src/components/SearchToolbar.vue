<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import {
  AdjustmentsHorizontalIcon,
  MagnifyingGlassIcon,
  QuestionMarkCircleIcon,
  ArrowPathIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline'
import type { SearchOptions } from '@/api/client'
import { useMemoriesStore } from '@/stores/memories'
import { useDevStateStore, type AnalysisOverride, type SyncOverride } from '@/stores/devState'
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
const devState = useDevStateStore()
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
  devDelayMs: 0,
  devFailSearch: false,
})

const sources = [
  { value: 'all', labelKey: 'search.all' },
  { value: 'exact', labelKey: 'search.exactOnly' },
  { value: 'semantic', labelKey: 'search.semanticOnly' },
] as const

const analysisOverrideOptions = [
  { value: 'none', labelKey: 'search.devAnalysisDefault' },
  { value: 'processing', labelKey: 'search.devAnalysisProcessing' },
  { value: 'failed', labelKey: 'search.devAnalysisFailed' },
] as const
const syncOverrideOptions = [
  { value: 'none', labelKey: 'search.devSyncDefault' },
  { value: 'pending', labelKey: 'search.devSyncPending' },
  { value: 'failed', labelKey: 'search.devSyncFailed' },
] as const

// 滑块按列等宽，translateX 的 100% 即一列宽度，跨列平移只需叠加列距
const activeSourceIndex = computed(() =>
  Math.max(0, sources.findIndex((item) => item.value === source.value)),
)

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
    devDelayMs: clampNumber(devOptions.value.devDelayMs, 0, 0, 60_000),
    devFailSearch: devOptions.value.devFailSearch,
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

const closeDebugPanel = () => {
  if (!debugPanelOpen.value) return
  debugPanelOpen.value = false
  if (debugPanelElement.value) debugPanelElement.value.open = false
  emit('debug-panel-change', false)
}

const handleDebugToggle = (event: Event) => {
  const open = (event.currentTarget as HTMLDetailsElement).open
  if (debugPanelOpen.value === open) return
  debugPanelOpen.value = open
  emit('debug-panel-change', open)
}

// 全局指针监听：点击面板外任何位置（包括不可聚焦的空白处）都关闭。
// 用 pointerdown 而非 click，在焦点转移前判定，避免点击按钮等控件先抢走焦点再判定时丢失目标。
const handleDocumentPointerDown = (event: PointerEvent) => {
  if (!debugPanelOpen.value) return
  const panel = debugPanelElement.value
  if (!panel || !(event.target instanceof Node)) return
  if (panel.contains(event.target)) return
  closeDebugPanel()
}

// 全局 ESC：挂 document 而非 details，避免浏览器原生 details-ESC 行为绕过处理器导致状态脱轨。
// 捕获阶段 + stopPropagation，避免同时触发全局“Esc 清空搜索”。
const handleDocumentKeydown = (event: KeyboardEvent) => {
  if (event.key !== 'Escape' || !debugPanelOpen.value) return
  event.stopPropagation()
  closeDebugPanel()
}

const bindDebugPanelListeners = (open: boolean) => {
  if (open) {
    document.addEventListener('pointerdown', handleDocumentPointerDown, true)
    document.addEventListener('keydown', handleDocumentKeydown, true)
  } else {
    document.removeEventListener('pointerdown', handleDocumentPointerDown, true)
    document.removeEventListener('keydown', handleDocumentKeydown, true)
  }
}

watch(debugPanelOpen, bindDebugPanelListeners)

const handleShowOnboarding = () => {
  closeDebugPanel()
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
  bindDebugPanelListeners(false)
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
            class="search-toolbar__control h-8 w-full border border-transparent bg-[var(--color-surface-subtle)] pl-11 pr-24 text-sm text-[var(--shell-ink)] outline-none transition placeholder:text-[var(--shell-muted)] [&::-webkit-search-cancel-button]:appearance-none [&::-webkit-search-cancel-button]:hidden [&::-webkit-search-cancel-button]:[display:none]"
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
            <kbd class="search-toolbar__detail-control border border-[var(--shell-line)] px-1 py-0 text-[11px] leading-[14px] text-[var(--shell-muted)]">
              {{ shortcutLabel }}
            </kbd>
          </div>
        </div>

        <div
          class="search-toolbar__control search-toolbar__source-switcher inline-grid h-8 grid-flow-col auto-cols-fr items-center"
          role="group"
          :aria-label="t('search.sourceLabel')"
        >
          <span
            class="search-toolbar__source-thumb"
            :style="{ transform: `translateX(calc(${activeSourceIndex} * (100% + var(--search-toolbar-segment-inset))))` }"
            aria-hidden="true"
          ></span>
          <button
            v-for="item in sources"
            :key="item.value"
            type="button"
            class="search-toolbar__source-button h-7 min-h-0 px-2.5 text-[13px] font-medium"
            :class="source === item.value
              ? 'text-[var(--color-on-primary)]'
              : 'text-[var(--shell-ink)] hover:text-[var(--color-primary)]'"
            :aria-pressed="source === item.value"
            @click="source = item.value"
          >
            {{ t(item.labelKey) }}
          </button>
        </div>

        <div class="search-toolbar__actions flex shrink-0 items-center gap-2.5">
          <button
            type="button"
            class="search-toolbar__control inline-flex h-8 min-h-0 w-8 items-center justify-center bg-[var(--color-surface-subtle)] text-[var(--shell-muted)] transition hover:bg-[var(--color-surface-hover)] disabled:opacity-50"
            :aria-label="t('action.refresh')"
            :disabled="refreshing"
            @click="emit('refresh')"
          >
            <ArrowPathIcon class="h-4 w-4" :class="{ 'animate-spin': refreshing }" aria-hidden="true" />
          </button>

        <details
          ref="debugPanelElement"
          v-if="isDev"
          class="relative"
          :open="debugPanelOpen"
          @toggle="handleDebugToggle"
        >
          <summary
            class="search-toolbar__control flex h-8 cursor-pointer list-none items-center gap-1.5 bg-amber-50/75 px-3 text-amber-800 transition hover:bg-amber-100"
            :aria-label="t('search.debugTitle')"
          >
            <AdjustmentsHorizontalIcon class="h-4 w-4 flex-none" aria-hidden="true" />
            <span class="search-toolbar__dev-label text-[10px] font-bold tracking-wide">DEV</span>
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
                  class="w-full rounded-md border border-[var(--shell-line)] bg-[var(--shell-control-bg)] px-2 py-1.5 text-sm text-[var(--shell-ink)] outline-none focus:border-[color-mix(in_srgb,var(--color-primary)_55%,var(--shell-line))]"
                />
              </label>
            </div>
            <div class="mt-3 grid grid-cols-2 gap-3">
              <label class="text-xs text-[var(--shell-muted)]">
                <span class="mb-1 block">{{ t('search.devDelayMs') }}</span>
                <input
                  v-model.number="devOptions.devDelayMs"
                  type="number"
                  :min="0"
                  :step="100"
                  class="w-full rounded-md border border-[var(--shell-line)] bg-[var(--shell-control-bg)] px-2 py-1.5 text-sm text-[var(--shell-ink)] outline-none focus:border-[color-mix(in_srgb,var(--color-primary)_55%,var(--shell-line))]"
                />
              </label>
              <label class="flex cursor-pointer items-end gap-2 pb-1.5 text-xs text-amber-800">
                <input v-model="devOptions.devFailSearch" type="checkbox" class="h-4 w-4 accent-amber-600" />
                {{ t('search.devFailSearch') }}
              </label>
            </div>
            <label class="mt-3 flex cursor-pointer items-center gap-2 text-xs text-amber-800">
              <input v-model="devOptions.debug" type="checkbox" class="h-4 w-4 accent-amber-600" />
              {{ t('search.showScores') }}
            </label>

            <div class="mt-3 border-t border-amber-200/60 pt-3">
              <div class="flex items-center justify-between">
                <p class="text-xs font-semibold text-amber-800">{{ t('search.devStateOverride') }}</p>
                <p v-if="devState.hasOverride" class="text-[10px] font-medium text-amber-700">{{ t('search.devStateOverrideActive') }}</p>
              </div>
              <p class="mt-0.5 text-[11px] text-[var(--shell-muted)]">{{ t('search.devStateOverrideHint') }}</p>
              <div class="mt-2 grid grid-cols-2 gap-3">
                <div>
                  <span class="mb-1 block text-xs text-[var(--shell-muted)]">{{ t('search.devAnalysisState') }}</span>
                  <div class="flex flex-col gap-1.5">
                    <label
                      v-for="option in analysisOverrideOptions"
                      :key="option.value"
                      class="flex cursor-pointer items-center gap-1.5 text-xs text-amber-800"
                    >
                      <input
                        type="radio"
                        name="dev-analysis-override"
                        :checked="devState.analysisOverride === option.value"
                        class="h-3.5 w-3.5 accent-amber-600"
                        @change="devState.setAnalysisOverride(option.value as AnalysisOverride)"
                      />
                      {{ t(option.labelKey) }}
                    </label>
                  </div>
                </div>
                <div>
                  <span class="mb-1 block text-xs text-[var(--shell-muted)]">{{ t('search.devSyncState') }}</span>
                  <div class="flex flex-col gap-1.5">
                    <label
                      v-for="option in syncOverrideOptions"
                      :key="option.value"
                      class="flex cursor-pointer items-center gap-1.5 text-xs text-amber-800"
                    >
                      <input
                        type="radio"
                        name="dev-sync-override"
                        :checked="devState.syncOverride === option.value"
                        class="h-3.5 w-3.5 accent-amber-600"
                        @change="devState.setSyncOverride(option.value as SyncOverride)"
                      />
                      {{ t(option.labelKey) }}
                    </label>
                  </div>
                </div>
              </div>
            </div>
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

        <span class="search-toolbar__actions-divider" aria-hidden="true"></span>

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
.search-toolbar__dev-label {
  font-family: var(--font-ui);
}

.search-toolbar {
  --search-toolbar-surface-radius: var(--radius-xl);
  --search-toolbar-surface-inset: 0.625rem;
  --search-toolbar-control-radius: var(--radius-sm);
  --search-toolbar-segment-inset: 2px;
  --search-toolbar-segment-radius: max(
    1px,
    calc(var(--radius-md) - var(--search-toolbar-segment-inset))
  );
  --search-toolbar-detail-radius: var(--search-toolbar-control-radius);
  --search-toolbar-surface-shadow:
    0 1px 2px rgba(26, 38, 64, 0.05),
    0 6px 16px rgba(26, 38, 64, 0.08);

  position: sticky;
  z-index: var(--z-sticky);
  top: 0;
  isolation: isolate;
  padding: 0.5rem 1.25rem 0.375rem;
  background: transparent;
}

/* 浮条滚动遮罩只做磨砂不做提亮：内容从卡下滑过时仅模糊、不叠加白色，
   白色渐变遮罩已按设计决策移除。 */
.search-toolbar::after {
  position: absolute;
  z-index: 0;
  inset: 0 0 -0.75rem;
  pointer-events: none;
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
  grid-template-columns: minmax(260px, 1fr) 12.25rem auto;
  align-items: center;
  gap: 0.625rem;
}

/* 搜索模式三段式是工具条里的强调控件：仅此组件保留凹槽拟物（subtle 底 + 内阴影），
   激活段用深主色保证醒目；圆角沿用记忆墙排版切换器的 md 体系。
   用复合选择器压过下方 .search-toolbar__control 的统一圆角 */
.search-toolbar__control.search-toolbar__source-switcher {
  position: relative;
  width: 12.25rem;
  gap: var(--search-toolbar-segment-inset);
  padding: var(--search-toolbar-segment-inset);
  border-radius: var(--radius-md);
  background: var(--color-surface-subtle);
  box-shadow: inset 0 1px 2px rgba(26, 38, 64, 0.1);
}

/* 激活底色做成独立滑块，切换时在凹槽内线性平移 */
.search-toolbar__source-thumb {
  position: absolute;
  top: var(--search-toolbar-segment-inset);
  bottom: var(--search-toolbar-segment-inset);
  left: var(--search-toolbar-segment-inset);
  width: calc((100% - var(--search-toolbar-segment-inset) * 4) / 3);
  border-radius: var(--search-toolbar-segment-radius);
  background: var(--color-primary);
  box-shadow: 0 1px 2px 0 rgb(0 0 0 / 5%);
  will-change: transform;
  transition: transform 240ms cubic-bezier(0.4, 0, 0.2, 1);
}

.search-toolbar__source-button {
  position: relative;
  transition: color 240ms cubic-bezier(0.4, 0, 0.2, 1), background-color 240ms cubic-bezier(0.4, 0, 0.2, 1);
}

.search-toolbar__source-button:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 1px;
}

@media (prefers-reduced-motion: reduce) {
  .search-toolbar__source-thumb,
  .search-toolbar__source-button {
    transition: none;
  }
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

.search-toolbar__actions-divider {
  width: 1px;
  height: 1.25rem;
  flex: 0 0 1px;
  margin-inline: -0.125rem;
  background: var(--shell-line);
}

.search-toolbar__debug-panel {
  z-index: var(--z-popover);
}

:global(:root[data-theme='dark']) .search-toolbar {
  --search-toolbar-surface-shadow: 0 6px 16px rgba(0, 0, 0, 0.35);
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
    width: 11rem;
  }

  .search-toolbar__actions {
    grid-column: 2;
    grid-row: 2;
    justify-self: end;
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
  }
}
</style>
