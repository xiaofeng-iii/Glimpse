<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import { useNotificationStore } from '@/stores/notification'
import SwipeToastItem from './SwipeToastItem.vue'

const notificationStore = useNotificationStore()

// Esc 关最新一条：仅当没有模态对话框时生效——弹窗的 Esc 语义优先，
// 且侧栏/搜索的 Esc 由 Home 处理（其自身已有弹窗探测守卫，正常场景下
// 有 toast 时按 Esc 先关 toast 属更高频的轻量操作）。
const handleKeydown = (event: KeyboardEvent) => {
  if (event.key !== 'Escape') return
  if (!notificationStore.notifications.length) return
  if (document.querySelector('[role="dialog"][aria-modal="true"]')) return
  event.preventDefault()
  event.stopPropagation()
  const latest = notificationStore.notifications[notificationStore.notifications.length - 1]
  notificationStore.dismiss(latest.id)
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown, true)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeydown, true)
})
</script>

<template>
  <!-- items-end：右缘对齐，各卡片按自身内容定宽（默认 stretch 会把短通知
       拉宽到与最宽一条同宽）；容器右下锚定，最宽一条离场时右缘不动。 -->
  <div class="swipe-toast-host fixed bottom-6 right-6 z-[var(--z-toast)] flex flex-col items-end gap-2">
    <SwipeToastItem
      v-for="notification in notificationStore.notifications"
      :key="notification.id"
      :notification="notification"
    />
  </div>
</template>
