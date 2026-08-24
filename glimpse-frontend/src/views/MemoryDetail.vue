<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  ArrowPathIcon,
  ClipboardDocumentIcon,
  TrashIcon,
} from '@heroicons/vue/24/outline'
import {
  onBeforeRouteLeave,
  onBeforeRouteUpdate,
  useRoute,
  useRouter,
} from 'vue-router'
import { memoriesApi } from '@/api/client'
import { useMemoriesStore } from '@/stores/memories'
import { useNotificationStore } from '@/stores/notification'
import { createLogger } from '@/utils/logger'
import { t } from '@/utils/i18n'
import { isTextMemory } from '@/utils/memory-types'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import MediaGallery from '@/components/MediaGallery.vue'
import OcrText from '@/components/OcrText.vue'
import SummaryEditor from '@/components/SummaryEditor.vue'

type SummaryEditorExpose = {
  canLeave: () => Promise<boolean>
}

const route = useRoute()
const router = useRouter()
const memoriesStore = useMemoriesStore()
const notifications = useNotificationStore()
const logger = createLogger('views/MemoryDetail')

const summaryEditor = ref<SummaryEditorExpose | null>(null)
const loading = ref(false)
const loadFailed = ref(false)
const deleteDialogOpen = ref(false)
const deleting = ref(false)
const memoryId = computed(() => String(route.params.id ?? ''))
const memory = computed(() => memoriesStore.entities[memoryId.value] ?? null)
const textMemory = computed(() => Boolean(memory.value && isTextMemory(memory.value)))

const formatDate = (value: string) =>
  new Date(value).toLocaleString([], {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })

const loadMemory = async () => {
  if (!memoryId.value) return
  loading.value = true
  loadFailed.value = false
  try {
    memoriesStore.upsert(await memoriesApi.get(memoryId.value))
  } catch (error) {
    logger.error('Failed to load memory: %s', error)
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}

watch(memoryId, () => void loadMemory(), { immediate: true })

const canLeave = () => summaryEditor.value?.canLeave() ?? Promise.resolve(true)
onBeforeRouteLeave(async () => canLeave())
onBeforeRouteUpdate(async () => canLeave())

const copySummary = async () => {
  if (!memory.value) return
  try {
    await navigator.clipboard.writeText(memory.value.ai_summary)
    notifications.show(t('message.copied'), 'success', 1800)
  } catch {
    notifications.show(t('message.copyFailed'), 'error', 2800)
  }
}

const confirmDelete = async () => {
  if (!memory.value || deleting.value) return
  deleting.value = true
  try {
    await memoriesStore.remove(memory.value.id)
    notifications.show(t('message.deleted'), 'success', 1800)
    deleteDialogOpen.value = false
    await router.push('/')
  } catch (error) {
    logger.error('Delete memory failed: %s', error)
    notifications.show(t('message.deleteFailed'), 'error', 2800)
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <main class="h-full min-h-0 overflow-y-auto bg-[var(--shell-window-bg)] px-5 py-4 sm:px-6">
    <div class="mx-auto max-w-[1440px]">
      <header class="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div class="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <h1 class="text-lg font-semibold tracking-[-0.01em] text-[var(--shell-ink)]">{{ t('memory.detail') }}</h1>
          <time v-if="memory" class="text-sm text-[var(--shell-muted)]" :datetime="memory.created_at">
            {{ formatDate(memory.created_at) }}
          </time>
        </div>

        <button
          v-if="memory"
          type="button"
          class="inline-flex min-h-10 items-center gap-2 rounded-md border border-red-200 px-3.5 text-sm font-medium text-red-600 transition hover:bg-red-50"
          @click="deleteDialogOpen = true"
        >
          <TrashIcon class="h-5 w-5 flex-none" aria-hidden="true" />
          {{ t('action.delete') }}
        </button>
      </header>

      <div v-if="loading" class="flex min-h-[65vh] items-center justify-center">
        <ArrowPathIcon class="h-8 w-8 animate-spin text-[var(--color-primary)]" :aria-label="t('memory.loading')" />
      </div>

      <div
        v-else-if="loadFailed || !memory"
        class="flex min-h-[65vh] flex-col items-center justify-center text-center"
      >
        <h2 class="text-lg font-semibold text-[var(--shell-ink)]">{{ t('memory.missing') }}</h2>
        <p class="mt-2 text-sm text-[var(--shell-muted)]">{{ t('memory.loadFailedHint') }}</p>
        <button type="button" class="btn-primary mt-4 min-h-10" @click="loadMemory">
          <ArrowPathIcon class="h-5 w-5 flex-none" aria-hidden="true" />
          {{ t('action.retry') }}
        </button>
      </div>

      <div v-else class="detail-layout" :class="{ 'detail-layout--text': textMemory }">
        <section v-if="!textMemory" class="min-w-0">
          <MediaGallery :memory="memory" />
        </section>

        <section class="min-w-0 space-y-5">
          <SummaryEditor ref="summaryEditor" :memory="memory" />

          <button type="button" class="btn-secondary min-h-10" @click="copySummary">
            <ClipboardDocumentIcon class="h-5 w-5 flex-none" aria-hidden="true" />
            {{ t(textMemory ? 'action.copyContent' : 'action.copySummary') }}
          </button>

          <div v-if="!textMemory" class="border-t border-[var(--shell-line)] pt-5">
            <OcrText :text="memory.text_content" />
          </div>

          <p class="text-xs text-[var(--shell-muted)]">
            {{ t('memory.createdAt', { date: formatDate(memory.created_at) }) }}
          </p>
        </section>
      </div>
    </div>

    <ConfirmDialog
      id="detail-delete-memory"
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
  </main>
</template>

<style scoped>
.detail-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.9fr);
  gap: 1.5rem;
}

.detail-layout--text {
  grid-template-columns: minmax(0, 760px);
  justify-content: center;
}

@media (max-width: 960px) {
  .detail-layout {
    grid-template-columns: 1fr;
  }
}
</style>
