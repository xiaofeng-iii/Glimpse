<script setup lang="ts">
import { RouterView } from 'vue-router'
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useWebSocket } from '@/api/websocket'
import { useSettingsStore } from '@/stores/settings'
import { useHotkeyRegistrationStore } from '@/stores/hotkeyRegistration'
import { useNotificationStore } from '@/stores/notification'
import { whenBackendRuntimeReady } from '@/config/runtime'
import { applyScreenshotShortcut } from '@/platform/global-shortcut'
import { applyThemePreference, watchSystemTheme } from '@/utils/theme'
import { setLanguagePreference, t } from '@/utils/i18n'
import {
  completeOnboarding,
  ONBOARDING_REQUEST_EVENT,
  shouldShowOnboarding,
} from '@/utils/onboarding'
import { sweepTourSamples } from '@/utils/tour-samples'
import DesktopShell from '@/components/DesktopShell.vue'
import EditTextContextMenu from '@/components/EditTextContextMenu.vue'
import GuidedTour from '@/components/GuidedTour.vue'
import ImagePreviewModal from '@/components/ImagePreviewModal.vue'
import SwipeToastHost from '@/components/toast/SwipeToastHost.vue'

const websocket = useWebSocket()
const settingsStore = useSettingsStore()
const hotkeyRegistration = useHotkeyRegistrationStore()
const notifications = useNotificationStore()
const guidedTourOpen = ref(shouldShowOnboarding())
let stopWatchingSystemTheme: (() => void) | null = null
const editTextMenu = ref<{
  x: number
  y: number
  target: HTMLInputElement | HTMLTextAreaElement | null
}>({ x: 0, y: 0, target: null })

const finishOnboarding = () => {
  completeOnboarding()
  guidedTourOpen.value = false
}

const showOnboarding = () => {
  guidedTourOpen.value = true
}

const applySavedTheme = async () => {
  await settingsStore.load()
  applyThemePreference(settingsStore.settings?.ui?.theme)
  setLanguagePreference(settingsStore.settings?.ui?.language)
}

// 全局热键注册跟随设置：加载出热键或热键变更（设置页保存）时重挂；
// 注册失败（被其他应用占用等）toast 一次并写入状态，设置页据此显示行内异常。
const syncGlobalScreenshotShortcut = async () => {
  const hotkey = settingsStore.settings?.hotkeys?.screenshot ?? ''
  const result = await applyScreenshotShortcut(hotkey)
  if (result.ok) {
    hotkeyRegistration.reportSuccess(hotkey)
  } else {
    hotkeyRegistration.reportFailure(hotkey, result.error)
    notifications.show(t('message.hotkeyRegisterFailed'), 'error', 4200)
  }
}

watch(
  () => settingsStore.settings?.hotkeys?.screenshot,
  () => void syncGlobalScreenshotShortcut(),
)

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
  void sweepTourSamples()
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
    <GuidedTour :open="guidedTourOpen" @complete="finishOnboarding" />
    <EditTextContextMenu
      :x="editTextMenu.x"
      :y="editTextMenu.y"
      :target="editTextMenu.target"
      @close="closeEditTextMenu"
    />
    <ImagePreviewModal />
    <SwipeToastHost />
  </div>
</template>
