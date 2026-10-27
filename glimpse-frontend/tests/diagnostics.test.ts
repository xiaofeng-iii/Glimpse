import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { invoke } = vi.hoisted(() => ({ invoke: vi.fn() }))
vi.mock('@tauri-apps/api/core', () => ({ invoke }))
vi.mock('@/platform/desktop', () => ({ isDesktopShell: () => true }))

let logger: ReturnType<(typeof import('@/utils/logger'))['createLogger']>
let bridge: typeof import('@/platform/diagnosticsBridge')
let diagnostics: typeof import('@/utils/diagnostics')

beforeEach(async () => {
  vi.resetModules()
  vi.useFakeTimers()
  invoke.mockReset().mockImplementation(async (command, args) => {
    if (command === 'diagnostic_session_id') return 'host-session'
    if (command === 'append_diagnostic_logs') return args.events.length
    return 'bundle.zip'
  })
  vi.spyOn(console, 'info').mockImplementation(() => {})
  vi.spyOn(console, 'error').mockImplementation(() => {})
  diagnostics = await import('@/utils/diagnostics')
  bridge = await import('@/platform/diagnosticsBridge')
  logger = (await import('@/utils/logger')).createLogger('test')
})
afterEach(() => {
  vi.clearAllTimers()
  vi.useRealTimers()
  vi.restoreAllMocks()
})

const writes = () => invoke.mock.calls.filter(([command]) => command === 'append_diagnostic_logs')

