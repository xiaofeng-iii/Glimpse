// 诊断专用桥接：与 platform/desktop.ts 的通用 helper 不同，这里必须拿到明确的
// 成败结果（而不是统一吞成 false/null），且失败提示不走业务 logger，防止递归。
import type { DiagnosticsSinkEvent } from '@/utils/logger'
import { isDesktopShell } from '@/platform/desktop'

export const appendDiagnosticLogs = async (events: DiagnosticsSinkEvent[]): Promise<boolean> => {
  if (!isDesktopShell() || events.length === 0) return false
  try {
    const module = await import('@tauri-apps/api/core')
    await module.invoke('append_diagnostic_logs', { events })
    return true
  } catch (error) {
    console.error('[diagnostics] Failed to persist diagnostic logs:', error)
    return false
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

export const exportDiagnostics = async (sessionId: string): Promise<string | null> => {
  if (!isDesktopShell()) return null
  try {
    const module = await import('@tauri-apps/api/core')
    return await module.invoke<string>('export_diagnostics', { sessionId })
  } catch (error) {
    console.error('[diagnostics] Failed to export diagnostics bundle:', error)
    return null
  }
}
