<script setup lang="ts">
import { RouterView } from 'vue-router'
import { onMounted, onUnmounted, ref } from 'vue'
import { useWebSocket } from '@/api/websocket'
import { useSettingsStore } from '@/stores/settings'
import { whenBackendRuntimeReady } from '@/config/runtime'
import { applyThemePreference, watchSystemTheme } from '@/utils/theme'
import { setLanguagePreference } from '@/utils/i18n'
import {
  completeOnboarding,
  ONBOARDING_REQUEST_EVENT,
  shouldShowOnboarding,
} from '@/utils/onboarding'
import DesktopShell from '@/components/DesktopShell.vue'
import FirstRunGuide from '@/components/FirstRunGuide.vue'
import ImagePreviewModal from '@/components/ImagePreviewModal.vue'
import NotificationToast from '@/components/NotificationToast.vue'

const websocket = useWebSocket()
const settingsStore = useSettingsStore()
const firstRunGuideOpen = ref(shouldShowOnboarding())
let stopWatchingSystemTheme: (() => void) | null = null

const finishOnboarding = () => {
  completeOnboarding()
  firstRunGuideOpen.value = false
}

const showOnboarding = () => {
  firstRunGuideOpen.value = true
}

const applySavedTheme = async () => {
  await settingsStore.load()
  applyThemePreference(settingsStore.settings?.ui?.theme)
  setLanguagePreference(settingsStore.settings?.ui?.language)
}

// Connect WebSocket on app mount
onMounted(async () => {
  window.addEventListener(ONBOARDING_REQUEST_EVENT, showOnboarding)
  await whenBackendRuntimeReady()
  await applySavedTheme()
  stopWatchingSystemTheme = watchSystemTheme(() => {
    applyThemePreference(settingsStore.settings?.ui?.theme)
  })
  websocket.connect()
  websocket.startKeepalive()
})

onUnmounted(() => {
  window.removeEventListener(ONBOARDING_REQUEST_EVENT, showOnboarding)
  stopWatchingSystemTheme?.()
  stopWatchingSystemTheme = null
})
</script>

<template>
  <div class="app-root">
    <DesktopShell>
      <RouterView />
    </DesktopShell>
    <FirstRunGuide :open="firstRunGuideOpen" @complete="finishOnboarding" />
    <ImagePreviewModal />
    <NotificationToast />
  </div>
</template>
