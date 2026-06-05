import { ref, onUnmounted } from 'vue'
import { useMemoriesStore } from '@/stores/memories'
import { useClusterStore } from '@/stores/cluster'
import { useNotificationStore } from '@/stores/notification'
import { focusDesktopWindow } from '@/platform/desktop'
import { appendBackendAuthToken, getWsBaseUrl } from '@/config/runtime'
import { t } from '@/utils/i18n'

type WebSocketEvent = {
  type: string
  data: Record<string, any>
  timestamp: string
}

let ws: WebSocket | null = null
const isConnected = ref(false)
let reconnectAttempts = 0
const maxReconnectAttempts = 5

export function useWebSocket() {
  const connect = () => {
    if (ws?.readyState === WebSocket.OPEN) return

    const wsBaseUrl = getWsBaseUrl().replace(/\/$/, '')
    const wsUrl = appendBackendAuthToken(`${wsBaseUrl}/events`)

    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      console.log('WebSocket connected')
      isConnected.value = true
      reconnectAttempts = 0
    }

    ws.onmessage = (event) => {
      try {
        const message: WebSocketEvent = JSON.parse(event.data)
        handleMessage(message)
      } catch (e) {
        // Handle non-JSON messages (like pong)
        if (event.data === 'pong') {
          // Keepalive response
        }
      }
    }

    ws.onclose = () => {
      console.log('WebSocket disconnected')
      isConnected.value = false
      attemptReconnect()
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
  }

  const disconnect = () => {
    if (ws) {
      ws.close()
      ws = null
    }
  }

  const attemptReconnect = () => {
    if (reconnectAttempts < maxReconnectAttempts) {
      reconnectAttempts++
      console.log(`Reconnecting in ${reconnectAttempts * 2} seconds...`)
      setTimeout(connect, reconnectAttempts * 2000)
    }
  }

  const handleMessage = (event: WebSocketEvent) => {
    const memoriesStore = useMemoriesStore()
    const clusterStore = useClusterStore()
    const notificationStore = useNotificationStore()

    switch (event.type) {
      case 'memory_saved':
        void memoriesStore.refresh().then(() => {
          const memoryId = event.data.memory_id
          if (!memoryId) {
            return
          }

          const savedMemory = memoriesStore.memories.find((memory) => memory.id === memoryId)
          if (savedMemory) {
            memoriesStore.select(savedMemory)
          }
        })
        notificationStore.show(t('message.saved'), 'success')
        if (event.data.source === 'global_hotkey') {
          void focusDesktopWindow()
        }
        break

      case 'memory_deleted':
        memoriesStore.refresh()
        break

      case 'screenshot_completed':
        notificationStore.show(t('message.screenshotDone'), 'info')
        break

      case 'status_updated':
        notificationStore.show(
          event.data.message || event.data.status,
          event.data.level || 'info',
        )
        break

      case 'error_occurred':
        notificationStore.show(event.data.message, 'error')
        break

      case 'cluster_state_changed':
        clusterStore.setState(event.data as { state: string; count: number; max_count: number; images?: string[] })
        break

      case 'cluster_countdown':
        clusterStore.setCountdown(event.data.remaining_seconds)
        break

      case 'cluster_flushed':
        clusterStore.flush(event.data.images)
        notificationStore.show(t('message.clusterSubmitted'), 'success')
        break

      case 'cluster_discarded':
        clusterStore.discard()
        notificationStore.show(t('message.clusterCancelled'), 'info')
        break

      case 'desktop_action':
        if (event.data.action === 'focus_search') {
          void focusDesktopWindow().then(() => {
            window.dispatchEvent(new CustomEvent('glimpse:focus-search'))
          })
        } else if (event.data.action === 'trigger_screenshot') {
          window.dispatchEvent(new CustomEvent('glimpse:shortcut-screenshot', {
            detail: event.data,
          }))
        }
        break

      default:
        console.log('Unknown event:', event.type, event.data)
    }
  }

  const send = (type: string, data: Record<string, any> = {}) => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type, data }))
    }
  }

  const ping = () => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send('ping')
    }
  }

  // Keepalive ping every 30 seconds
  let keepaliveInterval: ReturnType<typeof setInterval> | null = null
  const startKeepalive = () => {
    if (!keepaliveInterval) {
      keepaliveInterval = setInterval(ping, 30000)
    }
  }

  const stopKeepalive = () => {
    if (keepaliveInterval) {
      clearInterval(keepaliveInterval)
      keepaliveInterval = null
    }
  }

  // Auto-cleanup
  onUnmounted(() => {
    stopKeepalive()
    disconnect()
  })

  return {
    isConnected,
    connect,
    disconnect,
    send,
    ping,
    startKeepalive,
    stopKeepalive,
  }
}
