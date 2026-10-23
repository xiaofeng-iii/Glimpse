import { defineStore } from 'pinia'
import { ref } from 'vue'

type NotificationType = 'success' | 'error' | 'info' | 'warning'

export interface Notification {
  id: number
  message: string
  type: NotificationType
  /** 展示时长（ms）。定时器由展示组件持有（支持悬停暂停），store 只管队列。 */
  duration: number
}

/** 同屏堆叠上限：超出立即淘汰最旧一条（swipe-toast 交互约定）。 */
export const MAX_VISIBLE_NOTIFICATIONS = 3

export const useNotificationStore = defineStore('notification', () => {
  const notifications = ref<Notification[]>([])
  let nextId = 0
  let lastMessage = ''
  let lastType: NotificationType = 'info'
  let lastShownAt = 0

  const show = (message: string, type: NotificationType = 'info', duration = 3000) => {
    const now = Date.now()
    if (message === lastMessage && type === lastType && now - lastShownAt < 1200) {
      return -1
    }

    lastMessage = message
    lastType = type
    lastShownAt = now

    const id = nextId++
    notifications.value.push({ id, message, type, duration })
    while (notifications.value.length > MAX_VISIBLE_NOTIFICATIONS) {
      notifications.value.shift()
    }

    return id
  }

  const dismiss = (id: number) => {
    const index = notifications.value.findIndex(n => n.id === id)
    if (index > -1) {
      notifications.value.splice(index, 1)
    }
  }

  return {
    notifications,
    show,
    dismiss,
  }
})
