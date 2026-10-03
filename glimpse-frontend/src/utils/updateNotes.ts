export type SortKey = number[]
export interface ReleaseNotes { version: string; preview: boolean; notes: string; sortKey: SortKey }
export interface Notes { sections: Record<'features' | 'improvements' | 'fixes', string[]>; miscellaneous: string[] }
export const notesIndexUrl = 'https://xiaofeng-iii.github.io/Glimpse/updates/index.json'

export function versionKey(version: string): SortKey | null {
  const match = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-preview\.(\d{8})(?:\.(0|[1-9]\d*))?)?$/.exec(version)
  if (!match) return null
  const key = [Number(match[1]), Number(match[2]), Number(match[3]), match[4] ? 0 : 1, Number(match[4] ?? 0), Number(match[5] ?? 0)]
  return key.every(Number.isSafeInteger) ? key : null
}
export function compareKeys(a: SortKey, b: SortKey): number {
  for (let i = 0; i < 6; i++) if (a[i] !== b[i]) return a[i] - b[i]
  return 0
}
export function parseIndex(value: unknown): ReleaseNotes[] {
  if (!value || typeof value !== 'object' || !('schemaVersion' in value) || value.schemaVersion !== 1 || !('releases' in value) || !Array.isArray(value.releases)) throw new Error('Invalid notes index')
  const seen = new Set<string>()
  return value.releases.map((entry: unknown) => {
    if (!entry || typeof entry !== 'object') throw new Error('Invalid release')
    const item = entry as ReleaseNotes
    const key = typeof item.version === 'string' ? versionKey(item.version) : null
    if (!key || typeof item.notes !== 'string' || item.preview !== (key[3] === 0) || !Array.isArray(item.sortKey) || item.sortKey.length !== 6 || !item.sortKey.every(Number.isSafeInteger) || compareKeys(key, item.sortKey) !== 0 || seen.has(item.version)) throw new Error('Invalid release')
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
export function aggregateNotes(releases: ReleaseNotes[], current: string, target: string, channel: 'stable' | 'preview'): Notes | null {
  const lower = releases.find((r) => r.version === current)?.sortKey ?? versionKey(current)
  const upper = releases.find((r) => r.version === target)
  if (!lower || !upper || (channel === 'stable' && upper.preview) || compareKeys(lower, upper.sortKey) >= 0) return null
  let candidates = releases.filter((r) => compareKeys(r.sortKey, lower) > 0 && compareKeys(r.sortKey, upper.sortKey) <= 0 && (channel === 'preview' || !r.preview)).sort((a, b) => compareKeys(b.sortKey, a.sortKey))
  const newestStable = candidates.find((r) => !r.preview)
  if (newestStable) candidates = candidates.filter((r) => !r.preview || compareKeys(r.sortKey, newestStable.sortKey) > 0)
  const result = parseNotes('')
  for (const release of candidates) {
    const parsed = parseNotes(release.notes)
    for (const category of ['features', 'improvements', 'fixes'] as const) result.sections[category].push(...parsed.sections[category])
    result.miscellaneous.push(...parsed.miscellaneous)
  }
  return result
}

// Page-session cache; public fetch never uses the authenticated local API client.
export function createNotesLoader() {
  let pending: Promise<ReleaseNotes[]> | undefined
  return () => pending ??= (async () => {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 12000)
    try {
      const response = await fetch(notesIndexUrl, { credentials: 'omit', signal: controller.signal })
      if (!response.ok) throw new Error('Notes unavailable')
      return parseIndex(await response.json())
    } finally { clearTimeout(timer) }
  })()
}
