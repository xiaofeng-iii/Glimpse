import { defineStore } from 'pinia'
import { ref } from 'vue'
import { settingsApi, type Settings } from '@/api/client'

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref<Settings | null>(null)
  const isLoading = ref(false)

  const load = async () => {
    isLoading.value = true
    try {
      settings.value = await settingsApi.get()
    } catch (error) {
      console.error('Failed to load settings:', error)
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
      console.error('Failed to update settings:', error)
      throw error
    }
  }

  const reset = async () => {
    try {
      await settingsApi.reset()
      await load()
    } catch (error) {
      console.error('Failed to reset settings:', error)
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