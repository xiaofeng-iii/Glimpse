<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  ArrowPathIcon,
  ExclamationTriangleIcon,
  PencilSquareIcon,
} from '@heroicons/vue/24/outline'
import type { Memory } from '@/api/client'
import { useMemoriesStore } from '@/stores/memories'
import { useNotificationStore } from '@/stores/notification'
import { useUnsavedChangesStore } from '@/stores/unsavedChanges'
import { useDevStateStore } from '@/stores/devState'
import { t, type MessageKey } from '@/utils/i18n'
import { hasUserNote, isTextMemory } from '@/utils/memory-types'
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
const devState = useDevStateStore()
const editing = ref(false)
const draft = ref(
  hasUserNote(props.memory) ? (props.memory.user_text ?? '') : props.memory.ai_summary,
)
const saving = ref(false)
const errorMessage = ref('')
const discardDialogOpen = ref(false)
const compactEditor = ref<HTMLTextAreaElement | null>(null)
const compactFrame = ref<HTMLElement | null>(null)
const compactHeight = ref(80)
const compactOverflowing = ref(false)
const textMemory = computed(() => isTextMemory(props.memory))
const noteMode = computed(() => hasUserNote(props.memory))
// DEV 状态覆盖只影响同步状态展示；编辑与保存仍走原始 memory。
const displaySyncStatus = computed(() =>
  import.meta.env.DEV ? devState.applyOverride(props.memory).sync_status : props.memory.sync_status,
)
// 展示与编辑的文本字段：带用户说明的记忆编辑 user_text（AI 摘要仅作检索资源，不展示）；
// 文案与纯文本记忆统一为“记忆内容”。其余记忆与旧行为一致，编辑 ai_summary。
const fieldText = computed(() =>
  noteMode.value ? (props.memory.user_text ?? '') : props.memory.ai_summary,
)
const contentLabel = computed(() =>
  t(textMemory.value || noteMode.value ? 'memory.content' : 'memory.summary'),
)
const editorText = (key: string) =>
  t(
    `${textMemory.value || noteMode.value ? 'content' : 'summary'}.${key}` as MessageKey,
  )
let discardResolver: ((confirmed: boolean) => void) | null = null
let pendingDiscardPromise: Promise<boolean> | null = null
let unregisterGuard: (() => boolean) | null = null
let compactResizeObserver: ResizeObserver | null = null

const COMPACT_MIN_HEIGHT = 80
const COMPACT_MAX_HEIGHT = 256

const compactHeightLimit = () => {
  const viewportHeight = typeof window === 'undefined' ? 720 : window.innerHeight
  return Math.max(160, Math.min(COMPACT_MAX_HEIGHT, Math.floor(viewportHeight * 0.36)))
}

const resizeCompactEditor = () => {
  if (!props.compact) return
  const editor = compactEditor.value
  if (!editor) return

  editor.style.height = 'auto'
  const naturalHeight = Math.ceil(editor.scrollHeight)
  const maximumHeight = compactHeightLimit()
  compactHeight.value = Math.min(maximumHeight, Math.max(COMPACT_MIN_HEIGHT, naturalHeight))
  compactOverflowing.value = naturalHeight > maximumHeight
  editor.style.height = '100%'
}

const scheduleCompactEditorResize = async () => {
  await nextTick()
  resizeCompactEditor()
}

const handleViewportResize = () => {
  void scheduleCompactEditorResize()
}

const normalizedDraft = computed(() => draft.value.trim())
const dirty = computed(() => normalizedDraft.value !== fieldText.value.trim())
const validationMessage = computed(() => {
  if (!normalizedDraft.value) return editorText('required')
  if (normalizedDraft.value.length > 4000) return editorText('tooLong')
  return ''
})
const canSave = computed(() => dirty.value && !validationMessage.value && !saving.value)

watch(
  () => props.memory.id,
  () => {
    editing.value = false
    draft.value = fieldText.value
    errorMessage.value = ''
  },
)

watch(
  fieldText,
  (value) => {
    if (!editing.value || !dirty.value) {
      draft.value = value
    }
  },
)

