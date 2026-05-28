<script setup lang="ts">
import { computed } from 'vue'
import { useClusterStore } from '@/stores/cluster'

const clusterStore = useClusterStore()

const progressText = computed(() => {
  return `${clusterStore.count}/${clusterStore.maxCount} 张截图`
})

const countdownText = computed(() => {
  if (clusterStore.remainingSeconds > 0) {
    return `(${clusterStore.remainingSeconds}s)`
  }
  return ''
})
</script>

<template>
  <div class="card p-4 mb-6 bg-gradient-to-r from-violet-50 to-pink-50 border-violet-200">
    <div class="flex items-center justify-between">
      <!-- Status -->
      <div class="flex items-center gap-3">
        <div class="w-3 h-3 rounded-full bg-violet-500 animate-pulse-soft"></div>
        <span class="text-violet-700 font-medium">
          正在收集 {{ progressText }} {{ countdownText }}
        </span>
      </div>

      <!-- Actions -->
      <div class="flex gap-2">
        <button
          @click="$emit('submit')"
          class="px-4 py-2 rounded-lg bg-gradient-to-r from-violet-600 to-pink-600 text-white text-sm font-medium hover:scale-105 transition-transform"
        >
          立即提交
        </button>
        <button
          @click="$emit('cancel')"
          class="px-4 py-2 rounded-lg bg-white text-gray-600 text-sm font-medium hover:bg-gray-100 transition-colors"
        >
          取消
        </button>
      </div>
    </div>

    <!-- Progress Bar -->
    <div class="mt-3 h-2 bg-gray-200 rounded-full overflow-hidden">
      <div
        :style="{ width: `${(clusterStore.count / clusterStore.maxCount) * 100}%` }"
        class="h-full bg-gradient-to-r from-violet-500 to-pink-500 transition-all duration-300"
      ></div>
    </div>
  </div>
</template>