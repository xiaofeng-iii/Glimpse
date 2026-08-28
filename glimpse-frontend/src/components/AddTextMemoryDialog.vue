<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { ArrowPathIcon, DocumentTextIcon, XMarkIcon } from '@heroicons/vue/24/outline'
import {
  DialogContent,
  DialogDescription,
  DialogOverlay,
  DialogPortal,
  DialogRoot,
  DialogTitle,
} from 'reka-ui'
import { t } from '@/utils/i18n'

const props = withDefaults(defineProps<{
  open: boolean
  busy?: boolean
  errorMessage?: string
}>(), {
  busy: false,
  errorMessage: '',
})

const emit = defineEmits<{
  (event: 'cancel'): void
  (event: 'submit', content: string): void
}>()

const content = ref('')
const submitted = ref(false)
const dismissedExternalError = ref(false)
const editor = ref<HTMLTextAreaElement | null>(null)
const normalizedContent = computed(() => content.value.trim())
const validationMessage = computed(() => {
  if (!submitted.value) return ''
  if (!normalizedContent.value) return t('addMemory.required')
  if (normalizedContent.value.length > 4000) return t('addMemory.tooLong')
  return ''
})
const visibleError = computed(() => (
  validationMessage.value
  || (dismissedExternalError.value ? '' : props.errorMessage)
))

watch(
  () => props.open,
  (open) => {
    if (open) {
      content.value = ''
      submitted.value = false
      dismissedExternalError.value = false
    }
  },
)

watch(
  () => props.errorMessage,
  () => {
    dismissedExternalError.value = false
  },
)

const requestCancel = () => {
  if (!props.busy) emit('cancel')
}

const handleOpenChange = (open: boolean) => {
  if (!open) requestCancel()
}

const focusEditor = async (event: Event) => {
  event.preventDefault()
  await nextTick()
  editor.value?.focus({ preventScroll: true })
}

const submit = () => {
  if (props.busy) return
  submitted.value = true
  if (validationMessage.value) {
    editor.value?.focus({ preventScroll: true })
    return
  }
  emit('submit', normalizedContent.value)
}

const handleEditorKeydown = (event: KeyboardEvent) => {
  if (event.isComposing || event.key !== 'Enter' || !event.ctrlKey) return
  event.preventDefault()
  submit()
}

const handleContentInput = () => {
  submitted.value = false
  dismissedExternalError.value = true
}

const preventDismissWhileBusy = (event: Event) => {
  if (props.busy) event.preventDefault()
}

const preventOutsideDismiss = (event: Event) => {
  event.preventDefault()
}
</script>

