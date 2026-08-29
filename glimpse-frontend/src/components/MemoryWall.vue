<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { CameraIcon, FunnelIcon, MagnifyingGlassIcon } from '@heroicons/vue/24/outline'
import type { Memory } from '@/api/client'
import { languagePreference, t } from '@/utils/i18n'
import {
  createEmptyMemoryFilters,
  hasActiveMemoryFilters,
  type MemoryFilters,
} from '@/utils/memory-filters'
import CaptureButton from './CaptureButton.vue'
import AddMemoryButton from './AddMemoryButton.vue'
import MemoryCard from './MemoryCard.vue'
import MemoryFiltersControl from './MemoryFilters.vue'
import LoadingSpinner from './LoadingSpinner.vue'

const props = defineProps<{
  memories: Memory[]
  total: number
  loading?: boolean
  selectedId?: string | null
  query?: string
  showSearchDebug?: boolean
  capturing?: boolean
  captureDisabled?: boolean
  addingMemory?: boolean
  addMemoryDisabled?: boolean
  filters?: MemoryFilters
}>()

const emit = defineEmits<{
  (event: 'select', memory: Memory): void
  (event: 'open', memory: Memory): void
  (event: 'contextmenu', payload: { memory: Memory; x: number; y: number }): void
  (event: 'capture'): void
  (event: 'add-memory'): void
  (event: 'apply-filters', filters: MemoryFilters): void
}>()

type MemoryGroup = { key: string; label: string; memories: Memory[] }

const searching = computed(() => Boolean(props.query?.trim()))
const filters = computed(() => props.filters ?? createEmptyMemoryFilters())
const filtering = computed(() => hasActiveMemoryFilters(filters.value))
const wall = ref<HTMLElement | null>(null)
const compactFilter = ref(false)
let scrollContainer: HTMLElement | null = null
let toolbarResizeObserver: ResizeObserver | null = null

const updateStickyFilter = () => {
  if (!scrollContainer || !wall.value) return
  const toolbar = scrollContainer.querySelector<HTMLElement>('.search-toolbar')
  if (!toolbar) return

  const stickyTop = toolbar.getBoundingClientRect().height
  wall.value.style.setProperty('--memory-wall-sticky-top', `${stickyTop}px`)
  compactFilter.value = scrollContainer.scrollTop > 0
}

onMounted(() => {
  scrollContainer = wall.value?.closest<HTMLElement>('.home-memory-pane') ?? null
  if (!scrollContainer) return

  scrollContainer.addEventListener('scroll', updateStickyFilter, { passive: true })
  const toolbar = scrollContainer.querySelector<HTMLElement>('.search-toolbar')
  if (toolbar && 'ResizeObserver' in window) {
    toolbarResizeObserver = new ResizeObserver(updateStickyFilter)
    toolbarResizeObserver.observe(toolbar)
  }
  void nextTick(updateStickyFilter)
})

onUnmounted(() => {
  scrollContainer?.removeEventListener('scroll', updateStickyFilter)
  toolbarResizeObserver?.disconnect()
})
const startOfDay = (date: Date) => new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()

const groups = computed<MemoryGroup[]>(() => {
  void languagePreference.value
  if (searching.value) {
    return [{ key: 'search', label: '', memories: props.memories }]
  }

  const now = new Date()
  const today = startOfDay(now)
  const yesterday = today - 86_400_000
  const result = new Map<string, MemoryGroup>()

  for (const memory of props.memories) {
    const date = new Date(memory.created_at)
    const day = startOfDay(date)
    let key: string
    let label: string
    if (day === today) {
      key = 'today'
      label = t('memory.today')
    } else if (day === yesterday) {
      key = 'yesterday'
      label = t('memory.yesterday')
    } else {
      key = date.toLocaleDateString(languagePreference.value, {
        year: date.getFullYear() === now.getFullYear() ? undefined : 'numeric',
        month: 'long',
        day: 'numeric',
      })
      label = key
    }

    const group = result.get(key) ?? { key, label, memories: [] }
    group.memories.push(memory)
    result.set(key, group)
  }

  return [...result.values()]
})
</script>

