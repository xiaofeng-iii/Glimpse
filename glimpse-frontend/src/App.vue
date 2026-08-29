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
import EditTextContextMenu from '@/components/EditTextContextMenu.vue'
import FirstRunGuide from '@/components/FirstRunGuide.vue'
import ImagePreviewModal from '@/components/ImagePreviewModal.vue'
import NotificationToast from '@/components/NotificationToast.vue'

const websocket = useWebSocket()
const settingsStore = useSettingsStore()
const firstRunGuideOpen = ref(shouldShowOnboarding())
let stopWatchingSystemTheme: (() => void) | null = null
const editTextMenu = ref<{
  x: number
  y: number
  target: HTMLInputElement | HTMLTextAreaElement | null
}>({ x: 0, y: 0, target: null })

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

// 应用内一律不显示 WebView 原生右键菜单（图二那种）。三处例外各有专属菜单：
// 记忆卡片 → MemoryContextMenu；标题栏 → 系统窗口菜单；输入框 → 自定义文本编辑菜单；
// 其余区域右键无任何反应。
const handleDocumentContextMenu = (event: MouseEvent) => {
  const target = event.target
  if (!(target instanceof Element)) {
    event.preventDefault()
    return
  }

  const editable = target.closest<HTMLInputElement | HTMLTextAreaElement>('input, textarea')
  if (editable && !editable.disabled) {
    event.preventDefault()
    editTextMenu.value = { x: event.clientX, y: event.clientY, target: editable }
    return
  }

  if (target.closest('[contenteditable="true"], [contenteditable=""]')) {
    return
  }

  event.preventDefault()
}

const closeEditTextMenu = () => {
  editTextMenu.value = { x: 0, y: 0, target: null }
}

// Connect WebSocket on app mount
onMounted(async () => {
  document.addEventListener('contextmenu', handleDocumentContextMenu, true)
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
  document.removeEventListener('contextmenu', handleDocumentContextMenu, true)
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
    <EditTextContextMenu
      :x="editTextMenu.x"
      :y="editTextMenu.y"
      :target="editTextMenu.target"
      @close="closeEditTextMenu"
    />
    <ImagePreviewModal />
    <NotificationToast />
  </div>
</template>
