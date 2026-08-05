<script setup lang="ts">
import type { Memory } from '@/api/client'
import MemoryInspector from './MemoryInspector.vue'

defineProps<{
  memory: Memory
}>()

const emit = defineEmits<{
  (event: 'close'): void
  (event: 'open', memoryId: string): void
}>()
</script>

<template>
  <MemoryInspector
    :memory="memory"
    @close="emit('close')"
    @open="emit('open', $event)"
  />
</template>
