<script setup lang="ts">
import { ref, watch } from 'vue'
import { t } from '@/utils/i18n'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'choose', payload: { action: 'minimize' | 'exit'; remember: boolean }): void
}>()

const rememberChoice = ref(false)

watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) {
      rememberChoice.value = false
    }
  },
)

const chooseAction = (action: 'minimize' | 'exit') => {
  emit('choose', {
    action,
    remember: rememberChoice.value,
  })
}
</script>

<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/30 px-4"
    @click.self="emit('close')"
  >
    <div class="glass w-full max-w-md rounded-[24px] p-6 shadow-2xl">
      <div class="space-y-3">
        <h2 class="text-lg font-semibold text-slate-900">{{ t('close.title') }}</h2>
        <p class="text-sm text-slate-700">
          {{ t('close.question') }}
        </p>
        <p class="text-xs leading-6 text-slate-500">
          {{ t('close.description') }}
        </p>
      </div>

      <label class="close-action-remember mt-5 flex items-center gap-3 rounded-2xl bg-white/70 px-4 py-3 text-sm text-slate-700">
        <input
          v-model="rememberChoice"
          type="checkbox"
          class="close-action-checkbox h-4 w-4 rounded border-slate-300 text-[var(--shell-highlight)] focus:ring-[var(--shell-highlight)]"
        />
        <span>{{ t('close.remember') }}</span>
      </label>

      <div class="mt-6 flex flex-wrap justify-end gap-3">
        <button class="btn-secondary" @click="emit('close')">{{ t('action.cancel') }}</button>
        <button class="btn-secondary" @click="chooseAction('minimize')">{{ t('close.minimize') }}</button>
        <button class="btn-primary" @click="chooseAction('exit')">{{ t('close.exit') }}</button>
      </div>
    </div>
  </div>
</template>
