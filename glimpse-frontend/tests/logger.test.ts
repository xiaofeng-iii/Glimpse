import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  createLogger,
  getDebugLoggingRemainingMs,
  isDebugLoggingActive,
  redactText,
  setDiagnosticsSink,
  startDebugLogging,
  stopDebugLogging,
  DEBUG_LOG_STORAGE_KEY,
  type DiagnosticsSinkEvent,
} from '@/utils/logger'

type Captured = DiagnosticsSinkEvent[]

const captureSink = (): Captured => {
  const events: Captured = []
  setDiagnosticsSink((event) => events.push(event))
  return events
}

describe('logger', () => {
  let consoleSpy: ReturnType<typeof vi.spyOn>[]
  let events: Captured

  beforeEach(() => {
    window.localStorage.clear()
    stopDebugLogging()
    events = captureSink()
    consoleSpy = [
      vi.spyOn(console, 'info').mockImplementation(() => {}),
      vi.spyOn(console, 'warn').mockImplementation(() => {}),
      vi.spyOn(console, 'error').mockImplementation(() => {}),
      vi.spyOn(console, 'debug').mockImplementation(() => {}),
    ]
  })

  afterEach(() => {
    setDiagnosticsSink(null)
    vi.restoreAllMocks()
  })

  it('serializes Error args into the structured error field without throwing', () => {
    const logger = createLogger('tests/logger')
    const error = new Error('boom')
    logger.error('Failed to load: %s', error)

    expect(events).toHaveLength(1)
    expect(events[0].level).toBe('error')
    expect(events[0].context).toBe('tests/logger')
    expect(events[0].error?.name).toBe('Error')
    expect(events[0].error?.message).toBe('boom')
    expect(typeof events[0].error?.stack).toBe('string')
    // 控制台行同样应包含错误信息而不是 [object Object]。
    expect(consoleSpy[2].mock.calls[0][0]).toContain('boom')
  })

  it('never throws on circular refs, BigInt, or throwing getters', () => {
    const logger = createLogger('tests/logger')
    const circular: Record<string, unknown> = {}
    circular.self = circular
    const hostile = {
      get bomb(): string {
        throw new Error('getter exploded')
      },
    }

    expect(() => logger.warn('circular: %s', circular)).not.toThrow()
    expect(() => logger.warn('bigint: %s', 10n)).not.toThrow()
    expect(() => logger.warn('hostile: %s', hostile)).not.toThrow()
    expect(events.length).toBeGreaterThanOrEqual(3)
  })

  it('redacts credentials and local user paths in messages and args', () => {
    const logger = createLogger('tests/logger')
    const message = 'request failed token=sk-live-1234567890 for C:\\Users\\alice\\secret.png'
    logger.error(message)

    const serialized = JSON.stringify(events[0])
    expect(serialized).not.toContain('sk-live-1234567890')
    expect(serialized).not.toContain('alice')
    expect(serialized).toContain('<redacted-credential>')
    expect(serialized).toContain('<user>')
  })

  it('redacts bearer headers and signed query strings', () => {
    expect(redactText('Authorization: Bearer abc.def.ghi123')).not.toContain('abc.def.ghi123')
    expect(redactText('https://x.io/a?access_token=TOKEN1&b=2')).not.toContain('TOKEN1')
    expect(redactText('https://user:pass@host/path')).not.toContain('user:pass')
  })

  it('drops redacted values when object keys look sensitive', () => {
    const logger = createLogger('tests/logger')
    logger.warn('payload: %s', { api_key: 'super-secret-value', ok: 1 })

    const serialized = JSON.stringify(events[0])
    expect(serialized).not.toContain('super-secret-value')
    expect(serialized).toContain('ok')
  })

  it('emits debug events only while the debug window is active', () => {
    const logger = createLogger('tests/logger')
    logger.debug('before window')
    expect(events).toHaveLength(0)

    startDebugLogging(60_000)
    expect(isDebugLoggingActive()).toBe(true)
    logger.debug('during window')
    expect(events).toHaveLength(1)

    stopDebugLogging()
    logger.debug('after window')
    expect(events).toHaveLength(1)
  })

  it('expires the debug window based on the stored deadline, not a timer', () => {
    startDebugLogging(60_000)
    window.localStorage.setItem(DEBUG_LOG_STORAGE_KEY, String(Date.now() - 1))
    expect(isDebugLoggingActive()).toBe(false)
    expect(getDebugLoggingRemainingMs()).toBe(0)
  })

  it('keeps info level always on and merges child fields into events', () => {
    const logger = createLogger('tests/updates')
    const child = logger.child({ operationId: 'op-1', event: 'updates.notes.ready', outcome: 'success', durationMs: 42 })
    child.info('notes aggregated')

    expect(events).toHaveLength(1)
    expect(events[0].operationId).toBe('op-1')
    expect(events[0].event).toBe('updates.notes.ready')
    expect(events[0].outcome).toBe('success')
    expect(events[0].durationMs).toBe(42)
  })

  it('silently ignores a throwing diagnostics sink', () => {
    setDiagnosticsSink(() => {
      throw new Error('sink exploded')
    })
    const logger = createLogger('tests/logger')
    expect(() => logger.error('still fine')).not.toThrow()
    expect(consoleSpy[2]).toHaveBeenCalled()
  })

  it('caps argument count and truncates long messages', () => {
    const logger = createLogger('tests/logger')
    const long = 'x'.repeat(5000)
    logger.error(long, 1, 2, 3, 4, 5, 6, 7, 8)

    expect(events[0].message.length).toBeLessThanOrEqual(2015)
    expect(events[0].args?.length).toBe(6)
  })
})
