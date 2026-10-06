<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { CameraIcon, FunnelIcon, MagnifyingGlassIcon } from '@heroicons/vue/24/outline'
import type { Memory } from '@/api/client'
import { languagePreference, t } from '@/utils/i18n'
import {
  createEmptyMemoryFilters,
  hasActiveMemoryFilters,
  type MemoryFilters,
} from '@/utils/memory-filters'
import CaptureButton from './CaptureButton.vue'
import AddMemoryButton from './AddMemoryButton.vue'
import MemoryCard from './MemoryCard.vue'
import { groupMemories, type CardTimeDisplay, type MemoryGroup } from '@/utils/memory-grouping'
import { wallLayoutMode } from '@/utils/wall-layout'

const props = defineProps<{
  memories: Memory[]
  total: number
  loading?: boolean
  selectedId?: string | null
  query?: string
  showSearchDebug?: boolean
  capturing?: boolean
  captureDisabled?: boolean
  addingMemory?: boolean
  addMemoryDisabled?: boolean
  filters?: MemoryFilters
  /** 列数上限：未显示右侧装饰板前封顶三列，宽度先攒着（由调用方传入）。 */
  maxColumns?: number
}>()

const emit = defineEmits<{
  (event: 'select', memory: Memory): void
  (event: 'open', memory: Memory): void
  (event: 'contextmenu', payload: { memory: Memory; x: number; y: number }): void
  (event: 'capture'): void
  (event: 'add-memory'): void
  (event: 'apply-filters', filters: MemoryFilters): void
  (event: 'scroll-state', scrolled: boolean): void
}>()

// 搜索反馈分治：搜索期间锁住上一轮已渲染的数据与布局，直到新结果就绪才
// 一帧内整体替换——杜绝“新布局×旧数据”的中间态（未分组全量闪现的根源）。
// 超过 200ms 才淡入骨架屏；快路径全程只有轻微降透明，无任何布局跳动。
const SKELETON_SHOW_DELAY_MS = 200

const searching = computed(() => Boolean(props.query?.trim()))
const filters = computed(() => props.filters ?? createEmptyMemoryFilters())
const filtering = computed(() => hasActiveMemoryFilters(filters.value))
const deferredSearchingLoad = ref(false)
let skeletonDelayTimer: number | null = null

// 已渲染数据快照：仅在新一轮数据实际到达（loading 结束）时更新布局标志与数据，
// 保证“布局切换”与“数据替换”严格同帧——查询框已变、结果未变的窗口内，
// 记忆墙继续以上一轮布局渲染上一轮数据，任何中间态都不会被画出来。
const renderedMemories = ref<Memory[]>([...props.memories])
const renderedSearching = ref(searching.value)
const wall = ref<HTMLElement | null>(null)
watch(
  () => [props.loading, props.memories, props.query] as const,
  ([loading, memories]) => {
    if (loading) return
    renderedMemories.value = [...memories]
    renderedSearching.value = searching.value
  },
  { immediate: true },
)

watch(
  () => props.loading && searching.value,
  (active) => {
    if (skeletonDelayTimer !== null) {
      window.clearTimeout(skeletonDelayTimer)
      skeletonDelayTimer = null
    }
    if (active) {
      skeletonDelayTimer = window.setTimeout(() => {
        skeletonDelayTimer = null
        deferredSearchingLoad.value = true
      }, SKELETON_SHOW_DELAY_MS)
    } else {
      deferredSearchingLoad.value = false
    }
  },
  { immediate: true },
)

onUnmounted(() => {
  if (skeletonDelayTimer !== null) window.clearTimeout(skeletonDelayTimer)
})

// 数据换血（新结果替换旧内容）时重建结果容器，触发挂载淡入，
// 避免 transition 因 DOM 复用不生效导致结果“硬切闪现”。
// 排版模式变化同样换 key：切换分组粒度时复用同一套交叉淡化换墙。
const resultsRenderKey = computed(() =>
  `${renderedSearching.value ? 's' : wallLayoutMode.value}:${renderedMemories.value.map((memory) => memory.id).join(',')}`,
)

// 按日期墙卡片只显示时分；按月份墙组标题只有月份，卡片需补“几号”；
// 全部墙没有日期上下文，卡片带完整日期时间。
const cardTimeDisplay = computed<CardTimeDisplay>(() => {
  if (wallLayoutMode.value === 'month') return 'dayTime'
  if (wallLayoutMode.value === 'all') return 'full'
  return 'time'
})

let scrollContainer: HTMLElement | null = null

// 滚动越顶只负责上报，紧凑态与吸顶参照由调用方（Home 控件行）托管。
const reportScrollState = () => {
  if (!scrollContainer) return
  emit('scroll-state', scrollContainer.scrollTop > 0)
}

// 墙内容块整体居中：按容器可用宽度求出实际列数（受 maxColumns 封顶），把
// 内容块宽度写入 --wall-content-width，供样式把分组标题、网格与骨架屏一起居中。
const CARD_WIDTH_PX = 239
const CARD_GAP_PX = 12
let paneResizeObserver: ResizeObserver | null = null

