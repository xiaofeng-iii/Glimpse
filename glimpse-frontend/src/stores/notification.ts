import { defineStore } from 'pinia'
import { ref } from 'vue'

type NotificationType = 'success' | 'error' | 'info' | 'warning'

interface Notification {
  id: number
  message: string
  type: NotificationType
  timeout: ReturnType<typeof setTimeout> | null
}

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
    const notification: Notification = {
      id,
      message,
      type,
      timeout: null,
    }

    notifications.value.push(notification)

    if (duration > 0) {
      notification.timeout = setTimeout(() => {
        dismiss(id)
      }, duration)
    }

    return id
  }

  const dismiss = (id: number) => {
    const index = notifications.value.findIndex(n => n.id === id)
    if (index > -1) {
      const notification = notifications.value[index]
      if (notification.timeout) {
        clearTimeout(notification.timeout)
      }
      notifications.value.splice(index, 1)
    }
  }

  const clear = () => {
    notifications.value.forEach(n => {
      if (n.timeout) clearTimeout(n.timeout)
    })
    notifications.value = []
  }

  return {
    notifications,
    show,
    dismiss,
    clear,
  }
})
