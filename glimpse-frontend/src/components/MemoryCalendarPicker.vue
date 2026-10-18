<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, shallowReactive, watch } from 'vue'
import { ChevronLeftIcon, ChevronRightIcon, Squares2X2Icon } from '@heroicons/vue/24/outline'
import { languagePreference, t } from '@/utils/i18n'
import { cloneMemoryFilters, toDateInputValue, type MemoryFilters } from '@/utils/memory-filters'
import {
  buildMonthGrid,
  weekStartsOnMonday,
  weekdayLabels,
  type WallCalendarCell,
} from '@/utils/memory-grouping'

const props = defineProps<{
  filters: MemoryFilters
  /** 可注入的当前时间（测试用）；默认取真实当前时间 */
  now?: Date
}>()

const emit = defineEmits<{
  (event: 'apply', filters: MemoryFilters): void
}>()

// 打开面板时锚定到已选时段（或当前月）；‹ ›/滚轮只移动视图，不改已选范围
const anchorDate = props.filters.dateFrom || props.filters.dateTo
const anchor = anchorDate ? new Date(`${anchorDate}T00:00:00`) : (props.now ?? new Date())
const viewYear = ref(anchor.getFullYear())
const viewMonth = ref(anchor.getMonth())

// 「范围」模式：开启后点两次选起止日期；关闭时按下拖动框选、单击即单日
// 开关在筛选面板头部，状态经 v-model 双向同步
const rangeMode = defineModel<boolean>('rangeMode', { default: false })
const pendingStart = ref('')
const dragging = ref(false)
const dragStart = ref('')
const dragPreviewEnd = ref('')

const currentNow = computed(() => props.now ?? new Date())

const atCurrentMonth = computed(() =>
  viewYear.value === currentNow.value.getFullYear()
  && viewMonth.value === currentNow.value.getMonth(),
)

const monthTitle = computed(() =>
  new Date(viewYear.value, viewMonth.value, 1).toLocaleDateString(languagePreference.value, {
    year: 'numeric',
    month: 'long',
  }),
)

const weekdayHeader = computed(() =>
  weekdayLabels(languagePreference.value, weekStartsOnMonday(languagePreference.value)),
)

const normalizeRange = (a: string, b: string): [string, string] => (a <= b ? [a, b] : [b, a])

// 网格高亮优先展示“进行中”的选择（拖拽预览/待终点），否则回显已选时段
const selection = computed(() => {
  if (dragging.value) return { dateFrom: dragStart.value, dateTo: dragPreviewEnd.value }
  if (pendingStart.value) return { dateFrom: pendingStart.value, dateTo: pendingStart.value }
  return { dateFrom: props.filters.dateFrom, dateTo: props.filters.dateTo }
})

const grid = computed(() =>
  buildMonthGrid(viewYear.value, viewMonth.value, weekStartsOnMonday(languagePreference.value), languagePreference.value, {
    dateFrom: selection.value.dateFrom,
    dateTo: selection.value.dateTo,
    now: currentNow.value,
  }),
)

const emitPeriod = (dateFrom: string, dateTo: string) => {
  emit('apply', {
    ...cloneMemoryFilters(props.filters),
    datePreset: 'custom',
    dateFrom,
    dateTo,
  })
}

const chooseWholeMonth = () => {
  pendingStart.value = ''
  emitPeriod(
    toDateInputValue(new Date(viewYear.value, viewMonth.value, 1)),
    toDateInputValue(new Date(viewYear.value, viewMonth.value + 1, 0)),
  )
}

