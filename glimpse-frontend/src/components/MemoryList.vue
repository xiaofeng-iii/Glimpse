<script setup lang="ts">
import { computed, ref } from 'vue'
import { PhotoIcon } from '@heroicons/vue/24/outline'
import type { Memory } from '@/api/client'
import { getMemoryImageUrls } from '@/utils/memory-images'
import { getMatchSourceKinds } from '@/utils/match-sources'
import { t } from '@/utils/i18n'
import EmptyState from './EmptyState.vue'
import LoadingSpinner from './LoadingSpinner.vue'

const props = defineProps<{
  memories: Memory[]
  isLoading: boolean
  selectedId?: string
  deletingId?: string | null
  shortcutLabel?: string
}>()

const emit = defineEmits<{
  (e: 'select', memory: Memory): void
  (e: 'open', memory: Memory): void
  (e: 'delete', memory: Memory): void
}>()

const hasMemories = computed(() => props.memories.length > 0)
const failedImages = ref<Record<string, boolean>>({})
const isDev = import.meta.env.DEV

const formatTime = (dateStr: string) => {
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const truncate = (text: string, length: number) => {
  if (!text) return ''
  return text.length > length ? text.slice(0, length) + '...' : text
}

const formatScore = (value: number) => value.toFixed(5)
const formatDistance = (value: number) => value.toFixed(4)

const handleDelete = (memory: Memory) => {
  emit('delete', memory)
}

const getPrimaryImageUrl = (memory: Memory) => getMemoryImageUrls(memory)[0] || ''

const markImageError = (memoryId: string) => {
  failedImages.value = {
    ...failedImages.value,
    [memoryId]: true,
  }
}
</script>

<template>
  <div class="card flex h-full min-h-0 flex-col overflow-hidden p-4">
    <!-- Loading State -->
    <div v-if="isLoading" class="flex justify-center py-12">
      <LoadingSpinner />
    </div>

    <!-- Empty State -->
    <EmptyState v-else-if="!hasMemories" :shortcut-label="shortcutLabel ?? 'Ctrl+Shift+G'" />

    <!-- Memory List -->
    <div v-else class="flex min-h-0 flex-1 flex-col">
      <!-- Header -->
      <div class="mb-4 flex items-center justify-between">
        <span class="text-sm text-gray-500">{{ t('memory.count', { count: memories.length }) }}</span>
      </div>

      <!-- Memory Cards -->
      <div class="min-h-0 flex-1 overflow-y-auto pr-1">
        <div class="space-y-3">
          <div
            v-for="memory in memories"
            :key="memory.id"
            @click="emit('select', memory)"
            @dblclick.stop="emit('open', memory)"
            :class="[
              'group relative cursor-pointer rounded-2xl border p-4 transition-all duration-300',
              selectedId === memory.id
                ? 'border-blue-300 bg-blue-50 shadow-sm'
                : 'border-gray-100 bg-white hover:border-violet-200 hover:bg-gray-50',
            ]"
          >
            <div class="flex items-start gap-4">
              <!-- Thumbnail -->
              <div class="relative flex-shrink-0">
                <div class="relative z-10 flex h-14 w-14 items-center justify-center overflow-hidden rounded-xl bg-gray-100">
                  <img
                    v-if="getPrimaryImageUrl(memory) && !failedImages[memory.id]"
                    :src="getPrimaryImageUrl(memory)"
                    :alt="memory.ai_summary"
                    class="h-full w-full object-cover"
                    loading="lazy"
                    @error="markImageError(memory.id)"
                  />
                  <PhotoIcon v-else class="h-6 w-6 text-gray-400" aria-hidden="true" />
                </div>
              </div>

              <!-- Content -->
              <div class="min-w-0 flex-1">
                <p class="truncate text-sm font-medium text-gray-900">
                  {{ truncate(memory.ai_summary, 80) }}
                </p>

                <!-- Badges -->
                <div class="mt-2 flex items-center gap-2">
                  <span
                    v-for="kind in getMatchSourceKinds(memory.match_sources)"
                    :key="kind"
                    class="badge"
                    :class="kind === 'exact' ? 'badge-exact' : 'badge-semantic'"
                  >
                    {{ t(kind === 'exact' ? 'match.exact' : 'match.semantic') }}
                  </span>
                  <span class="text-xs text-gray-400">
                    {{ formatTime(memory.created_at) }}
                  </span>
                </div>

                <div
                  v-if="isDev && memory.search_debug"
                  class="mt-2 flex flex-wrap gap-x-3 gap-y-1 rounded-lg bg-slate-100/80 px-2 py-1.5 font-mono text-[11px] text-slate-600"
                >
                  <span
                    v-if="memory.search_debug.semantic_distance != null"
                    :title="t('search.distanceHint')"
                  >
                    {{ t('search.semanticDistance') }} {{ formatDistance(memory.search_debug.semantic_distance) }}
                  </span>
                  <span v-if="memory.search_debug.rrf_score != null">
                    RRF {{ formatScore(memory.search_debug.rrf_score) }}
                  </span>
                  <span v-if="memory.search_debug.text_rank != null">
                    {{ t('search.textRank') }} #{{ memory.search_debug.text_rank }}
                  </span>
                  <span v-if="memory.search_debug.semantic_rank != null">
                    {{ t('search.semanticRank') }} #{{ memory.search_debug.semantic_rank }}
                  </span>
                </div>

                <div class="mt-3 flex items-center justify-between gap-3">
                  <div class="text-xs text-gray-400">
                    {{ t('memory.openHint') }}
                  </div>

                  <button
                    class="inline-flex items-center rounded-full border border-slate-200/85 bg-slate-50/72 px-3 py-1.5 text-xs font-medium text-slate-500 transition-colors hover:border-sky-200 hover:bg-sky-50/82 hover:text-sky-600 disabled:cursor-not-allowed disabled:opacity-60"
                    :disabled="Boolean(deletingId)"
                    @click.stop="handleDelete(memory)"
                  >
                    {{ deletingId === memory.id ? t('action.deleting') : t('action.delete') }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
