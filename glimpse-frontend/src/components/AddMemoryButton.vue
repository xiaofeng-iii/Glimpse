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
    :class="density === 'toolbar' ? 'h-8 add-memory-button--slim' : 'h-10'"
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
/* 工具区密度：常规字重与更小字号、收窄内边距并解除最小宽度，高度维持 32px 紧凑档；
   主操作的辨识度由颜色与位置承担，不靠加粗。 */
.add-memory-button--slim {
  min-width: 0;
  padding-inline: 0.625rem;
  font-size: 0.8125rem;
  font-weight: 400;
}

.add-memory-button:disabled:not([aria-busy='true']) {
  cursor: not-allowed;
  opacity: 0.55;
}

.add-memory-button[aria-busy='true'] {
  cursor: wait;
}
</style>
