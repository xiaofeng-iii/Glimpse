<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Memory } from '@/api/client'
import { getMemoryImageUrls } from '@/utils/memory-images'
import EmptyState from './EmptyState.vue'
import LoadingSpinner from './LoadingSpinner.vue'

const props = defineProps<{
  memories: Memory[]
  isLoading: boolean
  selectedId?: string
  deletingId?: string | null
}>()

const emit = defineEmits<{
  (e: 'select', memory: Memory): void
  (e: 'open', memory: Memory): void
  (e: 'delete', memory: Memory): void
}>()

const hasMemories = computed(() => props.memories.length > 0)
const failedImages = ref<Record<string, boolean>>({})

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
  <div class="card flex h-full max-h-[calc(100vh-11rem)] min-h-[420px] flex-col overflow-hidden p-4 xl:sticky xl:top-24">
    <!-- Loading State -->
    <div v-if="isLoading" class="flex justify-center py-12">
      <LoadingSpinner />
    </div>

    <!-- Empty State -->
    <EmptyState v-else-if="!hasMemories" />

    <!-- Memory List -->
    <div v-else class="flex min-h-0 flex-1 flex-col">
      <!-- Header -->
      <div class="mb-4 flex items-center justify-between">
        <span class="text-sm text-gray-500">{{ memories.length }} 条记忆</span>
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
                ? 'border-violet-200 bg-gradient-to-r from-violet-50 to-pink-50 shadow-sm'
                : 'border-gray-100 bg-white hover:border-violet-200 hover:bg-gray-50',
            ]"
          >
            <div class="flex items-start gap-4">
              <!-- Thumbnail -->
              <div class="relative flex-shrink-0">
                <div class="absolute inset-0 rounded-xl bg-gradient-to-br from-violet-400 to-pink-400 opacity-0 transition-opacity duration-300 group-hover:opacity-100" style="transform: scale(1.05);"></div>
                <div class="relative z-10 flex h-14 w-14 items-center justify-center overflow-hidden rounded-xl bg-gray-100">
                  <img
                    v-if="getPrimaryImageUrl(memory) && !failedImages[memory.id]"
                    :src="getPrimaryImageUrl(memory)"
                    :alt="memory.ai_summary"
                    class="h-full w-full object-cover"
                    loading="lazy"
                    @error="markImageError(memory.id)"
                  />
                  <svg v-else class="h-6 w-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
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
                    v-if="memory.match_sources?.includes('精确')"
                    class="badge badge-exact"
                  >
                    精确
                  </span>
                  <span
                    v-if="memory.match_sources?.includes('语义')"
                    class="badge badge-semantic"
                  >
                    语义
                  </span>
                  <span class="text-xs text-gray-400">
                    {{ formatTime(memory.created_at) }}
                  </span>
                </div>

                <div class="mt-3 flex items-center justify-between gap-3">
                  <div
                    v-if="memory.app_name && memory.app_name !== 'unknown'"
                    class="rounded-lg bg-gradient-to-r from-indigo-50 to-violet-50 px-3 py-1 text-xs font-medium text-indigo-600"
                  >
                    {{ memory.app_name }}
                  </div>
                  <div v-else class="text-xs text-gray-400">
                    双击查看详情
                  </div>

                  <button
                    class="inline-flex items-center rounded-full border border-slate-200/85 bg-slate-50/72 px-3 py-1.5 text-xs font-medium text-slate-500 transition-colors hover:border-sky-200 hover:bg-sky-50/82 hover:text-sky-600 disabled:cursor-not-allowed disabled:opacity-60"
                    :disabled="Boolean(deletingId)"
                    @click.stop="handleDelete(memory)"
                  >
                    {{ deletingId === memory.id ? '删除中...' : '删除' }}
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
