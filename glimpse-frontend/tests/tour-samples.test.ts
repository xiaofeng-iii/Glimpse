import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import {
  injectTourSamples,
  removeTourSamples,
  sweepTourSamples,
  TOUR_SAMPLE_IDS_STORAGE_KEY,
} from '@/utils/tour-samples'
import { completeOnboarding } from '@/utils/onboarding'
import { setLanguagePreference } from '@/utils/i18n'

const apiMocks = vi.hoisted(() => ({
  list: vi.fn(),
  createText: vi.fn(),
  delete: vi.fn(),
  check: vi.fn(),
  load: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  memoriesApi: {
    list: apiMocks.list,
    createText: apiMocks.createText,
    delete: apiMocks.delete,
  },
}))

vi.mock('@/stores/backendStatus', () => ({
  useBackendStatusStore: () => ({ check: apiMocks.check }),
}))

vi.mock('@/stores/memories', () => ({
  useMemoriesStore: () => ({ load: apiMocks.load }),
}))

vi.mock('@/config/runtime', () => ({
  whenBackendRuntimeReady: vi.fn().mockResolvedValue(undefined),
}))

const seedSampleIds = (ids: string[]) => {
  window.localStorage.setItem(TOUR_SAMPLE_IDS_STORAGE_KEY, JSON.stringify(ids))
}

describe('tour samples', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    setActivePinia(createPinia())
    setLanguagePreference('zh-CN')
    apiMocks.check.mockResolvedValue(true)
  })

  it('injects four samples into an empty library and records their ids', async () => {
    apiMocks.list.mockResolvedValue({ memories: [], total: 0 })
    apiMocks.createText.mockImplementation(async () => ({
      id: `sample-${apiMocks.createText.mock.calls.length}`,
    }))

    await injectTourSamples()

    expect(apiMocks.createText).toHaveBeenCalledTimes(4)
    expect(window.localStorage.getItem(TOUR_SAMPLE_IDS_STORAGE_KEY)).toBe(
      JSON.stringify(['sample-1', 'sample-2', 'sample-3', 'sample-4']),
    )
    expect(apiMocks.load).toHaveBeenCalledTimes(1)
  })

  it('skips injection when the library already has memories (dev replay path)', async () => {
    apiMocks.list.mockResolvedValue({ memories: [{ id: 'user-1' }], total: 1 })

    await injectTourSamples()

    expect(apiMocks.createText).not.toHaveBeenCalled()
    expect(window.localStorage.getItem(TOUR_SAMPLE_IDS_STORAGE_KEY)).toBeNull()
    expect(apiMocks.load).not.toHaveBeenCalled()
  })

  it('gives up silently when the backend never becomes ready', async () => {
    apiMocks.check.mockResolvedValue(false)
    vi.useFakeTimers()

    const injection = injectTourSamples()
    await vi.advanceTimersByTimeAsync(31_000)
    await injection

    expect(apiMocks.list).not.toHaveBeenCalled()
    expect(apiMocks.createText).not.toHaveBeenCalled()
  })

  it('removes recorded samples and clears storage, tolerating 404s', async () => {
    seedSampleIds(['a', 'b'])
    apiMocks.delete.mockRejectedValueOnce({ response: { status: 404 } })

    await removeTourSamples()

    expect(apiMocks.delete).toHaveBeenCalledTimes(2)
    expect(window.localStorage.getItem(TOUR_SAMPLE_IDS_STORAGE_KEY)).toBeNull()
    expect(apiMocks.load).toHaveBeenCalledTimes(1)
  })

  it('keeps ids for the next sweep when a delete fails beyond 404', async () => {
    seedSampleIds(['a', 'b'])
    apiMocks.delete.mockRejectedValueOnce(new Error('backend offline'))

    await removeTourSamples()

    expect(window.localStorage.getItem(TOUR_SAMPLE_IDS_STORAGE_KEY)).toBe(
      JSON.stringify(['a', 'b']),
    )
  })

  it('sweeps leftovers only when the tour will not replay', async () => {
    seedSampleIds(['a'])
    await sweepTourSamples()
    expect(apiMocks.delete).not.toHaveBeenCalled()

    seedSampleIds(['a'])
    completeOnboarding()
    await sweepTourSamples()
    expect(apiMocks.delete).toHaveBeenCalledWith('a')
    expect(window.localStorage.getItem(TOUR_SAMPLE_IDS_STORAGE_KEY)).toBeNull()
  })
})
