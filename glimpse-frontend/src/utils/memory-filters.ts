export type MemoryDatePreset = 'all' | 'today' | 'last7Days' | 'last30Days' | 'custom'
export type MemoryContentType = 'screenshot' | 'text'

export interface MemoryFilters {
  datePreset: MemoryDatePreset
  dateFrom: string
  dateTo: string
  sourceChannels: string[]
  contentTypes: MemoryContentType[]
  /** 选中的标签 ID 集合；组内为 OR，与其他筛选组之间为 AND。 */
  tagIds: number[]
}

export interface MemoryFilterQuery {
  dateFrom?: string
  dateTo?: string
  memoryType?: MemoryContentType
  tagIds?: number[]
}

const effectiveContentType = (contentTypes: MemoryContentType[]) => {
  const unique = Array.from(new Set(contentTypes))
  return unique.length === 1 ? unique[0] : undefined
}

export const toDateInputValue = (date: Date) => {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export const createEmptyMemoryFilters = (): MemoryFilters => ({
  datePreset: 'all',
  dateFrom: '',
  dateTo: '',
  sourceChannels: [],
  contentTypes: [],
  tagIds: [],
})

export const cloneMemoryFilters = (filters: MemoryFilters): MemoryFilters => ({
  ...filters,
  sourceChannels: [...filters.sourceChannels],
  contentTypes: [...filters.contentTypes],
  tagIds: [...filters.tagIds],
})

export const toMemoryFilterQuery = (filters: MemoryFilters): MemoryFilterQuery => ({
  dateFrom: filters.dateFrom || undefined,
  dateTo: filters.dateTo || undefined,
  memoryType: effectiveContentType(filters.contentTypes),
  tagIds: filters.tagIds.length ? [...filters.tagIds] : undefined,
})

export const memoryMatchesFilters = (
  memory: {
    created_at: string
    memory_type?: MemoryContentType
    tags?: Array<{ id: number }>
  },
  filters: MemoryFilters,
) => {
  const contentType = effectiveContentType(filters.contentTypes)
  if (contentType && (memory.memory_type ?? 'screenshot') !== contentType) return false

  const memoryDate = memory.created_at.trim().slice(0, 10)
  if (filters.dateFrom && memoryDate < filters.dateFrom) return false
  if (filters.dateTo && memoryDate > filters.dateTo) return false

  // 标签组内 OR：记忆关联任意一个选中标签即通过；未选标签则不限制。
  if (filters.tagIds.length) {
    const memoryTagIds = (memory.tags ?? []).map((tag) => tag.id)
    if (!filters.tagIds.some((tagId) => memoryTagIds.includes(tagId))) return false
  }
  return true
}

export const hasActiveMemoryFilters = (filters: MemoryFilters) => Boolean(
  filters.dateFrom
  || filters.dateTo
  || filters.sourceChannels.length
  || filters.contentTypes.length
  || filters.tagIds.length,
)

export const getActiveMemoryFilterCount = (filters: MemoryFilters) => [
  Boolean(filters.dateFrom || filters.dateTo),
  filters.sourceChannels.length > 0,
  filters.contentTypes.length > 0,
  filters.tagIds.length > 0,
].filter(Boolean).length