// 条带滑动小机芯，日历翻月与月份速选翻年共用：新旧两格并排成条带，整体平移
// 一个视口宽，结束后落回单格渲染；连翻中断时先立即落地当前格再开始下一段。
// 不依赖 Vue Transition 的离场元素回收，条带内容完全由这里的状态决定
const createStripSlider = <T,>() => {
  const state = shallowReactive({ panes: null as T[] | null, offset: 0, animated: false })
  let fallbackTimer: number | null = null
  let rafIds: number[] = []

  const commit = () => {
    if (fallbackTimer !== null) {
      window.clearTimeout(fallbackTimer)
      fallbackTimer = null
    }
    rafIds.forEach((id) => cancelAnimationFrame(id))
    rafIds = []
    state.panes = null
    state.offset = 0
    state.animated = false
  }

  const slide = (delta: number, previous: T, current: T) => {
    commit()
    state.panes = delta > 0 ? [previous, current] : [current, previous]
    state.animated = false
    state.offset = delta > 0 ? 0 : -100
    rafIds.push(requestAnimationFrame(() => {
      rafIds.push(requestAnimationFrame(() => {
        rafIds = []
        state.animated = true
        state.offset = delta > 0 ? -100 : 0
        // transitionend 在正常路径下先行落地；被中断或 reduced-motion 时由兜底计时收口
        fallbackTimer = window.setTimeout(commit, 320)
      }))
    }))
  }

  const onTransitionEnd = (event: TransitionEvent) => {
    if (event.propertyName === 'transform') commit()
  }

  return {
    state,
    get sliding() { return state.panes !== null },
    commit,
    slide,
    onTransitionEnd,
  }
}

type CalendarPane = { key: string; cells: WallCalendarCell[] }
const monthSlider = createStripSlider<CalendarPane>()
const yearSlider = createStripSlider<{ year: number }>()

const currentPane = computed<CalendarPane>(() => ({
  key: `${viewYear.value}-${viewMonth.value}`,
  cells: grid.value.flat(),
}))
const renderedPanes = computed(() => monthSlider.state.panes ?? [currentPane.value])
const renderedYearPanes = computed(() => yearSlider.state.panes ?? [{ year: pickerYear.value }])

const shiftMonth = (delta: number) => {
  const previous = currentPane.value
  const next = new Date(viewYear.value, viewMonth.value + delta, 1)
  viewYear.value = next.getFullYear()
  viewMonth.value = next.getMonth()
  monthSlider.slide(delta, previous, currentPane.value)
}

// 「月份速选」面板：只负责跨年快速跳转视图，不改动已选时段；
// 进行中的范围选择（pendingStart）跨月保留，方便“这月点起点、跳月后点终点”
const monthPickerOpen = ref(false)
const pickerYear = ref(anchor.getFullYear())

const toggleMonthPicker = () => {
  yearSlider.commit()
  monthPickerOpen.value = !monthPickerOpen.value
  if (monthPickerOpen.value) pickerYear.value = viewYear.value
}

const shiftPickerYear = (delta: number) => {
  if (delta > 0 && pickerYear.value >= currentNow.value.getFullYear()) return
  const previous = pickerYear.value
  pickerYear.value += delta
  yearSlider.slide(delta, { year: previous }, { year: pickerYear.value })
}

const jumpToMonth = (month: number) => {
  monthSlider.commit()
  yearSlider.commit()
  viewYear.value = pickerYear.value
  viewMonth.value = month
  monthPickerOpen.value = false
}

// 某年某月是否超出当前月（速选格里禁用）；按格所属年份判定，滑动中的旧年格同样正确
const isFutureMonth = (year: number, month: number) =>
  year === currentNow.value.getFullYear() && month > currentNow.value.getMonth()

const isCurrentMonth = (year: number, month: number) =>
  year === currentNow.value.getFullYear() && month === currentNow.value.getMonth()

const yearLabel = computed(() =>
  new Date(pickerYear.value, 0, 1).toLocaleDateString(languagePreference.value, { year: 'numeric' }),
)

const monthPickerLabels = computed(() => {
  const locale = languagePreference.value
  return Array.from({ length: 12 }, (_, month) =>
    new Date(2024, month, 1).toLocaleDateString(locale, { month: 'short' }),
  )
})

// 滚轮在日历块上翻月、速选面板打开时翻年；短冷却吸收触控板的连续滚动
let lastWheelAt = 0
const handleWheel = (event: WheelEvent) => {
  const delta = event.deltaY > 8 ? 1 : event.deltaY < -8 ? -1 : 0
  if (delta === 0 || performance.now() - lastWheelAt < 140) return
  // 向未来翻到当月/本年即边界，挡下且不占用冷却
  if (monthPickerOpen.value) {
    if (delta > 0 && pickerYear.value >= currentNow.value.getFullYear()) return
    lastWheelAt = performance.now()
    shiftPickerYear(delta)
    return
  }
  if (delta > 0 && atCurrentMonth.value) return
  lastWheelAt = performance.now()
  shiftMonth(delta)
}

