import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { Memory } from '@/api/client'

const apiMocks = vi.hoisted(() => ({
  list: vi.fn(),
  search: vi.fn(),
  updateSummary: vi.fn(),
  updateTags: vi.fn(),
  listTags: vi.fn(),
  delete: vi.fn(),
}))

vi.mock('@/api/client', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/api/client')>()
  return {
    ...original,
    memoriesApi: {
      ...original.memoriesApi,
      list: apiMocks.list,
      updateSummary: apiMocks.updateSummary,
      updateTags: apiMocks.updateTags,
      delete: apiMocks.delete,
    },
    searchApi: {
      ...original.searchApi,
      search: apiMocks.search,
    },
    tagsApi: {
      ...original.tagsApi,
      list: apiMocks.listTags,
    },
  }
})

import { useMemoriesStore } from '@/stores/memories'
import { createEmptyMemoryFilters } from '@/utils/memory-filters'

const memory = (id: string, summary = `summary-${id}`): Memory => ({
  id,
  created_at: '2026-07-30T14:32:00',
  image_path: '',
  ai_summary: summary,
  app_name: 'unknown',
  text_content: '',
  extra_images: '[]',
  sync_status: 'SYNCED',
  match_sources: [],
})

const deferred = <T>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((next) => {
    resolve = next
  })
  return { promise, resolve }
}