<template>
  <DialogRoot :open="open" modal @update:open="handleOpenChange">
    <DialogPortal>
      <DialogOverlay class="text-memory-dialog__overlay" />
      <DialogContent
        class="text-memory-dialog__content"
        :aria-busy="busy"
        @open-auto-focus="focusEditor"
        @escape-key-down="preventDismissWhileBusy"
        @pointer-down-outside="preventOutsideDismiss"
      >
        <header class="flex flex-none items-start gap-3.5 border-b border-[var(--shell-line)] px-5 py-4">
          <div class="flex h-10 w-10 flex-none items-center justify-center rounded-lg bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
            <DocumentTextIcon class="h-5 w-5" aria-hidden="true" />
          </div>
          <div class="min-w-0 flex-1">
            <DialogTitle class="text-base font-semibold text-[var(--shell-ink)]">
              {{ t('addMemory.title') }}
            </DialogTitle>
            <DialogDescription class="mt-1 text-sm text-[var(--shell-muted)]">
              {{ t('addMemory.description') }}
            </DialogDescription>
          </div>
          <button
            type="button"
            class="inline-flex h-9 w-9 flex-none items-center justify-center rounded-md text-[var(--shell-muted)] transition hover:bg-[var(--shell-control-hover)] disabled:cursor-not-allowed disabled:opacity-50"
            :aria-label="t('action.close')"
            :disabled="busy"
            @click="requestCancel"
          >
            <XMarkIcon class="h-5 w-5" aria-hidden="true" />
          </button>
        </header>

        <form class="flex min-h-0 flex-1 flex-col" novalidate @submit.prevent="submit">
          <div class="min-h-0 flex-1 overflow-y-auto px-5 py-4">
            <label for="text-memory-content" class="text-sm font-semibold text-[var(--shell-ink)]">
              {{ t('addMemory.contentLabel') }}
            </label>
            <textarea
              id="text-memory-content"
              ref="editor"
              v-model="content"
              class="mt-2 block min-h-48 w-full resize-none rounded-lg border bg-[var(--shell-control-bg)] px-3.5 py-3 text-sm text-[var(--shell-ink)] outline-none transition placeholder:text-[var(--shell-muted)]"
              :class="visibleError ? 'border-red-400 focus:border-red-500' : 'border-[var(--shell-line)] focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]'"
              :placeholder="t('addMemory.placeholder')"
              :readonly="busy"
              :aria-invalid="Boolean(visibleError)"
              aria-describedby="text-memory-help text-memory-feedback"
              maxlength="4000"
              @input="handleContentInput"
              @keydown="handleEditorKeydown"
            />
            <div class="mt-2 flex min-h-5 items-start justify-between gap-4 text-xs">
              <p id="text-memory-feedback" class="text-red-600" :role="visibleError ? 'alert' : undefined">
                {{ visibleError }}
              </p>
              <span class="flex-none tabular-nums text-[var(--shell-muted)]">
                {{ content.length }} / 4000
              </span>
            </div>
            <p id="text-memory-help" class="mt-1 text-xs text-[var(--shell-muted)]">
              {{ t('addMemory.shortcut') }}
            </p>
          </div>

          <footer class="flex flex-none justify-end gap-2.5 border-t border-[var(--shell-line)] bg-[var(--color-surface-subtle)] px-5 py-3.5">
            <button
              type="button"
              class="btn-secondary min-h-10 min-w-24 px-4 disabled:cursor-not-allowed disabled:opacity-60"
              :disabled="busy"
              @click="requestCancel"
            >
              {{ t('action.cancel') }}
            </button>
            <button
              type="submit"
              class="btn-primary min-h-10 min-w-32 px-4"
              :disabled="busy"
              :aria-busy="busy"
            >
              <ArrowPathIcon v-if="busy" class="h-5 w-5 animate-spin" aria-hidden="true" />
              <span>{{ t('action.addMemory') }}</span>
            </button>
          </footer>
        </form>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>

<style scoped>
.text-memory-dialog__overlay {
  position: fixed;
  inset: 0;
  z-index: var(--z-backdrop);
  background: var(--color-overlay);
  backdrop-filter: blur(3px);
  -webkit-backdrop-filter: blur(3px);
}

.text-memory-dialog__content {
  position: fixed;
  z-index: var(--z-dialog);
  top: 50%;
  left: 50%;
  display: flex;
  width: min(34rem, calc(100vw - 2rem));
  max-height: min(42rem, calc(100dvh - 2rem));
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--shell-line);
  border-radius: var(--radius-xl);
  color: var(--shell-ink);
  background: var(--shell-card);
  box-shadow: var(--shadow-modal);
  transform: translate(-50%, -50%);
}

.text-memory-dialog__overlay[data-state='open'] {
  animation: text-memory-overlay-in 160ms ease-out;
}

.text-memory-dialog__content[data-state='open'] {
  animation: text-memory-dialog-in 180ms ease-out;
}

@keyframes text-memory-overlay-in {
  from { opacity: 0; }
}

@keyframes text-memory-dialog-in {
  from {
    opacity: 0;
    transform: translate(-50%, calc(-50% + 8px)) scale(0.985);
  }
}

@media (max-width: 520px) {
  .text-memory-dialog__content {
    width: calc(100vw - 1rem);
    max-height: calc(100dvh - 1rem);
  }
}

@media (prefers-reduced-motion: reduce) {
  .text-memory-dialog__overlay[data-state='open'],
  .text-memory-dialog__content[data-state='open'] {
    animation-duration: 1ms;
  }
}
</style>
