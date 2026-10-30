<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { HugeiconsIcon } from '@hugeicons/vue'
import { Image01FreeIcons } from '@hugeicons/core-free-icons'
import type { Memory } from '@/api/client'
import { getMemoryImageUrls } from '@/utils/memory-images'
import { getMatchSourceKinds } from '@/utils/match-sources'
import { getMemoryDisplayText, isTextMemory } from '@/utils/memory-types'
import type { CardTimeDisplay } from '@/utils/memory-grouping'
import { languagePreference, t } from '@/utils/i18n'
import { useDevStateStore } from '@/stores/devState'
import MemoryAnalysisState from './MemoryAnalysisState.vue'

const props = defineProps<{
  memory: Memory
  selected?: boolean
  searching?: boolean
  showDebug?: boolean
  timeDisplay?: CardTimeDisplay
}>()

const emit = defineEmits<{
  (event: 'select', memory: Memory): void
  (event: 'open', memory: Memory): void
  (event: 'contextmenu', payload: { memory: Memory; x: number; y: number }): void
}>()

const imageFailed = ref(false)
const isDev = import.meta.env.DEV
const devState = useDevStateStore()
// DEV 状态覆盖只影响展示判定；交互与数据仍走原始 memory。
const effectiveMemory = computed(() =>
  isDev ? devState.applyOverride(props.memory) : props.memory,
)
const imageUrl = computed(() => getMemoryImageUrls(props.memory)[0] ?? '')
const textMemory = computed(() => isTextMemory(props.memory))
const displayText = computed(() => getMemoryDisplayText(props.memory))
const matchSourceKinds = computed(() => getMatchSourceKinds(props.memory.match_sources))
const analysisStatus = computed(() => effectiveMemory.value.analysis_status ?? 'COMPLETED')
const analyzing = computed(() => analysisStatus.value === 'PROCESSING')
const analysisUnavailable = computed(() => analysisStatus.value === 'FAILED')
// 图片记忆的分析/失败态统一叠加在元数据行；正文始终内容优先，有用户文字时不占位。
const showStatus = computed(() => !textMemory.value && (analyzing.value || analysisUnavailable.value))
// 卡片标签最多展示 2 个，其余折叠为 +N；单行排列、超长省略，完整名走 title。
const cardTags = computed(() => props.memory.tags ?? [])
const visibleTags = computed(() => cardTags.value.slice(0, 2))
const hiddenTagCount = computed(() => Math.max(0, cardTags.value.length - visibleTags.value.length))

// 单击选中延迟确认：双击进入详情时取消侧栏弹出，避免“先弹预览再跳页”的闪动。
const SELECT_INTENT_DELAY_MS = 250
let selectIntentTimer: number | null = null

const cancelSelectIntent = () => {
  if (selectIntentTimer !== null) {
    window.clearTimeout(selectIntentTimer)
    selectIntentTimer = null
  }
}

const handleCardClick = () => {
  if (selectIntentTimer !== null) return
  selectIntentTimer = window.setTimeout(() => {
    selectIntentTimer = null
    emit('select', props.memory)
  }, SELECT_INTENT_DELAY_MS)
}

const handleCardDoubleClick = () => {
  cancelSelectIntent()
  emit('open', props.memory)
}

const formatTime = (value: string) =>
  new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

const formatCardTime = (value: string) => {
  const date = new Date(value)
  if (props.timeDisplay === 'full') {
    return date.toLocaleString(languagePreference.value, {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }
  if (props.timeDisplay === 'dayTime') {
    const dayText = date.toLocaleDateString(languagePreference.value, { month: 'long', day: 'numeric' })
    return `${dayText} ${formatTime(value)}`
  }
  return formatTime(value)
}

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Enter') {
    event.preventDefault()
    emit('open', props.memory)
  } else if (event.key === ' ') {
    event.preventDefault()
    emit('select', props.memory)
  }
}

