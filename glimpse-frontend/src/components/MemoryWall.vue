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
import MemoryFiltersControl from './MemoryFilters.vue'
import WallLayoutSwitcher from './WallLayoutSwitcher.vue'
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
}>()

const emit = defineEmits<{
  (event: 'select', memory: Memory): void
  (event: 'open', memory: Memory): void
  (event: 'contextmenu', payload: { memory: Memory; x: number; y: number }): void
  (event: 'capture'): void
  (event: 'add-memory'): void
  (event: 'apply-filters', filters: MemoryFilters): void
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
const renderedTotal = ref(props.total)
const renderedSearching = ref(searching.value)
const wall = ref<HTMLElement | null>(null)
watch(
  () => [props.loading, props.memories, props.total, props.query] as const,
  ([loading, memories, total]) => {
    if (loading) return
    renderedMemories.value = [...memories]
    renderedTotal.value = total
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

const compactFilter = ref(false)
let scrollContainer: HTMLElement | null = null
let toolbarResizeObserver: ResizeObserver | null = null

const updateStickyFilter = () => {
  if (!scrollContainer || !wall.value) return
  const toolbar = scrollContainer.querySelector<HTMLElement>('.search-toolbar')
  if (!toolbar) return

  const stickyTop = toolbar.getBoundingClientRect().height
  wall.value.style.setProperty('--memory-wall-sticky-top', `${stickyTop}px`)
  compactFilter.value = scrollContainer.scrollTop > 0
}

onMounted(() => {
  scrollContainer = wall.value?.closest<HTMLElement>('.home-memory-pane') ?? null
  if (!scrollContainer) return

  scrollContainer.addEventListener('scroll', updateStickyFilter, { passive: true })
  const toolbar = scrollContainer.querySelector<HTMLElement>('.search-toolbar')
  if (toolbar && 'ResizeObserver' in window) {
    toolbarResizeObserver = new ResizeObserver(updateStickyFilter)
    toolbarResizeObserver.observe(toolbar)
  }
  void nextTick(updateStickyFilter)
})

onUnmounted(() => {
  scrollContainer?.removeEventListener('scroll', updateStickyFilter)
  toolbarResizeObserver?.disconnect()
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
    <header
      class="memory-wall__header"
      :class="{ 'memory-wall__header--compact': compactFilter }"
    >
      <h1 class="text-base font-semibold tracking-[-0.01em] text-[var(--shell-ink)]">
        {{
          renderedSearching
            ? t('memory.searchCount', { count: renderedMemories.length })
            : t('memory.count', { count: renderedTotal })
        }}
      </h1>
      <div class="memory-wall__controls">
        <WallLayoutSwitcher :disabled="renderedSearching" :compact="compactFilter" />
        <MemoryFiltersControl
          :model-value="filters"
          :loading="loading"
          :compact="compactFilter"
          @apply="emit('apply-filters', $event)"
        />
      </div>
    </header>

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
  --memory-wall-sticky-top: 5rem;
  --memory-card-width: 239px;

  position: relative;
  display: flex;
  flex-direction: column;
  container-type: inline-size;
}

.memory-wall__header {
  position: sticky;
  z-index: 2;
  top: var(--memory-wall-sticky-top);
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.375rem var(--memory-wall-inline-inset) 0.25rem;
  background: var(--shell-window-bg);
}

.memory-wall__header h1 {
  transition: opacity 160ms ease, transform 160ms ease;
}

.memory-wall__controls {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 0.5rem;
}

.memory-wall__header--compact {
  background: transparent;
}

.memory-wall__header--compact h1 {
  transform: translateY(-0.25rem);
  opacity: 0;
  pointer-events: none;
}

.memory-wall__header::after {
  content: '';
  position: absolute;
  right: var(--memory-wall-inline-inset);
  bottom: 0;
  left: var(--memory-wall-inline-inset);
  height: 1px;
  background: color-mix(in srgb, var(--shell-line) 72%, transparent);
  transition: opacity 160ms ease;
}

.memory-wall__header--compact::after {
  opacity: 0;
}

.memory-wall-scroll {
  position: relative;
  padding-inline: var(--memory-wall-inline-inset);
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
  left: var(--memory-wall-inline-inset);
  right: var(--memory-wall-inline-inset);
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

@container (max-width: 560px) {
  .memory-wall__header {
    align-items: flex-start;
  }
}

@media (prefers-reduced-motion: reduce) {
  .memory-wall__header h1,
  .memory-wall__header::after {
    transition: none;
  }

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
