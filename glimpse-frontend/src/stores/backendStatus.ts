import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { healthApi } from '@/api/client'

export type BackendState = 'checking' | 'ready' | 'offline'

export const useBackendStatusStore = defineStore('backend-status', () => {
  const state = ref<BackendState>('checking')
  const isChecking = ref(false)
  const lastCheckedAt = ref<number | null>(null)
  let pendingCheck: Promise<boolean> | null = null

  const isReady = computed(() => state.value === 'ready')

  const check = async () => {
    if (pendingCheck) {
      return pendingCheck
    }

    isChecking.value = true
    pendingCheck = (async () => {
      try {
        const result = await healthApi.check()
        const ready = result.status === 'healthy'
        state.value = ready ? 'ready' : 'offline'
        return ready
      } catch {
        state.value = 'offline'
        return false
      } finally {
        isChecking.value = false
        lastCheckedAt.value = Date.now()
        pendingCheck = null
      }
    })()

    return pendingCheck
  }

  return {
    state,
    isReady,
    isChecking,
    lastCheckedAt,
    check,
  }
})