const updateContentWidth = () => {
  const wallElement = wall.value
  if (!wallElement || !scrollContainer) return
  const inset = Number.parseFloat(
    getComputedStyle(wallElement).getPropertyValue('--memory-wall-inline-inset'),
  ) || 16
  const available = scrollContainer.clientWidth - inset * 2
  const fit = Math.max(1, Math.floor((available + CARD_GAP_PX) / (CARD_WIDTH_PX + CARD_GAP_PX)))
  const columns = props.maxColumns ? Math.min(fit, props.maxColumns) : fit
  wallElement.style.setProperty(
    '--wall-content-width',
    `${columns * CARD_WIDTH_PX + (columns - 1) * CARD_GAP_PX}px`,
  )
}

watch(() => props.maxColumns, () => void nextTick(updateContentWidth))

onMounted(() => {
  scrollContainer = wall.value?.closest<HTMLElement>('.home-memory-pane') ?? null
  if (!scrollContainer) return

  scrollContainer.addEventListener('scroll', reportScrollState, { passive: true })
  if ('ResizeObserver' in window) {
    paneResizeObserver = new ResizeObserver(updateContentWidth)
    paneResizeObserver.observe(scrollContainer)
  }
  void nextTick(() => {
    updateContentWidth()
  })
})

onUnmounted(() => {
  scrollContainer?.removeEventListener('scroll', reportScrollState)
  paneResizeObserver?.disconnect()
})
const groups = computed<MemoryGroup[]>(() => {
  void languagePreference.value
  if (renderedSearching.value) {
    return [{ key: 'search', label: '', memories: renderedMemories.value }]
  }
  return groupMemories(renderedMemories.value, wallLayoutMode.value, languagePreference.value)
})
</script>

<template>
  <section ref="wall" class="memory-wall">
    <div class="memory-wall-scroll pb-6 pt-4" aria-live="polite" :aria-busy="loading || undefined">

      <Transition name="wall-cross">
        <div
          v-if="searching && deferredSearchingLoad"
          key="skeleton"
          class="memory-grid memory-wall__skeleton-grid"
          aria-hidden="true"
        >
        <div v-for="i in 8" :key="i" class="memory-card-skeleton">
          <div class="memory-card-skeleton__media"></div>
          <div class="memory-card-skeleton__body">
            <div class="memory-card-skeleton__line"></div>
            <div class="memory-card-skeleton__line"></div>
            <div class="memory-card-skeleton__line memory-card-skeleton__line--short"></div>
            <div class="memory-card-skeleton__time"></div>
          </div>
        </div>
      </div>

      <div v-else-if="!renderedMemories.length" key="empty" class="flex min-h-[52vh] flex-col items-center justify-center text-center">
        <div
          class="flex h-14 w-14 items-center justify-center rounded-xl"
          :class="renderedSearching || filtering
            ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary)]'
            : 'memory-wall__capture-icon'"
        >
          <FunnelIcon v-if="filtering" class="h-7 w-7" aria-hidden="true" />
          <MagnifyingGlassIcon v-else-if="renderedSearching" class="h-7 w-7" aria-hidden="true" />
          <CameraIcon v-else class="h-7 w-7" aria-hidden="true" />
        </div>
        <h2 class="mt-4 text-base font-semibold text-[var(--shell-ink)]">
          {{ filtering
            ? t('memory.noFilterResults')
            : renderedSearching ? t('memory.noSearchResults') : t('memory.emptyTitle') }}
        </h2>
        <p class="mt-1.5 max-w-sm text-sm text-[var(--shell-muted)]">
          {{ filtering
            ? t('memory.noFilterResultsHint')
            : renderedSearching ? t('memory.noSearchResultsHint') : t('memory.emptyHint') }}
        </p>
        <button
          v-if="filtering"
          type="button"
          class="btn-secondary mt-4"
          @click="emit('apply-filters', createEmptyMemoryFilters())"
        >
          {{ t('filter.clear') }}
        </button>
        <div v-else-if="!renderedSearching" class="mt-4 flex flex-wrap items-center justify-center gap-2.5">
          <CaptureButton
            :capturing="capturing"
            :disabled="captureDisabled"
            @capture="emit('capture')"
          />
          <AddMemoryButton
            :busy="addingMemory"
            :disabled="addMemoryDisabled"
            @add="emit('add-memory')"
          />
        </div>
      </div>

      <div
        v-else
        :key="resultsRenderKey"
        class="memory-wall__results space-y-5"
        :class="{ 'memory-wall__results--stale': loading }"
      >
        <section v-for="group in groups" :key="group.key">
          <h2 v-if="group.label" class="mb-2.5 text-xs font-semibold tracking-wide text-[var(--shell-muted)]">
            {{ group.label }}
          </h2>
          <div class="memory-grid">
            <MemoryCard
              v-for="memory in group.memories"
              :key="memory.id"
              :memory="memory"
              :selected="selectedId === memory.id"
              :searching="searching"
              :show-debug="showSearchDebug"
              :time-display="cardTimeDisplay"
              @select="emit('select', $event)"
              @open="emit('open', $event)"
              @contextmenu="emit('contextmenu', $event)"
            />
          </div>
        </section>
      </div>
      </Transition>
    </div>
  </section>
