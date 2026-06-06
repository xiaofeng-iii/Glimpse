import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { memoriesApi, searchApi, type Memory } from '@/api/client'
import { createLogger } from '@/utils/logger'

const logger = createLogger('stores/memories')

export const useMemoriesStore = defineStore('memories', () => {
  const memories = ref<Memory[]>([])
  const selectedMemory = ref<Memory | null>(null)
  const searchQuery = ref('')
  const searchSource = ref('all')
  const isLoading = ref(false)
  const total = ref(0)

  const hasMemories = computed(() => memories.value.length > 0)

  const load = async (limit = 100) => {
    isLoading.value = true
    try {
      const result = await memoriesApi.list(limit)
      memories.value = result.memories
      total.value = result.total
    } catch (error) {
      logger.error('Failed to load memories: %s', error)
    } finally {
      isLoading.value = false
    }
  }

  const search = async (query: string, source = 'all') => {
    if (!query.trim()) {
      await load()
      return
    }

    isLoading.value = true
    searchQuery.value = query
    searchSource.value = source

    try {
      const result = await searchApi.search(query, source)
      memories.value = result.memories
      total.value = result.memories.length
    } catch (error) {
      logger.error('Search failed: %s', error)
    } finally {
      isLoading.value = false
    }
  }

  const select = (memory: Memory | null) => {
    selectedMemory.value = memory
  }

  const remove = async (id: string) => {
    try {
      await memoriesApi.delete(id)
      const remainingMemories = memories.value.filter(m => m.id !== id)
      memories.value = remainingMemories
      total.value = Math.max(0, total.value - 1)
      if (selectedMemory.value?.id === id) {
        selectedMemory.value = remainingMemories[0] ?? null
      }
    } catch (error) {
      logger.error('Failed to delete memory: %s', error)
      throw error
    }
  }

  const refresh = async () => {
    if (searchQuery.value) {
      await search(searchQuery.value, searchSource.value)
    } else {
      await load()
    }
  }

  return {
    memories,
    selectedMemory,
    searchQuery,
    searchSource,
    isLoading,
    total,
    hasMemories,
    load,
    search,
    select,
    remove,
    refresh,
  }
})
