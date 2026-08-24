<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  ArrowTopRightOnSquareIcon,
  ClipboardDocumentIcon,
  TrashIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline'
import type { Memory } from '@/api/client'
import { useMemoriesStore } from '@/stores/memories'
import { useNotificationStore } from '@/stores/notification'
import { t } from '@/utils/i18n'
import { isTextMemory } from '@/utils/memory-types'
import ConfirmDialog from './ConfirmDialog.vue'
import MediaGallery from './MediaGallery.vue'
import OcrText from './OcrText.vue'
import SummaryEditor from './SummaryEditor.vue'

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
    await navigator.clipboard.writeText(props.memory.ai_summary)
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
  <aside class="flex h-full min-h-0 w-full flex-col bg-[var(--shell-frame-bg)]">
    <header class="flex items-start justify-between border-b border-[var(--shell-line)] px-5 py-3.5">
      <div>
        <h2 class="text-base font-semibold text-[var(--shell-ink)]">{{ t('memory.detail') }}</h2>
        <time class="mt-0.5 block text-xs text-[var(--shell-muted)]" :datetime="memory.created_at">
          {{ formatDate(memory.created_at) }}
        </time>
      </div>
      <button
        type="button"
        class="rounded-md p-1.5 text-[var(--shell-muted)] transition hover:bg-[var(--shell-control-hover)]"
        :aria-label="t('action.close')"
        @click="emit('close')"
      >
        <XMarkIcon class="h-5 w-5" aria-hidden="true" />
      </button>
    </header>

    <div class="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
      <MediaGallery v-if="!textMemory" :memory="memory" compact />

      <div
        v-if="memoriesStore.selectedOutsideSearch"
        class="rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-sm leading-6 text-amber-800"
      >
        {{ t('memory.savedOutsideSearch') }}
      </div>

      <SummaryEditor ref="summaryEditor" :memory="memory" compact />

      <div class="memory-inspector__summary-actions grid grid-cols-2 gap-2.5">
        <button type="button" class="btn-secondary min-h-10 justify-center" @click="copySummary">
          <ClipboardDocumentIcon class="h-5 w-5 flex-none" aria-hidden="true" />
          {{ t(textMemory ? 'action.copyContent' : 'action.copySummary') }}
        </button>
        <button type="button" class="btn-secondary min-h-10 justify-center" @click="emit('open', memory.id)">
          <ArrowTopRightOnSquareIcon class="h-5 w-5 flex-none" aria-hidden="true" />
          {{ t('action.viewDetail') }}
        </button>
      </div>

      <OcrText v-if="!textMemory" :text="memory.text_content" />

      <button
        type="button"
        class="inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-md text-sm font-medium text-red-600 transition hover:bg-red-50"
        @click="deleteDialogOpen = true"
      >
        <TrashIcon class="h-5 w-5 flex-none" aria-hidden="true" />
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
