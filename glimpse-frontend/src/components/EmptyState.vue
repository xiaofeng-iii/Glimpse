<script setup lang="ts">
import { computed } from 'vue'
import { PhotoIcon } from '@heroicons/vue/24/outline'
import { t } from '@/utils/i18n'

const props = defineProps<{
  shortcutLabel: string
}>()

const shortcutParts = computed(() => {
  if (!props.shortcutLabel) return []
  return props.shortcutLabel.split('+').map(s => s.trim()).flatMap((part, i, arr) => {
    if (i < arr.length - 1) return [part, '+']
    return [part]
  })
})
</script>

<template>
  <div class="flex flex-col items-center justify-center py-16 text-center">
    <div class="mb-6 flex h-20 w-20 items-center justify-center rounded-2xl bg-violet-100">
      <PhotoIcon class="h-10 w-10 text-violet-500" aria-hidden="true" />
    </div>

    <h3 class="text-lg font-medium text-gray-900 mb-2">{{ t('memory.emptyTitle') }}</h3>
    <p class="text-gray-500 text-sm mb-4">{{ t('memory.emptyHint') }}</p>

    <div class="empty-shortcut flex items-center gap-1">
      <template v-for="(part, i) in shortcutParts" :key="i">
        <kbd v-if="part !== '+'" class="empty-shortcut-key px-3 py-1.5 rounded-lg text-sm">{{ part }}</kbd>
        <span v-else class="empty-shortcut-plus">+</span>
      </template>
    </div>
  </div>
</template>

<style scoped>
.empty-shortcut {
  color: rgba(23, 32, 51, 0.84);
  font-weight: 700;
}

.empty-shortcut-plus {
  color: var(--shell-accent);
  opacity: 0.92;
}

.empty-shortcut-key {
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(35, 93, 103, 0.18);
  color: var(--shell-highlight-strong);
  font-weight: 700;
  box-shadow: 0 8px 18px rgba(35, 93, 103, 0.08);
}
</style>
