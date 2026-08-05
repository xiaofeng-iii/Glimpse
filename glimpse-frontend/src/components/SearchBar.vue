<script setup lang="ts">
import { ref, watch } from 'vue'
import { MagnifyingGlassIcon } from '@heroicons/vue/24/outline'
import { useMemoriesStore } from '@/stores/memories'
import type { SearchOptions } from '@/api/client'
import { t } from '@/utils/i18n'

const props = defineProps<{
  modelValue?: string
  shortcutLabel?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'search', query: string, source: string): void
}>()

const memoriesStore = useMemoriesStore()

const query = ref(props.modelValue || '')
const source = ref('all')
const searchInput = ref<HTMLInputElement | null>(null)
const isDev = import.meta.env.DEV
const devOptions = ref({
  limit: 20,
  semanticThreshold: 1.15,
  candidateMultiplier: 2,
  rrfK: 60,
  debug: true,
})

const sources = [
  { value: 'all', labelKey: 'search.all' },
  { value: 'exact', labelKey: 'search.exactOnly' },
  { value: 'semantic', labelKey: 'search.semanticOnly' },
] as const

let debounceTimeout: ReturnType<typeof setTimeout> | null = null

const clampNumber = (
  value: unknown,
  fallback: number,
  minimum: number,
  maximum: number,
) => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return fallback
  return Math.min(maximum, Math.max(minimum, value))
}

const currentSearchOptions = (): SearchOptions => {
  if (!isDev) return {}
  return {
    limit: clampNumber(devOptions.value.limit, 20, 1, 100),
    semanticThreshold: clampNumber(devOptions.value.semanticThreshold, 1.15, 0, 4),
    candidateMultiplier: clampNumber(devOptions.value.candidateMultiplier, 2, 1, 10),
    rrfK: clampNumber(devOptions.value.rrfK, 60, 1, 200),
    debug: devOptions.value.debug,
  }
}

const scheduleSearch = () => {
  memoriesStore.invalidatePendingRequests()
  if (debounceTimeout) {
    clearTimeout(debounceTimeout)
  }

  debounceTimeout = setTimeout(() => {
    if (query.value.trim()) {
      memoriesStore.search(query.value, source.value, currentSearchOptions())
    } else {
      memoriesStore.load()
    }
  }, 300)
}

watch(query, (newQuery) => {
  emit('update:modelValue', newQuery)
  scheduleSearch()
})

watch(source, () => {
  if (query.value.trim()) {
    scheduleSearch()
  }
})

if (isDev) {
  watch(devOptions, () => {
    if (query.value.trim()) {
      scheduleSearch()
    }
  }, { deep: true })
}

const focus = () => {
  searchInput.value?.focus()
  searchInput.value?.select()
}

defineExpose({ focus })
</script>

<template>
  <div class="w-full">
    <!-- Search Input -->
    <div class="search-bar relative flex items-center p-1">
      <!-- Search Icon -->
      <MagnifyingGlassIcon class="ml-4 h-5 w-5 text-gray-400" aria-hidden="true" />

      <!-- Input -->
      <input
        ref="searchInput"
        v-model="query"
        type="text"
        :placeholder="t('search.placeholder')"
        class="flex-1 bg-transparent border-none outline-none px-4 py-3 text-gray-900 placeholder-gray-400 text-lg"
      />

      <!-- Keyboard Shortcut -->
      <kbd class="mr-4 px-2 py-1 rounded-lg bg-gray-100 text-gray-500 text-xs">
        {{ shortcutLabel || 'Ctrl+F' }}
      </kbd>
    </div>

    <!-- Source Filter Tabs -->
    <div class="flex justify-center gap-2 mt-4">
      <button
        v-for="s in sources"
        :key="s.value"
        @click="source = s.value"
        :class="[
          'source-filter-button px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200',
          source === s.value
            ? 'source-filter-button-active'
            : ''
        ]"
      >
        {{ t(s.labelKey) }}
      </button>
    </div>

    <details
      v-if="isDev"
      class="mt-3 rounded-xl border border-amber-200/80 bg-amber-50/70 px-4 py-3 text-left"
    >
      <summary class="cursor-pointer select-none text-xs font-semibold text-amber-800">
        {{ t('search.debugTitle') }}
        <span class="ml-2 font-normal text-amber-700">{{ t('search.debugHint') }}</span>
      </summary>

      <div class="mt-3 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <label class="text-xs text-slate-600">
          <span class="mb-1 block">{{ t('search.resultLimit') }}</span>
          <input
            v-model.number="devOptions.limit"
            type="number"
            min="1"
            max="100"
            class="w-full rounded-lg border border-amber-200 bg-white px-2 py-1.5 text-sm text-slate-800 outline-none focus:border-amber-400"
          />
        </label>

        <label class="text-xs text-slate-600">
          <span class="mb-1 block">{{ t('search.semanticThreshold') }}</span>
          <input
            v-model.number="devOptions.semanticThreshold"
            type="number"
            min="0"
            max="4"
            step="0.05"
            class="w-full rounded-lg border border-amber-200 bg-white px-2 py-1.5 text-sm text-slate-800 outline-none focus:border-amber-400"
          />
        </label>

        <label class="text-xs text-slate-600">
          <span class="mb-1 block">{{ t('search.candidateMultiplier') }}</span>
          <input
            v-model.number="devOptions.candidateMultiplier"
            type="number"
            min="1"
            max="10"
            class="w-full rounded-lg border border-amber-200 bg-white px-2 py-1.5 text-sm text-slate-800 outline-none focus:border-amber-400"
          />
        </label>

        <label class="text-xs text-slate-600">
          <span class="mb-1 block">{{ t('search.rrfK') }}</span>
          <input
            v-model.number="devOptions.rrfK"
            type="number"
            min="1"
            max="200"
            class="w-full rounded-lg border border-amber-200 bg-white px-2 py-1.5 text-sm text-slate-800 outline-none focus:border-amber-400"
          />
        </label>
      </div>

      <label class="mt-3 flex cursor-pointer items-center gap-2 text-xs text-amber-800">
        <input v-model="devOptions.debug" type="checkbox" class="h-4 w-4 accent-amber-600" />
        {{ t('search.showScores') }}
      </label>
    </details>
  </div>
</template>
