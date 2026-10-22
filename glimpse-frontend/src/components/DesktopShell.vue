<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeftIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  Cog6ToothIcon,
  ExclamationCircleIcon,
  MinusIcon,
  Square2StackIcon,
  StopIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline'
import CloseActionDialog from '@/components/CloseActionDialog.vue'
import UpdateBadge from '@/components/UpdateBadge.vue'
import glimpseLogo from '@/assets/glimpse.svg'
import { settingsApi } from '@/api/client'
import { whenBackendRuntimeReady } from '@/config/runtime'
import {
  closeDesktopWindow,
  focusDesktopWindow,
  getDesktopWindowMaximized,
  hideDesktopWindow,
  isDesktopShell,
  listenForBackendCorruption,
  listenForDesktopCloseRequests,
  minimizeDesktopWindow,
  toggleDesktopMaximize,
} from '@/platform/desktop'
import { popupDesktopWindowMenu } from '@/platform/window-menu'
import { useBackendStatusStore } from '@/stores/backendStatus'
import { useNotificationStore } from '@/stores/notification'
import { useOcrRepairStore } from '@/stores/ocrRepair'
import { useSettingsStore } from '@/stores/settings'
import { useUnsavedChangesStore } from '@/stores/unsavedChanges'
import { useUpdatesStore } from '@/stores/updates'
import { t } from '@/utils/i18n'
import { createLogger } from '@/utils/logger'

type CloseAction = 'ask' | 'minimize' | 'exit'

const HEALTH_POLL_INTERVAL_MS = 10_000

const route = useRoute()
const router = useRouter()
const backendStatus = useBackendStatusStore()
const notificationStore = useNotificationStore()
const ocrRepair = useOcrRepairStore()
const settingsStore = useSettingsStore()
const unsavedChanges = useUnsavedChangesStore()
const updatesStore = useUpdatesStore()
const logger = createLogger('components/DesktopShell')

const isDesktop = isDesktopShell()
const isHome = computed(() => route.name === 'home')
const serviceLabel = computed(() => {
  if (backendStatus.isCorrupted) return t('status.corrupted')
  if (backendStatus.isOffline) return t('status.offline')
  if (backendStatus.isStarting) return t('status.starting')
  if (backendStatus.aiUnavailable) return t('status.aiDisabled')
  return t('status.ready')
})
const showOcrRepair = computed(() =>
  ocrRepair.running
  && route.name !== 'settings'
  && !backendStatus.isOffline
  && !backendStatus.isStarting
  && !backendStatus.isCorrupted,
)
const statusLabel = computed(() =>
  showOcrRepair.value
    ? t('status.ocrRepair', { percent: ocrRepair.percent })
    : serviceLabel.value,
)

const isWindowMaximized = ref(false)
const closeAction = ref<CloseAction>('ask')
const closeDialogOpen = ref(false)
let removeDesktopCloseListener: (() => void) | null = null
let removeBackendCorruptionListener: (() => void) | null = null
let removeNavigationGuard: (() => void) | null = null
let healthPollTimer: ReturnType<typeof window.setInterval> | null = null

watch(
  () => settingsStore.settings?.ui?.close_action,
  (value) => {
    if (value === 'ask' || value === 'minimize' || value === 'exit') {
      closeAction.value = value
    }
  },
  { immediate: true },
)

const syncDesktopWindowState = async () => {
  if (!isDesktop) {
    isWindowMaximized.value = false
    return
  }

  isWindowMaximized.value = await getDesktopWindowMaximized()
}

const handleToggleMaximize = async () => {
  await toggleDesktopMaximize()
  await syncDesktopWindowState()
}

const performCloseAction = async (action: Exclude<CloseAction, 'ask'>) => {
  if (action === 'minimize') {
    await hideDesktopWindow()
    return
  }

  await closeDesktopWindow()
}

const requestWindowClose = async () => {
  if (closeDialogOpen.value) {
    return
  }

  if (!(await unsavedChanges.canLeave())) {
    return
  }

  if (closeAction.value === 'ask') {
    closeDialogOpen.value = true
    return
  }

  try {
    await performCloseAction(closeAction.value)
  } catch (error) {
    logger.error('Close window failed: %s', error)
    notificationStore.show(t('message.exitFailed'), 'error', 3200)
  }
}

const handleTitlebarContextMenu = (event: MouseEvent) => {
  if (!isDesktop) return
  event.preventDefault()
  void popupDesktopWindowMenu({ onCloseRequested: () => void requestWindowClose() })
}

const handleCloseDialogChoice = async (payload: {
  action: 'minimize' | 'exit'
  remember: boolean
}) => {
  closeDialogOpen.value = false

  try {
    if (payload.remember) {
      try {
        await settingsApi.update({
          ui: {
            close_action: payload.action,
          },
        })
        closeAction.value = payload.action
        await settingsStore.load()
      } catch (error) {
        logger.error('Saving close action failed: %s', error)
        notificationStore.show(t('message.closePreferenceFailed'), 'warning', 3200)
      }
    }

    await performCloseAction(payload.action)
  } catch (error) {
    logger.error('Applying close action failed: %s', error)
    notificationStore.show(t('message.closeActionFailed'), 'error', 3200)
  }
}

const navigateHome = async () => {
  if (!isHome.value) {
    await router.push('/')
  }
}

const navigateSettings = async () => {
  if (route.name !== 'settings') {
    await router.push('/settings')
  }
}

