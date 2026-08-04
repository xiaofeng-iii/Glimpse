<script setup lang="ts">
import { computed, ref } from 'vue'
import { CheckCircleIcon, PhotoIcon } from '@heroicons/vue/24/outline'
import type { Memory } from '@/api/client'
import { getMemoryImageUrls } from '@/utils/memory-images'
import { getMatchSourceKinds } from '@/utils/match-sources'
import { t } from '@/utils/i18n'

const props = defineProps<{
  memory: Memory
  selected?: boolean
  searching?: boolean
  showDebug?: boolean
}>()

const emit = defineEmits<{
  (event: 'select', memory: Memory): void
  (event: 'open', memory: Memory): void
}>()

const imageFailed = ref(false)
const isDev = import.meta.env.DEV
const imageUrl = computed(() => getMemoryImageUrls(props.memory)[0] ?? '')
const matchSourceKinds = computed(() => getMatchSourceKinds(props.memory.match_sources))

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
    class="memory-card group cursor-pointer overflow-hidden rounded-lg border bg-[var(--shell-card)] outline-none transition duration-200 focus-visible:ring-2 focus-visible:ring-[var(--color-primary)]"
    :class="selected
      ? 'border-[var(--color-primary)] shadow-[0_4px_14px_rgba(59,86,201,.10)] ring-1 ring-[var(--color-primary)]'
      : 'border-[var(--shell-line)] hover:border-[var(--color-border-strong)] hover:shadow-md'"
    tabindex="0"
    :aria-selected="selected"
    @click="emit('select', memory)"
    @dblclick.stop="emit('open', memory)"
    @keydown="handleKeydown"
  >
    <div class="relative flex aspect-[1.28/1] items-center justify-center overflow-hidden bg-slate-100/70">
      <img
        v-if="imageUrl && !imageFailed"
        :src="imageUrl"
        :alt="memory.ai_summary"
        class="h-full w-full object-contain transition duration-300 group-hover:scale-[1.01]"
        loading="lazy"
        @error="imageFailed = true"
      />
      <PhotoIcon v-else class="h-9 w-9 text-[var(--shell-muted)]" aria-hidden="true" />
      <CheckCircleIcon
        v-if="selected"
        class="absolute left-2.5 top-2.5 h-5 w-5 rounded-full bg-white text-[var(--color-primary)]"
        aria-hidden="true"
      />
    </div>

    <div class="p-3.5">
      <p class="line-clamp-2 min-h-10 text-[13px] leading-5 text-[var(--shell-ink)]">
        {{ memory.ai_summary || t('memory.noContent') }}
      </p>
      <div class="mt-2.5 flex min-h-6 items-center gap-2">
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
        <time class="ml-auto text-xs text-[var(--shell-muted)]" :datetime="memory.created_at">
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
