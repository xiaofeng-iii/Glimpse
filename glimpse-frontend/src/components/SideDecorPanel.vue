<script setup lang="ts">
import { computed } from 'vue'
import { SparklesIcon } from '@heroicons/vue/24/outline'
import { languagePreference, t, type MessageKey } from '@/utils/i18n'

const PHRASE_POOL_SIZE = 5

// 面板为挂载时快照：日期与句子按天轮换，当日之内保持稳定。
const mountedAt = new Date()
const dayOfYear = Math.floor(
  (mountedAt.getTime() - new Date(mountedAt.getFullYear(), 0, 0).getTime()) / 86_400_000,
)

const dayNumber = mountedAt.getDate()
const yearNumber = mountedAt.getFullYear()
const monthLabel = computed(() =>
  mountedAt.toLocaleDateString(languagePreference.value, { month: 'long' }),
)
const weekdayLabel = computed(() =>
  mountedAt.toLocaleDateString(languagePreference.value, { weekday: 'long' }),
)
const phrase = computed(() =>
  t(`decor.phrase${(dayOfYear % PHRASE_POOL_SIZE) + 1}` as MessageKey),
)
</script>

<template>
  <div class="side-decor">
    <div class="side-decor__blob side-decor__blob--one" aria-hidden="true" />
    <div class="side-decor__blob side-decor__blob--two" aria-hidden="true" />
    <div class="side-decor__content">
      <div class="side-decor__date">
        <span class="side-decor__day">{{ dayNumber }}</span>
        <div class="side-decor__date-side">
          <span class="side-decor__month">{{ monthLabel }}</span>
          <span class="side-decor__date-meta">{{ weekdayLabel }} · {{ yearNumber }}</span>
        </div>
      </div>
      <div class="side-decor__divider" aria-hidden="true" />
      <SparklesIcon class="side-decor__spark" aria-hidden="true" />
      <p class="side-decor__phrase">{{ phrase }}</p>
    </div>
  </div>
</template>

<style scoped>
/* 与记忆墙背景一体：自身不带底色，仅以低对比色斑与文字点缀。 */
.side-decor {
  position: relative;
  height: 100%;
}

/* 两个低对比色斑，圆心完整落在面板内：渐变在触边前淡尽，不产生剪裁分界线 */
.side-decor__blob {
  position: absolute;
  border-radius: 999px;
  filter: blur(3px);
  pointer-events: none;
}

.side-decor__blob--one {
  top: 20px;
  right: 16px;
  width: 128px;
  height: 128px;
  background: radial-gradient(
    circle,
    color-mix(in srgb, var(--color-accent) 14%, transparent),
    transparent 70%
  );
}

.side-decor__blob--two {
  bottom: 24px;
  left: 20px;
  width: 148px;
  height: 148px;
  background: radial-gradient(
    circle,
    color-mix(in srgb, var(--color-primary) 12%, transparent),
    transparent 68%
  );
}

.side-decor__content {
  position: relative;
  display: flex;
  height: 100%;
  flex-direction: column;
  justify-content: center;
  padding: 1.75rem 1.5rem;
}

.side-decor__date {
  display: flex;
  align-items: baseline;
  gap: 0.625rem;
}

.side-decor__day {
  font-size: 2.75rem;
  font-weight: 700;
  line-height: 1;
  letter-spacing: -0.02em;
  color: color-mix(in srgb, var(--color-primary) 82%, var(--shell-ink));
}

.side-decor__date-side {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.side-decor__month {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--shell-ink);
}

.side-decor__date-meta {
  font-size: 0.75rem;
  color: var(--shell-muted);
}

.side-decor__divider {
  width: 2.25rem;
  height: 2px;
  margin: 1.25rem 0;
  border-radius: 999px;
  background: color-mix(in srgb, var(--color-primary) 45%, transparent);
}

.side-decor__spark {
  width: 1.125rem;
  height: 1.125rem;
  margin-bottom: 0.5rem;
  color: color-mix(in srgb, var(--color-accent) 75%, transparent);
}

.side-decor__phrase {
  max-width: 17rem;
  font-size: 0.9375rem;
  font-weight: 500;
  line-height: 1.7;
  color: var(--shell-muted);
}
</style>
