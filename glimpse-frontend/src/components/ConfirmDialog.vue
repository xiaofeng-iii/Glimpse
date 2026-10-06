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
  hideIcon?: boolean
}>(), {
  destructive: false,
  busy: false,
  hideIcon: false,
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
        class="w-full max-w-md rounded-xl border border-[var(--shell-line)] bg-[var(--color-surface-raised)] p-5 shadow-2xl"
        role="alertdialog"
        aria-modal="true"
        :aria-busy="busy"
        :aria-labelledby="`${$attrs.id ?? 'confirm'}-title`"
        :aria-describedby="`${$attrs.id ?? 'confirm'}-description`"
        tabindex="-1"
      >
        <div class="flex items-start gap-3.5">
          <div
            v-if="!hideIcon"
            class="flex h-9 w-9 flex-none items-center justify-center rounded-lg"
            :class="destructive ? 'bg-red-50 text-red-600' : 'bg-amber-50 text-amber-600'"
          >
            <ExclamationTriangleIcon class="h-5 w-5" aria-hidden="true" />
          </div>
          <div class="min-w-0 flex-1">
            <h2 :id="`${$attrs.id ?? 'confirm'}-title`" class="text-base font-semibold text-[var(--shell-ink)]">
              {{ title }}
            </h2>
            <p
              :id="`${$attrs.id ?? 'confirm'}-description`"
              class="mt-1.5 text-sm text-[var(--shell-muted)]"
            >
              {{ description }}
            </p>
          </div>
          <button
            type="button"
            class="inline-flex h-[var(--control-h-md)] w-[var(--control-h-md)] min-h-[var(--control-h-md)] flex-none items-center justify-center rounded-[var(--radius-md)] text-[var(--shell-muted)] transition hover:bg-[var(--shell-control-hover)]"
            :aria-label="cancelLabel"
            :disabled="busy"
            @click="cancel"
          >
            <XMarkIcon class="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        </div>

        <div v-if="$slots.default" class="confirm-dialog__body mt-4 max-h-[50dvh] overflow-y-auto overflow-x-hidden"><slot /></div>
        <div class="mt-4 flex justify-end gap-2.5">
          <button ref="cancelButton" type="button" class="btn-secondary" :disabled="busy" @click="cancel">
            {{ cancelLabel }}
          </button>
          <button
            type="button"
            class="text-white transition disabled:cursor-not-allowed disabled:opacity-60"
            :class="[destructive ? 'btn-danger' : 'btn-primary']"
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

<style scoped>
/* 弹窗内的小滚动区不挂全局常驻轨道：隐藏滚动条、保留滚轮纵向滚动。 */
.confirm-dialog__body {
  scrollbar-width: none;
}

.confirm-dialog__body::-webkit-scrollbar {
  display: none;
}
</style>
