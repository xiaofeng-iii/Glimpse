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
const statusVisible = computed(() => analyzing.value || analysisUnavailable.value)
// 有用户文字的记忆随时有内容可展示：分析期间保留用户文字，只叠加状态行。
const userNote = computed(() => hasUserNote(props.memory))
const displayText = computed(() => getMemoryDisplayText(props.memory))

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
    <header class="flex items-center gap-3 px-5 pb-3 pt-3.5">
      <div class="flex min-w-0 flex-1 items-baseline gap-x-2.5">
        <h2 class="flex-none text-base font-semibold text-[var(--shell-ink)]">{{ t('memory.detail') }}</h2>
        <time class="min-w-0 truncate text-xs text-[var(--shell-muted)]" :datetime="memory.created_at">
          {{ formatDate(memory.created_at) }}
        </time>
      </div>
      <button
        type="button"
        class="inline-flex h-8 w-8 min-h-0 flex-none items-center justify-center rounded-md text-[var(--shell-muted)] transition hover:bg-[var(--shell-control-hover)]"
        :aria-label="t('action.close')"
        @click="emit('close')"
      >
        <XMarkIcon class="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    </header>

    <div class="memory-inspector__divider" aria-hidden="true"></div>

    <div class="memory-inspector__body min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
      <MediaGallery v-if="!textMemory" :memory="memory" compact />

      <div
        v-if="memoriesStore.selectedOutsideSearch"
        class="rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-sm text-amber-800"
      >
        {{ t('memory.savedOutsideSearch') }}
      </div>

      <p
        v-if="statusVisible && userNote"
        class="whitespace-pre-wrap text-sm text-[var(--shell-ink)]"
      >
        {{ memory.user_text }}
      </p>
      <MemoryAnalysisState
        v-if="statusVisible"
        variant="inline"
        :status="analysisUnavailable ? 'FAILED' : 'PROCESSING'"
      />
      <SummaryEditor v-else ref="summaryEditor" :memory="memory" compact />

      <div
        class="memory-inspector__summary-actions grid gap-2.5"
        :class="displayText ? 'grid-cols-2' : 'grid-cols-1'"
      >
        <button v-if="displayText" type="button" class="btn-secondary justify-center" @click="copySummary">
          <ClipboardDocumentIcon class="h-4 w-4 flex-none" aria-hidden="true" />
          {{ t(textMemory || hasUserNote(props.memory) ? 'action.copyContent' : 'action.copySummary') }}
        </button>
        <button type="button" class="btn-secondary justify-center" @click="emit('open', memory.id)">
          <ArrowTopRightOnSquareIcon class="h-4 w-4 flex-none" aria-hidden="true" />
          {{ t('action.viewDetail') }}
        </button>
      </div>

      <OcrText v-if="!textMemory && !analyzing && !analysisUnavailable" :text="memory.text_content" compact />

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

<style scoped>
/* 标题栏与滚动内容之间只留一道内缩低对比细线（设置页同款），
   不再使用贯通两缘的 border-b 硬分割。 */
.memory-inspector__divider {
  flex: none;
  height: 1px;
  margin-inline: 1.25rem;
  background: color-mix(in srgb, var(--shell-line) 55%, transparent);
}

/* 侧栏滚动条隐藏（设置页正文同策略）：滚动能力保留，滚动条不占视觉宽度，
   避免在白卡右缘形成常驻分割线。 */
.memory-inspector__body {
  scrollbar-width: none;
}

.memory-inspector__body::-webkit-scrollbar {
  display: none;
}
</style>
