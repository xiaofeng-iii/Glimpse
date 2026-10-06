<script setup lang="ts">
import { ref } from 'vue'
import { PopoverRoot, PopoverTrigger, PopoverPortal, PopoverContent } from 'reka-ui'
import { XMarkIcon } from '@heroicons/vue/24/outline'
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
      <PopoverContent :aria-label="label" align="start" :side-offset="6" :collision-padding="12" class="notes-popover rounded-xl border border-[var(--shell-line)] bg-[var(--color-surface-raised)] shadow-2xl" @close-auto-focus="restoreFocus">
        <div class="notes-popover__header">
          <h2 class="text-sm font-semibold text-[var(--shell-ink)]">{{ label }}</h2>
          <button type="button" class="notes-popover__close" :aria-label="t('settings.notesClose')" @click="open = false">
            <XMarkIcon class="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        </div>
        <div class="notes-popover__body px-4 pb-4"><slot /></div>
        <div v-if="$slots.footer" class="notes-popover__footer"><slot name="footer" /></div>
      </PopoverContent>
    </PopoverPortal>
  </PopoverRoot>
</template>
<style>
/* 浮窗内容经 PopoverPortal 挂载到 body 下，scoped 样式的 data-v 属性打不到，必须用全局样式 */
.notes-popover {
  z-index: 90;
  width: min(28rem, calc(100vw - 24px));
  display: flex;
  flex-direction: column;
  /* reka popper 在 size 中间件里设置 --reka-popper-available-height（触发点到视口边缘的可用高度），
     Popover 转发为 --reka-popover-content-available-height；与 100dvh 兜底一起约束，
     浮窗高度永不超出视口，超出部分内部滚动。 */
  max-height: min(32rem, var(--reka-popover-content-available-height, 100dvh), calc(100dvh - 24px));
  overflow: hidden;
  transform-origin: var(--reka-popover-content-transform-origin);
  animation: notes-popover-in 160ms ease-out;
}

@keyframes notes-popover-in {
  from {
    opacity: 0;
    transform: translateY(-3px) scale(.985);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@media (prefers-reduced-motion: reduce) {
  .notes-popover {
    animation: none;
  }
}

/* 标题栏常驻不随内容滚动，关闭按钮固定右上角 */
.notes-popover__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: .5rem;
  flex: none;
  padding: .5rem 1rem .25rem;
}

.notes-popover__body {
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: none;
}

.notes-popover__body::-webkit-scrollbar {
  display: none;
}

/* 操作按钮常驻浮窗底部，不随超长正文滚动；仅当调用方提供 footer 插槽时出现。 */
.notes-popover__footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: .5rem;
  flex: none;
  padding: .5rem 1rem;
}

.notes-popover__close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: var(--control-h-md);
  height: var(--control-h-md);
  min-height: var(--control-h-md);
  flex: none;
  border: none;
  border-radius: var(--radius-md);
  color: var(--color-text-muted);
  background: transparent;
  cursor: pointer;
  transition: color 140ms ease, background-color 140ms ease;
}

.notes-popover__close:hover {
  color: var(--color-text);
  background: var(--color-surface-hover);
}

.notes-popover__close:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 1px;
}

.notes-popover__close:active {
  background: var(--color-surface-active, var(--color-surface-hover));
  transform: scale(.92);
}
</style>
