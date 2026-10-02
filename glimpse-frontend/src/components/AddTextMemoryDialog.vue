<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { ArrowPathIcon, DocumentTextIcon, PlusIcon, XMarkIcon } from '@heroicons/vue/24/outline'
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
  (event: 'submit', payload: { content: string; images: File[] }): void
}>()

const MAX_IMAGES = 10
const MAX_IMAGE_BYTES = 20 * 1024 * 1024
const MAX_IMAGE_MB = MAX_IMAGE_BYTES / (1024 * 1024)
const ACCEPTED_IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/gif', 'image/bmp']
const ACCEPTED_IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp']

const content = ref('')
const submitted = ref(false)
const dismissedExternalError = ref(false)
const editor = ref<HTMLTextAreaElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const images = ref<File[]>([])
const previewUrls = ref<string[]>([])
const imageNotice = ref('')
const dragging = ref(false)
let dragDepth = 0

const normalizedContent = computed(() => content.value.trim())
const validationMessage = computed(() => {
  if (!submitted.value) return ''
  if (images.value.length === 0 && !normalizedContent.value) return t('addMemory.required')
  if (normalizedContent.value.length > 4000) return t('addMemory.tooLong')
  return ''
})
const visibleError = computed(() => (
  imageNotice.value
  || validationMessage.value
  || (dismissedExternalError.value ? '' : props.errorMessage)
))
const placeholder = computed(() =>
  images.value.length ? t('addMemory.placeholderWithImages') : t('addMemory.placeholder'),
)

watch(
  () => props.open,
  (open) => {
    if (open) {
      content.value = ''
      submitted.value = false
      dismissedExternalError.value = false
      clearImages()
      imageNotice.value = ''
    }
  },
)

watch(
  () => props.errorMessage,
  () => {
    dismissedExternalError.value = false
  },
)

const clearImages = () => {
  for (const url of previewUrls.value) URL.revokeObjectURL(url)
  images.value = []
  previewUrls.value = []
}

onUnmounted(clearImages)

const isAcceptedImage = (file: File) => {
  if (file.type) return ACCEPTED_IMAGE_TYPES.includes(file.type)
  const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
  return ACCEPTED_IMAGE_EXTENSIONS.includes(extension)
}

const addFiles = (files: File[]) => {
  if (props.busy) return
  imageNotice.value = ''
  for (const file of files) {
    if (images.value.length >= MAX_IMAGES) {
      imageNotice.value = t('addMemory.imageCountLimit', { n: MAX_IMAGES })
      break
    }
    if (!isAcceptedImage(file)) {
      imageNotice.value = t('addMemory.imageUnsupported', { name: file.name })
      continue
    }
    if (file.size > MAX_IMAGE_BYTES) {
      imageNotice.value = t('addMemory.imageTooLarge', { name: file.name, n: MAX_IMAGE_MB })
      continue
    }
    images.value.push(file)
    previewUrls.value.push(URL.createObjectURL(file))
  }
}

const removeImage = (index: number) => {
  if (props.busy) return
  URL.revokeObjectURL(previewUrls.value[index] ?? '')
  images.value.splice(index, 1)
  previewUrls.value.splice(index, 1)
  imageNotice.value = ''
}

const openFilePicker = () => {
  if (!props.busy) fileInput.value?.click()
}

const handleFileInputChange = (event: Event) => {
  const input = event.target as HTMLInputElement
  if (input.files?.length) addFiles(Array.from(input.files))
  input.value = ''
}

const handlePaste = (event: ClipboardEvent) => {
  const files = Array.from(event.clipboardData?.files ?? [])
  if (!files.length) return
  event.preventDefault()
  addFiles(files)
}

const handleDragEnter = (event: DragEvent) => {
  if (!event.dataTransfer?.types.includes('Files')) return
  event.preventDefault()
  dragDepth += 1
  dragging.value = true
}

const handleDragLeave = () => {
  dragDepth = Math.max(0, dragDepth - 1)
  if (!dragDepth) dragging.value = false
}