describe('memories store', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('ignores an older search response that arrives last', async () => {
    const first = deferred<{ memories: Memory[]; query: string; source: string }>()
    const second = deferred<{ memories: Memory[]; query: string; source: string }>()
    apiMocks.search
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise)

    const store = useMemoriesStore()
    const olderRequest = store.search('older')
    const latestRequest = store.search('latest')

    second.resolve({ memories: [memory('latest')], query: 'latest', source: 'all' })
    await latestRequest
    first.resolve({ memories: [memory('older')], query: 'older', source: 'all' })
    await olderRequest

    expect(store.searchQuery).toBe('latest')
    expect(store.memories.map((item) => item.id)).toEqual(['latest'])
  })

  it('preserves the backend relevance order for search results', async () => {
    apiMocks.search.mockResolvedValue({
      memories: [memory('third'), memory('first'), memory('second')],
      query: 'payment',
      source: 'all',
    })

    const store = useMemoriesStore()
    await store.search('payment')

    expect(store.memories.map((item) => item.id)).toEqual(['third', 'first', 'second'])
  })

  it('does not auto-select the first item when a browse result loads', async () => {
    apiMocks.list.mockResolvedValue({ memories: [memory('1')], total: 1 })

    const store = useMemoriesStore()
    await store.load()

    expect(store.memories.map((item) => item.id)).toEqual(['1'])
    expect(store.selectedId).toBeNull()
  })

  it('preserves current search metadata across ordinary websocket-style upserts', async () => {
    const searchResult = {
      ...memory('1'),
      match_sources: ['精确', '语义'],
      search_debug: { mode: 'hybrid' as const, rrf_score: 0.42 },
    }
    apiMocks.search.mockResolvedValue({ memories: [searchResult], query: 'summary', source: 'all' })

    const store = useMemoriesStore()
    await store.search('summary')
    store.upsert({
      ...memory('1', 'updated through websocket'),
      match_sources: [],
      search_debug: null,
    })

    expect(store.memories[0].ai_summary).toBe('updated through websocket')
    expect(store.memories[0].match_sources).toEqual(['精确', '语义'])
    expect(store.memories[0].search_debug?.rrf_score).toBe(0.42)
  })

  it('clears result metadata when returning to browse mode', async () => {
    apiMocks.search.mockResolvedValue({
      memories: [{ ...memory('1'), match_sources: ['精确'] }],
      query: 'summary',
      source: 'all',
    })
    apiMocks.list.mockResolvedValue({
      memories: [{ ...memory('1'), match_sources: ['精确'] }],
      total: 1,
    })

    const store = useMemoriesStore()
    await store.search('summary')
    await store.load()

    expect(store.memories[0].match_sources).toEqual([])
    expect(store.memories[0].search_debug).toBeNull()
  })

  it('shows a newly processing screenshot immediately even while search is active', async () => {
    apiMocks.search.mockResolvedValue({
      memories: [memory('search-result')],
      query: 'payment',
      source: 'all',
    })

    const store = useMemoriesStore()
    await store.search('payment')
    store.upsert({
      ...memory('processing', ''),
      image_path: 'capture.png',
      analysis_status: 'PROCESSING',
      sync_status: 'PENDING',
    })

    expect(store.memories.map((item) => item.id)).toEqual(['processing', 'search-result'])
    expect(store.memories[0].analysis_status).toBe('PROCESSING')
  })

  it('applies the same date and content filters to browse and search requests', async () => {
    apiMocks.list.mockResolvedValue({ memories: [memory('1')], total: 1 })
    apiMocks.search.mockResolvedValue({
      memories: [memory('1')],
      query: 'summary',
      source: 'all',
    })

    const store = useMemoriesStore()
    await store.applyFilters({
      datePreset: 'custom',
      dateFrom: '2026-08-01',
      dateTo: '2026-08-24',
      sourceChannels: [],
      contentTypes: ['text'],
      tagIds: [],
    })

    expect(apiMocks.list).toHaveBeenCalledWith(expect.objectContaining({
      dateFrom: '2026-08-01',
      dateTo: '2026-08-24',
      memoryType: 'text',
    }))

    await store.search('summary')
    expect(apiMocks.search).toHaveBeenCalledWith('summary', 'all', expect.objectContaining({
      dateFrom: '2026-08-01',
      dateTo: '2026-08-24',
      memoryType: 'text',
    }))
  })

  it('does not insert an upserted memory outside the active content filter', async () => {
    const screenshot = { ...memory('1'), memory_type: 'screenshot' as const }
    apiMocks.list.mockResolvedValue({ memories: [screenshot], total: 1 })

    const store = useMemoriesStore()
    await store.applyFilters({
      datePreset: 'all',
      dateFrom: '',
      dateTo: '',
      sourceChannels: [],
      contentTypes: ['screenshot'],
      tagIds: [],
    })
    store.upsert({
      ...memory('text-1'),
      image_path: '',
      memory_type: 'text',
    })

    expect(store.memories.map((item) => item.id)).toEqual(['1'])
    expect(store.total).toBe(1)
  })

  it('does not claim a summary edit removed a selection during an ordinary search change', async () => {
    apiMocks.search
      .mockResolvedValueOnce({ memories: [memory('1')], query: 'first', source: 'all' })
      .mockResolvedValueOnce({ memories: [memory('2')], query: 'second', source: 'all' })

    const store = useMemoriesStore()
    await store.search('first')
    store.select(store.memories[0])
    await store.search('second')

    expect(store.selectedMemory?.id).toBe('1')
    expect(store.selectedOutsideSearch).toBe(false)
  })

  it('keeps the edited memory selected when it leaves the current search', async () => {
    const original = { ...memory('1', 'old summary'), match_sources: ['精确'] }
    apiMocks.search
      .mockResolvedValueOnce({ memories: [original], query: 'old', source: 'all' })
      .mockResolvedValueOnce({ memories: [], query: 'old', source: 'all' })
    apiMocks.updateSummary.mockResolvedValue(memory('1', 'new summary'))

    const store = useMemoriesStore()
    await store.search('old')
    store.select(original)
    await store.updateSummary('1', 'new summary')

    expect(store.memories).toEqual([])
    expect(store.selectedMemory?.ai_summary).toBe('new summary')
    expect(store.selectedOutsideSearch).toBe(true)
    expect(store.selectedMemory?.match_sources).toEqual([])
  })

  it('does not restore an edit-removal notice after a newer user search wins', async () => {
    const staleEditSearch = deferred<{ memories: Memory[]; query: string; source: string }>()
    apiMocks.search
      .mockResolvedValueOnce({ memories: [memory('1')], query: 'old', source: 'all' })
      .mockReturnValueOnce(staleEditSearch.promise)
      .mockResolvedValueOnce({ memories: [memory('2')], query: 'new', source: 'all' })
    apiMocks.updateSummary.mockResolvedValue(memory('1', 'revised summary'))

    const store = useMemoriesStore()
    await store.search('old')
    store.select(store.memories[0])

    const updateRequest = store.updateSummary('1', 'revised summary')
    await vi.waitFor(() => expect(apiMocks.search).toHaveBeenCalledTimes(2))
    store.invalidatePendingRequests()
    await store.search('new')

    staleEditSearch.resolve({ memories: [], query: 'old', source: 'all' })
    await updateRequest

    expect(store.memories.map((item) => item.id)).toEqual(['2'])
    expect(store.selectedMemory?.id).toBe('1')
    expect(store.selectedOutsideSearch).toBe(false)
  })

  it('updateTags merges the returned memory and refreshes the tag catalog', async () => {
    apiMocks.list.mockResolvedValue({ memories: [memory('1')], total: 1 })
    apiMocks.updateTags.mockResolvedValue({
      ...memory('1'),
      tags: [{ id: 1, name: '工作' }],
    })
    apiMocks.listTags.mockResolvedValue({
      tags: [{ id: 1, name: '工作', memory_count: 1 }],
    })

    const store = useMemoriesStore()
    await store.load()
    const updated = await store.updateTags('1', ['工作'])

    expect(apiMocks.updateTags).toHaveBeenCalledWith('1', ['工作'])
    expect(updated?.tags?.map((tag) => tag.name)).toEqual(['工作'])
    expect(store.selectedMemory?.tags?.[0]?.name).toBe('工作')
    await vi.waitFor(() => expect(apiMocks.listTags).toHaveBeenCalledTimes(1))
    expect(store.tags).toEqual([{ id: 1, name: '工作', memory_count: 1 }])
    // 浏览态且无标签筛选：结果集成员不变，无需重跑查询
    expect(apiMocks.list).toHaveBeenCalledTimes(1)
  })

  it('updateTags re-runs the active search so filtered results stay consistent', async () => {
    apiMocks.search.mockResolvedValue({ memories: [memory('1')], query: 'q', source: 'all' })
    apiMocks.updateTags.mockResolvedValue({ ...memory('1'), tags: [] })
    apiMocks.listTags.mockResolvedValue({ tags: [] })

    const store = useMemoriesStore()
    await store.search('q')
    await store.updateTags('1', [])

    expect(apiMocks.search).toHaveBeenCalledTimes(2)
  })

  it('updateTags reloads browse results when the active filter uses tags', async () => {
    apiMocks.list.mockResolvedValue({ memories: [], total: 0 })
    apiMocks.updateTags.mockResolvedValue({ ...memory('1'), tags: [] })
    apiMocks.listTags.mockResolvedValue({ tags: [] })

    const store = useMemoriesStore()
    await store.applyFilters({ ...createEmptyMemoryFilters(), tagIds: [1] })
    await store.updateTags('1', [])

    // applyFilters 一次 + updateTags 触发一次
    expect(apiMocks.list).toHaveBeenCalledTimes(2)
    expect(apiMocks.list).toHaveBeenLastCalledWith(
      expect.objectContaining({ tagIds: [1] }),
    )
  })

  it('updateTags propagates failures without merging anything', async () => {
    apiMocks.list.mockResolvedValue({ memories: [memory('1')], total: 1 })
    apiMocks.updateTags.mockRejectedValue(new Error('network down'))

    const store = useMemoriesStore()
    await store.load()
    await expect(store.updateTags('1', ['工作'])).rejects.toThrow('network down')
    expect(store.entities['1']?.tags).toBeUndefined()
  })

  it('loadTags dedupes concurrent requests and caches the catalog', async () => {
    const pending = deferred<{ tags: Array<{ id: number; name: string; memory_count: number }> }>()
    apiMocks.listTags.mockReturnValue(pending.promise)

    const store = useMemoriesStore()
    const first = store.loadTags()
    const second = store.loadTags()
    pending.resolve({ tags: [{ id: 1, name: '工作', memory_count: 2 }] })
    await Promise.all([first, second])

    expect(apiMocks.listTags).toHaveBeenCalledTimes(1)
    expect(store.tagsLoaded).toBe(true)

    await store.loadTags()
    expect(apiMocks.listTags).toHaveBeenCalledTimes(1)
  })

  it('loadTags keeps the previous catalog when the request fails', async () => {
    apiMocks.listTags.mockRejectedValue(new Error('offline'))

    const store = useMemoriesStore()
    const result = await store.loadTags()

    expect(result).toEqual([])
    expect(store.tags).toEqual([])
    expect(store.tagsLoaded).toBe(false)
  })
})
