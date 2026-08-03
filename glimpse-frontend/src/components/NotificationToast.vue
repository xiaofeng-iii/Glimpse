<script setup lang="ts">
import { computed } from 'vue'
import {
  CheckIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline'
import { useNotificationStore } from '@/stores/notification'

const notificationStore = useNotificationStore()

const notifications = computed(() => notificationStore.notifications)

const getTypeClass = (type: string) => {
  switch (type) {
    case 'success':
      return 'bg-green-500'
    case 'error':
      return 'bg-red-500'
    case 'warning':
      return 'bg-yellow-500'
    default:
      return 'bg-violet-500'
  }
}

const getIcon = (type: string) => {
  switch (type) {
    case 'success':
      return CheckIcon
    case 'error':
      return XMarkIcon
    case 'warning':
      return ExclamationTriangleIcon
    default:
      return InformationCircleIcon
  }
}
</script>

<template>
  <div class="fixed bottom-6 right-6 z-50 space-y-2">
    <TransitionGroup name="notification">
      <div
        v-for="notification in notifications"
        :key="notification.id"
        class="glass flex min-w-[280px] items-center gap-3 rounded-xl px-4 py-3 shadow-lg animate-slide-up"
      >
        <!-- Icon -->
        <div :class="['flex h-6 w-6 flex-none items-center justify-center rounded-full', getTypeClass(notification.type)]">
          <component :is="getIcon(notification.type)" class="h-4 w-4 text-white" aria-hidden="true" />
        </div>

        <!-- Message -->
        <p class="flex-1 text-gray-900 text-sm">{{ notification.message }}</p>

        <!-- Close Button -->
        <button
          @click="notificationStore.dismiss(notification.id)"
          class="inline-flex flex-none items-center justify-center rounded p-1 transition-colors hover:bg-gray-100"
        >
          <XMarkIcon class="h-4 w-4 text-gray-400" aria-hidden="true" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.notification-enter-active,
.notification-leave-active {
  transition: all 0.3s ease;
}

.notification-enter-from {
  opacity: 0;
  transform: translateX(100%);
}

.notification-leave-to {
  opacity: 0;
  transform: translateX(100%);
}
</style>
