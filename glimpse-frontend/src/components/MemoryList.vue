<script setup lang="ts">
import { computed } from 'vue'
import type { Memory } from '@/api/client'
import EmptyState from './EmptyState.vue'
import LoadingSpinner from './LoadingSpinner.vue'

const props = defineProps<{
  memories: Memory[]
  isLoading: boolean
  selectedId?: string
}>()

const emit = defineEmits<{
  (e: 'select', memory: Memory): void
  (e: 'open', memory: Memory): void
}>()

const hasMemories = computed(() => props.memories.length > 0)

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
</script>

<template>
  <div class="card p-4">
    <!-- Loading State -->
    <div v-if="isLoading" class="flex justify-center py-12">
      <LoadingSpinner />
    </div>

    <!-- Empty State -->
    <EmptyState v-else-if="!hasMemories" />

    <!-- Memory List -->
    <div v-else class="space-y-3">
      <!-- Header -->
      <div class="flex items-center justify-between mb-4">
        <span class="text-sm text-gray-500">{{ memories.length }} 条记忆</span>
      </div>

      <!-- Memory Cards -->
      <div
        v-for="memory in memories"
        :key="memory.id"
        @click="emit('select', memory)"
        @dblclick.stop="emit('open', memory)"
        :class="[
          'group relative p-4 rounded-2xl cursor-pointer transition-all duration-300',
          selectedId === memory.id
            ? 'bg-gradient-to-r from-violet-50 to-pink-50 border-2 border-violet-200'
            : 'bg-white hover:bg-gray-50 border border-gray-100 hover:border-violet-200'
        ]"
      >
        <div class="flex gap-4 items-start">
          <!-- Thumbnail -->
          <div class="relative flex-shrink-0">
            <div class="absolute inset-0 rounded-xl bg-gradient-to-br from-violet-400 to-pink-400 opacity-0 group-hover:opacity-100 transition-opacity duration-300" style="transform: scale(1.05);"></div>
            <div class="w-14 h-14 rounded-xl bg-gray-100 flex items-center justify-center overflow-hidden relative z-10">
              <svg class="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
          </div>

          <!-- Content -->
          <div class="flex-1 min-w-0">
            <p class="text-gray-900 text-sm font-medium truncate">
              {{ truncate(memory.ai_summary, 80) }}
            </p>

            <!-- Badges -->
            <div class="flex items-center gap-2 mt-2">
              <span
                v-if="memory.match_sources?.includes('精确')"
                class="badge badge-ocr"
              >
                OCR
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
          </div>

          <!-- App Badge -->
          <div
            v-if="memory.app_name && memory.app_name !== 'unknown'"
            class="px-3 py-1 rounded-lg bg-gradient-to-r from-indigo-50 to-violet-50 text-indigo-600 text-xs font-medium flex-shrink-0"
          >
            {{ memory.app_name }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
