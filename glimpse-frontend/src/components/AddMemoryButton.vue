<script setup lang="ts">
import { ArrowPathIcon, PlusIcon } from '@heroicons/vue/24/outline'
import { t } from '@/utils/i18n'

withDefaults(defineProps<{
  busy?: boolean
  disabled?: boolean
  density?: 'standard' | 'toolbar'
}>(), {
  busy: false,
  disabled: false,
  density: 'standard',
})

const emit = defineEmits<{
  (event: 'add'): void
}>()
</script>

<template>
  <button
    type="button"
    class="btn-primary add-memory-button min-w-[7.25rem] shrink-0 gap-2 whitespace-nowrap px-4 text-sm"
    :class="density === 'toolbar' ? 'h-9 min-h-0' : 'h-11'"
    :disabled="busy || disabled"
    :aria-busy="busy"
    :aria-label="busy ? t('action.addMemoryProcessing') : undefined"
    @click="emit('add')"
  >
    <ArrowPathIcon v-if="busy" class="h-5 w-5 flex-none animate-spin" aria-hidden="true" />
    <PlusIcon v-else class="h-5 w-5 flex-none" aria-hidden="true" />
    <span>{{ t('action.addMemory') }}</span>
  </button>
</template>

<style scoped>
.add-memory-button:disabled:not([aria-busy='true']) {
  cursor: not-allowed;
  opacity: 0.55;
}

.add-memory-button[aria-busy='true'] {
  cursor: wait;
}
</style>