const handleDrop = (event: DragEvent) => {
  dragDepth = 0
  dragging.value = false
  const files = Array.from(event.dataTransfer?.files ?? [])
  if (!files.length) return
  event.preventDefault()
  addFiles(files)
}

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
  emit('submit', { content: normalizedContent.value, images: [...images.value] })
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
        @paste="handlePaste"
        @dragenter="handleDragEnter"
        @dragover.prevent
        @dragleave="handleDragLeave"
        @drop="handleDrop"
      >
        <header class="flex flex-none items-center gap-3 px-5 pb-1 pt-3">
          <div class="flex h-8 w-8 flex-none items-center justify-center rounded-lg bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
            <DocumentTextIcon class="h-4 w-4" aria-hidden="true" />
          </div>
          <div class="min-w-0 flex-1">
            <DialogTitle class="text-base font-semibold text-[var(--shell-ink)]">
              {{ t('addMemory.title') }}
            </DialogTitle>
            <DialogDescription class="sr-only">
              {{ t('addMemory.description') }}
            </DialogDescription>
          </div>
          <button
            type="button"
            class="inline-flex h-8 w-8 flex-none items-center justify-center rounded-md text-[var(--shell-muted)] transition hover:bg-[var(--shell-control-hover)] disabled:cursor-not-allowed disabled:opacity-50"
            :aria-label="t('action.close')"
            :disabled="busy"
            @click="requestCancel"
          >
            <XMarkIcon class="h-4 w-4" aria-hidden="true" />
          </button>
        </header>

        <form class="flex min-h-0 flex-1 flex-col" novalidate @submit.prevent="submit">
          <div class="min-h-0 flex-1 overflow-y-auto px-5 py-4">
            <label for="text-memory-content" class="text-sm font-semibold text-[var(--shell-ink)]">
              {{ t('addMemory.contentLabel') }}
            </label>
            <input
              ref="fileInput"
              type="file"
              class="sr-only"
              multiple
              accept="image/png,image/jpeg,image/webp,image/gif,image/bmp"
              aria-hidden="true"
              tabindex="-1"
              @change="handleFileInputChange"
            />
            <textarea
              id="text-memory-content"
              ref="editor"
              v-model="content"
              class="mt-2 block min-h-48 w-full resize-none rounded-lg border bg-[var(--color-surface-subtle)] px-3.5 py-3 text-sm text-[var(--shell-ink)] outline-none transition placeholder:text-[var(--shell-muted)]"
              :class="visibleError ? 'border-red-400 focus:border-red-500' : 'border-[var(--shell-line)] focus:border-[color-mix(in_srgb,var(--color-primary)_55%,var(--shell-line))]'"
              :placeholder="placeholder"
              :readonly="busy"
              :aria-invalid="Boolean(visibleError)"
              aria-describedby="text-memory-help text-memory-feedback"
              maxlength="4000"
              @input="handleContentInput"
              @keydown="handleEditorKeydown"
            />

            <div class="mt-3 grid grid-cols-5 gap-2">
              <div
                v-for="(url, index) in previewUrls"
                :key="url"
                class="group relative aspect-square overflow-hidden rounded-lg border border-[var(--shell-line)] bg-[var(--color-surface-subtle)]"
              >
                <img
                  :src="url"
                  :alt="images[index]?.name ?? ''"
                  class="h-full w-full object-cover"
                />
                <button
                  type="button"
                  class="absolute right-1 top-1 inline-flex h-6 w-6 items-center justify-center rounded-full bg-slate-950/65 text-white opacity-0 transition focus-visible:opacity-100 group-hover:opacity-100 disabled:cursor-not-allowed"
                  :disabled="busy"
                  :aria-label="t('addMemory.removeImage', { name: images[index]?.name ?? '' })"
                  @click="removeImage(index)"
                >
                  <XMarkIcon class="h-3.5 w-3.5" aria-hidden="true" />
                </button>
              </div>
              <button
                type="button"
                class="text-memory-dialog__attach flex aspect-square items-center justify-center rounded-lg border border-dashed text-[var(--shell-muted)] transition hover:text-[var(--color-primary)] disabled:cursor-not-allowed disabled:opacity-50"
                :class="dragging ? 'text-memory-dialog__attach--active' : ''"
                :aria-label="t('addMemory.attachImage')"
                :title="t('addMemory.attachImage')"
                :disabled="busy"
                @click="openFilePicker"
              >
                <PlusIcon v-if="!dragging" class="h-5 w-5" aria-hidden="true" />
                <span v-else class="px-1 text-center text-xs font-medium leading-4">{{ t('addMemory.dropHint') }}</span>
              </button>
            </div>

            <div class="mt-2 flex min-h-5 items-center justify-between gap-4 text-xs">
              <p
                v-if="visibleError"
                id="text-memory-feedback"
                class="text-red-600"
                role="alert"
              >
                {{ visibleError }}
              </p>
              <p v-else id="text-memory-help" class="text-[var(--shell-muted)]">
                {{ t('addMemory.shortcut') }}
              </p>
              <span class="flex-none tabular-nums text-[var(--shell-muted)]">
                {{ content.length }} / 4000
              </span>
            </div>
          </div>

          <footer class="flex flex-none justify-end gap-2.5 px-5 pb-3 pt-1.5">
            <button
              type="button"
              class="btn-secondary px-4 disabled:cursor-not-allowed disabled:opacity-60"
              :disabled="busy"
              @click="requestCancel"
            >
              {{ t('action.cancel') }}
            </button>
            <button
              type="submit"
              class="btn-primary px-4"
              :disabled="busy"
              :aria-busy="busy"
            >
              <ArrowPathIcon v-if="busy" class="h-4 w-4 animate-spin" aria-hidden="true" />
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
  background: var(--color-surface-raised);
  box-shadow: var(--shadow-modal);
  transform: translate(-50%, -50%);
}

.text-memory-dialog__overlay[data-state='open'] {
  animation: text-memory-overlay-in 160ms ease-out;
}

.text-memory-dialog__content[data-state='open'] {
  animation: text-memory-dialog-in 180ms ease-out;
}

/* 图片添加占位格：与预览图同处一个网格、同尺寸，空态即独占一格表示图片落位，
   拖拽悬停时原位切换为放置提示 */
.text-memory-dialog__attach {
  border-color: color-mix(in srgb, var(--color-primary) 24%, var(--color-border));
}

.text-memory-dialog__attach:hover {
  border-color: color-mix(in srgb, var(--color-primary) 48%, var(--color-border));
  background: color-mix(in srgb, var(--color-primary) 6%, transparent);
}

.text-memory-dialog__attach--active {
  border-style: solid;
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
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
