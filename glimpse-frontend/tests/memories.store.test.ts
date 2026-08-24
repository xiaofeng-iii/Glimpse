import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { Memory } from '@/api/client'

const apiMocks = vi.hoisted(() => ({
  list: vi.fn(),
  search: vi.fn(),
  updateSummary: vi.fn(),
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
      delete: apiMocks.delete,
    },
    searchApi: {
      ...original.searchApi,
      search: apiMocks.search,
    },
  }
})

import { useMemoriesStore } from '@/stores/memories'

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
})
