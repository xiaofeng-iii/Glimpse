<script setup lang="ts">
import { ref } from 'vue'
import { ClipboardDocumentIcon, CheckIcon } from '@heroicons/vue/24/outline'
import { t } from '@/utils/i18n'

const props = withDefaults(
  defineProps<{
    text?: string
    /** 侧栏内嵌形态：去描边、subtle 底，与摘要块同饰；详情页保持白底线框 */
    compact?: boolean
  }>(),
  { compact: false },
)

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
  <section
    class="ocr-text rounded-lg p-3.5"
    :class="compact
      ? 'bg-[var(--color-surface-subtle)]'
      : 'border border-[var(--shell-line)] bg-[var(--shell-control-bg)]'"
  >
    <div class="mb-2.5 flex items-center justify-between gap-3">
      <h3 class="text-sm font-semibold text-[var(--shell-ink)]">{{ t('memory.text') }}</h3>
      <button
        v-if="text"
        type="button"
        class="inline-flex items-center gap-2 rounded-md text-[var(--shell-muted)] transition hover:bg-[var(--shell-control-hover)]"
        :class="compact ? 'min-h-7 px-2 text-[0.8125rem]' : 'min-h-8 px-2.5 text-sm'"
        @click="copyText"
      >
        <CheckIcon v-if="copied" class="h-4 w-4 flex-none text-emerald-600" aria-hidden="true" />
        <ClipboardDocumentIcon v-else class="h-4 w-4 flex-none" aria-hidden="true" />
        {{ copied ? t('action.copied') : t('action.copyText') }}
      </button>
    </div>
    <p
      v-if="text"
      class="max-h-64 overflow-y-auto whitespace-pre-wrap text-sm text-[var(--shell-ink)]"
    >
      {{ text }}
    </p>
    <p v-else class="text-sm text-[var(--shell-muted)]">{{ t('memory.noRecognizedText') }}</p>
  </section>
</template>
