<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { ExclamationTriangleIcon, XMarkIcon } from '@heroicons/vue/24/outline'

defineOptions({ inheritAttrs: false })

const FOCUSABLE_SELECTOR = [
  'button:not([disabled])',
  '[href]',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

const props = withDefaults(defineProps<{
  open: boolean
  title: string
  description: string
  confirmLabel: string
  cancelLabel: string
  destructive?: boolean
  busy?: boolean
}>(), {
  destructive: false,
  busy: false,
})

const emit = defineEmits<{
  (event: 'confirm'): void
  (event: 'cancel'): void
}>()

const dialogPanel = ref<HTMLElement | null>(null)
const cancelButton = ref<HTMLButtonElement | null>(null)
let originElement: HTMLElement | null = null

const cancel = () => {
  if (!props.busy) emit('cancel')
}

const focusableElements = () => (
  dialogPanel.value
    ? Array.from(dialogPanel.value.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
    : []
)

const trapFocus = (event: KeyboardEvent) => {
  const focusable = focusableElements()
  if (!focusable.length) {
    event.preventDefault()
    dialogPanel.value?.focus()
    return
  }

  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  const active = document.activeElement
  if (event.shiftKey && (active === first || !dialogPanel.value?.contains(active))) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && active === last) {
    event.preventDefault()
    first.focus()
  }
}

const handleKeydown = (event: KeyboardEvent) => {
  if (!props.open) return
  if (event.key === 'Escape') {
    event.preventDefault()
    event.stopPropagation()
    cancel()
  } else if (event.key === 'Tab') {
    trapFocus(event)
  }
}

watch(
  () => props.open,
  async (open) => {
    if (open) {
      originElement = document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null
      document.addEventListener('keydown', handleKeydown, true)
      await nextTick()
      cancelButton.value?.focus({ preventScroll: true })
      return
    }

    document.removeEventListener('keydown', handleKeydown, true)
    await nextTick()
    if (originElement?.isConnected) {
      originElement.focus({ preventScroll: true })
    }
    originElement = null
  },
)

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleKeydown, true)
  if (originElement?.isConnected) originElement.focus({ preventScroll: true })
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-[120] flex items-center justify-center bg-slate-950/35 p-5 backdrop-blur-sm"
      role="presentation"
      @click.self="cancel"
    >
      <section
        ref="dialogPanel"
        class="w-full max-w-md rounded-[24px] border border-[var(--shell-line)] bg-[var(--shell-frame-bg)] p-6 shadow-2xl"
        role="alertdialog"
        aria-modal="true"
        :aria-busy="busy"
        :aria-labelledby="`${$attrs.id ?? 'confirm'}-title`"
        :aria-describedby="`${$attrs.id ?? 'confirm'}-description`"
        tabindex="-1"
      >
        <div class="flex items-start gap-4">
          <div
            class="flex h-11 w-11 flex-none items-center justify-center rounded-2xl"
            :class="destructive ? 'bg-red-50 text-red-600' : 'bg-amber-50 text-amber-600'"
          >
            <ExclamationTriangleIcon class="h-6 w-6" aria-hidden="true" />
          </div>
          <div class="min-w-0 flex-1">
            <h2 :id="`${$attrs.id ?? 'confirm'}-title`" class="text-lg font-semibold text-[var(--shell-ink)]">
              {{ title }}
            </h2>
            <p
              :id="`${$attrs.id ?? 'confirm'}-description`"
              class="mt-2 text-sm leading-6 text-[var(--shell-muted)]"
            >
              {{ description }}
            </p>
          </div>
          <button
            type="button"
            class="rounded-xl p-2 text-[var(--shell-muted)] transition hover:bg-[var(--shell-control-hover)]"
            :aria-label="cancelLabel"
            :disabled="busy"
            @click="cancel"
          >
            <XMarkIcon class="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        <div class="mt-6 flex justify-end gap-3">
          <button ref="cancelButton" type="button" class="btn-secondary min-h-10 px-5" :disabled="busy" @click="cancel">
            {{ cancelLabel }}
          </button>
          <button
            type="button"
            class="min-h-10 rounded-xl px-5 text-sm font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-60"
            :class="destructive ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'"
            :disabled="busy"
            @click="emit('confirm')"
          >
            {{ confirmLabel }}
          </button>
        </div>
      </section>
    </div>
  </Teleport>
</template>
