import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createNotesLoader, notesIndexUrl, NotesLoaderError } from '@/utils/updateNotes'

const validIndex = {
  schemaVersion: 1,
  releases: [
    { version: '0.3.2', preview: false, notes: '正文', sortKey: [0, 3, 2, 1, 0, 0] },
  ],
}

const okResponse = (body: unknown) => ({ ok: true, status: 200, json: async () => body })

describe('update notes loader', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('deduplicates concurrent calls and caches only successes', async () => {
    fetchMock.mockResolvedValue(okResponse(validIndex))
    const load = createNotesLoader()

    const [first, second] = await Promise.all([load(), load()])
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(first).toEqual(second)

    await load()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('allows retrying after a failure without caching the rejection', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('offline'))
    const load = createNotesLoader()

    await expect(load()).rejects.toBeInstanceOf(NotesLoaderError)
    fetchMock.mockResolvedValue(okResponse(validIndex))
    await expect(load()).resolves.toHaveLength(1)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('classifies HTTP status failures', async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 503, json: async () => ({}) })
    const load = createNotesLoader()

    await expect(load()).rejects.toMatchObject({ kind: 'http_error', status: 503 })
  })

  it('classifies JSON parse failures', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => {
        throw new SyntaxError('Unexpected token <')
      },
    })
    const load = createNotesLoader()

    await expect(load()).rejects.toMatchObject({ kind: 'json_parse' })
  })

  it('classifies schema violations with details', async () => {
    fetchMock.mockResolvedValue(okResponse({ schemaVersion: 2, releases: [] }))
    await expect(createNotesLoader()()).rejects.toMatchObject({
      kind: 'schema',
      detail: 'schema_version',
    })

    fetchMock.mockResolvedValue(okResponse({ schemaVersion: 1, releases: [{ version: 'x' }] }))
    await expect(createNotesLoader()()).rejects.toMatchObject({
      kind: 'schema',
      detail: 'release_invalid',
    })
  })

  it('classifies request timeouts through the abort signal', async () => {
    vi.useFakeTimers()
    fetchMock.mockImplementation((_url: string, init: RequestInit) =>
      new Promise((_resolve, reject) => {
        init.signal?.addEventListener('abort', () => {
          reject(new DOMException('The operation was aborted.', 'AbortError'))
        })
      }),
    )
    const load = createNotesLoader()

    const pending = expect(load()).rejects.toMatchObject({ kind: 'timeout' })
    await vi.advanceTimersByTimeAsync(12_000)
    await pending
    expect(vi.getTimerCount()).toBe(0)
  })

  it('requests the public index without credentials', async () => {
    fetchMock.mockResolvedValue(okResponse(validIndex))
    await createNotesLoader()()

    expect(fetchMock).toHaveBeenCalledWith(
      notesIndexUrl,
      expect.objectContaining({ credentials: 'omit' }),
    )
  })

  it('reports cache phases through the telemetry hook', async () => {
    fetchMock.mockResolvedValue(okResponse(validIndex))
    const phases: string[] = []
    const load = createNotesLoader((event) => phases.push(event.phase))

    const first = load()
    const joined = load()
    await Promise.all([first, joined])
    await load()

    expect(phases).toEqual(['cache_miss', 'inflight_join', 'cache_hit'])
  })
})
