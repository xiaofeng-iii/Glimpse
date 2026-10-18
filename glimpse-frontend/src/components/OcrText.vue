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
    class="ocr-text rounded-lg"
    :class="compact
      ? 'ocr-text--compact bg-[var(--color-surface-subtle)]'
      : 'border border-[var(--shell-line)] bg-[var(--shell-control-bg)] p-3.5'"
  >
    <div class="ocr-text__header mb-2.5 flex items-center justify-between gap-3">
      <h3 class="text-sm font-semibold text-[var(--shell-ink)]">{{ t('memory.text') }}</h3>
      <button
        v-if="text"
        type="button"
        class="ocr-text__copy inline-flex items-center gap-2 rounded-md text-[var(--shell-muted)] transition duration-[160ms] ease-[ease] hover:bg-[var(--shell-control-hover)]"
        :class="compact ? 'min-h-7 px-2 text-sm' : 'min-h-8 px-2.5 text-sm'"
        @click="copyText"
      >
        <CheckIcon v-if="copied" class="h-4 w-4 flex-none text-emerald-600" aria-hidden="true" />
        <ClipboardDocumentIcon v-else class="h-4 w-4 flex-none" aria-hidden="true" />
        {{ copied ? t('action.copied') : t('action.copyText') }}
      </button>
    </div>
    <p
      v-if="text"
      class="max-h-64 overflow-y-auto whitespace-pre-wrap text-sm text-[var(--shell-ink)] [overflow-wrap:anywhere]"
      :class="compact ? 'ocr-text__body--compact' : ''"
    >
      {{ text }}
    </p>
    <p v-else class="text-sm text-[var(--shell-muted)]" :class="compact ? 'ocr-text__body--compact' : ''">{{ t('memory.noRecognizedText') }}</p>
  </section>
</template>

<style scoped>

/* 紧凑形态与摘要块同构：容器内衬 10/12/12，标题行与正文再让出同样的内衬，
   两块的标题、按钮、文字到灰边的距离逐边一致 */
.ocr-text--compact {
  padding: 0.625rem 0.75rem 0.75rem;
}

.ocr-text--compact .ocr-text__header {
  min-height: 2rem;
  margin-bottom: 0.375rem;
  padding-inline: 0.75rem;
}

.ocr-text__body--compact {
  /* 摘要块的文本框带 1px 透明边框占位，识别文本同构补齐，四向距离逐像素一致 */
  border: 1px solid transparent;
  padding: 0.5rem 0.75rem 1.75rem;
}

.ocr-text--compact .ocr-text__copy:hover {
  background: rgb(224, 228, 237);
}

:root[data-theme='dark'] .ocr-text--compact .ocr-text__copy:hover {
  background: var(--color-surface-hover);
}
</style>