describe('diagnostics export drain', () => {
  it('awaits every queued batch before exporting', async () => {
    for (let i = 0; i < 121; i++) logger.info(`event-${i}`)
    expect(await bridge.exportDiagnostics()).toBe('bundle.zip')
    expect(writes().map(([, args]) => args.events.length)).toEqual([50, 50, 21])
    expect(invoke.mock.calls.at(-1)?.[0]).toBe('export_diagnostics')
    expect(vi.getTimerCount()).toBe(0)
  })

  it('awaits an inflight batch and events added during the write', async () => {
    let release!: (count: number) => void
    invoke.mockImplementationOnce(() => new Promise<number>((resolve) => { release = resolve }))
    logger.error('early')
    await vi.waitFor(() => expect(writes()).toHaveLength(1))
    for (let i = 0; i < 60; i++) logger.info(`later-${i}`)
    let done = false
    const exported = bridge.exportDiagnostics().then((result) => { done = true; return result })
    await Promise.resolve()
    expect(done).toBe(false)
    expect(invoke.mock.calls.some(([command]) => command === 'export_diagnostics')).toBe(false)
    release(1)
    expect(await exported).toBe('bundle.zip')
    expect(writes().map(([, args]) => args.events.length)).toEqual([1, 50, 10])
    expect(invoke.mock.calls.at(-1)?.[0]).toBe('export_diagnostics')
  })

  it.each(['reject', 'partial'])('does not export after a %s write failure', async (failure) => {
    invoke.mockImplementation(async (command) => {
      if (command === 'append_diagnostic_logs') {
        if (failure === 'reject') throw new Error('disk full')
        return 0
      }
      return 'bundle.zip'
    })
    logger.info('must persist')
    expect(await bridge.exportDiagnostics()).toBeNull()
    expect(diagnostics.getDiagnosticsDropCount()).toBe(0)
    expect(writes()).toHaveLength(1)
    expect(invoke.mock.calls.some(([command]) => command === 'export_diagnostics')).toBe(false)
    invoke.mockImplementation(async (command, args) => command === 'append_diagnostic_logs' ? args.events.length : 'bundle.zip')
    expect(await bridge.exportDiagnostics()).toBe('bundle.zip')
    expect(writes()).toHaveLength(2)
    expect(writes()[1][1].events).toEqual(writes()[0][1].events)
    expect(invoke.mock.calls.at(-1)?.[0]).toBe('export_diagnostics')
  })

  it('exports after overflow with a persisted drop-count warning', async () => {
    for (let i = 0; i < 510; i++) logger.info(`event-${i}`)
    expect(diagnostics.getDiagnosticsDropCount()).toBe(10)
    expect(await bridge.exportDiagnostics()).toBe('bundle.zip')
    const events = writes().flatMap(([, args]) => args.events)
    expect(events).toHaveLength(501)
    expect(events.at(-1)).toMatchObject({
      level: 'warning', event: 'diagnostics.queue.dropped', data: { dropCount: 10 },
    })
    expect(invoke.mock.calls.at(-1)?.[0]).toBe('export_diagnostics')
  })

  it('bounds the retained failed batch while new events arrive and permits retry', async () => {
    let release!: (count: number) => void
    invoke.mockImplementationOnce(() => new Promise<number>((resolve) => { release = resolve }))
    logger.error('failed batch must survive')
    await vi.waitFor(() => expect(writes()).toHaveLength(1))
    for (let i = 0; i < 500; i++) logger.info(`later-${i}`)
    expect(diagnostics.getDiagnosticsDropCount()).toBe(1)
    const first = bridge.exportDiagnostics()
    await vi.dynamicImportSettled()
    release(0)
    expect(await first).toBeNull()
    expect(await bridge.exportDiagnostics()).toBe('bundle.zip')
    const retried = writes().slice(1).flatMap(([, args]) => args.events)
    expect(retried).toHaveLength(501)
    expect(retried[0].message).toContain('failed batch must survive')
    expect(retried.at(-1).data).toEqual({ dropCount: 1 })
    expect(retried.filter((event) => event.message === 'later-499')).toHaveLength(1)
  })

  it('retains the complete failed batch after the queue fills during a write', async () => {
    let reject!: (error: Error) => void
    invoke.mockImplementationOnce(() => new Promise<number>((_resolve, fail) => { reject = fail }))
    for (let i = 0; i < 50; i++) logger.info(`failed-${i}`)
    logger.error('start')
    await vi.waitFor(() => expect(writes()).toHaveLength(1))
    for (let i = 0; i < 450; i++) logger.info(`later-${i}`)
    expect(diagnostics.getDiagnosticsDropCount()).toBe(1)
    reject(new Error('write failed'))
    await vi.dynamicImportSettled()
    expect(await bridge.exportDiagnostics()).toBe('bundle.zip')
    const events = writes().slice(1).flatMap(([, args]) => args.events)
    expect(events).toHaveLength(501)
    expect(events.filter((event) => event.message === 'failed-49')).toHaveLength(1)
    expect(events.filter((event) => event.message === 'later-449')).toHaveLength(1)
    expect(diagnostics.getDiagnosticsDropCount()).toBe(1)
  })

  it('flushes every batch immediately for errors and page hiding', async () => {
    for (let i = 0; i < 51; i++) logger.info(`event-${i}`)
    logger.error('last error')
    await vi.waitFor(() => expect(writes().map(([, args]) => args.events.length)).toEqual([50, 2]))

    for (let i = 0; i < 120; i++) logger.info(`hidden-${i}`)
    window.dispatchEvent(new Event('pagehide'))
    await vi.waitFor(() => expect(writes().slice(2).map(([, args]) => args.events.length)).toEqual([50, 50, 20]))
  })

  it('reports a failed inflight write rather than silently exporting', async () => {
    let reject!: (error: Error) => void
    invoke.mockImplementationOnce(() => new Promise<number>((_resolve, fail) => { reject = fail }))
    logger.error('flush immediately')
    await vi.waitFor(() => expect(writes()).toHaveLength(1))
    const exported = bridge.exportDiagnostics()
    await vi.dynamicImportSettled()
    reject(new Error('write failed'))
    expect(await exported).toBeNull()
    expect(invoke.mock.calls.some(([command]) => command === 'export_diagnostics')).toBe(false)
  })
})
