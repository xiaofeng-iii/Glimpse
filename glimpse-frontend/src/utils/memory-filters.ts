export type MemoryDatePreset = 'all' | 'today' | 'last7Days' | 'last30Days' | 'custom'

export interface MemoryFilters {
  datePreset: MemoryDatePreset
  dateFrom: string
  dateTo: string
  sourceChannels: string[]
  contentTypes: string[]
}

export interface MemoryFilterQuery {
  dateFrom?: string
  dateTo?: string
}

const toDateInputValue = (date: Date) => {
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
})

export const cloneMemoryFilters = (filters: MemoryFilters): MemoryFilters => ({
  ...filters,
  sourceChannels: [...filters.sourceChannels],
  contentTypes: [...filters.contentTypes],
})

export const resolveMemoryDatePreset = (
  preset: Exclude<MemoryDatePreset, 'custom'>,
  now = new Date(),
): Pick<MemoryFilters, 'datePreset' | 'dateFrom' | 'dateTo'> => {
  if (preset === 'all') {
    return { datePreset: preset, dateFrom: '', dateTo: '' }
  }

  const end = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const start = new Date(end)
  if (preset === 'last7Days') start.setDate(start.getDate() - 6)
  if (preset === 'last30Days') start.setDate(start.getDate() - 29)

  return {
    datePreset: preset,
    dateFrom: toDateInputValue(start),
    dateTo: toDateInputValue(end),
  }
}

export const toMemoryFilterQuery = (filters: MemoryFilters): MemoryFilterQuery => ({
  dateFrom: filters.dateFrom || undefined,
  dateTo: filters.dateTo || undefined,
})

export const hasActiveMemoryFilters = (filters: MemoryFilters) => Boolean(
  filters.dateFrom
  || filters.dateTo
  || filters.sourceChannels.length
  || filters.contentTypes.length,
)

export const getActiveMemoryFilterCount = (filters: MemoryFilters) => [
  Boolean(filters.dateFrom || filters.dateTo),
  filters.sourceChannels.length > 0,
  filters.contentTypes.length > 0,
].filter(Boolean).length
