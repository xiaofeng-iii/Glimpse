export const MATCH_SOURCE_ORDER = ['exact', 'semantic'] as const

export type MatchSourceKind = typeof MATCH_SOURCE_ORDER[number]

const MATCH_SOURCE_PROTOCOL: Record<MatchSourceKind, string> = {
  exact: '精确',
  semantic: '语义',
}

export const getMatchSourceKinds = (
  matchSources?: readonly string[] | null,
): MatchSourceKind[] => {
  const sources = new Set(matchSources ?? [])
  return MATCH_SOURCE_ORDER.filter((kind) => sources.has(MATCH_SOURCE_PROTOCOL[kind]))
}
