<script setup lang="ts">
import { RouterView } from 'vue-router'
import { onMounted, onUnmounted } from 'vue'
import { useWebSocket } from '@/api/websocket'
import { useSettingsStore } from '@/stores/settings'
import { applyThemePreference, watchSystemTheme } from '@/utils/theme'
import NotificationToast from '@/components/NotificationToast.vue'

const websocket = useWebSocket()
const settingsStore = useSettingsStore()
let stopWatchingSystemTheme: (() => void) | null = null

const applySavedTheme = async () => {
  await settingsStore.load()
  applyThemePreference(settingsStore.settings?.ui?.theme)
}

// Connect WebSocket on app mount
onMounted(async () => {
  await applySavedTheme()
  stopWatchingSystemTheme = watchSystemTheme(() => {
    applyThemePreference(settingsStore.settings?.ui?.theme)
  })
  websocket.connect()
  websocket.startKeepalive()
})

onUnmounted(() => {
  stopWatchingSystemTheme?.()
  stopWatchingSystemTheme = null
})
</script>

<template>
  <div class="h-screen min-h-0 overflow-hidden">
    <RouterView />
    <NotificationToast />
  </div>
</template>

<style scoped>
</style>
