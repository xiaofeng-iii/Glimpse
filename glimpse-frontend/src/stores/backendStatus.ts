import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'
import { healthApi } from '@/api/client'

export const BACKEND_STARTUP_GRACE_PERIOD_MS = 30_000

export type BackendState = 'starting' | 'ready' | 'offline'

export const useBackendStatusStore = defineStore('backend-status', () => {
  const state = ref<BackendState>('starting')
  const isChecking = ref(false)
  const lastCheckedAt = ref<number | null>(null)
  const startupDeadlineAt = Date.now() + BACKEND_STARTUP_GRACE_PERIOD_MS
  let pendingCheck: Promise<boolean> | null = null
  let hasEverBeenReady = false

  const isReady = computed(() => state.value === 'ready')
  const isStarting = computed(() => state.value === 'starting')
  const isOffline = computed(() => state.value === 'offline')

  const applyCheckFailure = (error: unknown) => {
    const coldStartConnectionFailure = state.value === 'starting'
      && !hasEverBeenReady
      && Date.now() < startupDeadlineAt
      && axios.isAxiosError(error)
      && !error.response

    state.value = coldStartConnectionFailure ? 'starting' : 'offline'
  }

  const check = async () => {
    if (pendingCheck) {
      return pendingCheck
    }

    isChecking.value = true
    pendingCheck = (async () => {
      try {
        const result = await healthApi.check()
        const ready = result.status === 'healthy'
        if (ready) {
          hasEverBeenReady = true
          state.value = 'ready'
        } else {
          state.value = 'offline'
        }
        return ready
      } catch (error) {
        applyCheckFailure(error)
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
    isStarting,
    isOffline,
    isChecking,
    lastCheckedAt,
    check,
  }
})
