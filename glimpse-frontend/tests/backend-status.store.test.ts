import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import {
  BACKEND_STARTUP_GRACE_PERIOD_MS,
  useBackendStatusStore,
} from '@/stores/backendStatus'

const apiMocks = vi.hoisted(() => ({
  checkHealth: vi.fn(),
}))

vi.mock('@/api/client', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/api/client')>()
  return {
    ...original,
    healthApi: {
      check: apiMocks.checkHealth,
    },
  }
})

const connectionFailure = () => Object.assign(new Error('Network Error'), {
  isAxiosError: true,
  response: undefined,
})

describe('backend status store', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-08-22T00:00:00Z'))
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('keeps cold-start connection failures in starting state, then treats a later outage as an error', async () => {
    const store = useBackendStatusStore()
    expect(store.state).toBe('starting')
    expect(store.isStarting).toBe(true)

    apiMocks.checkHealth.mockRejectedValueOnce(connectionFailure())
    await expect(store.check()).resolves.toBe(false)
    expect(store.state).toBe('starting')

    apiMocks.checkHealth.mockResolvedValueOnce({ status: 'healthy' })
    await expect(store.check()).resolves.toBe(true)
    expect(store.state).toBe('ready')

    apiMocks.checkHealth.mockRejectedValueOnce(connectionFailure())
    await expect(store.check()).resolves.toBe(false)
    expect(store.state).toBe('offline')

    apiMocks.checkHealth.mockResolvedValueOnce({ status: 'healthy' })
    await expect(store.check()).resolves.toBe(true)
    expect(store.state).toBe('ready')
  })

  it('treats an explicit unhealthy response as an error even during cold start', async () => {
    apiMocks.checkHealth.mockResolvedValueOnce({ status: 'unhealthy' })
    const store = useBackendStatusStore()

    await expect(store.check()).resolves.toBe(false)
    expect(store.state).toBe('offline')

    apiMocks.checkHealth.mockRejectedValueOnce(connectionFailure())
    await expect(store.check()).resolves.toBe(false)
    expect(store.state).toBe('offline')
  })

  it('treats an unexpected check failure as an error during cold start', async () => {
    apiMocks.checkHealth.mockRejectedValueOnce(new Error('unexpected parser failure'))
    const store = useBackendStatusStore()

    await expect(store.check()).resolves.toBe(false)
    expect(store.state).toBe('offline')
  })

  it('turns an unresponsive cold start into an error after the grace period', async () => {
    const store = useBackendStatusStore()
    vi.advanceTimersByTime(BACKEND_STARTUP_GRACE_PERIOD_MS)
    apiMocks.checkHealth.mockRejectedValueOnce(connectionFailure())

    await expect(store.check()).resolves.toBe(false)
    expect(store.state).toBe('offline')
  })

  it('reuses an in-flight health request for concurrent checks', async () => {
    let resolveHealth: ((value: { status: string }) => void) | null = null
    apiMocks.checkHealth.mockReturnValueOnce(new Promise((resolve) => {
      resolveHealth = resolve
    }))
    const store = useBackendStatusStore()

    const first = store.check()
    const second = store.check()
    expect(apiMocks.checkHealth).toHaveBeenCalledTimes(1)

    resolveHealth?.({ status: 'healthy' })
    await expect(Promise.all([first, second])).resolves.toEqual([true, true])
    expect(store.state).toBe('ready')
  })
})
