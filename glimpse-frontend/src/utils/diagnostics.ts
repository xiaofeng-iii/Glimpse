// 诊断事件落盘编排：宿主会话标识、有界内存队列、批量桥接到 Tauri 宿主。
// 本模块在 main.ts 里最先导入；浏览器开发环境自动退化为仅 console。
import { setDiagnosticsSink, type DiagnosticsSinkEvent } from '@/utils/logger'
import { appendDiagnosticLogs, getDiagnosticSessionId, setDiagnosticsDrain } from '@/platform/diagnosticsBridge'

const MAX_QUEUE = 500
const FLUSH_BATCH = 50
const FLUSH_INTERVAL_MS = 2000

let queue: DiagnosticsSinkEvent[] = []
let flushTimer: ReturnType<typeof window.setTimeout> | null = null
let inFlight: Promise<boolean> | null = null
let droppedCount = 0

// 会话标识由宿主进程生成并共享给 Python sidecar（manifest 里也用它）；
// 浏览器开发环境拿不到宿主，退化为本次页面会话的本地标识。
let sessionId = ''
void getDiagnosticSessionId().then((hostSessionId) => {
  sessionId = hostSessionId ?? createBrowserSessionId()
})

function createBrowserSessionId(): string {
  try {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID()
    }
  } catch {
    // 走随机数回退。
  }
  const bytes = new Uint8Array(16)
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    crypto.getRandomValues(bytes)
  } else {
    for (let i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256)
  }
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
}

const flush = (): Promise<boolean> => {
  if (inFlight) return inFlight
  if (queue.length === 0) return Promise.resolve(true)
  const batch = queue.splice(0, FLUSH_BATCH)
  inFlight = (async () => {
    try {
      if (!(await appendDiagnosticLogs(batch))) throw new Error('Diagnostic batch was not fully persisted')
      return true
    } catch {
      // 优先保留失败批次供下次重试；并发新增事件仍受同一队列上限约束。
      queue = batch.concat(queue)
      if (queue.length > MAX_QUEUE) {
        droppedCount += queue.length - MAX_QUEUE
        queue.length = MAX_QUEUE
      }
      return false
    } finally {
      inFlight = null
      if (queue.length > 0) scheduleFlush()
    }
  })()
  return inFlight
}

export const drainDiagnostics = async (): Promise<void> => {
  const clearTimer = () => {
    if (flushTimer !== null) window.clearTimeout(flushTimer)
    flushTimer = null
  }
  clearTimer()
  while (inFlight || queue.length > 0) {
    const delivered = await flush()
    clearTimer()
    // 本次失败立即结束，避免 drain 无限重试；失败批次留给后续导出。
    if (!delivered) throw new Error('Diagnostic batch was not fully persisted; retry export')
  }
  if (droppedCount > 0) {
    const health: DiagnosticsSinkEvent = {
      v: 1,
      ts: new Date().toISOString(),
      level: 'warning',
      context: 'diagnostics',
      message: 'Diagnostic queue overflow; some events were dropped',
      event: 'diagnostics.queue.dropped',
      data: { dropCount: droppedCount },
    }
    if (!(await appendDiagnosticLogs([health]))) throw new Error('Failed to persist diagnostics health warning')
  }
}
setDiagnosticsDrain(drainDiagnostics)

function scheduleFlush(): void {
  if (flushTimer !== null || queue.length === 0) return
  flushTimer = window.setTimeout(() => {
    flushTimer = null
    void flush()
  }, FLUSH_INTERVAL_MS)
}

setDiagnosticsSink((event) => {
  const enriched: DiagnosticsSinkEvent = sessionId
    ? { ...event, sessionId }
    : event
  if (queue.length >= MAX_QUEUE) {
    queue.shift()
    droppedCount += 1
  }
  queue.push(enriched)
  if (event.level === 'error') {
    if (flushTimer !== null) {
      window.clearTimeout(flushTimer)
      flushTimer = null
    }
    void flush()
    return
  }
  scheduleFlush()
})

// 页面隐藏/退出前尽力冲刷一次；失败批次有界保留，后续可重试。
window.addEventListener('pagehide', () => { void flush() })
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') void flush()
})

// 只统计不可恢复的队列溢出；导出前用健康 warning 写入累计数量。
export const getDiagnosticsDropCount = (): number => droppedCount
