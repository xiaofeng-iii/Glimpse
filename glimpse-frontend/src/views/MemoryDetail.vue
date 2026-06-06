<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { memoriesApi, type Memory } from '@/api/client'
import { getImageUrl } from '@/config/runtime'
import { openExternalTarget } from '@/platform/desktop'
import { useNotificationStore } from '@/stores/notification'
import { getMemoryImageUrls } from '@/utils/memory-images'
import { createLogger } from '@/utils/logger'
import ImagePreviewModal from '@/components/ImagePreviewModal.vue'

const logger = createLogger('views/MemoryDetail')

const route = useRoute()
const router = useRouter()
const notificationStore = useNotificationStore()

const memory = ref<Memory | null>(null)
const isLoading = ref(true)
const previewOpen = ref(false)
const previewIndex = ref(0)
const failedImages = ref<Record<string, boolean>>({})

onMounted(async () => {
  const id = route.params.id as string
  try {
    memory.value = await memoriesApi.get(id)
  } catch (error) {
    logger.error('Failed to load memory: %s', error)
  } finally {
    isLoading.value = false
  }
})

const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleString('zh-CN')
}

const handleDelete = async () => {
  if (memory.value && confirm('确定要删除这条记忆吗？')) {
    await memoriesApi.delete(memory.value.id)
    router.push('/')
  }
}

const handleCopy = async () => {
  if (!memory.value) {
    return
  }

  try {
    await navigator.clipboard.writeText(memory.value.ai_summary)
    notificationStore.show('已复制成功', 'success', 2200)
  } catch (error) {
    notificationStore.show('复制失败，请重试。', 'error', 3000)
  }
}

const handleOpenImage = () => {
  if (!memory.value) {
    return
  }
  void openExternalTarget(getImageUrl(memory.value.image_path))
}

const imageUrls = computed(() => {
  if (!memory.value) {
    return []
  }

  return getMemoryImageUrls(memory.value)
})

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
  <div class="h-screen overflow-y-auto overflow-x-hidden p-4 sm:p-6">
    <div class="max-w-3xl mx-auto pb-10">
      <!-- Loading -->
      <div v-if="isLoading" class="flex justify-center py-20">
        <div class="spinner"></div>
      </div>

      <!-- Memory Detail -->
      <div v-else-if="memory">
        <!-- Header -->
        <div class="flex items-center justify-between mb-6">
          <button @click="router.back()" class="btn-secondary">
            <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            返回
          </button>
          <div class="flex gap-2">
            <button @click="handleCopy" class="btn-secondary">复制摘要</button>
            <button @click="handleOpenImage" class="btn-secondary">查看图片</button>
            <button @click="handleDelete" class="px-4 py-2 text-red-500 hover:bg-red-50 rounded-lg transition-colors">删除</button>
          </div>
        </div>

        <!-- Content Card -->
        <div class="card p-8">
          <!-- Image Preview -->
          <div v-if="imageUrls.length" class="mb-8 space-y-3">
            <button
              class="block w-full overflow-hidden rounded-3xl border border-slate-200 bg-slate-100"
              @click="openPreview(0)"
            >
              <img
                v-if="!failedImages[imageUrls[0]]"
                :src="imageUrls[0]"
                :alt="memory.ai_summary"
                class="h-[420px] w-full object-contain"
                @error="markImageError(imageUrls[0])"
              />
              <div v-else class="flex h-[420px] items-center justify-center text-sm text-slate-500">
                图片预览加载失败
              </div>
            </button>

            <div v-if="imageUrls.length > 1" class="grid grid-cols-4 gap-3">
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
                  class="h-24 w-full object-cover"
                  @error="markImageError(imageUrl)"
                />
                <div v-else class="flex h-24 items-center justify-center text-[11px] text-slate-400">
                  加载失败
                </div>
              </button>
            </div>
          </div>

          <!-- Time -->
          <p class="text-sm text-gray-500 mb-4">{{ formatDate(memory.created_at) }}</p>

          <!-- App Badge -->
          <div v-if="memory.app_name && memory.app_name !== 'unknown'" class="inline-flex px-3 py-1 rounded-lg bg-gradient-to-r from-indigo-50 to-violet-50 text-indigo-600 text-sm font-medium mb-6">
            {{ memory.app_name }}
          </div>

          <!-- AI Summary -->
          <h2 class="text-lg font-semibold text-gray-900 mb-3">AI 摘要</h2>
          <p class="text-gray-900 leading-relaxed mb-8">{{ memory.ai_summary }}</p>

          <!-- Extracted Text -->
          <div v-if="memory.text_content">
            <h2 class="text-lg font-semibold text-gray-900 mb-3">识别文本</h2>
            <p class="text-gray-600 leading-relaxed bg-gray-50 p-4 rounded-xl">{{ memory.text_content }}</p>
          </div>

          <!-- Image Path -->
          <div class="mt-8 pt-6 border-t border-gray-100">
            <p class="text-xs text-gray-400">
              <span class="font-medium">图片路径:</span> {{ memory.image_path }}
            </p>
          </div>
        </div>
      </div>

      <!-- Not Found -->
      <div v-else class="text-center py-20 text-gray-500">
        记忆不存在或已删除
      </div>
    </div>

    <ImagePreviewModal
      v-if="memory"
      :open="previewOpen"
      :images="imageUrls"
      :start-index="previewIndex"
      @close="previewOpen = false"
      @update:start-index="previewIndex = $event"
    />
  </div>
</template>
