<script setup lang="ts">
import { ref, watch } from 'vue'
import { useMemoriesStore } from '@/stores/memories'

const props = defineProps<{
  modelValue?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'search', query: string, source: string): void
}>()

const memoriesStore = useMemoriesStore()

const query = ref(props.modelValue || '')
const source = ref('all')
const searchInput = ref<HTMLInputElement | null>(null)

const sources = [
  { value: 'all', label: '综合结果' },
  { value: 'exact', label: '仅看精确' },
  { value: 'semantic', label: '仅看语义' },
]

let debounceTimeout: ReturnType<typeof setTimeout> | null = null

watch(query, (newQuery) => {
  emit('update:modelValue', newQuery)

  if (debounceTimeout) {
    clearTimeout(debounceTimeout)
  }

  debounceTimeout = setTimeout(() => {
    if (newQuery.trim()) {
      memoriesStore.search(newQuery, source.value)
    } else {
      memoriesStore.load()
    }
  }, 300)
})

watch(source, (newSource) => {
  if (query.value.trim()) {
    memoriesStore.search(query.value, newSource)
  }
})

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
      <svg class="w-5 h-5 text-gray-400 ml-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>

      <!-- Input -->
      <input
        ref="searchInput"
        v-model="query"
        type="text"
        placeholder="搜索记忆..."
        class="flex-1 bg-transparent border-none outline-none px-4 py-3 text-gray-900 placeholder-gray-400 text-lg"
      />

      <!-- Keyboard Shortcut -->
      <kbd class="mr-4 px-2 py-1 rounded-lg bg-gray-100 text-gray-500 text-xs">
        Ctrl+F
      </kbd>
    </div>

    <!-- Source Filter Tabs -->
    <div class="flex justify-center gap-2 mt-4">
      <button
        v-for="s in sources"
        :key="s.value"
        @click="source = s.value"
        :class="[
          'px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200',
          source === s.value
            ? 'bg-gradient-to-r from-violet-500 to-pink-500 text-white shadow-lg shadow-violet-500/25'
            : 'bg-white/80 text-gray-600 hover:bg-gray-100'
        ]"
      >
        {{ s.label }}
      </button>
    </div>
  </div>
</template>