onBeforeUnmount(cancelSelectIntent)
</script>

<template>
  <article
    class="memory-card group flex cursor-pointer flex-col overflow-hidden rounded-lg border bg-[var(--memory-card-bg)] transition duration-[160ms] ease-[ease]"
    :class="[
      textMemory ? 'memory-card--text' : '',
      selected
        ? 'border-[var(--color-primary)] ring-1 ring-[var(--color-primary)]'
        : 'border-[var(--shell-line)] hover:border-[var(--color-border-strong)]',
    ]"
    role="button"
    tabindex="0"
    :data-memory-id="memory.id"
    aria-haspopup="menu"
    :aria-pressed="selected"
    :aria-busy="analyzing"
    @click="handleCardClick"
    @dblclick.stop="handleCardDoubleClick"
    @contextmenu.prevent="emit('contextmenu', { memory, x: $event.clientX, y: $event.clientY })"
    @keydown="handleKeydown"
  >
    <div
      v-if="textMemory"
      class="memory-card__text-body relative p-4"
    >
      <p class="memory-card__text-content whitespace-pre-wrap text-sm text-[var(--shell-ink)]">
        {{ memory.ai_summary || t('memory.noContent') }}
      </p>
    </div>

    <div v-else class="memory-card__media relative flex items-center justify-center overflow-hidden bg-[var(--color-surface-subtle)]">
      <img
        v-if="imageUrl && !imageFailed"
        :src="imageUrl"
        :alt="displayText || t('memory.imageAnalyzing')"
        class="h-full w-auto max-w-none flex-none transition duration-[160ms] ease-[ease] group-hover:scale-[1.01]"
        loading="lazy"
        @error="imageFailed = true"
      />
      <div v-else class="flex flex-col items-center gap-1.5 text-[var(--shell-muted)]">
        <HugeiconsIcon :icon="Image01FreeIcons" class="h-9 w-9" aria-hidden="true" />
        <span class="text-xs">{{ t('memory.previewFailed') }}</span>
      </div>
    </div>

    <div
      class="flex flex-col"
      :class="textMemory ? 'memory-card__text-footer' : 'memory-card__image-body flex-1 px-2 pt-1.5 pb-1'"
    >
      <p v-if="!textMemory" class="line-clamp-4 text-sm text-[var(--shell-ink)]">
        {{ displayText || (showStatus ? '' : t('memory.noContent')) }}
      </p>
      <div
        class="memory-card__metadata-row mt-auto flex min-h-5 items-center gap-2"
        :class="{ 'pt-0.5': !textMemory }"
      >
        <div class="memory-card__tag-area">
          <MemoryAnalysisState
            v-if="showStatus"
            variant="inline"
            :status="analysisUnavailable ? 'FAILED' : 'PROCESSING'"
          />
          <template v-if="searching">
            <span
              v-for="kind in matchSourceKinds"
              :key="kind"
              class="rounded px-2 py-0.5 text-xs"
              :class="kind === 'exact'
                ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-hover)]'
                : 'bg-[color-mix(in_srgb,var(--color-accent)_12%,transparent)] text-[var(--color-accent-hover)]'"
            >
              {{ t(kind === 'exact' ? 'match.exact' : 'match.semantic') }}
            </span>
          </template>
          <div v-if="visibleTags.length" class="memory-card__tags">
            <span
              v-for="tag in visibleTags"
              :key="tag.id"
              v-hint-tooltip="tag.name"
              class="memory-card__tag-chip"
            >
              <span class="memory-card__tag-chip__label">{{ tag.name }}</span>
            </span>
            <span
              v-if="hiddenTagCount"
              v-hint-tooltip="cardTags.map((tag) => tag.name).join(t('filter.valueSeparator'))"
              class="memory-card__tag-chip memory-card__tag-chip--more"
            >
              <span class="memory-card__tag-chip__label">+{{ hiddenTagCount }}</span>
            </span>
          </div>
        </div>
        <time class="flex-none text-xs text-[var(--shell-muted)]" :datetime="memory.created_at">
          {{ formatCardTime(memory.created_at) }}
        </time>
      </div>

      <div
        v-if="searching && isDev && showDebug && memory.search_debug"
        class="mt-2 flex flex-wrap gap-x-2 text-[10px] text-[var(--shell-muted)]"
      >
        <span v-if="memory.search_debug.semantic_distance != null">
          {{ t('search.semanticDistance') }} {{ memory.search_debug.semantic_distance.toFixed(4) }}
        </span>
        <span v-if="memory.search_debug.rrf_score != null">
          RRF {{ memory.search_debug.rrf_score.toFixed(5) }}
        </span>
      </div>
    </div>
  </article>
