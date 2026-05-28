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
  <div class="min-h-screen">
    <RouterView />
    <NotificationToast />
  </div>
</template>

<style scoped>
</style>
