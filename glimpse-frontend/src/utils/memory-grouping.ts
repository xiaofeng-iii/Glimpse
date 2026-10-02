import type { Memory } from '@/api/client'
import { t } from '@/utils/i18n'
import { toDateInputValue } from '@/utils/memory-filters'

export type WallLayoutMode = 'day' | 'month' | 'all'

/** 卡片时间粒度：按日期墙显示时分即可，按月份墙需补“几号”，全部墙没有日期上下文要带完整日期 */
export type CardTimeDisplay = 'time' | 'dayTime' | 'full'

export interface MemoryGroup {
  key: string
  label: string
  memories: Memory[]
}

export const startOfLocalDay = (date: Date) =>
  new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()

const monthKey = (date: Date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`

/**
 * 按排版模式把记忆划分成墙上的组。输入顺序即展示顺序（后端按时间倒序），
 * 标签依赖 locale，跨年时月份组始终带年份以消歧义。
 */
export const groupMemories = (
  memories: Memory[],
  mode: WallLayoutMode,
  locale: string,
  now = new Date(),
): MemoryGroup[] => {
  if (mode === 'all') {
    return [{ key: 'all', label: '', memories }]
  }

  const today = startOfLocalDay(now)
  const yesterday = today - 86_400_000
  const result = new Map<string, MemoryGroup>()

  for (const memory of memories) {
    const date = new Date(memory.created_at)
    let key: string
    let label: string
    if (mode === 'month') {
      key = monthKey(date)
      label = date.toLocaleDateString(locale, { year: 'numeric', month: 'long' })
    } else {
      const day = startOfLocalDay(date)
      if (day === today) {
        key = 'today'
        label = t('memory.today')
      } else if (day === yesterday) {
        key = 'yesterday'
        label = t('memory.yesterday')
      } else {
        key = date.toLocaleDateString(locale, {
          year: date.getFullYear() === now.getFullYear() ? undefined : 'numeric',
          month: 'long',
          day: 'numeric',
        })
        label = key
      }
    }

    const group = result.get(key) ?? { key, label, memories: [] }
    group.memories.push(memory)
    result.set(key, group)
  }

  return [...result.values()]
}

const fullDateLabel = (date: Date, locale: string) =>
  date.toLocaleDateString(locale, { year: 'numeric', month: 'long', day: 'numeric' })

const isWholeMonth = (from: Date, to: Date) =>
  from.getFullYear() === to.getFullYear()
  && from.getMonth() === to.getMonth()
  && from.getDate() === 1
  && to.getDate() === new Date(to.getFullYear(), to.getMonth() + 1, 0).getDate()

/** 由筛选里的日期范围推导跳转按钮的标签：单日、整月或自定义区间 */
export const describeMemoryPeriod = (dateFrom: string, dateTo: string, locale: string): string => {
  const parts = describeMemoryPeriodParts(dateFrom, dateTo, locale)
  return parts.tail ? `${parts.head} ${parts.tail}` : parts.head
}

/** 跨日区间把「至」并入首段、终点单独成段，供 UI 在宽度不足时整体换行；
 *  单日/整月等短标签只有首段 */
export const describeMemoryPeriodParts = (
  dateFrom: string,
  dateTo: string,
  locale: string,
): { head: string; tail: string | null } => {
  if (dateFrom && dateTo) {
    const from = new Date(`${dateFrom}T00:00:00`)
    const to = new Date(`${dateTo}T00:00:00`)
    if (dateFrom === dateTo) return { head: fullDateLabel(from, locale), tail: null }
    if (isWholeMonth(from, to)) {
      return { head: from.toLocaleDateString(locale, { year: 'numeric', month: 'long' }), tail: null }
    }
    return {
      head: `${fullDateLabel(from, locale)} ${t('filter.dateSeparator')}`,
      tail: fullDateLabel(to, locale),
    }
  }

  const single = dateFrom || dateTo
  if (single) return { head: fullDateLabel(new Date(`${single}T00:00:00`), locale), tail: null }
  return { head: t('wall.periodLatest'), tail: null }
}

export interface WallCalendarCell {
  date: Date
  dateStr: string
  inMonth: boolean
  /** 未来日期与邻月日期不可选 */
  disabled: boolean
  label: string
  inRange: boolean
  isEndpoint: boolean
  isToday: boolean
}

/** zh 习惯周一开头，其余按周日开头 */
export const weekStartsOnMonday = (locale: string) => locale.toLowerCase().startsWith('zh')

export const weekdayLabels = (locale: string, mondayFirst: boolean): string[] => {
  // 以 2024-01-01（周一）为基准滚出一周短标签，避免依赖系统“今天”落在哪天
  const base = new Date(2024, 0, mondayFirst ? 1 : 7)
  return Array.from({ length: 7 }, (_, index) => {
    const day = new Date(base)
    day.setDate(base.getDate() + index)
    return day.toLocaleDateString(locale, { weekday: 'short' })
  })
}

export const buildMonthGrid = (
  year: number,
  monthIndex: number,
  mondayFirst: boolean,
  locale: string,
  selection: { dateFrom?: string; dateTo?: string; now?: Date } = {},
): WallCalendarCell[][] => {
  const firstOfMonth = new Date(year, monthIndex, 1)
  const offset = (firstOfMonth.getDay() - (mondayFirst ? 1 : 0) + 7) % 7
  const cursor = new Date(year, monthIndex, 1 - offset)
  const todayStr = toDateInputValue(selection.now ?? new Date())
  const { dateFrom = '', dateTo = '' } = selection

  const weeks: WallCalendarCell[][] = []
  do {
    const week: WallCalendarCell[] = []
    for (let day = 0; day < 7; day += 1) {
      const date = new Date(cursor)
      const dateStr = toDateInputValue(date)
      week.push({
        date,
        dateStr,
        inMonth: date.getMonth() === monthIndex,
        disabled: dateStr > todayStr || date.getMonth() !== monthIndex,
        label: date.toLocaleDateString(locale, { year: 'numeric', month: 'long', day: 'numeric' }),
        inRange: Boolean(dateFrom && dateTo && dateStr >= dateFrom && dateStr <= dateTo),
        isEndpoint: Boolean(dateStr && (dateStr === dateFrom || dateStr === dateTo)),
        isToday: dateStr === todayStr,
      })
      cursor.setDate(cursor.getDate() + 1)
    }
    weeks.push(week)
  } while (cursor.getMonth() === monthIndex)

  return weeks
}
