<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ArrowPathIcon, ExclamationTriangleIcon } from '@heroicons/vue/24/outline'
import { t } from '@/utils/i18n'
import { startSynchronizedProgress } from '@/utils/synchronized-progress'

// inline：卡片与检查器的一行状态（图标+文案），不遮挡内容；
// block：详情页的完整等待面板，状态即主内容，进度条与其他等待面板共享墙钟相位。
const props = withDefaults(defineProps<{
  status?: 'PROCESSING' | 'FAILED'
  variant?: 'inline' | 'block'
}>(), {
  status: 'PROCESSING',
  variant: 'block',
})

const failed = computed(() => props.status === 'FAILED')
const isBlock = computed(() => props.variant === 'block')
const progressBar = ref<HTMLElement | null>(null)
let progressAnimation: Animation | null = null

const syncProgressAnimation = async () => {
  progressAnimation?.cancel()
  progressAnimation = null
  if (failed.value || !isBlock.value) return
  await nextTick()
  if (progressBar.value) {
    progressAnimation = startSynchronizedProgress(progressBar.value)
  }
}

onMounted(() => void syncProgressAnimation())
watch([failed, isBlock], () => void syncProgressAnimation())
onBeforeUnmount(() => progressAnimation?.cancel())
</script>

<template>
  <div
    v-if="!isBlock"
    class="memory-analysis-state__row"
    :class="{ 'memory-analysis-state__row--failed': failed }"
    role="status"
    :aria-live="failed ? 'assertive' : 'polite'"
    :aria-busy="!failed"
  >
    <ArrowPathIcon v-if="!failed" class="h-3.5 w-3.5 flex-none animate-spin" aria-hidden="true" />
    <ExclamationTriangleIcon v-else class="h-3.5 w-3.5 flex-none" aria-hidden="true" />
    <span>{{ t(failed ? 'memory.imageAnalysisFailed' : 'memory.imageAnalyzing') }}</span>
  </div>

  <div
    v-else
    class="memory-analysis-state"
    :class="{ 'memory-analysis-state--failed': failed }"
    role="status"
    :aria-live="failed ? 'assertive' : 'polite'"
    :aria-busy="!failed"
  >
    <div class="memory-analysis-state__heading">
      <ExclamationTriangleIcon
        v-if="failed"
        class="memory-analysis-state__icon"
        aria-hidden="true"
      />
      <span>{{ t(failed ? 'memory.imageAnalysisFailed' : 'memory.imageAnalyzing') }}</span>
    </div>
    <p class="memory-analysis-state__hint">
      {{ t(failed ? 'memory.analysisFailedHint' : 'memory.analysisProcessingHint') }}
    </p>
    <div v-if="!failed" class="memory-analysis-state__track" aria-hidden="true">
      <span ref="progressBar" class="memory-analysis-state__bar" />
    </div>
  </div>
</template>

<style scoped>
.memory-analysis-state {
  padding: 0.875rem;
  border: 1px solid color-mix(in srgb, var(--color-primary) 18%, var(--shell-line));
  border-radius: var(--radius-md);
  color: var(--shell-ink);
  background: var(--color-primary-soft);
}

.memory-analysis-state--failed {
  border-color: color-mix(in srgb, var(--color-danger) 28%, var(--shell-line));
  background: color-mix(in srgb, var(--color-danger) 7%, var(--shell-card));
}

.memory-analysis-state__row {
  display: inline-flex;
  min-height: 1.25rem;
  align-items: center;
  gap: 0.25rem;
  color: var(--color-primary);
  font-size: 0.75rem;
  font-weight: 500;
  line-height: 1rem;
}

.memory-analysis-state__row--failed {
  color: var(--color-danger);
}

.memory-analysis-state__heading {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.8125rem;
  font-weight: 600;
  line-height: 1.25rem;
}

.memory-analysis-state__icon {
  width: 1rem;
  height: 1rem;
  flex: none;
  color: var(--color-danger);
}

.memory-analysis-state__hint {
  margin-top: 0.125rem;
  color: var(--shell-muted);
  font-size: 0.75rem;
  line-height: var(--line-height-12);
}

.memory-analysis-state__track {
  height: 3px;
  margin-top: 0.625rem;
  overflow: hidden;
  border-radius: 999px;
  background: color-mix(in srgb, var(--color-primary) 15%, transparent);
}

.memory-analysis-state__bar {
  display: block;
  width: 42%;
  height: 100%;
  border-radius: inherit;
  background: var(--color-primary);
  transform: translateX(-110%);
  will-change: transform;
}

@media (prefers-reduced-motion: reduce) {
  .memory-analysis-state__bar {
    width: 55%;
    transform: translateX(0);
    will-change: auto;
  }
}
</style>