<template>
  <section ref="wall" class="memory-wall">
    <header
      class="memory-wall__header"
      :class="{ 'memory-wall__header--compact': compactFilter }"
    >
      <h1 class="text-base font-semibold tracking-[-0.01em] text-[var(--shell-ink)]">
        {{
          loading && searching
            ? t('search.searching')
            : searching
              ? t('memory.searchCount', { count: memories.length })
              : t('memory.count', { count: total })
        }}
      </h1>
      <MemoryFiltersControl
        :model-value="filters"
        :loading="loading"
        :compact="compactFilter"
        @apply="emit('apply-filters', $event)"
      />
    </header>

    <div class="memory-wall-scroll pb-6 pt-4" aria-live="polite">

      <div v-if="loading">
        <div v-if="searching" class="memory-grid" aria-hidden="true">
          <div v-for="i in 8" :key="i" class="memory-card-skeleton">
            <div class="memory-card-skeleton__media"></div>
            <div class="memory-card-skeleton__body">
              <div class="memory-card-skeleton__line"></div>
              <div class="memory-card-skeleton__line"></div>
              <div class="memory-card-skeleton__line memory-card-skeleton__line--short"></div>
              <div class="memory-card-skeleton__time"></div>
            </div>
          </div>
        </div>
        <div v-else class="flex min-h-64 items-center justify-center">
          <LoadingSpinner />
        </div>
      </div>

      <div v-else-if="!memories.length" class="flex min-h-[52vh] flex-col items-center justify-center text-center">
        <div
          class="flex h-14 w-14 items-center justify-center rounded-xl"
          :class="searching || filtering
            ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary)]'
            : 'memory-wall__capture-icon'"
        >
          <FunnelIcon v-if="filtering" class="h-7 w-7" aria-hidden="true" />
          <MagnifyingGlassIcon v-else-if="searching" class="h-7 w-7" aria-hidden="true" />
          <CameraIcon v-else class="h-7 w-7" aria-hidden="true" />
        </div>
        <h2 class="mt-4 text-base font-semibold text-[var(--shell-ink)]">
          {{ filtering
            ? t('memory.noFilterResults')
            : searching ? t('memory.noSearchResults') : t('memory.emptyTitle') }}
        </h2>
        <p class="mt-1.5 max-w-sm text-sm text-[var(--shell-muted)]">
          {{ filtering
            ? t('memory.noFilterResultsHint')
            : searching ? t('memory.noSearchResultsHint') : t('memory.emptyHint') }}
        </p>
        <button
          v-if="filtering"
          type="button"
          class="btn-secondary mt-4"
          @click="emit('apply-filters', createEmptyMemoryFilters())"
        >
          {{ t('filter.clear') }}
        </button>
        <div v-else-if="!searching" class="mt-4 flex flex-wrap items-center justify-center gap-2.5">
          <CaptureButton
            :capturing="capturing"
            :disabled="captureDisabled"
            @capture="emit('capture')"
          />
          <AddMemoryButton
            :busy="addingMemory"
            :disabled="addMemoryDisabled"
            @add="emit('add-memory')"
          />
        </div>
      </div>

      <div v-else class="space-y-5">
        <section v-for="group in groups" :key="group.key">
          <h2 v-if="group.label" class="mb-2.5 text-xs font-semibold tracking-wide text-[var(--shell-muted)]">
            {{ group.label }}
          </h2>
          <div class="memory-grid">
            <MemoryCard
              v-for="memory in group.memories"
              :key="memory.id"
              :memory="memory"
              :selected="selectedId === memory.id"
              :searching="searching"
              :show-debug="showSearchDebug"
              @select="emit('select', $event)"
              @open="emit('open', $event)"
              @contextmenu="emit('contextmenu', $event)"
            />
          </div>
        </section>
      </div>
    </div>
  </section>
</template>

<style scoped>
.memory-wall {
  --memory-wall-inline-inset: 1rem;
  --memory-wall-sticky-top: 5rem;
  --memory-card-width: 239px;

  position: relative;
  display: flex;
  flex-direction: column;
  container-type: inline-size;
}

.memory-wall__header {
  position: sticky;
  z-index: 2;
  top: var(--memory-wall-sticky-top);
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.375rem var(--memory-wall-inline-inset) 0.25rem;
  background: var(--shell-window-bg);
}

.memory-wall__header h1 {
  transition: opacity 160ms ease, transform 160ms ease;
}

.memory-wall__header--compact {
  background: transparent;
}

.memory-wall__header--compact h1 {
  transform: translateY(-0.25rem);
  opacity: 0;
  pointer-events: none;
}

.memory-wall__header::after {
  content: '';
  position: absolute;
  right: var(--memory-wall-inline-inset);
  bottom: 0;
  left: var(--memory-wall-inline-inset);
  height: 1px;
  background: color-mix(in srgb, var(--shell-line) 72%, transparent);
  transition: opacity 160ms ease;
}

.memory-wall__header--compact::after {
  opacity: 0;
}

.memory-wall-scroll {
  position: relative;
  padding-inline: var(--memory-wall-inline-inset);
}

.memory-wall__capture-icon {
  color: var(--color-accent);
  background: color-mix(in srgb, var(--color-accent) 10%, var(--color-surface));
}

.memory-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, var(--memory-card-width));
  align-items: start;
  justify-content: start;
  gap: 0.75rem;
}

/* 搜索加载骨架屏：占位卡片尺寸与 MemoryCard 对齐，shimmer 扫过提示加载中。 */
.memory-card-skeleton {
  display: flex;
  inline-size: var(--memory-card-width, 239px);
  block-size: 270px;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--shell-line);
  border-radius: var(--radius-lg);
}

.memory-card-skeleton__media {
  flex: 0 0 148px;
}

.memory-card-skeleton__body {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 0.5rem;
  padding: 8px;
}

.memory-card-skeleton__line {
  block-size: 12px;
  inline-size: 100%;
  border-radius: 6px;
}

.memory-card-skeleton__line--short {
  inline-size: 62%;
}

.memory-card-skeleton__time {
  margin-block-start: auto;
  block-size: 10px;
  inline-size: 32%;
  border-radius: 5px;
}

.memory-card-skeleton__media,
.memory-card-skeleton__line,
.memory-card-skeleton__time {
  background: linear-gradient(
    90deg,
    var(--color-surface-subtle) 25%,
    var(--color-surface-hover) 45%,
    var(--color-surface-subtle) 65%
  );
  background-size: 300% 100%;
  animation: memory-skeleton-shimmer 1.4s ease-in-out infinite;
}

@keyframes memory-skeleton-shimmer {
  from {
    background-position: 150% 0;
  }

  to {
    background-position: -150% 0;
  }
}

@container memory-pane (max-width: 960px) {
  .memory-wall {
    --memory-wall-inline-inset: 0.75rem;
  }
}

@container memory-pane (max-width: 640px) {
  .memory-wall {
    --memory-wall-inline-inset: 0.5rem;
  }
}

@container (max-width: 560px) {
  .memory-wall__header {
    align-items: flex-start;
  }
}

@media (prefers-reduced-motion: reduce) {
  .memory-wall__header h1,
  .memory-wall__header::after {
    transition: none;
  }

  .memory-card-skeleton__media,
  .memory-card-skeleton__line,
  .memory-card-skeleton__time {
    animation: none;
  }
}
</style>
