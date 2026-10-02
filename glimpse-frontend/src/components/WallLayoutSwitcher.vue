<script setup lang="ts">
import { CalendarDaysIcon, CalendarIcon, Squares2X2Icon } from '@heroicons/vue/24/outline'
import { t, type MessageKey } from '@/utils/i18n'
import type { WallLayoutMode } from '@/utils/memory-grouping'
import { setWallLayoutMode, wallLayoutMode } from '@/utils/wall-layout'

const props = defineProps<{
  /** 搜索结果不参与分组，切换期间整体禁用 */
  disabled?: boolean
  /** 墙头收起态：与「最近」「筛选」触发器一致的浮起效果 */
  compact?: boolean
}>()

const options: Array<{ value: WallLayoutMode; labelKey: MessageKey; icon: typeof CalendarIcon }> = [
  { value: 'day', labelKey: 'wall.layoutDay', icon: CalendarDaysIcon },
  { value: 'month', labelKey: 'wall.layoutMonth', icon: CalendarIcon },
  { value: 'all', labelKey: 'wall.layoutAll', icon: Squares2X2Icon },
]

const choose = (mode: WallLayoutMode) => {
  if (props.disabled || mode === wallLayoutMode.value) return
  setWallLayoutMode(mode)
}
</script>

<template>
  <div
    class="wall-layout-switcher"
    :class="{ 'wall-layout-switcher--compact': compact }"
    role="group"
    :aria-label="t('wall.layout')"
  >
    <button
      v-for="option in options"
      :key="option.value"
      type="button"
      class="wall-layout-switcher__option"
      :class="{ 'wall-layout-switcher__option--active': wallLayoutMode === option.value }"
      :aria-label="t(option.labelKey)"
      :aria-pressed="wallLayoutMode === option.value"
      :title="t(option.labelKey)"
      :disabled="disabled"
      @click="choose(option.value)"
    >
      <component :is="option.icon" class="wall-layout-switcher__icon" aria-hidden="true" />
    </button>
  </div>
</template>

<style scoped>
.wall-layout-switcher {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 2px;
  border: 1px solid color-mix(in srgb, var(--shell-line) 70%, transparent);
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--shell-window-bg) 70%, transparent);
  transition: box-shadow 160ms ease, border-color 160ms ease, background-color 160ms ease;
}

.wall-layout-switcher--compact {
  border-color: color-mix(in srgb, var(--shell-line) 70%, transparent);
  background: color-mix(in srgb, var(--shell-window-bg) 70%, transparent);
  box-shadow: var(--shadow-card);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

.wall-layout-switcher__option {
  display: inline-flex;
  width: 1.75rem;
  height: 1.625rem;
  min-height: 0;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 0;
  border-radius: calc(var(--radius-md) - 2px);
  color: var(--shell-muted);
  background: transparent;
  cursor: pointer;
  transition: color 160ms ease, background-color 160ms ease;
}

.wall-layout-switcher__option:hover:not(:disabled):not(.wall-layout-switcher__option--active) {
  color: var(--shell-ink);
  background: var(--shell-control-hover);
}

.wall-layout-switcher__option--active {
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.wall-layout-switcher__option:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 1px;
}

.wall-layout-switcher__option:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.wall-layout-switcher__icon {
  width: 1rem;
  height: 1rem;
  flex: 0 0 1rem;
}
</style>