watch(
  [draft, fieldText, editing],
  () => void scheduleCompactEditorResize(),
  { flush: 'post' },
)

const startEditing = async () => {
  draft.value = fieldText.value
  errorMessage.value = ''
  editing.value = true
  await nextTick()
  const editor = compactEditor.value
  if (!editor) return

  resizeCompactEditor()

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
  draft.value = fieldText.value
  errorMessage.value = ''
  editing.value = false
}

const save = async () => {
  if (!canSave.value) return

  saving.value = true
  errorMessage.value = ''
  try {
    const memory = noteMode.value
      ? await memoriesStore.updateUserText(props.memory.id, normalizedDraft.value)
      : await memoriesStore.updateSummary(props.memory.id, normalizedDraft.value)
    draft.value = noteMode.value ? (memory.user_text ?? '') : memory.ai_summary
    editing.value = false
    emit('saved', memory)
  } catch (error) {
    errorMessage.value = editorText('saveFailed')
    notifications.show(editorText('saveFailed'), 'error', 3000)
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
  void scheduleCompactEditorResize()

  if (typeof ResizeObserver !== 'undefined' && compactFrame.value) {
    let previousWidth = compactFrame.value.getBoundingClientRect().width
    compactResizeObserver = new ResizeObserver(([entry]) => {
      const nextWidth = entry?.contentRect.width ?? 0
      if (Math.abs(nextWidth - previousWidth) < 0.5) return
      previousWidth = nextWidth
      void scheduleCompactEditorResize()
    })
    compactResizeObserver.observe(compactFrame.value)
  }

  window.addEventListener('resize', handleViewportResize)
})

onBeforeUnmount(() => {
  unregisterGuard?.()
  discardResolver?.(false)
  compactResizeObserver?.disconnect()
  window.removeEventListener('resize', handleViewportResize)
})

defineExpose({
  canLeave,
  isDirty: dirty,
})
</script>

