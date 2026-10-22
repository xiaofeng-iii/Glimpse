export type SortKey = number[]
export interface ReleaseNotes { version: string; preview: boolean; notes: string; sortKey: SortKey }
export interface Notes { sections: Record<'features' | 'improvements' | 'fixes', string[]>; miscellaneous: string[] }
export const notesIndexUrl = 'https://xiaofeng-iii.github.io/Glimpse/updates/index.json'

// 分类错误：让"部分版本说明获取失败"不再是一个黑盒——超时、网络、HTTP 状态、
// JSON 解析、清单契约各自可辨，诊断日志直接记录 kind/detail/status。
export type NotesFailureKind = 'timeout' | 'network' | 'http_error' | 'json_parse' | 'schema'

export class NotesLoaderError extends Error {
  readonly kind: NotesFailureKind
  readonly status?: number
  readonly detail?: string

  constructor(kind: NotesFailureKind, message: string, extra?: { status?: number; detail?: string }) {
    super(message)
    this.name = 'NotesLoaderError'
    this.kind = kind
    this.status = extra?.status
    this.detail = extra?.detail
  }
}

export function versionKey(version: string): SortKey | null {
  const match = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-preview\.(\d{8})(?:\.(0|[1-9]\d*))?|-beta\.(0|[1-9]\d*))?$/.exec(version)
  if (!match) return null
  const key = [Number(match[1]), Number(match[2]), Number(match[3]), match[4] || match[6] ? 0 : 1, Number(match[4] ?? match[6] ?? 0), Number(match[5] ?? 0)]
  return key.every(Number.isSafeInteger) ? key : null
}
export function compareKeys(a: SortKey, b: SortKey): number {
  for (let i = 0; i < 6; i++) if (a[i] !== b[i]) return a[i] - b[i]
  return 0
}
export function parseIndex(value: unknown): ReleaseNotes[] {
  if (!value || typeof value !== 'object' || !('schemaVersion' in value) || value.schemaVersion !== 1 || !('releases' in value) || !Array.isArray(value.releases)) throw new NotesLoaderError('schema', 'Invalid notes index', { detail: 'schema_version' })
  const seen = new Set<string>()
  return value.releases.map((entry: unknown) => {
    if (!entry || typeof entry !== 'object') throw new NotesLoaderError('schema', 'Invalid release', { detail: 'release_invalid' })
    const item = entry as ReleaseNotes
    const key = typeof item.version === 'string' ? versionKey(item.version) : null
    if (!key || typeof item.notes !== 'string' || item.preview !== (key[3] === 0) || !Array.isArray(item.sortKey) || item.sortKey.length !== 6 || !item.sortKey.every(Number.isSafeInteger) || compareKeys(key, item.sortKey) !== 0 || seen.has(item.version)) throw new NotesLoaderError('schema', 'Invalid release', { detail: 'release_invalid' })
    seen.add(item.version)
    return { version: item.version, preview: item.preview, notes: item.notes, sortKey: item.sortKey }
  })
}
export function parseNotes(body: string): Notes {
  const result: Notes = { sections: { features: [], improvements: [], fixes: [] }, miscellaneous: [] }
  const headings: Record<string, keyof Notes['sections']> = { '新特性': 'features', '优化': 'improvements', '修复': 'fixes' }
  let section: keyof Notes['sections'] | undefined
  let recognized = false
  for (const line of body.replace(/\r\n?/g, '\n').split('\n')) {
    const heading = /^(?:#{1,6}\s+(.+?)\s*#*|\*\*(.+?)\*\*)\s*$/.exec(line.trim())
    if (heading) { section = headings[heading[1] ?? heading[2]]; if (section) recognized = true; continue }
    if (/^\s*(?:\*\*)?Full Changelog\b/i.test(line)) { section = undefined; continue }
    if (section && line.trim()) result.sections[section].push(line.trim().replace(/^[-*+]\s+/, ''))
  }
  if (!recognized && body.trim()) result.miscellaneous.push(body)
  return result
}
export type NotesLoaderTelemetry = {
  phase: 'cache_miss' | 'inflight_join' | 'cache_hit'
}

// Page-session cache; public fetch never uses the authenticated local API client.
// 只缓存成功的结果：网络失败时丢弃 promise，下次调用重新发起请求。
// 若缓存 rejected promise，瞬时断网会把整段会话锁死在失败态，再无重试入口。
export function createNotesLoader(notify?: (event: NotesLoaderTelemetry) => void) {
  let cached: Promise<ReleaseNotes[]> | undefined
  let settled = false
  return (): Promise<ReleaseNotes[]> => {
    if (cached) {
      notify?.({ phase: settled ? 'cache_hit' : 'inflight_join' })
      return cached
    }
    notify?.({ phase: 'cache_miss' })
    const request = (async () => {
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), 12000)
      try {
        // no-cache：index 部署后旧副本可能仍驻留在 WebView 磁盘缓存与 CDN 边缘
        // （max-age=600），条件请求回源的开销极小，换当前版本日志发布后即刻可见。
        const response = await fetch(notesIndexUrl, { credentials: 'omit', cache: 'no-cache', signal: controller.signal })
        if (!response.ok) throw new NotesLoaderError('http_error', `Notes unavailable (HTTP ${response.status})`, { status: response.status })
        let payload: unknown
        try {
          payload = await response.json()
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error)
          throw new NotesLoaderError('json_parse', `Notes index is not valid JSON: ${message}`)
        }
        const entries = parseIndex(payload)
        settled = true
        return entries
      } catch (error) {
        cached = undefined
        if (error instanceof NotesLoaderError) throw error
        if (error instanceof DOMException && error.name === 'AbortError') throw new NotesLoaderError('timeout', 'Notes request timed out after 12s')
        throw new NotesLoaderError('network', 'Notes request failed')
      } finally { clearTimeout(timer) }
    })()
    cached = request
    return request
  }
}
