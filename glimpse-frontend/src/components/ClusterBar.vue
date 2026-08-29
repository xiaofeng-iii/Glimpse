<script setup lang="ts">
import { computed } from 'vue'
import { useClusterStore } from '@/stores/cluster'
import { t } from '@/utils/i18n'

const clusterStore = useClusterStore()

const progressText = computed(() => {
  return t('cluster.progressCount', {
    count: clusterStore.count,
    max: clusterStore.maxCount,
  })
})

const countdownText = computed(() => {
  if (clusterStore.remainingSeconds > 0) {
    return `(${clusterStore.remainingSeconds}s)`
  }
  return ''
})
</script>

<template>
  <div class="card mb-4 border-[color-mix(in_srgb,var(--color-primary)_22%,transparent)] bg-[var(--color-primary-soft)] p-3.5">
    <div class="flex items-center justify-between">
      <!-- Status -->
      <div class="flex items-center gap-2.5">
        <div class="w-2.5 h-2.5 rounded-full bg-[var(--color-primary)] animate-pulse-soft"></div>
        <span class="text-sm font-medium text-[var(--color-primary-hover)]">
          {{ t('cluster.progress', { progress: progressText, countdown: countdownText }) }}
        </span>
      </div>

      <!-- Actions -->
      <div class="flex gap-2">
        <button @click="$emit('submit')" class="btn-primary">
          {{ t('cluster.submit') }}
        </button>
        <button @click="$emit('cancel')" class="btn-secondary">
          {{ t('action.cancel') }}
        </button>
      </div>
    </div>

    <!-- Progress Bar -->
    <div class="mt-2.5 h-1.5 bg-gray-200 rounded-full overflow-hidden">
      <div
        :style="{ width: `${(clusterStore.count / clusterStore.maxCount) * 100}%` }"
        class="h-full bg-[var(--color-primary)] transition-all duration-300"
      ></div>
    </div>
  </div>
</template>
