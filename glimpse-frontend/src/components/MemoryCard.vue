<script setup lang="ts">
import { computed, ref } from 'vue'
import { PhotoIcon } from '@heroicons/vue/24/outline'
import type { Memory } from '@/api/client'
import { getMemoryImageUrls } from '@/utils/memory-images'
import { getMatchSourceKinds } from '@/utils/match-sources'
import { isTextMemory } from '@/utils/memory-types'
import { t } from '@/utils/i18n'
import MemoryAnalysisState from './MemoryAnalysisState.vue'

const props = defineProps<{
  memory: Memory
  selected?: boolean
  searching?: boolean
  showDebug?: boolean
}>()

const emit = defineEmits<{
  (event: 'select', memory: Memory): void
  (event: 'open', memory: Memory): void
  (event: 'contextmenu', payload: { memory: Memory; x: number; y: number }): void
}>()

const imageFailed = ref(false)
const isDev = import.meta.env.DEV
const imageUrl = computed(() => getMemoryImageUrls(props.memory)[0] ?? '')
const textMemory = computed(() => isTextMemory(props.memory))
const matchSourceKinds = computed(() => getMatchSourceKinds(props.memory.match_sources))
const analysisStatus = computed(() => props.memory.analysis_status ?? 'COMPLETED')
const analyzing = computed(() => analysisStatus.value === 'PROCESSING')
const analysisUnavailable = computed(() => analysisStatus.value === 'FAILED')

const formatTime = (value: string) =>
  new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Enter') {
    event.preventDefault()
    emit('open', props.memory)
  } else if (event.key === ' ') {
    event.preventDefault()
    emit('select', props.memory)
  }
}
</script>

<template>
  <article
    class="memory-card group flex cursor-pointer flex-col overflow-hidden rounded-lg border bg-[var(--shell-card)] transition duration-200"
    :class="[
      textMemory ? 'memory-card--text' : '',
      selected
        ? 'border-[var(--color-primary)] shadow-[0_4px_14px_rgba(59,86,201,.10)] ring-1 ring-[var(--color-primary)]'
        : 'border-[var(--shell-line)] hover:border-[var(--color-border-strong)] hover:shadow-md',
    ]"
    role="button"
    tabindex="0"
    :data-memory-id="memory.id"
    aria-haspopup="menu"
    :aria-pressed="selected"
    :aria-busy="analyzing"
    @click="emit('select', memory)"
    @dblclick.stop="emit('open', memory)"
    @contextmenu.prevent="emit('contextmenu', { memory, x: $event.clientX, y: $event.clientY })"
    @keydown="handleKeydown"
  >
    <div
      v-if="textMemory"
      class="memory-card__text-body relative bg-[var(--color-primary-soft)] p-4"
    >
      <p class="memory-card__text-content whitespace-pre-wrap text-sm text-[var(--shell-ink)]">
        {{ memory.ai_summary || t('memory.noContent') }}
      </p>
    </div>

    <div v-else class="memory-card__media relative flex items-center justify-center overflow-hidden bg-slate-100/70">
      <img
        v-if="imageUrl && !imageFailed"
        :src="imageUrl"
        :alt="memory.ai_summary || t('memory.analysisProcessing')"
        class="h-full w-full object-contain transition duration-300 group-hover:scale-[1.01]"
        loading="lazy"
        @error="imageFailed = true"
      />
      <PhotoIcon v-else class="h-9 w-9 text-[var(--shell-muted)]" aria-hidden="true" />
    </div>

    <div
      class="flex flex-col"
      :class="textMemory ? 'memory-card__text-footer' : 'flex-1 p-2'"
    >
      <MemoryAnalysisState
        v-if="!textMemory && (analyzing || analysisUnavailable)"
        :status="analysisUnavailable ? 'FAILED' : 'PROCESSING'"
        compact
      />
      <p v-else-if="!textMemory" class="line-clamp-4 min-h-20 text-[13px] leading-5 text-[var(--shell-ink)]">
        {{ memory.ai_summary || t('memory.noContent') }}
      </p>
      <div
        class="memory-card__metadata-row mt-auto flex min-h-6 items-center gap-2"
        :class="{ 'pt-[5px]': !textMemory }"
      >
        <div class="memory-card__tag-area">
          <template v-if="searching">
            <span
              v-for="kind in matchSourceKinds"
              :key="kind"
              class="rounded px-2 py-0.5 text-[11px] font-semibold"
              :class="kind === 'exact'
                ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-hover)]'
                : 'bg-[color-mix(in_srgb,var(--color-accent)_12%,transparent)] text-[var(--color-accent-hover)]'"
            >
              {{ t(kind === 'exact' ? 'match.exact' : 'match.semantic') }}
            </span>
          </template>
        </div>
        <time class="flex-none text-xs text-[var(--shell-muted)]" :datetime="memory.created_at">
          {{ formatTime(memory.created_at) }}
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
  inline-size: var(--memory-card-width, 239px);
  block-size: 270px;
}

.memory-card__media {
  flex: 0 0 148px;
}

.memory-card__text-body {
  flex: 1 1 0;
  min-height: 0;
  border-bottom: 1px solid var(--shell-line);
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
  padding: 8px;
  background: var(--shell-card);
}

.memory-card__tag-area {
  display: flex;
  min-width: 0;
  flex: 1 1 auto;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

.memory-card:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
</style>
