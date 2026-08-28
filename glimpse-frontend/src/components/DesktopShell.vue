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
import glimpseLogo from '@/assets/glimpse.svg'
import { settingsApi } from '@/api/client'
import { whenBackendRuntimeReady } from '@/config/runtime'
import {
  closeDesktopWindow,
  focusDesktopWindow,
  getDesktopWindowMaximized,
  hideDesktopWindow,
  isDesktopShell,
  listenForDesktopCloseRequests,
  minimizeDesktopWindow,
  toggleDesktopMaximize,
} from '@/platform/desktop'
import { useBackendStatusStore } from '@/stores/backendStatus'
import { useNotificationStore } from '@/stores/notification'
import { useSettingsStore } from '@/stores/settings'
import { useUnsavedChangesStore } from '@/stores/unsavedChanges'
import { t } from '@/utils/i18n'
import { createLogger } from '@/utils/logger'

type CloseAction = 'ask' | 'minimize' | 'exit'

const HEALTH_POLL_INTERVAL_MS = 10_000

const route = useRoute()
const router = useRouter()
const backendStatus = useBackendStatusStore()
const notificationStore = useNotificationStore()
const settingsStore = useSettingsStore()
const unsavedChanges = useUnsavedChangesStore()
const logger = createLogger('components/DesktopShell')

const isDesktop = isDesktopShell()
const isHome = computed(() => route.name === 'home')
const serviceLabel = computed(() => {
  if (backendStatus.isReady) return t('status.ready')
  if (backendStatus.isStarting) return t('status.starting')
  return t('status.offline')
})

const isWindowMaximized = ref(false)
const closeAction = ref<CloseAction>('ask')
const closeDialogOpen = ref(false)
let removeDesktopCloseListener: (() => void) | null = null
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
    window.addEventListener('resize', syncDesktopWindowState)
  }

  if (!settingsStore.settings) {
    void settingsStore.load()
  }

  await whenBackendRuntimeReady()
  await backendStatus.check()
  healthPollTimer = window.setInterval(() => {
    void backendStatus.check()
  }, HEALTH_POLL_INTERVAL_MS)
})

onUnmounted(() => {
  removeNavigationGuard?.()
  removeNavigationGuard = null
  removeDesktopCloseListener?.()
  removeDesktopCloseListener = null
  window.removeEventListener('resize', syncDesktopWindowState)

  if (healthPollTimer) {
    window.clearInterval(healthPollTimer)
    healthPollTimer = null
  }
})
</script>

<template>
  <div class="desktop-shell">
    <header class="desktop-shell__titlebar">
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
            type="button"
            class="shell-icon-button desktop-shell__settings-button"
            :title="t('action.settings')"
            :aria-label="t('action.settings')"
            @click="navigateSettings"
          >
            <Cog6ToothIcon class="h-[15px] w-[15px]" aria-hidden="true" />
          </button>
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
            'service-status--ready': backendStatus.isReady,
            'service-status--starting': backendStatus.isStarting,
            'service-status--offline': backendStatus.isOffline,
          }"
          role="status"
          aria-live="polite"
        >
          <CheckCircleIcon
            v-if="backendStatus.isReady"
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
          <span>{{ serviceLabel }}</span>
        </div>

        <div v-if="isDesktop" class="desktop-shell__window-controls">
          <button
            type="button"
            class="window-control"
            :title="t('action.minimize')"
            :aria-label="t('action.minimize')"
            @click="minimizeDesktopWindow"
          >
            <MinusIcon class="h-3.5 w-3.5" aria-hidden="true" />
          </button>
          <button
            type="button"
            class="window-control"
            :title="isWindowMaximized ? t('action.restore') : t('action.maximize')"
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
            :title="t('action.close')"
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
