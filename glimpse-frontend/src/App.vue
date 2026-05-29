<script setup lang="ts">
import { RouterView } from 'vue-router'
import { onMounted } from 'vue'
import { useWebSocket } from '@/api/websocket'
import NotificationToast from '@/components/NotificationToast.vue'

const websocket = useWebSocket()

// Connect WebSocket on app mount
onMounted(() => {
  websocket.connect()
  websocket.startKeepalive()
})
</script>

<template>
  <div class="h-screen min-h-0 overflow-hidden">
    <RouterView />
    <NotificationToast />
  </div>
</template>

<style scoped>
</style>
