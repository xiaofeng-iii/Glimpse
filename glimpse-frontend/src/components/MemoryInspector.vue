<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  ArrowPathIcon,
  ArrowTopRightOnSquareIcon,
  ClipboardDocumentIcon,
  ExclamationTriangleIcon,
  TrashIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline'
import type { Memory } from '@/api/client'
import { useMemoriesStore } from '@/stores/memories'
import { useNotificationStore } from '@/stores/notification'
import { t } from '@/utils/i18n'
import { getMemoryDisplayText, hasUserNote, isTextMemory } from '@/utils/memory-types'
import { useDevStateStore } from '@/stores/devState'
import ConfirmDialog from './ConfirmDialog.vue'
import MediaGallery from './MediaGallery.vue'
import OcrText from './OcrText.vue'
import SummaryEditor from './SummaryEditor.vue'
import MemoryAnalysisState from './MemoryAnalysisState.vue'

const props = defineProps<{
  memory: Memory
}>()

const emit = defineEmits<{
  (event: 'close'): void
  (event: 'open', id: string): void
}>()

const memoriesStore = useMemoriesStore()
const notifications = useNotificationStore()
const summaryEditor = ref<InstanceType<typeof SummaryEditor> | null>(null)
const deleteDialogOpen = ref(false)
const deleting = ref(false)
const textMemory = computed(() => isTextMemory(props.memory))
const devState = useDevStateStore()
// DEV 状态覆盖只影响展示判定；编辑、删除等交互仍走原始 memory。
const effectiveMemory = computed(() =>
  import.meta.env.DEV ? devState.applyOverride(props.memory) : props.memory,
)
const analysisStatus = computed(() => effectiveMemory.value.analysis_status ?? 'COMPLETED')
const analyzing = computed(() => analysisStatus.value === 'PROCESSING')
const analysisUnavailable = computed(() => analysisStatus.value === 'FAILED')
// 有用户文字的记忆随时有内容可展示：分析期间以只读文本替代加载块，只叠加状态提示。
const userNote = computed(() => hasUserNote(props.memory))
const showAnalysisBlock = computed(() => !userNote.value && (analyzing.value || analysisUnavailable.value))

const formatDate = (value: string) =>
  new Date(value).toLocaleString([], {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })

const copySummary = async () => {
  try {
    await navigator.clipboard.writeText(getMemoryDisplayText(props.memory))
    notifications.show(t('message.copied'), 'success', 1800)
  } catch {
    notifications.show(t('message.copyFailed'), 'error', 2800)
  }
}

const confirmDelete = async () => {
  deleting.value = true
  try {
    await memoriesStore.remove(props.memory.id)
    notifications.show(t('message.deleted'), 'success', 1800)
    deleteDialogOpen.value = false
    emit('close')
  } catch {
    notifications.show(t('message.deleteFailed'), 'error', 2800)
  } finally {
    deleting.value = false
  }
}

const canLeave = () => summaryEditor.value?.canLeave() ?? Promise.resolve(true)
defineExpose({ canLeave })
</script>

<template>
  <aside class="flex h-full min-h-0 w-full flex-col bg-[var(--color-surface)]">
    <header class="flex items-start justify-between border-b border-[var(--shell-line)] px-5 py-3.5">
      <div>
        <h2 class="text-base font-semibold text-[var(--shell-ink)]">{{ t('memory.detail') }}</h2>
        <time class="mt-0.5 block text-xs text-[var(--shell-muted)]" :datetime="memory.created_at">
          {{ formatDate(memory.created_at) }}
        </time>
      </div>
      <button
        type="button"
        class="inline-flex h-8 w-8 min-h-0 items-center justify-center rounded-md text-[var(--shell-muted)] transition hover:bg-[var(--shell-control-hover)]"
        :aria-label="t('action.close')"
        @click="emit('close')"
      >
        <XMarkIcon class="h-4 w-4" aria-hidden="true" />
      </button>
    </header>

    <div class="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
      <MediaGallery v-if="!textMemory" :memory="memory" compact />

      <div
        v-if="memoriesStore.selectedOutsideSearch"
        class="rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-sm text-amber-800"
      >
        {{ t('memory.savedOutsideSearch') }}
      </div>

      <MemoryAnalysisState
        v-if="showAnalysisBlock"
        :status="analysisUnavailable ? 'FAILED' : 'PROCESSING'"
      />
      <div v-else-if="analyzing || analysisUnavailable">
        <p class="whitespace-pre-wrap text-sm text-[var(--shell-ink)]">{{ memory.user_text }}</p>
        <div
          class="mt-3 flex min-h-5 items-center gap-2 text-xs"
          :class="analyzing ? 'text-[var(--color-primary)]' : 'text-red-600'"
        >
          <ArrowPathIcon v-if="analyzing" class="h-4 w-4 flex-none animate-spin" aria-hidden="true" />
          <ExclamationTriangleIcon v-else class="h-4 w-4 flex-none" aria-hidden="true" />
          {{ t(analyzing ? 'memory.imageAnalyzing' : 'memory.imageAnalysisFailed') }}
        </div>
      </div>
      <SummaryEditor v-else ref="summaryEditor" :memory="memory" compact />

      <div
        class="memory-inspector__summary-actions grid gap-2.5"
        :class="showAnalysisBlock ? 'grid-cols-1' : 'grid-cols-2'"
      >
        <button v-if="!showAnalysisBlock" type="button" class="btn-secondary justify-center" @click="copySummary">
          <ClipboardDocumentIcon class="h-4 w-4 flex-none" aria-hidden="true" />
          {{ t(textMemory || hasUserNote(props.memory) ? 'action.copyContent' : 'action.copySummary') }}
        </button>
        <button type="button" class="btn-secondary justify-center" @click="emit('open', memory.id)">
          <ArrowTopRightOnSquareIcon class="h-4 w-4 flex-none" aria-hidden="true" />
          {{ t('action.viewDetail') }}
        </button>
      </div>

      <OcrText v-if="!textMemory && !analyzing && !analysisUnavailable" :text="memory.text_content" />

      <button
        v-if="!analyzing"
        type="button"
        class="btn-ghost-danger w-full"
        @click="deleteDialogOpen = true"
      >
        <TrashIcon class="h-4 w-4 flex-none" aria-hidden="true" />
        {{ t('action.delete') }}
      </button>
    </div>

    <ConfirmDialog
      id="delete-memory"
      :open="deleteDialogOpen"
      :title="t('delete.title')"
      :description="t('message.deleteConfirmIrreversible')"
      :confirm-label="t('action.delete')"
      :cancel-label="t('action.cancel')"
      :busy="deleting"
      destructive
      @confirm="confirmDelete"
      @cancel="deleteDialogOpen = false"
    />
  </aside>
</template>
