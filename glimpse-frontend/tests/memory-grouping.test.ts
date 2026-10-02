import { beforeEach, describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import type { Memory } from '@/api/client'
import MemoryCalendarPicker from '@/components/MemoryCalendarPicker.vue'
import WallLayoutSwitcher from '@/components/WallLayoutSwitcher.vue'
import { setLanguagePreference } from '@/utils/i18n'
import {
  buildMonthGrid,
  describeMemoryPeriod,
  groupMemories,
  weekdayLabels,
} from '@/utils/memory-grouping'
import { createEmptyMemoryFilters, type MemoryFilters } from '@/utils/memory-filters'
import { setWallLayoutMode, wallLayoutMode } from '@/utils/wall-layout'

const createMemory = (id: string, created_at: string): Memory => ({
  id,
  created_at,
  image_path: '',
  ai_summary: id,
  app_name: '',
  sync_status: 'SYNCED',
  match_sources: [],
})

describe('memory wall layout & grouping', () => {
  beforeEach(() => {
    setLanguagePreference('zh-CN')
    setWallLayoutMode('day')
  })

  describe('groupMemories', () => {
    const now = new Date(2026, 9, 2) // 2026-10-02

    it('按日期模式：今天/昨天/今年内/往年', () => {
      const groups = groupMemories([
        createMemory('a', '2026-10-02T09:00:00'),
        createMemory('b', '2026-10-02T08:00:00'),
        createMemory('c', '2026-10-01T23:00:00'),
        createMemory('d', '2026-09-28T10:00:00'),
        createMemory('e', '2025-12-31T10:00:00'),
      ], 'day', 'zh-CN', now)

      expect(groups.map((group) => group.label)).toEqual(['今天', '昨天', '9月28日', '2025年12月31日'])
      expect(groups[0]!.memories.map((memory) => memory.id)).toEqual(['a', 'b'])
    })

    it('按月份模式：同月合组、跨年分组并带年份', () => {
      const groups = groupMemories([
        createMemory('a', '2026-10-02T09:00:00'),
        createMemory('b', '2026-10-15T09:00:00'),
        createMemory('c', '2025-12-31T09:00:00'),
      ], 'month', 'zh-CN', now)

      expect(groups.map((group) => group.key)).toEqual(['2026-10', '2025-12'])
      expect(groups.map((group) => group.label)).toEqual(['2026年10月', '2025年12月'])
    })

    it('全部模式：单组无标题', () => {
      const memories = [
        createMemory('a', '2026-10-02T09:00:00'),
        createMemory('b', '2025-01-01T09:00:00'),
      ]
      const groups = groupMemories(memories, 'all', 'zh-CN', now)

      expect(groups).toHaveLength(1)
      expect(groups[0]!.label).toBe('')
      expect(groups[0]!.memories).toEqual(memories)
    })
  })

  describe('describeMemoryPeriod', () => {
    it('单日', () => {
      expect(describeMemoryPeriod('2026-08-14', '2026-08-14', 'zh-CN')).toBe('2026年8月14日')
    })

    it('整月', () => {
      expect(describeMemoryPeriod('2026-08-01', '2026-08-31', 'zh-CN')).toBe('2026年8月')
    })

    it('同月部分区间 → 完整日期区间', () => {
      const label = describeMemoryPeriod('2026-08-03', '2026-08-20', 'zh-CN')
      expect(label).toContain('2026年8月3日')
      expect(label).toContain('2026年8月20日')
      expect(label).toContain('至')
    })

    it('跨月区间', () => {
      const label = describeMemoryPeriod('2026-08-30', '2026-09-02', 'zh-CN')
      expect(label).toContain('2026年8月30日')
      expect(label).toContain('2026年9月2日')
    })

    it('无日期 → 最近', () => {
      expect(describeMemoryPeriod('', '', 'zh-CN')).toBe('最近')
    })
  })

  describe('buildMonthGrid', () => {
    const now = new Date(2026, 9, 15) // 2026-10-15

    it('周一开头：2026年10月首格为 9-28，共 5 周', () => {
      const grid = buildMonthGrid(2026, 9, true, 'zh-CN', { now })
      expect(grid).toHaveLength(5)
      expect(grid[0]![0]!.dateStr).toBe('2026-09-28')
      expect(grid[4]![6]!.dateStr).toBe('2026-11-01')
    })

    it('周日开头：首格为 9-27', () => {
      const grid = buildMonthGrid(2026, 9, false, 'zh-CN', { now })
      expect(grid[0]![0]!.dateStr).toBe('2026-09-27')
    })

    it('未来日与邻月日禁用，历史当日可选', () => {
      const cells = buildMonthGrid(2026, 9, true, 'zh-CN', { now }).flat()
      const byDate = new Map(cells.map((cell) => [cell.dateStr, cell]))
      expect(byDate.get('2026-10-20')!.disabled).toBe(true)
      expect(byDate.get('2026-10-10')!.disabled).toBe(false)
      expect(byDate.get('2026-09-28')!.disabled).toBe(true)
      expect(byDate.get('2026-10-15')!.isToday).toBe(true)
    })

    it('区间高亮与端点', () => {
      const cells = buildMonthGrid(2026, 9, true, 'zh-CN', {
        dateFrom: '2026-10-10',
        dateTo: '2026-10-12',
        now,
      }).flat()
      const byDate = new Map(cells.map((cell) => [cell.dateStr, cell]))
      expect(byDate.get('2026-10-11')!.inRange).toBe(true)
      expect(byDate.get('2026-10-11')!.isEndpoint).toBe(false)
      expect(byDate.get('2026-10-10')!.isEndpoint).toBe(true)
    })
  })

  it('weekdayLabels 提供一周标签', () => {
    expect(weekdayLabels('zh-CN', true)[0]).toBe('周一')
    expect(weekdayLabels('en-US', false)[0]).toBe('Sun')
  })

  describe('WallLayoutSwitcher', () => {
    it('点击切换模式并写入 localStorage', async () => {
      const wrapper = mount(WallLayoutSwitcher)
      const buttons = wrapper.findAll('button')
      expect(buttons).toHaveLength(3)
      await buttons[1]!.trigger('click')
      expect(wallLayoutMode.value).toBe('month')
      expect(window.localStorage.getItem('glimpse.wallLayout')).toBe('month')
    })

    it('搜索期间整体禁用', () => {
      const wrapper = mount(WallLayoutSwitcher, { props: { disabled: true } })
      for (const button of wrapper.findAll('button')) {
        expect(button.attributes('disabled')).toBeDefined()
      }
    })
  })

  describe('MemoryCalendarPicker', () => {
    const now = new Date(2026, 9, 15) // 2026-10-15

    const mountCalendar = (filters: MemoryFilters) =>
      mount(MemoryCalendarPicker, { props: { filters, now } })

    const cell = (wrapper: ReturnType<typeof mountCalendar>, date: string) =>
      wrapper.find(`[data-date="${date}"]`)

    const pointerPick = async (
      wrapper: ReturnType<typeof mountCalendar>,
      date: string,
    ) => {
      await cell(wrapper, date).trigger('pointerdown')
      window.dispatchEvent(new Event('pointerup'))
      await flushPromises()
    }

    it('默认单击选中单日', async () => {
      const wrapper = mountCalendar(createEmptyMemoryFilters())
      await pointerPick(wrapper, '2026-10-10')
      expect(wrapper.emitted('apply')![0]![0]).toMatchObject({
        datePreset: 'custom',
        dateFrom: '2026-10-10',
        dateTo: '2026-10-10',
      })
    })

    it('按住拖动框选区间', async () => {
      const wrapper = mountCalendar(createEmptyMemoryFilters())
      await cell(wrapper, '2026-10-08').trigger('pointerdown')
      await cell(wrapper, '2026-10-12').trigger('pointerenter')
      window.dispatchEvent(new Event('pointerup'))
      await flushPromises()
      expect(wrapper.emitted('apply')![0]![0]).toMatchObject({
        dateFrom: '2026-10-08',
        dateTo: '2026-10-12',
      })
    })

    it('范围模式两次点选起止并自动归一', async () => {
      const wrapper = mountCalendar(createEmptyMemoryFilters())
      await wrapper.find('.memory-calendar__mode-input').setValue(true)
      await cell(wrapper, '2026-10-12').trigger('pointerdown')
      expect(wrapper.emitted('apply')).toBeUndefined()
      await cell(wrapper, '2026-10-14').trigger('pointerdown')
      expect(wrapper.emitted('apply')![0]![0]).toMatchObject({
        dateFrom: '2026-10-12',
        dateTo: '2026-10-14',
      })
      await cell(wrapper, '2026-10-05').trigger('pointerdown')
      await cell(wrapper, '2026-10-02').trigger('pointerdown')
      expect(wrapper.emitted('apply')![1]![0]).toMatchObject({
        dateFrom: '2026-10-02',
        dateTo: '2026-10-05',
      })
    })

    it('范围模式点同一天两次 = 单日', async () => {
      const wrapper = mountCalendar(createEmptyMemoryFilters())
      await wrapper.find('.memory-calendar__mode-input').setValue(true)
      await cell(wrapper, '2026-10-10').trigger('pointerdown')
      await cell(wrapper, '2026-10-10').trigger('pointerdown')
      expect(wrapper.emitted('apply')![0]![0]).toMatchObject({
        dateFrom: '2026-10-10',
        dateTo: '2026-10-10',
      })
    })

    it('未来日期不可选', async () => {
      const wrapper = mountCalendar(createEmptyMemoryFilters())
      await cell(wrapper, '2026-10-20').trigger('pointerdown')
      window.dispatchEvent(new Event('pointerup'))
      await flushPromises()
      expect(wrapper.emitted('apply')).toBeUndefined()
    })

    it('键盘触发（click detail=0）选单日', async () => {
      const wrapper = mountCalendar(createEmptyMemoryFilters())
      await cell(wrapper, '2026-10-10').trigger('click')
      expect(wrapper.emitted('apply')![0]![0]).toMatchObject({
        dateFrom: '2026-10-10',
        dateTo: '2026-10-10',
      })
    })

    it('滚轮翻月：当前月向下禁用，向上回退', async () => {
      const wrapper = mountCalendar(createEmptyMemoryFilters())
      await wrapper.find('.memory-calendar__block').trigger('wheel', { deltaY: 120 })
      expect(wrapper.find('.memory-calendar__month').text()).toBe('2026年10月')
      await wrapper.find('.memory-calendar__block').trigger('wheel', { deltaY: -120 })
      expect(wrapper.find('.memory-calendar__month').text()).toBe('2026年9月')
    })

    it('月份标题 = 浏览整月', async () => {
      const wrapper = mountCalendar(createEmptyMemoryFilters())
      await wrapper.find('.memory-calendar__month').trigger('click')
      expect(wrapper.emitted('apply')![0]![0]).toMatchObject({
        dateFrom: '2026-10-01',
        dateTo: '2026-10-31',
      })
    })

    it('选中后显示清空按钮，点击只清日期', async () => {
      const wrapper = mountCalendar({
        ...createEmptyMemoryFilters(),
        datePreset: 'custom',
        dateFrom: '2026-08-01',
        dateTo: '2026-08-31',
        contentTypes: ['screenshot'],
      })
      expect(wrapper.find('.memory-calendar__chip').exists()).toBe(false)
      await wrapper.get('.memory-calendar__clear').trigger('click')
      expect(wrapper.emitted('apply')![0]![0]).toMatchObject({
        datePreset: 'all',
        dateFrom: '',
        dateTo: '',
        contentTypes: ['screenshot'],
      })
    })

    it('月份速选仅跳转视图，不改动已选时段', async () => {
      const wrapper = mountCalendar(createEmptyMemoryFilters())
      await wrapper.get('.memory-calendar__pick-btn').trigger('click')
      expect(wrapper.get('.memory-calendar__year').text()).toContain('2026')
      await wrapper.get('.memory-calendar__year-prev').trigger('click')
      expect(wrapper.get('.memory-calendar__year').text()).toContain('2025')
      await wrapper.get('[data-month="2"]').trigger('click')
      expect(wrapper.emitted('apply')).toBeUndefined()
      expect(wrapper.find('.memory-calendar__months').exists()).toBe(false)
      expect(wrapper.get('.memory-calendar__month').text()).toBe('2025年3月')
    })

    it('范围模式下跨月跳转后可继续点选终点', async () => {
      const wrapper = mountCalendar(createEmptyMemoryFilters())
      await wrapper.find('.memory-calendar__mode-input').setValue(true)
      await cell(wrapper, '2026-10-02').trigger('pointerdown')
      await wrapper.get('.memory-calendar__pick-btn').trigger('click')
      await wrapper.get('.memory-calendar__year-prev').trigger('click')
      await wrapper.get('[data-month="8"]').trigger('click')
      await cell(wrapper, '2025-09-15').trigger('pointerdown')
      expect(wrapper.emitted('apply')![0]![0]).toMatchObject({
        datePreset: 'custom',
        dateFrom: '2025-09-15',
        dateTo: '2026-10-02',
      })
    })

    it('月份速选禁用当年未来月份且无法越过当前年份', async () => {
      const wrapper = mountCalendar(createEmptyMemoryFilters())
      await wrapper.get('.memory-calendar__pick-btn').trigger('click')
      expect(wrapper.find('[data-month="11"]').attributes('disabled')).toBeDefined()
      expect(wrapper.get('.memory-calendar__year-next').attributes('disabled')).toBeDefined()
      await wrapper.get('.memory-calendar__year-next').trigger('click')
      expect(wrapper.get('.memory-calendar__year').text()).toContain('2026')
    })
  })
})
