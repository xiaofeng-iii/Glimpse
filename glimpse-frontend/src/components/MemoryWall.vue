<script setup lang="ts">
import { computed } from 'vue'
import { CameraIcon, MagnifyingGlassIcon } from '@heroicons/vue/24/outline'
import type { Memory } from '@/api/client'
import { languagePreference, t } from '@/utils/i18n'
import MemoryCard from './MemoryCard.vue'
import LoadingSpinner from './LoadingSpinner.vue'

const props = defineProps<{
  memories: Memory[]
  total: number
  loading?: boolean
  selectedId?: string | null
  query?: string
  inspectorOpen?: boolean
  showSearchDebug?: boolean
}>()

const emit = defineEmits<{
  (event: 'select', memory: Memory): void
  (event: 'open', memory: Memory): void
  (event: 'capture'): void
}>()

type MemoryGroup = { key: string; label: string; memories: Memory[] }

const searching = computed(() => Boolean(props.query?.trim()))
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
  <section class="min-h-0 flex-1 overflow-y-auto px-5 pb-6 pt-4" aria-live="polite">
    <div class="mb-3">
      <h1 class="text-base font-semibold tracking-[-0.01em] text-[var(--shell-ink)]">
        {{
          searching
            ? t('memory.searchCount', { count: memories.length })
            : t('memory.count', { count: total })
        }}
      </h1>
    </div>

    <div v-if="loading" class="flex min-h-64 items-center justify-center">
      <LoadingSpinner />
    </div>

    <div v-else-if="!memories.length" class="flex min-h-[52vh] flex-col items-center justify-center text-center">
      <div class="flex h-14 w-14 items-center justify-center rounded-xl bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
        <MagnifyingGlassIcon v-if="searching" class="h-7 w-7" aria-hidden="true" />
        <CameraIcon v-else class="h-7 w-7" aria-hidden="true" />
      </div>
      <h2 class="mt-4 text-base font-semibold text-[var(--shell-ink)]">
        {{ searching ? t('memory.noSearchResults') : t('memory.emptyTitle') }}
      </h2>
      <p class="mt-1.5 max-w-sm text-sm leading-6 text-[var(--shell-muted)]">
        {{ searching ? t('memory.noSearchResultsHint') : t('memory.emptyHint') }}
      </p>
      <button v-if="!searching" type="button" class="btn-primary mt-4 min-h-10" @click="emit('capture')">
        <CameraIcon class="h-5 w-5" aria-hidden="true" />
        {{ t('action.capture') }}
      </button>
    </div>

    <div v-else class="space-y-5">
      <section v-for="group in groups" :key="group.key">
        <h2 v-if="group.label" class="mb-2.5 text-xs font-semibold tracking-wide text-[var(--shell-muted)]">
          {{ group.label }}
        </h2>
        <div
          class="memory-grid"
          :class="{ 'memory-grid--with-inspector': inspectorOpen }"
        >
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
  </section>
</template>

<style scoped>
.memory-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.75rem;
}

@media (min-width: 1180px) {
  .memory-grid--with-inspector {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (min-width: 820px) and (max-width: 1179px) {
  .memory-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 819px) {
  .memory-grid {
    grid-template-columns: 1fr;
  }
}
</style>
