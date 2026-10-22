// 诊断事件落盘编排：启动会话标识、有界内存队列、批量桥接到 Tauri 宿主。
// 本模块在 main.ts 里最先导入；浏览器开发环境自动退化为仅 console。
import { setDiagnosticsSink, type DiagnosticsSinkEvent } from '@/utils/logger'
import { appendDiagnosticLogs } from '@/platform/diagnosticsBridge'

function createSessionId(): string {
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

// 每次前端启动生成一次；只活在内存里，不持久化、不参与任何设置保存。
export const diagnosticsSessionId = createSessionId()

const MAX_QUEUE = 500
const FLUSH_BATCH = 50
const FLUSH_INTERVAL_MS = 2000

let queue: DiagnosticsSinkEvent[] = []
let flushTimer: ReturnType<typeof window.setTimeout> | null = null
let flushing = false
let droppedCount = 0

const flush = async (): Promise<void> => {
  if (flushing || queue.length === 0) return
  flushing = true
  const batch = queue.splice(0, FLUSH_BATCH)
  try {
    const delivered = await appendDiagnosticLogs(batch)
    if (!delivered) droppedCount += batch.length
  } finally {
    flushing = false
    if (queue.length > 0) scheduleFlush()
  }
}

function scheduleFlush(): void {
  if (flushTimer !== null || queue.length === 0) return
  flushTimer = window.setTimeout(() => {
    flushTimer = null
    void flush()
  }, FLUSH_INTERVAL_MS)
}

setDiagnosticsSink((event) => {
  const enriched: DiagnosticsSinkEvent = { ...event, sessionId: diagnosticsSessionId }
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

// 页面隐藏/退出前尽力冲刷一次；失败即丢，不重试。
window.addEventListener('pagehide', () => { void flush() })
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') void flush()
})

// 诊断自身的健康状况：桥接失败或队列溢出时丢了多少条，导出诊断包时可附带。
export const getDiagnosticsDropCount = (): number => droppedCount
