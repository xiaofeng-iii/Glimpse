<script setup lang="ts">
import { ref } from 'vue'
import { PopoverRoot, PopoverTrigger, PopoverPortal, PopoverContent } from 'reka-ui'
import { t } from '@/utils/i18n'
defineProps<{ label: string }>()
const open = defineModel<boolean>('open', { default: false })
const trigger = ref<HTMLElement | null>(null)
function restoreFocus(event: Event) {
  event.preventDefault()
  trigger.value?.querySelector('button')?.focus({ preventScroll: true })
}
</script>
<template>
  <PopoverRoot v-model:open="open" :modal="false">
    <span ref="trigger"><PopoverTrigger as-child><slot name="trigger" /></PopoverTrigger></span>
    <PopoverPortal>
      <PopoverContent :aria-label="label" align="start" :side-offset="6" :collision-padding="12" class="notes-popover rounded-xl border border-[var(--shell-line)] bg-[var(--color-surface-raised)] p-4 shadow-2xl" @close-auto-focus="restoreFocus">
        <div class="mb-3 flex items-center justify-between gap-3"><h2 class="text-sm font-semibold text-[var(--shell-ink)]">{{ label }}</h2><button type="button" class="text-sm text-[var(--shell-muted)]" :aria-label="t('settings.notesClose')" @click="open = false">×</button></div>
        <slot />
      </PopoverContent>
    </PopoverPortal>
  </PopoverRoot>
</template>
<style scoped>
.notes-popover { z-index: 90; width: min(28rem, calc(100vw - 24px)); max-height: min(32rem, var(--reka-popover-content-available-height), calc(100dvh - 24px)); overflow-y: auto; }
</style>