</template>

<style scoped>
.memory-wall {
  --memory-wall-inline-inset: 1rem;
  --memory-card-width: 239px;

  position: relative;
  display: flex;
  flex-direction: column;
  container-type: inline-size;
}

.memory-wall-scroll {
  position: relative;
  padding-inline: var(--memory-wall-inline-inset);
}

/* 内容块整体居中：宽度 = 实际列数宽（--wall-content-width 由脚本按容器实测给出），
   分组标题与网格一起随动，标题与卡片的左基准线保持对齐。 */
.memory-wall__results > section,
.memory-wall__skeleton-grid {
  width: min(100%, var(--wall-content-width, 100%));
  margin-inline: auto;
}

/* 搜索加载期：旧内容降透明提示“检索中”，布局保持稳定不跳动。 */
.memory-wall__results--stale {
  opacity: 0.55;
  pointer-events: none;
}

/* 换墙交叉淡化：旧墙淡出与新墙淡入交叠 120ms，内容不再一帧闪换。
   离场墙临时绝对定位，水平锚定内容盒（对齐父容器 padding），垂直用静态位。 */
.wall-cross-enter-active,
.wall-cross-leave-active {
  transition: opacity 120ms ease;
}

.wall-cross-enter-from,
.wall-cross-leave-to {
  opacity: 0;
}

.wall-cross-leave-active {
  position: absolute;
  left: max(
    var(--memory-wall-inline-inset),
    calc((100% - var(--wall-content-width, 100%)) / 2)
  );
  right: max(
    var(--memory-wall-inline-inset),
    calc((100% - var(--wall-content-width, 100%)) / 2)
  );
}

/* 延迟骨架：超过阈值才淡入，快路径搜索完全不可见（进出场由 wall-cross 驱动）。 */
.memory-wall__skeleton-grid {
  align-content: start;
}

@keyframes memory-skeleton-in {
  from {
    opacity: 0;
  }
}

.memory-wall__capture-icon {
  color: var(--color-accent);
  background: color-mix(in srgb, var(--color-accent) 10%, var(--color-surface));
}

.memory-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, var(--memory-card-width));
  align-items: start;
  justify-content: start;
  gap: 0.75rem;
}

/* 搜索加载骨架屏：占位卡片尺寸与 MemoryCard 对齐，shimmer 扫过提示加载中。 */
.memory-card-skeleton {
  display: flex;
  inline-size: var(--memory-card-width, 239px);
  block-size: 270px;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--shell-line);
  border-radius: var(--radius-lg);
}

.memory-card-skeleton__media {
  flex: 0 0 148px;
}

.memory-card-skeleton__body {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 0.5rem;
  padding: 8px;
}

.memory-card-skeleton__line {
  block-size: 12px;
  inline-size: 100%;
  border-radius: 6px;
}

.memory-card-skeleton__line--short {
  inline-size: 62%;
}

.memory-card-skeleton__time {
  margin-block-start: auto;
  block-size: 10px;
  inline-size: 32%;
  border-radius: 5px;
}

.memory-card-skeleton__media,
.memory-card-skeleton__line,
.memory-card-skeleton__time {
  position: relative;
  overflow: hidden;
  background: var(--color-surface-subtle);
}

/* shimmer 用 transform 位移动画（合成器线程），替代逐帧重绘的 background-position */
.memory-card-skeleton__media::after,
.memory-card-skeleton__line::after,
.memory-card-skeleton__time::after {
  content: '';
  position: absolute;
  inset: 0;
  transform: translateX(-100%);
  background: linear-gradient(
    90deg,
    transparent,
    var(--color-surface-hover),
    transparent
  );
  animation: memory-skeleton-shimmer 1.4s ease-in-out infinite;
}

@keyframes memory-skeleton-shimmer {
  to {
    transform: translateX(100%);
  }
}

@container memory-pane (max-width: 960px) {
  .memory-wall {
    --memory-wall-inline-inset: 0.75rem;
  }
}

@container memory-pane (max-width: 640px) {
  .memory-wall {
    --memory-wall-inline-inset: 0.5rem;
  }
}

@media (prefers-reduced-motion: reduce) {
  .memory-wall__results,
  .memory-wall__skeleton-grid,
  .wall-cross-enter-active,
  .wall-cross-leave-active {
    transition: none;
    animation: none;
  }

  @keyframes memory-results-in {
    from {
      opacity: 1;
    }
  }

  .memory-card-skeleton__media::after,
  .memory-card-skeleton__line::after,
  .memory-card-skeleton__time::after {
    animation: none;
  }
}
</style>
