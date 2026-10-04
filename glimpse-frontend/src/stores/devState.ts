import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { Memory } from '@/api/client'

export type AnalysisOverride = 'none' | 'processing' | 'failed'
export type SyncOverride = 'none' | 'pending' | 'failed'

const STORAGE_KEY = 'glimpse.devMemoryStateOverride'

// 开发模式戏剧道具：强制记忆的分析/同步状态，便于观察各状态呈现；生产构建不存在此 store。
const readStored = (): { analysis: AnalysisOverride; sync: SyncOverride } => {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return { analysis: 'none', sync: 'none' }
    const parsed = JSON.parse(raw) as { analysis?: unknown; sync?: unknown }
    return {
      analysis: ['processing', 'failed'].includes(parsed.analysis as string)
        ? (parsed.analysis as AnalysisOverride)
        : 'none',
      sync: ['pending', 'failed'].includes(parsed.sync as string)
        ? (parsed.sync as SyncOverride)
        : 'none',
    }
  } catch {
    return { analysis: 'none', sync: 'none' }
  }
}

export const useDevStateStore = defineStore('dev-state', () => {
  const stored = readStored()
  const analysisOverride = ref<AnalysisOverride>(stored.analysis)
  const syncOverride = ref<SyncOverride>(stored.sync)

  const persist = () => {
    try {
      if (analysisOverride.value === 'none' && syncOverride.value === 'none') {
        window.localStorage.removeItem(STORAGE_KEY)
      } else {
        window.localStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({ analysis: analysisOverride.value, sync: syncOverride.value }),
        )
      }
    } catch {
      // localStorage 不可用时仅本次会话生效。
    }
  }

  const setAnalysisOverride = (value: AnalysisOverride) => {
    analysisOverride.value = value
    persist()
  }

  const setSyncOverride = (value: SyncOverride) => {
    syncOverride.value = value
    persist()
  }

  const applyOverride = <T extends Pick<Memory, 'analysis_status' | 'sync_status'>>(memory: T): T => ({
    ...memory,
    analysis_status: analysisOverride.value === 'none'
      ? memory.analysis_status
      : (analysisOverride.value.toUpperCase() as Memory['analysis_status']),
    sync_status: syncOverride.value === 'none'
      ? memory.sync_status
      : syncOverride.value.toUpperCase(),
  })

  const hasOverride = computed(
    () => analysisOverride.value !== 'none' || syncOverride.value !== 'none',
  )

  return {
    analysisOverride,
    syncOverride,
    hasOverride,
    setAnalysisOverride,
    setSyncOverride,
    applyOverride,
  }
})
