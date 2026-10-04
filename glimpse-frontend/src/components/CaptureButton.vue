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
    class="capture-button inline-flex min-w-[5.875rem] items-center gap-2 px-4 font-semibold text-white transition"
    :class="density === 'toolbar' ? 'h-8 capture-button--slim' : 'h-10'"
    :disabled="capturing || disabled"
    :aria-busy="capturing"
    :aria-label="capturing ? t('action.captureProcessing') : undefined"
    @click="emit('capture')"
  >
    <ArrowPathIcon v-if="capturing" class="h-5 w-5 flex-none animate-spin" aria-hidden="true" />
    <CameraIcon v-else class="h-5 w-5 flex-none" aria-hidden="true" />
    <span>{{ t('action.capture') }}</span>
    <kbd v-if="showShortcut" class="capture-shortcut rounded-md bg-white/18 text-xs">
      {{ shortcutLabel }}
    </kbd>
  </button>
</template>

<style scoped>
/* 工具区密度：常规字重与更小字号、收窄内边距并解除最小宽度，高度维持 32px 紧凑档；
   主操作的辨识度由颜色与位置承担，不靠加粗。 */
.capture-button--slim {
  min-width: 0;
  padding-inline: 0.625rem;
  font-size: 0.8125rem;
  font-weight: 400;
}

/* 全局 kbd 规则（.capture-button kbd）优先级高于工具类，芯片内衬需在此覆盖 */
.capture-shortcut {
  padding: 0 0.25rem;
  line-height: 14px;
}

@media (max-width: 1120px) {
  .capture-shortcut {
    display: none;
  }
}
</style>
