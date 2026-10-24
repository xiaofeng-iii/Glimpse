<script setup lang="ts">
import { HugeiconsIcon } from '@hugeicons/vue'
import { Camera01FreeIcons, ArrowReloadHorizontalFreeIcons } from '@hugeicons/core-free-icons'
import { t } from '@/utils/i18n'

withDefaults(defineProps<{
  capturing?: boolean
  disabled?: boolean
  shortcutLabel?: string
  density?: 'standard' | 'toolbar'
}>(), {
  capturing: false,
  disabled: false,
  shortcutLabel: 'Ctrl+Shift+G',
  density: 'standard',
})

const emit = defineEmits<{
  (event: 'capture'): void
}>()
</script>

<template>
  <button
    v-hint-tooltip="{ label: t('action.capture'), shortcut: shortcutLabel }"
    type="button"
    class="capture-button inline-flex min-w-[5.875rem] items-center gap-2 px-4 text-white transition duration-[160ms] ease-[ease]"
    :class="density === 'toolbar' ? 'h-8 capture-button--slim' : 'h-10'"
    :disabled="capturing || disabled"
    :aria-busy="capturing"
    :aria-label="capturing ? t('action.captureProcessing') : undefined"
    @click="emit('capture')"
  >
    <!-- 图标库对照实验（hugeicons 免费集 vs heroicons）：仅本组件替换，供目检对比 -->
    <HugeiconsIcon
      v-if="capturing"
      :icon="ArrowReloadHorizontalFreeIcons"
      class="h-5 w-5 flex-none animate-spin"
      aria-hidden="true"
    />
    <HugeiconsIcon v-else :icon="Camera01FreeIcons" class="h-5 w-5 flex-none" aria-hidden="true" />
    <span>{{ t('action.capture') }}</span>
  </button>
</template>

<style scoped>
/* 工具区密度：常规字重与更小字号、收窄内边距并解除最小宽度，高度维持 32px 紧凑档；
   主操作的辨识度由颜色与位置承担，不靠加粗。 */
.capture-button--slim {
  min-width: 0;
  padding-inline: 0.625rem;
  font-size: 0.875rem;
  font-weight: 400;
}
</style>