const onCellPointerDown = (cell: WallCalendarCell) => {
  if (cell.disabled) return
  if (rangeMode.value) {
    // 第二次点击收口：点同一天 = 单日，点另一天 = 起止区间（顺序自动归一）
    if (pendingStart.value) {
      const [from, to] = normalizeRange(pendingStart.value, cell.dateStr)
      pendingStart.value = ''
      emitPeriod(from, to)
    } else {
      pendingStart.value = cell.dateStr
    }
    return
  }
  pendingStart.value = ''
  dragging.value = true
  dragStart.value = cell.dateStr
  dragPreviewEnd.value = cell.dateStr
}

const onCellPointerEnter = (cell: WallCalendarCell) => {
  if (!dragging.value || cell.disabled) return
  dragPreviewEnd.value = cell.dateStr
}

const onCellClick = (event: MouseEvent, cell: WallCalendarCell) => {
  // 鼠标路径由 pointerdown/pointerup 处理；detail=0 是键盘触发的 click
  if (event.detail !== 0 || cell.disabled) return
  emitPeriod(cell.dateStr, cell.dateStr)
}

const handleWindowPointerUp = () => {
  if (!dragging.value) return
  const [from, to] = normalizeRange(dragStart.value, dragPreviewEnd.value)
  dragging.value = false
  emitPeriod(from, to)
}

watch(rangeMode, (on) => {
  if (!on) pendingStart.value = ''
})

// 「清除」按钮在筛选面板头部；父级清空时段后同步丢掉进行中的范围起点
watch(() => [props.filters.dateFrom, props.filters.dateTo], ([from, to]) => {
  if (!from && !to) pendingStart.value = ''
})

onMounted(() => window.addEventListener('pointerup', handleWindowPointerUp))
onUnmounted(() => {
  window.removeEventListener('pointerup', handleWindowPointerUp)
  monthSlider.commit()
  yearSlider.commit()
})
</script>

