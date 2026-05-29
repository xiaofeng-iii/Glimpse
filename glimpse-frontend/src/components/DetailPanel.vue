<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Memory } from '@/api/client'
import { getImageUrl } from '@/config/runtime'
import { openExternalTarget } from '@/platform/desktop'
import { useMemoriesStore } from '@/stores/memories'
import { useNotificationStore } from '@/stores/notification'
import { getMemoryImageUrls } from '@/utils/memory-images'
import ImagePreviewModal from './ImagePreviewModal.vue'

const props = defineProps<{
  memory: Memory
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'open', memoryId: string): void
}>()

const memoriesStore = useMemoriesStore()
const notificationStore = useNotificationStore()
const previewOpen = ref(false)
const previewIndex = ref(0)
const failedImages = ref<Record<string, boolean>>({})

const imageUrls = computed(() => getMemoryImageUrls(props.memory))

const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleString('zh-CN')
}

const handleDelete = async () => {
  if (confirm('确定要删除这条记忆吗？此操作不可撤销。')) {
    await memoriesStore.remove(props.memory.id)
    emit('close')
  }
}

const handleCopy = async () => {
  try {
    await navigator.clipboard.writeText(props.memory.ai_summary)
    notificationStore.show('已复制成功', 'success', 2200)
  } catch (error) {
    notificationStore.show('复制失败，请重试。', 'error', 3000)
  }
}

const handleOpenImage = () => {
  void openExternalTarget(getImageUrl(props.memory.image_path))
}

const handleOpenDetail = () => {
  emit('open', props.memory.id)
}

const openPreview = (index = 0) => {
  previewIndex.value = index
  previewOpen.value = true
}

const markImageError = (url: string) => {
  failedImages.value = {
    ...failedImages.value,
    [url]: true,
  }
}
</script>

<template>
  <div class="card h-full min-h-0 overflow-hidden">
    <div class="h-full min-h-0 overflow-y-auto p-6">
      <!-- Header -->
      <div class="flex items-start justify-between mb-4">
        <div>
          <h3 class="text-lg font-bold text-gray-900">记忆详情</h3>
          <p class="text-sm text-gray-500 mt-1">{{ formatDate(memory.created_at) }}</p>
        </div>
        <button
          @click="emit('close')"
          class="p-2 rounded-lg hover:bg-gray-100 transition-colors"
        >
          <svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- App Badge -->
      <div
        v-if="memory.app_name && memory.app_name !== 'unknown'"
        class="inline-flex px-3 py-1 rounded-lg bg-gradient-to-r from-indigo-50 to-violet-50 text-indigo-600 text-sm font-medium mb-4"
      >
        {{ memory.app_name }}
      </div>

      <div v-if="imageUrls.length" class="mb-6 space-y-3">
        <button
          class="block w-full overflow-hidden rounded-3xl border border-slate-200 bg-slate-100"
          @click="openPreview(0)"
        >
          <img
            v-if="!failedImages[imageUrls[0]]"
            :src="imageUrls[0]"
            :alt="memory.ai_summary"
            class="h-64 w-full object-cover"
            @error="markImageError(imageUrls[0])"
          />
          <div v-else class="flex h-64 items-center justify-center text-sm text-slate-500">
            图片预览加载失败
          </div>
        </button>

        <div v-if="imageUrls.length > 1" class="grid grid-cols-4 gap-2">
          <button
            v-for="(imageUrl, index) in imageUrls.slice(1)"
            :key="imageUrl"
            class="overflow-hidden rounded-2xl border border-slate-200 bg-slate-100"
            @click="openPreview(index + 1)"
          >
            <img
              v-if="!failedImages[imageUrl]"
              :src="imageUrl"
              :alt="`${memory.ai_summary}-${index + 2}`"
              class="h-20 w-full object-cover"
              @error="markImageError(imageUrl)"
            />
            <div v-else class="flex h-20 items-center justify-center text-[11px] text-slate-400">
              加载失败
            </div>
          </button>
        </div>
      </div>

      <!-- AI Summary -->
      <div class="mb-4">
        <h4 class="text-sm font-semibold text-gray-700 mb-2">AI 摘要</h4>
        <p class="text-gray-900 leading-relaxed">{{ memory.ai_summary }}</p>
      </div>

      <!-- Extracted Text -->
      <div v-if="memory.text_content" class="mb-4">
        <h4 class="text-sm font-semibold text-gray-700 mb-2">识别文本</h4>
        <p class="text-gray-600 text-sm leading-relaxed max-h-32 overflow-y-auto">{{ memory.text_content }}</p>
      </div>

      <!-- Image Path -->
      <div class="mb-6 text-xs text-gray-400 truncate">
        <span class="font-medium">图片:</span> {{ memory.image_path }}
      </div>

      <!-- Actions -->
      <div class="flex gap-2">
        <button
          @click="handleOpenDetail"
          class="flex-1 btn-primary text-sm py-2 justify-center"
        >
          查看详情
        </button>
        <button
          @click="handleCopy"
          class="flex-1 btn-secondary text-sm py-2"
        >
          复制摘要
        </button>
        <button
          @click="handleOpenImage"
          class="flex-1 btn-secondary text-sm py-2"
        >
          打开图片
        </button>
      </div>

      <button
        @click="handleDelete"
        class="w-full mt-3 py-2 text-sm text-red-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
      >
        删除记忆
      </button>
    </div>
  </div>

  <ImagePreviewModal
    :open="previewOpen"
    :images="imageUrls"
    :start-index="previewIndex"
    @close="previewOpen = false"
    @update:start-index="previewIndex = $event"
  />
</template>
