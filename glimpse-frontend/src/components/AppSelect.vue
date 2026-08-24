<script setup lang="ts">
import { computed } from 'vue'
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
</script>

<template>
  <SelectRoot v-model="model" :disabled="disabled" :name="name">
    <SelectTrigger
      :id="id"
      class="app-select__trigger"
      :aria-label="ariaLabel"
      :aria-labelledby="ariaLabelledby"
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
        :side-offset="6"
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
  min-height: 2.5rem;
  align-items: center;
  justify-content: space-between;
  gap: .75rem;
  padding: .45rem .75rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text);
  background: var(--shell-control-bg);
  cursor: pointer;
  text-align: left;
  transition:
    color 160ms ease,
    background-color 160ms ease,
    border-color 160ms ease,
    box-shadow 160ms ease;
}

.app-select__trigger:hover {
  border-color: var(--color-border-strong);
  background: color-mix(in srgb, var(--shell-control-bg) 72%, var(--shell-control-hover));
}

.app-select__trigger:focus-visible,
.app-select__trigger[data-state='open'] {
  border-color: var(--color-primary);
  background: color-mix(in srgb, var(--shell-control-bg) 96%, var(--color-primary));
  box-shadow: inset 0 0 0 2px color-mix(in srgb, var(--color-primary) 18%, transparent);
}

.app-select__trigger:disabled {
  color: var(--color-text-muted);
  background: var(--color-surface-subtle);
  cursor: not-allowed;
  opacity: .65;
}

.app-select__value {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-select__icon {
  width: 1rem;
  height: 1rem;
  flex: 0 0 1rem;
  color: var(--color-text-muted);
  transition: transform 160ms ease, color 160ms ease;
}

.app-select__icon > svg {
  display: block;
  width: 100%;
  height: 100%;
}

.app-select__trigger[data-state='open'] .app-select__icon {
  color: var(--color-primary);
  transform: rotate(180deg);
}

.app-select__content {
  z-index: 80;
  width: var(--reka-select-trigger-width);
  max-height: min(15rem, var(--reka-select-content-available-height));
  overflow: hidden;
  padding: .25rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  color: var(--color-text);
  background: color-mix(in srgb, var(--color-surface-raised) 96%, transparent);
  box-shadow:
    0 16px 36px rgba(26, 38, 64, .14),
    0 3px 10px rgba(26, 38, 64, .08);
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
  min-height: 2.25rem;
  align-items: center;
  padding: .45rem 2.25rem .45rem .75rem;
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: .875rem;
  line-height: 1.25rem;
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
  right: .7rem;
  display: inline-flex;
  width: 1rem;
  height: 1rem;
  align-items: center;
  justify-content: center;
  color: var(--color-primary);
}

.app-select__indicator > svg {
  width: 1rem;
  height: 1rem;
}

:root[data-theme='dark'] .app-select__content {
  box-shadow:
    0 18px 44px rgba(0, 0, 0, .42),
    0 3px 12px rgba(0, 0, 0, .28);
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
