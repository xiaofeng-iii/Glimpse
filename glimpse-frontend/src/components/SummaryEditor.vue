<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  ArrowPathIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  PencilSquareIcon,
} from '@heroicons/vue/24/outline'
import type { Memory } from '@/api/client'
import { useMemoriesStore } from '@/stores/memories'
import { useNotificationStore } from '@/stores/notification'
import { useUnsavedChangesStore } from '@/stores/unsavedChanges'
import { t } from '@/utils/i18n'
import ConfirmDialog from './ConfirmDialog.vue'

const props = withDefaults(defineProps<{
  memory: Memory
  compact?: boolean
}>(), {
  compact: false,
})

const emit = defineEmits<{
  (event: 'saved', memory: Memory): void
}>()

const memoriesStore = useMemoriesStore()
const notifications = useNotificationStore()
const unsavedChanges = useUnsavedChangesStore()
const editing = ref(false)
const draft = ref(props.memory.ai_summary)
const saving = ref(false)
const errorMessage = ref('')
const discardDialogOpen = ref(false)
const compactEditor = ref<HTMLTextAreaElement | null>(null)
let discardResolver: ((confirmed: boolean) => void) | null = null
let pendingDiscardPromise: Promise<boolean> | null = null
let unregisterGuard: (() => boolean) | null = null

const normalizedDraft = computed(() => draft.value.trim())
const dirty = computed(() => normalizedDraft.value !== props.memory.ai_summary.trim())
const validationMessage = computed(() => {
  if (!normalizedDraft.value) return t('summary.required')
  if (normalizedDraft.value.length > 4000) return t('summary.tooLong')
  return ''
})
const canSave = computed(() => dirty.value && !validationMessage.value && !saving.value)

watch(
  () => props.memory.id,
  () => {
    editing.value = false
    draft.value = props.memory.ai_summary
    errorMessage.value = ''
  },
)

watch(
  () => props.memory.ai_summary,
  (value) => {
    if (!editing.value || !dirty.value) {
      draft.value = value
    }
  },
)

const startEditing = async () => {
  draft.value = props.memory.ai_summary
  errorMessage.value = ''
  editing.value = true
  await nextTick()
  const editor = compactEditor.value
  if (!editor) return

  const scrollTop = editor.scrollTop
  const scrollLeft = editor.scrollLeft
  editor.focus({ preventScroll: true })
  const selectionEnd = editor.value.length
  editor.setSelectionRange(selectionEnd, selectionEnd)

  const restoreScrollPosition = () => {
    if (compactEditor.value !== editor) return
    editor.scrollTop = scrollTop
    editor.scrollLeft = scrollLeft
  }
  restoreScrollPosition()
  window.requestAnimationFrame(restoreScrollPosition)
}

const cancelEditing = () => {
  draft.value = props.memory.ai_summary
  errorMessage.value = ''
  editing.value = false
}

const save = async () => {
  if (!canSave.value) return

  saving.value = true
  errorMessage.value = ''
  try {
    const memory = await memoriesStore.updateSummary(props.memory.id, normalizedDraft.value)
    draft.value = memory.ai_summary
    editing.value = false
    emit('saved', memory)
  } catch (error) {
    errorMessage.value = t('summary.saveFailed')
    notifications.show(t('summary.saveFailed'), 'error', 3000)
  } finally {
    saving.value = false
  }
}

const handleEditorKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape') {
    event.preventDefault()
    cancelEditing()
    return
  }

  if (event.key === 'Enter' && event.ctrlKey) {
    event.preventDefault()
    void save()
  }
}

const resolveDiscard = (confirmed: boolean) => {
  discardDialogOpen.value = false
  if (confirmed) cancelEditing()
  discardResolver?.(confirmed)
  discardResolver = null
  pendingDiscardPromise = null
}

const canLeave = async () => {
  if (!editing.value || !dirty.value) return true
  if (pendingDiscardPromise) return pendingDiscardPromise
  discardDialogOpen.value = true
  pendingDiscardPromise = new Promise<boolean>((resolve) => {
    discardResolver = resolve
  })
  return pendingDiscardPromise
}

onMounted(() => {
  unregisterGuard = unsavedChanges.register(canLeave)
})

onBeforeUnmount(() => {
  unregisterGuard?.()
  discardResolver?.(false)
})

defineExpose({
  canLeave,
  isDirty: dirty,
})
</script>