<template>
  <div class="memory-calendar">
    <div
      class="memory-calendar__block"
      role="group"
      :aria-label="t('wall.jumpToPeriod')"
      @wheel.prevent="handleWheel"
    >
      <div class="memory-calendar__nav">
        <button
          type="button"
          class="memory-calendar__nav-btn"
          :aria-label="t('wall.prevMonth')"
          @click="shiftMonth(-1)"
        >
          <ChevronLeftIcon class="h-4 w-4" aria-hidden="true" />
        </button>
        <button
          type="button"
          class="memory-calendar__month"
          :title="t('wall.browseWholeMonth')"
          @click="chooseWholeMonth"
        >
          {{ monthTitle }}
        </button>
        <div class="memory-calendar__nav-right">
          <button
            type="button"
            class="memory-calendar__nav-btn memory-calendar__pick-btn"
            :class="{ 'memory-calendar__nav-btn--active': monthPickerOpen }"
            :aria-expanded="monthPickerOpen"
            :title="t('wall.pickMonth')"
            @click="toggleMonthPicker"
          >
            <Squares2X2Icon class="h-4 w-4" aria-hidden="true" />
          </button>
          <button
            type="button"
            class="memory-calendar__nav-btn"
            :aria-label="t('wall.nextMonth')"
            :disabled="atCurrentMonth"
            @click="shiftMonth(1)"
          >
            <ChevronRightIcon class="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>

      <div v-if="monthPickerOpen" class="memory-calendar__months" role="group" :aria-label="t('wall.pickMonth')">
        <div class="memory-calendar__year-nav">
          <button
            type="button"
            class="memory-calendar__nav-btn memory-calendar__year-prev"
            :aria-label="t('wall.prevYear')"
            @click="shiftPickerYear(-1)"
          >
            <ChevronLeftIcon class="h-3.5 w-3.5" aria-hidden="true" />
          </button>
          <span class="memory-calendar__year" aria-hidden="true">{{ yearLabel }}</span>
          <button
            type="button"
            class="memory-calendar__nav-btn memory-calendar__year-next"
            :aria-label="t('wall.nextYear')"
            :disabled="pickerYear >= currentNow.getFullYear()"
            @click="shiftPickerYear(1)"
          >
            <ChevronRightIcon class="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        </div>
        <div
          class="memory-calendar__viewport"
          :class="{ 'memory-calendar__viewport--sliding': yearSlider.sliding }"
        >
          <div
            class="memory-calendar__strip"
            :class="{ 'memory-calendar__strip--animated': yearSlider.state.animated }"
            :style="{ transform: `translateX(${yearSlider.state.offset}%)` }"
            @transitionend="yearSlider.onTransitionEnd"
          >
            <div
              v-for="pane in renderedYearPanes"
              :key="pane.year"
              class="memory-calendar__month-grid"
            >
              <button
                v-for="(label, month) in monthPickerLabels"
                :key="month"
                type="button"
                class="memory-calendar__month-cell"
                :class="{ 'memory-calendar__month-cell--current': isCurrentMonth(pane.year, month) }"
                :data-month="month"
                :disabled="isFutureMonth(pane.year, month)"
                @click="jumpToMonth(month)"
              >
                {{ label }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="memory-calendar__grid">
        <span
          v-for="label in weekdayHeader"
          :key="label"
          class="memory-calendar__weekday"
          aria-hidden="true"
        >{{ label }}</span>
        <div
          class="memory-calendar__viewport"
          :class="{ 'memory-calendar__viewport--sliding': monthSlider.sliding }"
        >
          <div
            class="memory-calendar__strip"
            :class="{ 'memory-calendar__strip--animated': monthSlider.state.animated }"
            :style="{ transform: `translateX(${monthSlider.state.offset}%)` }"
            @transitionend="monthSlider.onTransitionEnd"
          >
            <div
              v-for="pane in renderedPanes"
              :key="pane.key"
              class="memory-calendar__days"
            >
              <button
                v-for="cell in pane.cells"
                :key="cell.dateStr"
                type="button"
                class="memory-calendar__day"
                :class="{
                  'memory-calendar__day--outside': !cell.inMonth,
                  'memory-calendar__day--in-range': cell.inRange && !cell.isEndpoint,
                  'memory-calendar__day--endpoint': cell.isEndpoint,
                  'memory-calendar__day--today': cell.isToday && !cell.isEndpoint,
                }"
                :data-date="cell.dateStr"
                :aria-label="cell.label"
                :disabled="cell.disabled"
                @pointerdown="onCellPointerDown(cell)"
                @pointerenter="onCellPointerEnter(cell)"
                @click="onCellClick($event, cell)"
              >
                {{ cell.date.getDate() }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.memory-calendar {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.memory-calendar__block {
  padding: 0.75rem 0.75rem 0.875rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface-subtle);
}

.memory-calendar__nav {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.625rem;
}

.memory-calendar__nav > .memory-calendar__nav-btn:first-child {
  justify-self: start;
}

.memory-calendar__nav-right {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-self: end;
  gap: 0.125rem;
}

.memory-calendar__nav-btn--active {
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.memory-calendar__months {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.memory-calendar__year-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0 0.25rem;
}

/* 年份步进是速选面板里的次级导航：尺寸与内缩都弱于主导航箭头 */
.memory-calendar__year-nav .memory-calendar__nav-btn {
  width: 1.5rem;
  height: 1.5rem;
}

.memory-calendar__year {
  flex: 1;
  color: var(--color-text);
  font-size: 0.75rem;
  text-align: center;
}

.memory-calendar__month-grid {
  display: grid;
  flex: 0 0 100%;
  width: 100%;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 2px;
}

.memory-calendar__month-cell {
  height: 1.875rem;
  min-height: 0;
  padding: 0;
  border: 0;
  border-radius: var(--radius-sm);
  color: var(--color-text);
  background: transparent;
  cursor: pointer;
  font-size: 0.875rem;
  transition: background-color 160ms ease, color 160ms ease;
}

.memory-calendar__month-cell:hover:not(:disabled) {
  background: rgb(224, 228, 237);
}

.memory-calendar__month-cell:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 1px;
}

.memory-calendar__month-cell:disabled {
  cursor: default;
  opacity: 0.35;
}

.memory-calendar__month-cell--current {
  color: var(--color-primary-hover);
  background: var(--color-primary-soft);
}

.memory-calendar__nav-btn {
  display: inline-flex;
  width: 1.875rem;
  height: 1.875rem;
  min-height: 0;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 0;
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  background: transparent;
  cursor: pointer;
  transition: background-color 160ms ease, color 160ms ease;
}

.memory-calendar__nav-btn:hover:not(:disabled) {
  color: var(--color-text);
  background: rgb(224, 228, 237);
}

.memory-calendar__nav-btn:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 1px;
}

