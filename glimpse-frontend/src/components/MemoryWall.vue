<script setup lang="ts">
import { computed } from 'vue'
import { CameraIcon, FunnelIcon, MagnifyingGlassIcon } from '@heroicons/vue/24/outline'
import type { Memory } from '@/api/client'
import { languagePreference, t } from '@/utils/i18n'
import {
  createEmptyMemoryFilters,
  hasActiveMemoryFilters,
  type MemoryFilters,
} from '@/utils/memory-filters'
import CaptureButton from './CaptureButton.vue'
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
  filters?: MemoryFilters
}>()

const emit = defineEmits<{
  (event: 'select', memory: Memory): void
  (event: 'open', memory: Memory): void
  (event: 'capture'): void
  (event: 'apply-filters', filters: MemoryFilters): void
}>()

type MemoryGroup = { key: string; label: string; memories: Memory[] }

const searching = computed(() => Boolean(props.query?.trim()))
const filters = computed(() => props.filters ?? createEmptyMemoryFilters())
const filtering = computed(() => hasActiveMemoryFilters(filters.value))
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
  <section class="memory-wall min-h-0 flex-1">
    <header class="memory-wall__header">
      <h1 class="text-base font-semibold tracking-[-0.01em] text-[var(--shell-ink)]">
        {{
          searching
            ? t('memory.searchCount', { count: memories.length })
            : t('memory.count', { count: total })
        }}
      </h1>
      <MemoryFiltersControl
        :model-value="filters"
        :loading="loading"
        @apply="emit('apply-filters', $event)"
      />
    </header>

    <div class="memory-wall-scroll min-h-0 flex-1 overflow-y-auto px-5 pb-6 pt-4" aria-live="polite">

      <div v-if="loading" class="flex min-h-64 items-center justify-center">
        <LoadingSpinner />
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
        <p class="mt-1.5 max-w-sm text-sm leading-6 text-[var(--shell-muted)]">
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
        <CaptureButton
          v-else-if="!searching"
          class="mt-4"
          :capturing="capturing"
          :disabled="captureDisabled"
          @capture="emit('capture')"
        />
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
            />
          </div>
        </section>
      </div>
    </div>
  </section>
</template>

<style scoped>
.memory-wall {
  position: relative;
  display: flex;
  flex-direction: column;
  container-type: inline-size;
}

.memory-wall__header {
  position: relative;
  z-index: 2;
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.375rem 1.25rem 0.25rem;
  background: var(--shell-window-bg);
}

.memory-wall__header::after {
  content: '';
  position: absolute;
  right: 1.25rem;
  bottom: 0;
  left: 1.25rem;
  height: 1px;
  background: color-mix(in srgb, var(--shell-line) 72%, transparent);
}

.memory-wall-scroll {
  position: relative;
}

.memory-wall__capture-icon {
  color: var(--color-accent);
  background: color-mix(in srgb, var(--color-accent) 10%, var(--color-surface));
}

.memory-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.75rem;
}

/* 列数由网格容器的实际可用宽度决定，桌面端与网页端保持一致。
   两条规则用显式区间互斥，避免同时命中时后写规则覆盖列数；
   容器查询不生效的旧引擎会自动回退到上面的 auto-fill 网格。 */
@container (min-width: 480px) and (max-width: 759px) {
  .memory-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@container (min-width: 760px) {
  .memory-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@container (max-width: 560px) {
  .memory-wall__header {
    align-items: flex-start;
  }
}
</style>