<template>
  <section class="summary-editor" :aria-label="t('memory.summary')">
    <div class="mb-3 flex min-h-10 items-center justify-between gap-3">
      <h3 class="flex-none text-base font-semibold text-[var(--shell-ink)]">{{ t('memory.summary') }}</h3>
      <button
        v-if="!editing"
        type="button"
        class="summary-editor__edit-action inline-flex h-10 w-28 flex-none items-center justify-center gap-1.5 whitespace-nowrap rounded-xl border border-[var(--shell-line)] px-2 text-[13px] font-medium leading-none text-blue-600 transition hover:bg-blue-50"
        @click="startEditing"
      >
        <PencilSquareIcon class="h-5 w-5 flex-none" aria-hidden="true" />
        {{ t('summary.edit') }}
      </button>
      <div v-else class="summary-editor__edit-actions flex flex-none items-center gap-2">
        <button
          type="button"
          class="summary-editor__edit-action inline-flex h-10 w-28 items-center justify-center whitespace-nowrap rounded-xl border border-[var(--shell-line)] bg-[var(--shell-control-bg)] px-2 text-[13px] font-medium leading-none text-blue-600 transition hover:bg-[var(--shell-control-hover)] disabled:cursor-not-allowed disabled:opacity-60"
          :disabled="saving"
          @click="cancelEditing"
        >
          {{ t('action.cancel') }}
        </button>
        <button
          type="button"
          class="summary-editor__edit-action inline-flex h-10 w-28 items-center justify-center gap-1.5 whitespace-nowrap rounded-xl border border-blue-600 bg-blue-600 px-2 text-[13px] font-medium leading-none text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
          :disabled="!canSave"
          @click="save"
        >
          <ArrowPathIcon v-if="saving" class="h-4 w-4 flex-none animate-spin" aria-hidden="true" />
          {{ saving ? t('summary.saving') : t('summary.save') }}
        </button>
      </div>
    </div>

    <div v-if="compact" class="relative isolate h-20">
      <textarea
        ref="compactEditor"
        v-model="draft"
        class="peer relative z-10 block h-full w-full resize-none overflow-y-auto border-0 bg-transparent p-0 pb-5 text-sm leading-7 text-[var(--shell-ink)] outline-none"
        :readonly="!editing"
        :tabindex="editing ? 0 : -1"
        :aria-label="t('memory.summary')"
        :aria-readonly="!editing"
        :aria-invalid="editing && Boolean(validationMessage)"
        :aria-describedby="editing ? 'summary-editor-feedback summary-editor-shortcut' : undefined"
        maxlength="4001"
        @keydown="handleEditorKeydown"
      />
      <div
        aria-hidden="true"
        class="pointer-events-none absolute -inset-2 z-0 rounded-2xl border transition-[border-color,background-color,box-shadow]"
        :class="editing
          ? validationMessage
            ? 'border-red-400 bg-[var(--shell-control-bg)]'
            : 'border-[var(--shell-line)] bg-[var(--shell-control-bg)] peer-focus:border-blue-500 peer-focus:ring-2 peer-focus:ring-blue-500/15'
          : 'border-transparent bg-transparent'"
      />

      <div
        v-if="editing"
        id="summary-editor-feedback"
        class="pointer-events-none absolute inset-x-0 bottom-0 z-20 flex items-center justify-between gap-3 text-xs"
      >
        <p class="min-w-0 truncate text-red-600">
          {{ validationMessage || errorMessage }}
        </p>
        <span class="flex-none tabular-nums" :class="draft.length > 4000 ? 'text-red-600' : 'text-[var(--shell-muted)]'">
          {{ draft.length }} / 4000
        </span>
      </div>
    </div>

    <div v-else class="relative" :class="editing ? 'min-h-32' : ''">
      <textarea
        v-if="editing"
        v-model="draft"
        class="min-h-32 w-full resize-y rounded-2xl border bg-[var(--shell-control-bg)] px-4 py-3 text-sm leading-6 text-[var(--shell-ink)] outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/15"
        :class="validationMessage ? 'border-red-400' : 'border-[var(--shell-line)]'"
        :aria-invalid="Boolean(validationMessage)"
        aria-describedby="summary-editor-feedback summary-editor-shortcut"
        maxlength="4001"
        autofocus
        @keydown="handleEditorKeydown"
      />
      <p v-else class="whitespace-pre-wrap text-sm leading-7 text-[var(--shell-ink)]">
        {{ memory.ai_summary }}
      </p>

      <div v-if="editing" id="summary-editor-feedback" class="mt-2 flex items-center justify-between gap-3 text-xs">
        <p class="min-w-0 truncate text-red-600">
          {{ validationMessage || errorMessage }}
        </p>
        <span class="flex-none tabular-nums" :class="draft.length > 4000 ? 'text-red-600' : 'text-[var(--shell-muted)]'">
          {{ draft.length }} / 4000
        </span>
      </div>
    </div>

    <div
      class="mt-3 flex min-h-5 items-center gap-2 text-xs"
      :class="memory.sync_status === 'FAILED'
        ? 'text-red-600'
        : memory.sync_status === 'PENDING'
          ? 'text-amber-600'
          : 'text-emerald-600'"
    >
      <ExclamationTriangleIcon v-if="memory.sync_status === 'FAILED'" class="h-4 w-4 flex-none" aria-hidden="true" />
      <ArrowPathIcon v-else-if="memory.sync_status === 'PENDING'" class="h-4 w-4 flex-none animate-spin" aria-hidden="true" />
      <CheckCircleIcon v-else class="h-4 w-4 flex-none" aria-hidden="true" />
      {{
        memory.sync_status === 'FAILED'
          ? t('summary.indexFailed')
          : memory.sync_status === 'PENDING'
            ? t('summary.indexPending')
            : t('summary.indexSynced')
      }}
    </div>

    <p id="summary-editor-shortcut" class="sr-only">{{ t('summary.shortcut') }}</p>

    <ConfirmDialog
      id="discard-summary"
      :open="discardDialogOpen"
      :title="t('summary.discardTitle')"
      :description="t('summary.discardDescription')"
      :confirm-label="t('summary.discard')"
      :cancel-label="t('summary.keepEditing')"
      destructive
      @confirm="resolveDiscard(true)"
      @cancel="resolveDiscard(false)"
    />
  </section>
</template>
