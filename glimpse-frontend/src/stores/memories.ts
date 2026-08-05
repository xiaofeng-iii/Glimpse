import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { memoriesApi, searchApi, type Memory, type SearchOptions } from '@/api/client'
import { createLogger } from '@/utils/logger'

const logger = createLogger('stores/memories')

export const useMemoriesStore = defineStore('memories', () => {
  const entities = ref<Record<string, Memory>>({})
  const resultIds = ref<string[]>([])
  const selectedId = ref<string | null>(null)
  const searchQuery = ref('')
  const searchSource = ref('all')
  const searchOptions = ref<SearchOptions>({})
  const isLoading = ref(false)
  const total = ref(0)
  const selectedOutsideSearch = ref(false)
  let latestRequest = 0

  const memories = computed(() =>
    resultIds.value.map((id) => entities.value[id]).filter((memory): memory is Memory => Boolean(memory)),
  )
  const selectedMemory = computed(() =>
    selectedId.value ? entities.value[selectedId.value] ?? null : null,
  )
  const hasMemories = computed(() => memories.value.length > 0)

  const invalidatePendingRequests = () => {
    latestRequest += 1
    isLoading.value = false
    selectedOutsideSearch.value = false
  }

  const mergeMemory = (memory: Memory) => {
    const current = entities.value[memory.id]
    entities.value = {
      ...entities.value,
      [memory.id]: {
        ...current,
        ...memory,
        match_sources: current?.match_sources ?? [],
        search_debug: current?.search_debug ?? null,
      },
    }
    return entities.value[memory.id]
  }

  const applyResults = (items: Memory[], includeSearchMetadata = false) => {
    const nextResultIds = items.map((memory) => memory.id)
    const nextResultIdSet = new Set(nextResultIds)
    const nextEntities = { ...entities.value }

    for (const previousId of resultIds.value) {
      if (nextResultIdSet.has(previousId) || !nextEntities[previousId]) continue
      nextEntities[previousId] = {
        ...nextEntities[previousId],
        match_sources: [],
        search_debug: null,
      }
    }

    for (const memory of items) {
      nextEntities[memory.id] = {
        ...nextEntities[memory.id],
        ...memory,
        match_sources: includeSearchMetadata ? memory.match_sources ?? [] : [],
        search_debug: includeSearchMetadata ? memory.search_debug ?? null : null,
      }
    }
    entities.value = nextEntities
    resultIds.value = nextResultIds
  }

  const load = async (limit = 100) => {
    const requestId = ++latestRequest
    isLoading.value = true
    try {
      const result = await memoriesApi.list(limit)
      if (requestId !== latestRequest) return []
      applyResults(result.memories)
      total.value = result.total
      searchQuery.value = ''
      selectedOutsideSearch.value = false
      return result.memories
    } catch (error) {
      logger.error('Failed to load memories: %s', error)
      return []
    } finally {
      if (requestId === latestRequest) {
        isLoading.value = false
      }
    }
  }

  const executeSearch = async (
    query: string,
    source = 'all',
    options: SearchOptions = {},
    updatedMemoryId?: string,
  ) => {
    const normalizedQuery = query.trim()
    if (!normalizedQuery) {
      return load()
    }

    const requestId = ++latestRequest
    isLoading.value = true
    searchQuery.value = normalizedQuery
    searchSource.value = source
    searchOptions.value = { ...options }

    try {
      const result = await searchApi.search(normalizedQuery, source, options)
      if (requestId !== latestRequest) return []
      applyResults(result.memories, true)
      total.value = result.memories.length
      selectedOutsideSearch.value = Boolean(
        updatedMemoryId
        && selectedId.value === updatedMemoryId
        && !resultIds.value.includes(updatedMemoryId),
      )
      return result.memories
    } catch (error) {
      logger.error('Search failed: %s', error)
      return []
    } finally {
      if (requestId === latestRequest) {
        isLoading.value = false
      }
    }
  }

  const search = async (query: string, source = 'all', options: SearchOptions = {}) =>
    executeSearch(query, source, options)

  const select = (memory: Memory | null) => {
    if (!memory) {
      selectedId.value = null
      selectedOutsideSearch.value = false
      return
    }
    mergeMemory(memory)
    selectedId.value = memory.id
    selectedOutsideSearch.value = false
  }

  const upsert = (memory: Memory) => {
    const merged = mergeMemory(memory)
    if (!searchQuery.value && !resultIds.value.includes(memory.id)) {
      resultIds.value = [memory.id, ...resultIds.value]
      total.value += 1
    }
    return merged
  }

  const updateSummary = async (id: string, aiSummary: string) => {
    const updated = await memoriesApi.updateSummary(id, aiSummary.trim())
    mergeMemory(updated)
    selectedId.value = id

    if (searchQuery.value) {
      await executeSearch(searchQuery.value, searchSource.value, searchOptions.value, id)
    }

    return entities.value[id]
  }

  const remove = async (id: string) => {
    try {
      await memoriesApi.delete(id)
      resultIds.value = resultIds.value.filter((memoryId) => memoryId !== id)
      const nextEntities = { ...entities.value }
      delete nextEntities[id]
      entities.value = nextEntities
      total.value = Math.max(0, total.value - 1)
      if (selectedId.value === id) {
        selectedId.value = resultIds.value[0] ?? null
        selectedOutsideSearch.value = false
      }
    } catch (error) {
      logger.error('Failed to delete memory: %s', error)
      throw error
    }
  }

  const refresh = async () => {
    if (searchQuery.value) {
      await search(searchQuery.value, searchSource.value, searchOptions.value)
    } else {
      await load()
    }
  }

  return {
    entities,
    resultIds,
    memories,
    selectedId,
    selectedMemory,
    selectedOutsideSearch,
    searchQuery,
    searchSource,
    searchOptions,
    isLoading,
    total,
    hasMemories,
    invalidatePendingRequests,
    load,
    search,
    select,
    upsert,
    updateSummary,
    remove,
    refresh,
  }
})
