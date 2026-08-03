<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { t } from '@/utils/i18n'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (event: 'close'): void
  (
    event: 'choose',
    payload: { action: 'minimize' | 'exit'; remember: boolean },
  ): void
}>()

const dialogPanel = ref<HTMLElement | null>(null)
const cancelButton = ref<HTMLButtonElement | null>(null)
const rememberChoice = ref(false)
let originElement: HTMLElement | null = null

watch(
  () => props.open,
  async (isOpen) => {
    if (isOpen) {
      originElement = document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null
      await nextTick()
      cancelButton.value?.focus({ preventScroll: true })
      return
    }

    rememberChoice.value = false
    await nextTick()
    if (originElement?.isConnected) {
      originElement.focus({ preventScroll: true })
    }
    originElement = null
  },
)

const chooseAction = (action: 'minimize' | 'exit') => {
  emit('choose', {
    action,
    remember: rememberChoice.value,
  })
}

const handleTab = (event: KeyboardEvent) => {
  if (!dialogPanel.value) {
    return
  }

  const buttons = Array.from(
    dialogPanel.value.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  )
  if (buttons.length === 0) {
    return
  }

  const first = buttons[0]
  const last = buttons[buttons.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="dialog-backdrop"
      @mousedown.self="emit('close')"
      @keydown.esc.stop.prevent="emit('close')"
      @keydown.tab="handleTab"
    >
      <section
        ref="dialogPanel"
        class="confirmation-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="close-dialog-title"
        aria-describedby="close-dialog-description"
      >
        <div class="confirmation-dialog__copy">
          <h2 id="close-dialog-title">{{ t('close.title') }}</h2>
          <p>{{ t('close.question') }}</p>
          <p id="close-dialog-description">{{ t('close.description') }}</p>
        </div>

        <label class="confirmation-dialog__remember">
          <input
            v-model="rememberChoice"
            type="checkbox"
            class="close-action-checkbox"
          />
          <span>{{ t('close.remember') }}</span>
        </label>

        <div class="confirmation-dialog__actions">
          <button
            ref="cancelButton"
            type="button"
            class="btn-secondary"
            @click="emit('close')"
          >
            {{ t('action.cancel') }}
          </button>
          <button
            type="button"
            class="btn-secondary"
            @click="chooseAction('minimize')"
          >
            {{ t('close.minimize') }}
          </button>
          <button
            type="button"
            class="btn-primary"
            @click="chooseAction('exit')"
          >
            {{ t('close.exit') }}
          </button>
        </div>
      </section>
    </div>
  </Teleport>
</template>
