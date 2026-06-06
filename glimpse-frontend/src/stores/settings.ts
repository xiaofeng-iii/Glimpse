import { defineStore } from 'pinia'
import { ref } from 'vue'
import { settingsApi, type Settings } from '@/api/client'
import { createLogger } from '@/utils/logger'

const logger = createLogger('stores/settings')

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref<Settings | null>(null)
  const isLoading = ref(false)

  const load = async () => {
    isLoading.value = true
    try {
      settings.value = await settingsApi.get()
    } catch (error) {
      logger.error('Failed to load settings: %s', error)
    } finally {
      isLoading.value = false
    }
  }

  const update = async (newSettings: Partial<Settings>) => {
    try {
      await settingsApi.update(newSettings)
      if (settings.value) {
        settings.value = { ...settings.value, ...newSettings } as Settings
      }
    } catch (error) {
      logger.error('Failed to update settings: %s', error)
      throw error
    }
  }

  const reset = async () => {
    try {
      await settingsApi.reset()
      await load()
    } catch (error) {
      logger.error('Failed to reset settings: %s', error)
      throw error
    }
  }

  const testAi = async (apiKey?: string, baseUrl?: string, model?: string) => {
    return settingsApi.testAi(apiKey, baseUrl, model)
  }

  return {
    settings,
    isLoading,
    load,
    update,
    reset,
    testAi,
  }
})