<template>
  <section class="summary-editor" :aria-label="contentLabel">
    <div class="summary-editor__header mb-2.5 flex min-h-8 items-center justify-between gap-3">
      <h3 class="flex-none text-sm font-semibold text-[var(--shell-ink)]">{{ contentLabel }}</h3>
      <button
        v-if="!editing"
        type="button"
        class="summary-editor__edit-action inline-flex h-8 w-28 flex-none items-center justify-center gap-0.5 whitespace-nowrap rounded-md border border-[var(--shell-line)] px-1 text-sm font-semibold text-[var(--color-primary)] transition hover:bg-[var(--color-primary-soft)]"
        @click="startEditing"
      >
        <PencilSquareIcon class="h-3.5 w-3.5 flex-none" aria-hidden="true" />
        {{ editorText('edit') }}
      </button>
      <div v-else class="summary-editor__edit-actions flex flex-none items-center gap-2">
        <button
          type="button"
          class="summary-editor__edit-action inline-flex h-8 w-28 items-center justify-center whitespace-nowrap rounded-md border border-[var(--shell-line)] bg-[var(--shell-control-bg)] px-2 text-sm font-semibold text-[var(--color-primary)] transition hover:bg-[var(--shell-control-hover)] disabled:cursor-not-allowed disabled:opacity-60"
          :disabled="saving"
          @click="cancelEditing"
        >
          {{ t('action.cancel') }}
        </button>
        <button
          type="button"
          class="summary-editor__edit-action inline-flex h-8 w-28 items-center justify-center gap-1.5 whitespace-nowrap rounded-md border border-[var(--color-primary)] bg-[var(--color-primary)] px-2 text-sm font-semibold text-white transition hover:bg-[var(--color-primary-hover)] disabled:cursor-not-allowed disabled:opacity-60"
          :disabled="!canSave"
          @click="save"
        >
          <ArrowPathIcon v-if="saving" class="h-4 w-4 flex-none animate-spin" aria-hidden="true" />
          {{ saving ? editorText('saving') : editorText('save') }}
        </button>
      </div>
    </div>

    <div
      v-if="compact"
      ref="compactFrame"
      class="summary-editor__compact-frame relative isolate min-h-20 overflow-hidden rounded-lg border transition-[border-color,background-color,box-shadow]"
      :class="editing
        ? validationMessage
          ? 'border-red-400 bg-[var(--shell-control-bg)]'
          : 'summary-editor__compact-frame--editing border-[var(--shell-line)] bg-[var(--shell-control-bg)]'
        : compactOverflowing
          ? 'summary-editor__compact-frame--scrollable border-transparent bg-transparent'
          : 'border-transparent bg-transparent'"
      :style="{ height: `${compactHeight}px` }"
    >
      <textarea
        ref="compactEditor"
        v-model="draft"
        class="summary-editor__compact-control relative z-10 block h-full w-full resize-none border-0 bg-transparent px-3 py-2 pb-7 text-sm text-[var(--shell-ink)] outline-none"
        :class="compactOverflowing ? 'overflow-y-auto' : 'overflow-y-hidden'"
        :readonly="!editing"
        :tabindex="editing || compactOverflowing ? 0 : -1"
        :aria-label="contentLabel"
        :aria-readonly="!editing"
        :aria-invalid="editing && Boolean(validationMessage)"
        :aria-describedby="editing ? 'summary-editor-feedback summary-editor-shortcut' : undefined"
        maxlength="4001"
        @keydown="handleEditorKeydown"
      />

      <div
        v-if="editing"
        id="summary-editor-feedback"
        class="pointer-events-none absolute inset-x-3 bottom-2 z-20 flex items-center justify-between gap-3 text-xs"
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
        class="min-h-32 w-full resize-none rounded-lg border bg-[var(--shell-control-bg)] px-3.5 py-2.5 text-sm text-[var(--shell-ink)] outline-none transition"
        :class="validationMessage ? 'border-red-400' : 'border-[var(--shell-line)]'"
        :aria-invalid="Boolean(validationMessage)"
        aria-describedby="summary-editor-feedback summary-editor-shortcut"
        maxlength="4001"
        autofocus
        :aria-label="contentLabel"
        @keydown="handleEditorKeydown"
      />
      <p v-else class="whitespace-pre-wrap text-sm text-[var(--shell-ink)]">
        {{ fieldText }}
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

    <!-- 一切正常时不打扰：只有索引尚未同步或同步失败才显示状态行。 -->
    <div
      v-if="displaySyncStatus === 'PENDING' || displaySyncStatus === 'FAILED'"
      class="mt-3 flex min-h-5 items-center gap-2 text-xs"
      :class="displaySyncStatus === 'FAILED' ? 'text-red-600' : 'text-amber-600'"
    >
      <ExclamationTriangleIcon v-if="displaySyncStatus === 'FAILED'" class="h-4 w-4 flex-none" aria-hidden="true" />
      <ArrowPathIcon v-else class="h-4 w-4 flex-none animate-spin" aria-hidden="true" />
      {{
        displaySyncStatus === 'FAILED'
          ? editorText('indexFailed')
          : editorText('indexPending')
      }}
    </div>

    <p id="summary-editor-shortcut" class="sr-only">{{ editorText('shortcut') }}</p>

    <ConfirmDialog
      id="discard-summary"
      :open="discardDialogOpen"
      :title="editorText('discardTitle')"
      :description="editorText('discardDescription')"
      :confirm-label="editorText('discard')"
      :cancel-label="editorText('keepEditing')"
      destructive
      @confirm="resolveDiscard(true)"
      @cancel="resolveDiscard(false)"
    />
  </section>
</template>

<style scoped>
.summary-editor {
  container-type: inline-size;
}

.summary-editor__compact-frame--editing:focus-within,
.summary-editor__compact-frame--scrollable:focus-within {
  border-color: var(--color-focus);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--color-focus) 28%, transparent);
}

.summary-editor__compact-control:focus,
.summary-editor__compact-control:focus-visible {
  border-color: transparent;
  box-shadow: none;
}

@container (max-width: 20rem) {
  .summary-editor__header {
    align-items: flex-start;
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 0.5rem;
  }

  .summary-editor__header > .summary-editor__edit-action {
    justify-self: end;
  }

  .summary-editor__edit-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
