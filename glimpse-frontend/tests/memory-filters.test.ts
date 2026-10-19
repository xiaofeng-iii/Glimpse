import { describe, expect, it } from 'vitest'
import {
  cloneMemoryFilters,
  createEmptyMemoryFilters,
  getActiveMemoryFilterCount,
  hasActiveMemoryFilters,
  memoryMatchesFilters,
  toMemoryFilterQuery,
} from '@/utils/memory-filters'

describe('memory filters: tags', () => {
  it('creates empty filters with no tag selection', () => {
    expect(createEmptyMemoryFilters().tagIds).toEqual([])
  })

  it('clones tag selections by value', () => {
    const filters = { ...createEmptyMemoryFilters(), tagIds: [1, 2] }
    const copy = cloneMemoryFilters(filters)
    expect(copy.tagIds).toEqual([1, 2])
    copy.tagIds.push(3)
    expect(filters.tagIds).toEqual([1, 2])
  })

  it('maps non-empty tag selection into the backend query', () => {
    expect(toMemoryFilterQuery(createEmptyMemoryFilters()).tagIds).toBeUndefined()
    expect(
      toMemoryFilterQuery({ ...createEmptyMemoryFilters(), tagIds: [1, 2] }).tagIds,
    ).toEqual([1, 2])
  })

  it('treats a lone tag selection as an active filter', () => {
    const filters = { ...createEmptyMemoryFilters(), tagIds: [7] }
    expect(hasActiveMemoryFilters(filters)).toBe(true)
    expect(getActiveMemoryFilterCount(filters)).toBe(1)
    expect(hasActiveMemoryFilters(createEmptyMemoryFilters())).toBe(false)
  })

  it('matches tags with OR semantics and ANDs against other groups', () => {
    const memory = {
      created_at: '2026-08-10 12:00:00',
      memory_type: 'screenshot' as const,
      tags: [{ id: 1 }, { id: 2 }],
    }
    const base = createEmptyMemoryFilters()

    // 组内 OR：关联任意一个选中标签即通过
    expect(memoryMatchesFilters(memory, { ...base, tagIds: [3, 2] })).toBe(true)
    expect(memoryMatchesFilters(memory, { ...base, tagIds: [3] })).toBe(false)
    // 空选择不限制标签
    expect(memoryMatchesFilters({ ...memory, tags: [] }, base)).toBe(true)
    // 与其他筛选组之间为 AND
    expect(
      memoryMatchesFilters(memory, { ...base, tagIds: [1], contentTypes: ['text'] }),
    ).toBe(false)
    expect(
      memoryMatchesFilters(memory, { ...base, tagIds: [1], dateFrom: '2026-08-11' }),
    ).toBe(false)
    // 无标签记忆在标签筛选下不通过
    expect(
      memoryMatchesFilters(
        { created_at: '2026-08-10 12:00:00', memory_type: 'screenshot' as const },
        { ...base, tagIds: [1] },
      ),
    ).toBe(false)
  })
})
