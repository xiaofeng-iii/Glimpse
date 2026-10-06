<script setup lang="ts">
import { computed, nextTick } from 'vue'
import { CheckIcon, ChevronDownIcon } from '@heroicons/vue/20/solid'
import {
  SelectContent,
  SelectIcon,
  SelectItem,
  SelectItemIndicator,
  SelectItemText,
  SelectPortal,
  SelectRoot,
  SelectTrigger,
  SelectValue,
  SelectViewport,
} from 'reka-ui'

export interface AppSelectOption {
  value: string
  label: string
  disabled?: boolean
}

const props = withDefaults(defineProps<{
  options: readonly AppSelectOption[]
  id?: string
  name?: string
  ariaLabel?: string
  ariaLabelledby?: string
  disabled?: boolean
}>(), {
  id: undefined,
  name: undefined,
  ariaLabel: undefined,
  ariaLabelledby: undefined,
  disabled: false,
})

const model = defineModel<string>({ required: true })
const selectedOption = computed(() => props.options.find((option) => option.value === model.value))

// reka-ui 打开菜单时通过 focusFirst([selectedItem, content]) 把焦点放到选中项上，
// 而 data-highlighted 由焦点驱动，所以鼠标打开时选中项总呈现悬浮高亮。
// 这里在鼠标打开后把焦点改放到 content 容器（focusFirst 原本的 fallback），
// 选中项 blur 后高亮消失，此后只有鼠标悬浮或键盘导航才会产生高亮。
// 键盘打开时不干预，焦点导航是预期行为。
let openedByKeyboard = false

const handleTriggerKeydown = () => {
  openedByKeyboard = true
}

const handleOpenChange = async (open: boolean) => {
  if (!open) return
  const byKeyboard = openedByKeyboard
  openedByKeyboard = false
  if (byKeyboard) return
  await nextTick()
  // isPositioned 的 watch 在内容定位完成后才聚焦选中项，等一拍再重聚焦
  await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
  const content = document.querySelector<HTMLElement>('.app-select__content')
  const highlighted = content?.querySelector<HTMLElement>('[data-highlighted]')
  if (content && highlighted) {
    highlighted.blur()
    content.focus({ preventScroll: true })
  }
}
</script>

<template>
  <SelectRoot v-model="model" :disabled="disabled" :name="name" @update:open="handleOpenChange">
    <SelectTrigger
      :id="id"
      class="app-select__trigger"
      :aria-label="ariaLabel"
      :aria-labelledby="ariaLabelledby"
      @keydown="handleTriggerKeydown"
    >
      <SelectValue :aria-label="selectedOption?.label">
        <span class="app-select__value">{{ selectedOption?.label }}</span>
      </SelectValue>
      <SelectIcon class="app-select__icon" aria-hidden="true">
        <ChevronDownIcon />
      </SelectIcon>
    </SelectTrigger>

    <SelectPortal>
      <SelectContent
        class="app-select__content"
        position="popper"
        side="bottom"
        align="start"
        :side-offset="4"
        :collision-padding="12"
        :body-lock="false"
      >
        <SelectViewport class="app-select__viewport">
          <SelectItem
            v-for="option in options"
            :key="option.value"
            class="app-select__item"
            :value="option.value"
            :disabled="option.disabled"
            :text-value="option.label"
          >
            <SelectItemText>{{ option.label }}</SelectItemText>
            <SelectItemIndicator class="app-select__indicator">
              <CheckIcon aria-hidden="true" />
            </SelectItemIndicator>
          </SelectItem>
        </SelectViewport>
      </SelectContent>
    </SelectPortal>
  </SelectRoot>
</template>

<style>
.app-select__trigger {
  display: inline-flex;
  width: 100%;
  max-width: 240px;
  min-height: var(--control-h-md);
  align-items: center;
  justify-content: space-between;
  gap: .5rem;
  padding: .35rem .65rem;
  border: none;
  border-radius: var(--radius-md);
  font-size: .8125rem;
  font-weight: 400;
  color: var(--color-text);
  background: var(--color-surface-hover);
  cursor: pointer;
  text-align: left;
  transition:
    color 140ms ease,
    background-color 140ms ease;
}

.app-select__trigger:hover {
  background: color-mix(in srgb, var(--color-surface-hover) 75%, var(--color-border-strong));
  color: var(--color-text);
}

.app-select__trigger:focus-visible,
.app-select__trigger[data-state='open'] {
  background: var(--color-primary-soft);
  color: var(--color-primary-hover);
  outline: none;
}

.app-select__trigger:disabled {
  color: var(--color-text-muted);
  background: var(--color-surface-subtle);
  cursor: not-allowed;
  opacity: .55;
}

.app-select__value {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-select__icon {
  width: .875rem;
  height: .875rem;
  flex: 0 0 .875rem;
  color: var(--color-text-muted);
  transition: transform 160ms ease, color 140ms ease;
}

.app-select__icon > svg {
  display: block;
  width: 100%;
  height: 100%;
}

.app-select__trigger[data-state='open'] .app-select__icon {
  color: var(--color-primary-hover);
  transform: rotate(180deg);
}

.app-select__content {
  z-index: 80;
  min-width: var(--reka-select-trigger-width);
  max-height: min(15rem, var(--reka-select-content-available-height));
  overflow: hidden;
  padding: 3px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text);
  background: var(--color-surface-raised, var(--shell-card));
  box-shadow:
    0 10px 24px rgba(26, 38, 64, .12),
    0 2px 6px rgba(26, 38, 64, .06);
  transform-origin: var(--reka-select-content-transform-origin);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  animation: app-select-in 140ms ease-out;
}

.app-select__viewport {
  max-height: min(14.5rem, var(--reka-select-content-available-height));
}

.app-select__item {
  position: relative;
  display: flex;
  min-height: 1.875rem;
  align-items: center;
  padding: .25rem 1.85rem .25rem .65rem;
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: .8125rem;
  line-height: var(--line-height-14);
  outline: none;
  user-select: none;
  transition: color 120ms ease, background-color 120ms ease;
}

.app-select__item[data-highlighted] {
  color: var(--color-primary-hover);
  background: var(--color-primary-soft);
}

.app-select__content .app-select__item:focus-visible {
  outline: none;
  box-shadow: none;
}

.app-select__item[data-state='checked'] {
  color: var(--color-text);
  font-weight: 600;
}

.app-select__item[data-state='checked'][data-highlighted] {
  color: var(--color-primary-hover);
}

.app-select__item[data-disabled] {
  color: var(--color-text-muted);
  cursor: not-allowed;
  opacity: .5;
}

.app-select__indicator {
  position: absolute;
  right: .55rem;
  display: inline-flex;
  width: .875rem;
  height: .875rem;
  align-items: center;
  justify-content: center;
  color: var(--color-primary);
}

.app-select__indicator > svg {
  width: .875rem;
  height: .875rem;
}

:root[data-theme='dark'] .app-select__content {
  box-shadow:
    0 12px 28px rgba(0, 0, 0, .45),
    0 2px 8px rgba(0, 0, 0, .3);
}

@keyframes app-select-in {
  from {
    opacity: 0;
    transform: translateY(-3px) scale(.985);
  }

  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@media (forced-colors: active) {
  .app-select__trigger,
  .app-select__content,
  .app-select__item {
    forced-color-adjust: auto;
  }
}
</style>