.memory-calendar__nav-btn:disabled {
  cursor: default;
  opacity: 0.4;
}

.memory-calendar__month {
  min-width: 0;
  padding: 0.25rem 0.625rem;
  border: 0;
  border-radius: var(--radius-sm);
  color: var(--color-text);
  background: transparent;
  cursor: pointer;
  font-size: 0.875rem;
  transition: background-color 160ms ease, color 160ms ease;
}

.memory-calendar__month:hover {
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.memory-calendar__month:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 1px;
}

.memory-calendar__grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 2px;
  user-select: none;
  -webkit-user-select: none;
}

.memory-calendar__viewport {
  grid-column: 1 / -1;
}

/* 滑动只在翻月的 200ms 内存在：条带横向溢出由视口裁切、日格暂停响应指针；
   平时单月渲染不裁切，日格的焦点描边完整可见 */
.memory-calendar__viewport--sliding {
  overflow: hidden;
}

.memory-calendar__viewport--sliding .memory-calendar__day,
.memory-calendar__viewport--sliding .memory-calendar__month-cell {
  pointer-events: none;
}

.memory-calendar__strip {
  display: flex;
  width: 100%;
}

.memory-calendar__strip--animated {
  /* 与筛选面板 reveal 的高度过渡同一条缓动曲线 */
  transition: transform 200ms cubic-bezier(0.32, 0.72, 0, 1);
}

.memory-calendar__days {
  display: grid;
  flex: 0 0 100%;
  width: 100%;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 2px;
}

.memory-calendar__weekday {
  padding: 0.25rem 0;
  color: var(--color-text-muted);
  font-size: 0.75rem;
  text-align: center;
}

.memory-calendar__day {
  position: relative;
  height: 2rem;
  min-height: 0;
  padding: 0;
  border: 0;
  border-radius: var(--radius-sm);
  color: var(--color-text);
  background: transparent;
  cursor: pointer;
  font-size: 0.875rem;
  transition: background-color 160ms ease, color 160ms ease;
}

.memory-calendar__day:hover:not(:disabled) {
  background: rgb(224, 228, 237);
}

:root[data-theme='dark'] .memory-calendar__month-cell:hover:not(:disabled),
:root[data-theme='dark'] .memory-calendar__day:hover:not(:disabled),
:root[data-theme='dark'] .memory-calendar__nav-btn:hover:not(:disabled) {
  background: var(--color-surface-hover);
}

.memory-calendar__day--endpoint:hover:not(:disabled),
:root[data-theme='dark'] .memory-calendar__day--endpoint:hover:not(:disabled) {
  background: var(--color-primary-hover);
}

.memory-calendar__day:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 1px;
}

.memory-calendar__day--outside {
  opacity: 0.35;
}

.memory-calendar__day:disabled {
  cursor: default;
  opacity: 0.35;
}

.memory-calendar__day--in-range {
  background: var(--color-primary-soft);
}

.memory-calendar__day--endpoint {
  color: var(--color-on-primary);
  background: var(--color-primary);
}

.memory-calendar__day--today::after {
  content: '';
  position: absolute;
  bottom: 3px;
  left: 50%;
  width: 4px;
  height: 4px;
  margin-left: -2px;
  border-radius: 50%;
  background: var(--color-primary);
}

@media (prefers-reduced-motion: reduce) {
  .memory-calendar__strip--animated {
    transition: none;
  }
}
</style>