</template>

<style scoped>
.memory-card {
  --memory-card-shadow-hover:
    0 1px 2px rgba(43, 70, 120, 0.08),
    0 12px 28px rgba(43, 70, 120, 0.13);
  --memory-card-shadow-selected:
    0 2px 5px rgba(59, 86, 201, 0.1),
    0 12px 26px rgba(59, 86, 201, 0.13);

  inline-size: var(--memory-card-width, 290px);
  block-size: 280px;
  box-shadow: var(--shadow-card);
}

.memory-card:hover {
  box-shadow: var(--memory-card-shadow-hover);
}

.memory-card[aria-pressed='true'] {
  box-shadow: var(--memory-card-shadow-selected);
}

:global(:root[data-theme='dark'] .memory-card) {
  --memory-card-shadow-hover: 0 14px 34px rgba(0, 0, 0, 0.3);
  --memory-card-shadow-selected: 0 14px 34px rgba(0, 0, 0, 0.34);
}

.memory-card__media {
  flex: 0 0 148px;
  margin: var(--memory-card-layer-inset);
  border-radius: calc(var(--radius-lg) - 1px - var(--memory-card-layer-inset));
}

.memory-card__text-body {
  flex: 1 1 0;
  min-height: 0;
  margin: var(--memory-card-layer-inset);
  overflow: hidden;
  border-radius: calc(var(--radius-lg) - 1px - var(--memory-card-layer-inset));
  /* 文字卡主题色块：比画布更深、更蓝一档，避免整卡与画布背景混成一片 */
  background: color-mix(in srgb, var(--color-primary) 20%, var(--color-surface));
}

:global(:root:not([data-theme='dark']) .memory-card__text-body) {
  background: color-mix(in srgb, var(--color-primary) 28%, var(--color-surface));
}

.memory-card__text-content {
  display: -webkit-box;
  height: 100%;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 8;
}

.memory-card__text-footer {
  flex: 0 0 3.5rem;
  padding: 4px 8px;
  background: var(--memory-card-bg);
}

.memory-card__tag-area {
  display: flex;
  min-width: 0;
  flex: 1 1 auto;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

/* 标签组单行展示：挤不下时逐个截断，时间列在右侧不受影响。 */
.memory-card__tags {
  display: flex;
  min-width: 0;
  flex: 0 1 auto;
  flex-wrap: nowrap;
  align-items: center;
  gap: 0.25rem;
  overflow: hidden;
}

.memory-card__tag-chip {
  display: inline-flex;
  min-width: calc(1.125rem + 1em);
  flex: 0 1 auto;
  align-items: center;
  justify-content: center;
  height: 1.125rem;
  overflow: hidden;
  padding: 0 calc(1.125rem / 2);
  border-radius: 999px;
  background: color-mix(in srgb, var(--color-primary) 24%, var(--color-surface));
  color: var(--color-primary-hover);
  font-size: 0.75rem;
}

.memory-card__tag-chip__label {
  min-width: 0;
  overflow: hidden;
  font-size: inherit;
  line-height: 1rem;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.memory-card__tag-chip--more {
  flex: none;
}

</style>
