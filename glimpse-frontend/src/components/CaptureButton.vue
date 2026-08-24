<script setup lang="ts">
import { ArrowPathIcon, CameraIcon } from '@heroicons/vue/24/outline'
import { t } from '@/utils/i18n'

withDefaults(defineProps<{
  capturing?: boolean
  disabled?: boolean
  shortcutLabel?: string
  showShortcut?: boolean
  density?: 'standard' | 'toolbar'
}>(), {
  capturing: false,
  disabled: false,
  shortcutLabel: 'Ctrl+Shift+G',
  showShortcut: false,
  density: 'standard',
})

const emit = defineEmits<{
  (event: 'capture'): void
}>()
</script>

<template>
  <button
    type="button"
    class="capture-button inline-flex min-w-[5.875rem] items-center gap-2 rounded-lg px-4 font-semibold text-white transition"
    :class="density === 'toolbar' ? 'h-9 min-h-0' : 'h-11'"
    :disabled="capturing || disabled"
    :aria-busy="capturing"
    :aria-label="capturing ? t('action.captureProcessing') : undefined"
    @click="emit('capture')"
  >
    <ArrowPathIcon v-if="capturing" class="h-5 w-5 flex-none animate-spin" aria-hidden="true" />
    <CameraIcon v-else class="h-5 w-5 flex-none" aria-hidden="true" />
    <span>{{ t('action.capture') }}</span>
    <kbd v-if="showShortcut" class="capture-shortcut rounded-md bg-white/18 px-1.5 py-0.5 text-xs">
      {{ shortcutLabel }}
    </kbd>
  </button>
</template>

<style scoped>
@media (max-width: 1120px) {
  .capture-shortcut {
    display: none;
  }
}
</style>
