<script setup lang="ts">
import { ref } from 'vue'
import { ClipboardDocumentIcon, CheckIcon } from '@heroicons/vue/24/outline'
import { t } from '@/utils/i18n'

const props = defineProps<{
  text?: string
}>()

const copied = ref(false)
let copiedTimer: ReturnType<typeof window.setTimeout> | null = null

const copyText = async () => {
  if (!props.text) return
  await navigator.clipboard.writeText(props.text)
  copied.value = true
  if (copiedTimer) window.clearTimeout(copiedTimer)
  copiedTimer = window.setTimeout(() => {
    copied.value = false
  }, 1800)
}
</script>

<template>
  <section class="ocr-text rounded-lg border border-[var(--shell-line)] bg-[var(--shell-control-bg)] p-3.5">
    <div class="mb-2.5 flex items-center justify-between gap-3">
      <h3 class="text-sm font-semibold text-[var(--shell-ink)]">{{ t('memory.text') }}</h3>
      <button
        v-if="text"
        type="button"
        class="inline-flex min-h-9 items-center gap-2 rounded-md px-2.5 text-sm text-[var(--shell-muted)] transition hover:bg-[var(--shell-control-hover)]"
        @click="copyText"
      >
        <CheckIcon v-if="copied" class="h-4 w-4 flex-none text-emerald-600" aria-hidden="true" />
        <ClipboardDocumentIcon v-else class="h-4 w-4 flex-none" aria-hidden="true" />
        {{ copied ? t('action.copied') : t('action.copyText') }}
      </button>
    </div>
    <p
      v-if="text"
      class="max-h-64 overflow-y-auto whitespace-pre-wrap text-sm leading-7 text-[var(--shell-ink)]"
    >
      {{ text }}
    </p>
    <p v-else class="text-sm text-[var(--shell-muted)]">{{ t('memory.noRecognizedText') }}</p>
  </section>
</template>
