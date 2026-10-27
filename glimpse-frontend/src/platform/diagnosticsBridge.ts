// 诊断专用桥接：与 platform/desktop.ts 的通用 helper 不同，这里必须拿到明确的
// 成败结果（而不是统一吞成 false/null），且失败提示不走业务 logger，防止递归。
import type { DiagnosticsSinkEvent } from '@/utils/logger'
import { isDesktopShell } from '@/platform/desktop'

// 注入 drain，避免 bridge 反向导入队列模块造成循环依赖。
let drainDiagnostics: (() => Promise<void>) | null = null
export const setDiagnosticsDrain = (drain: () => Promise<void>): void => {
  drainDiagnostics = drain
}

export const appendDiagnosticLogs = async (events: DiagnosticsSinkEvent[]): Promise<boolean> => {
  if (!isDesktopShell() || events.length === 0) return false
  try {
    const module = await import('@tauri-apps/api/core')
    const written = await module.invoke<number>('append_diagnostic_logs', { events })
    return written === events.length
  } catch (error) {
    console.error('[diagnostics] Failed to persist diagnostic logs:', error)
    return false
  }
}

export const getDiagnosticSessionId = async (): Promise<string | null> => {
  if (!isDesktopShell()) return null
  try {
    const module = await import('@tauri-apps/api/core')
    return await module.invoke<string>('diagnostic_session_id')
  } catch (error) {
    console.error('[diagnostics] Failed to read diagnostic session id:', error)
    return null
  }
}

export const openLogsDirectory = async (): Promise<boolean> => {
  if (!isDesktopShell()) return false
  try {
    const module = await import('@tauri-apps/api/core')
    await module.invoke('open_logs_directory')
    return true
  } catch (error) {
    console.error('[diagnostics] Failed to open logs directory:', error)
    return false
  }
}

export const exportDiagnostics = async (): Promise<string | null> => {
  if (!isDesktopShell()) return null
  try {
    const module = await import('@tauri-apps/api/core')
    if (!drainDiagnostics) throw new Error('Diagnostics queue is not initialized')
    await drainDiagnostics()
    return await module.invoke<string>('export_diagnostics')
  } catch (error) {
    console.error('[diagnostics] Failed to export diagnostics bundle:', error)
    return null
  }
}
