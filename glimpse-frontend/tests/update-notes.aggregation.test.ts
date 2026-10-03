import { describe, expect, it } from 'vitest'
import {
  aggregateNotes,
  compareKeys,
  parseIndex,
  parseNotes,
  versionKey,
  type ReleaseNotes,
} from '@/utils/updateNotes'

const release = (version: string, notes: string): ReleaseNotes => ({
  version,
  preview: version.includes('-preview'),
  notes,
  sortKey: versionKey(version)!,
})

describe('versionKey', () => {
  it('builds a numeric key where a stable beats same-base previews', () => {
    expect(compareKeys(versionKey('0.3.2')!, versionKey('0.3.2-preview.20261003')!)).toBe(1)
    expect(compareKeys(versionKey('0.3.3-preview.20261003')!, versionKey('0.3.3-preview.20261002')!)).toBe(1)
    expect(compareKeys(versionKey('0.3.2')!, versionKey('0.3.3')!)).toBe(-1)
  })

  it('throws for malformed versions', () => {
    expect(versionKey('abc')).toBeNull()
    expect(versionKey('0.3.2-dev.1')).toBeNull()
    expect(versionKey('0.3.2+build.1')).toBeNull()
  })
})

describe('parseIndex', () => {
  it('accepts a valid schema-1 index', () => {
    const entries = parseIndex({
      schemaVersion: 1,
      releases: [
        { version: '0.3.2', preview: false, notes: 'a', sortKey: [0, 3, 2, 1, 0, 0] },
        { version: '0.3.3-preview.20261003', preview: true, notes: 'b', sortKey: [0, 3, 3, 0, 20261003, 0] },
      ],
    })
    expect(entries).toHaveLength(2)
    expect(entries[0]!.version).toBe('0.3.2')
  })

  it('rejects wrong schema, duplicates, inconsistent keys and preview flags', () => {
    expect(() => parseIndex({ releases: [] })).toThrow()
    expect(() => parseIndex({ schemaVersion: 2, releases: [] })).toThrow()
    expect(() => parseIndex({
      schemaVersion: 1,
      releases: [{ version: '0.3.2', preview: true, notes: 'a', sortKey: [0, 3, 2, 1, 0, 0] }],
    })).toThrow()
    expect(() => parseIndex({
      schemaVersion: 1,
      releases: [{ version: '0.3.2', preview: false, notes: 'a', sortKey: [0, 3, 2, 1, 0, 1] }],
    })).toThrow()
    expect(() => parseIndex({
      schemaVersion: 1,
      releases: [
        { version: '0.3.2', preview: false, notes: 'a', sortKey: [0, 3, 2, 1, 0, 0] },
        { version: '0.3.2', preview: false, notes: 'a', sortKey: [0, 3, 2, 1, 0, 0] },
      ],
    })).toThrow()
  })
})

describe('parseNotes', () => {
  it('splits the fixed three-section release skeleton', () => {
    const notes = parseNotes([
      '## Glimpse v0.3.2',
      '',
      '**新特性**',
      '- 功能一',
      '**优化**',
      '- 体验一',
      '**修复**',
      '',
      '**Full Changelog**: https://example.com',
    ].join('\n'))
    expect(notes.sections).toEqual({ features: ['功能一'], improvements: ['体验一'], fixes: [] })
    expect(notes.miscellaneous).toEqual([])
  })

  it('keeps unknown bodies as miscellaneous instead of dropping them', () => {
    const notes = parseNotes('自由文本正文，没有小节标题。')
    expect(notes.sections).toEqual({ features: [], improvements: [], fixes: [] })
    expect(notes.miscellaneous).toEqual(['自由文本正文，没有小节标题。'])
  })

  it('returns empty notes for an empty body', () => {
    expect(parseNotes('   \n  ')).toEqual({
      sections: { features: [], improvements: [], fixes: [] },
      miscellaneous: [],
    })
  })
})

describe('aggregateNotes', () => {
  const v032 = release('0.3.2', '**修复**\n- 0.3.2 修复')
  const preview102 = release('0.3.3-preview.20261002', '**新特性**\n- 10.02 功能')
  const preview103 = release('0.3.3-preview.20261003', '**修复**\n- 10.03 修复')
  const v033 = release('0.3.3', '**新特性**\n- 0.3.3 正式功能')
  const preview402 = release('0.3.4-preview.20261002', '**优化**\n- 0.3.4 预览优化')
  const releases = [v032, preview102, preview103, v033, preview402]

  it('counts target version but not current or anything newer', () => {
    const notes = aggregateNotes(releases, '0.3.2', '0.3.3', 'stable')!
    expect(notes.sections.features).toEqual(['0.3.3 正式功能'])
    expect(notes.sections.improvements).toEqual([])
    expect(notes.sections.fixes).toEqual([])
    expect(aggregateNotes(releases, '0.3.3', '0.3.3', 'stable')).toBeNull()
  })

  it('aggregates preview-only channel ranges', () => {
    const notes = aggregateNotes(releases, '0.3.2', '0.3.4-preview.20261002', 'preview')!
    // 0.3.3 正式版在范围内，其内容已覆盖两个高于 0.3.2 的预览——预览条目被剔除。
    expect(notes.sections.features).toEqual(['0.3.3 正式功能'])
    expect(notes.sections.improvements).toEqual(['0.3.4 预览优化'])
    expect(notes.sections.fixes).toEqual([])
  })

  it('drops previews covered by the newest stable inside the range', () => {
    const notes = aggregateNotes(releases, '0.3.2', '0.3.3', 'preview')!
    expect(notes.sections.features).toEqual(['0.3.3 正式功能'])
    expect(notes.sections.fixes).toEqual([])
  })

  it('returns null for a stable target marked as preview or unknown target', () => {
    expect(aggregateNotes(releases, '0.3.2', '0.3.3-preview.20261003', 'stable')).toBeNull()
    expect(aggregateNotes(releases, '0.3.2', '9.9.9', 'stable')).toBeNull()
    expect(aggregateNotes(releases, '9.9.9', '0.3.3', 'stable')).toBeNull()
  })

  it('merges category order and newest-first ordering across mixed range', () => {
    const notes = aggregateNotes(releases, '0.3.3', '0.3.4-preview.20261002', 'preview')!
    // 范围内没有正式版时，预览条目全部保留。
    expect(notes.sections.improvements).toEqual(['0.3.4 预览优化'])
    expect(notes.sections.features).toEqual([])
    expect(notes.sections.fixes).toEqual([])
  })
})