// 启动时静默检测一次更新：读当前版本（识别"刚升级完"），再按通道查新版本。
// 失败完全静默，用户仍可在设置页手动检查。
const checkUpdatesAtStartup = async () => {
  if (!isDesktop) return
  try {
    const { getVersion } = await import('@tauri-apps/api/app')
    updatesStore.recordCurrentVersion(await getVersion())
  } catch (error) {
    logger.error('Failed to read app version: %s', error)
  }
  if (!settingsStore.settings) {
    await settingsStore.load()
  }
  await updatesStore.checkForUpdate()
}

onMounted(async () => {
  removeNavigationGuard = router.beforeEach(async (to, from) => {
    if (to.fullPath === from.fullPath) {
      return true
    }

    return await unsavedChanges.canLeave()
  })

  if (isDesktop) {
    await focusDesktopWindow()
    await syncDesktopWindowState()
    removeDesktopCloseListener = await listenForDesktopCloseRequests(() => {
      void requestWindowClose()
    })
    removeBackendCorruptionListener = await listenForBackendCorruption(() => {
      backendStatus.markCorrupted()
    })
    window.addEventListener('resize', syncDesktopWindowState)
  }

  if (!settingsStore.settings) {
    void settingsStore.load()
  }

  await whenBackendRuntimeReady()
  await backendStatus.check()
  void ocrRepair.ensurePolling()
  void checkUpdatesAtStartup()
  healthPollTimer = window.setInterval(() => {
    void backendStatus.check()
  }, HEALTH_POLL_INTERVAL_MS)
})

onUnmounted(() => {
  removeNavigationGuard?.()
  removeNavigationGuard = null
  removeDesktopCloseListener?.()
  removeDesktopCloseListener = null
  removeBackendCorruptionListener?.()
  removeBackendCorruptionListener = null
  window.removeEventListener('resize', syncDesktopWindowState)

  if (healthPollTimer) {
    window.clearInterval(healthPollTimer)
    healthPollTimer = null
  }
})
</script>

<template>
  <div class="desktop-shell">
    <header
      class="desktop-shell__titlebar"
      @contextmenu="handleTitlebarContextMenu"
    >
      <div
        class="desktop-shell__drag-layer"
        aria-hidden="true"
        data-tauri-drag-region
        @dblclick="handleToggleMaximize"
      ></div>

      <div class="desktop-shell__leading">
        <div class="desktop-shell__brand" data-tauri-drag-region>
          <slot name="brand">
            <img
              class="desktop-shell__logo"
              :src="glimpseLogo"
              alt=""
              draggable="false"
            />
            <span class="desktop-shell__brand-name">Glimpse</span>
          </slot>
        </div>

        <span class="desktop-shell__leading-divider" aria-hidden="true"></span>

        <slot name="navigation">
          <button
            v-if="isHome"
            v-hint-tooltip="t('action.settings')"
            type="button"
            class="shell-icon-button desktop-shell__settings-button"
            :aria-label="t('action.settings')"
            @click="navigateSettings"
          >
            <Cog6ToothIcon class="h-[15px] w-[15px]" aria-hidden="true" />
          </button>
          <UpdateBadge v-if="isHome" />
          <button
            v-else
            type="button"
            class="shell-navigation-button"
            @click="navigateHome"
          >
            <ArrowLeftIcon class="h-3.5 w-3.5" aria-hidden="true" />
            <span>{{ t('action.back') }}</span>
          </button>
        </slot>
      </div>

      <div class="desktop-shell__actions">
        <div
          class="service-status"
          :class="{
            'service-status--ready': !showOcrRepair && backendStatus.isReady && !backendStatus.aiUnavailable,
            'service-status--ai-off': backendStatus.aiUnavailable,
            'service-status--starting': showOcrRepair || backendStatus.isStarting,
            'service-status--offline': backendStatus.isOffline || backendStatus.isCorrupted,
          }"
          role="status"
          :aria-live="showOcrRepair ? 'off' : 'polite'"
        >
          <ArrowPathIcon
            v-if="showOcrRepair"
            class="service-status__icon animate-spin"
            aria-hidden="true"
          />
          <CheckCircleIcon
            v-else-if="backendStatus.isReady && !backendStatus.aiUnavailable"
            class="service-status__icon"
            aria-hidden="true"
          />
          <ArrowPathIcon
            v-else-if="backendStatus.isStarting"
            class="service-status__icon animate-spin"
            aria-hidden="true"
          />
          <ExclamationCircleIcon
            v-else
            class="service-status__icon"
            aria-hidden="true"
          />
          <span>{{ statusLabel }}</span>
        </div>

        <div v-if="isDesktop" class="desktop-shell__window-controls">
          <button
            type="button"
            class="window-control"
            :aria-label="t('action.minimize')"
            @click="minimizeDesktopWindow"
          >
            <MinusIcon class="h-3.5 w-3.5" aria-hidden="true" />
          </button>
          <button
            type="button"
            class="window-control"
            :aria-label="isWindowMaximized ? t('action.restore') : t('action.maximize')"
            @click="handleToggleMaximize"
          >
            <Square2StackIcon
              v-if="isWindowMaximized"
              class="h-[13px] w-[13px]"
              aria-hidden="true"
            />
            <StopIcon
              v-else
              class="h-[13px] w-[13px]"
              aria-hidden="true"
            />
          </button>
          <button
            type="button"
            class="window-control window-control--danger"
            :aria-label="t('action.close')"
            @click="requestWindowClose"
          >
            <XMarkIcon class="h-[15px] w-[15px]" aria-hidden="true" />
          </button>
        </div>
      </div>
    </header>

    <div class="desktop-shell__content">
      <slot></slot>
    </div>

    <CloseActionDialog
      :open="closeDialogOpen"
      @close="closeDialogOpen = false"
      @choose="handleCloseDialogChoice"
    />
  </div>
</template>
