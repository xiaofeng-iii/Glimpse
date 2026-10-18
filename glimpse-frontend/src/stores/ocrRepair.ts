import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { ocrApi, type OcrBackfillStatus } from '@/api/client'
import { createLogger } from '@/utils/logger'

const logger = createLogger('stores/ocrRepair')
const POLL_INTERVAL_MS = 1000

export const useOcrRepairStore = defineStore('ocr-repair', () => {
  const status = ref<OcrBackfillStatus | null>(null)
  const starting = ref(false)
  const error = ref<string | null>(null)
  let pollTimer: ReturnType<typeof window.setTimeout> | null = null

  const running = computed(() => Boolean(status.value?.running))
  const result = computed(() => status.value?.result ?? null)
  const total = computed(() => result.value?.total ?? 0)
  const processed = computed(() => result.value?.processed ?? 0)
  const percent = computed(() =>
    total.value > 0
      ? Math.min(100, Math.max(0, Math.round((processed.value / total.value) * 100)))
      : 0,
  )

  const stopPolling = () => {
    if (pollTimer) {
      window.clearTimeout(pollTimer)
      pollTimer = null
    }
  }

  const schedule = () => {
    stopPolling()
    if (!running.value) return
    pollTimer = window.setTimeout(() => {
      pollTimer = null
      void refresh()
    }, POLL_INTERVAL_MS)
  }

  const refresh = async () => {
    try {
      status.value = await ocrApi.repairStatus()
      error.value = null
    } catch (err) {
      logger.warn('OCR repair status failed: %s', err)
    } finally {
      schedule()
    }
  }

  const ensurePolling = async () => {
    await refresh()
  }

  const start = async () => {
    if (starting.value || running.value) return status.value
    starting.value = true
    error.value = null
    try {
      status.value = await ocrApi.repair()
      schedule()
      return status.value
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
      throw err
    } finally {
      starting.value = false
    }
  }

  return {
    status,
    starting,
    error,
    running,
    result,
    total,
    processed,
    percent,
    start,
    refresh,
    ensurePolling,
  }
})
