import { defineStore } from 'pinia'
import { ref } from 'vue'
import { createLogger } from '@/utils/logger'

const logger = createLogger('stores/cluster')

export const useClusterStore = defineStore('cluster', () => {
  const state = ref<'IDLE' | 'COLLECTING'>('IDLE')
  const count = ref(0)
  const maxCount = ref(5)
  const images = ref<string[]>([])
  const remainingSeconds = ref(0)

  const isCollecting = () => state.value === 'COLLECTING'

  const setState = (data: { state: string; count: number; max_count: number; images?: string[] }) => {
    state.value = data.state as 'IDLE' | 'COLLECTING'
    count.value = data.count
    maxCount.value = data.max_count
    if (data.images) {
      images.value = data.images
    }
  }

  const setCountdown = (seconds: number) => {
    remainingSeconds.value = seconds
  }

  const flush = (flushedImages: string[]) => {
    images.value = []
    count.value = 0
    state.value = 'IDLE'
    remainingSeconds.value = 0
    logger.info('Cluster flushed: %s', flushedImages)
  }

  const discard = () => {
    images.value = []
    count.value = 0
    state.value = 'IDLE'
    remainingSeconds.value = 0
  }

  return {
    state,
    count,
    maxCount,
    images,
    remainingSeconds,
    isCollecting,
    setState,
    setCountdown,
    flush,
    discard,
  }
})