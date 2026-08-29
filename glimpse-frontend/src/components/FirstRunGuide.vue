<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import {
  ArrowRightIcon,
  CameraIcon,
  Cog6ToothIcon,
  MagnifyingGlassIcon,
  SparklesIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline'
import { t } from '@/utils/i18n'

const FOCUSABLE_SELECTOR = [
  'button:not([disabled])',
  '[href]',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (event: 'complete'): void
}>()

const guideItems = [
  {
    icon: CameraIcon,
    titleKey: 'onboarding.captureTitle',
    descriptionKey: 'onboarding.captureDescription',
    shortcut: 'Ctrl + Shift + G',
  },
  {
    icon: SparklesIcon,
    titleKey: 'onboarding.organizeTitle',
    descriptionKey: 'onboarding.organizeDescription',
    shortcut: '',
  },
  {
    icon: MagnifyingGlassIcon,
    titleKey: 'onboarding.searchTitle',
    descriptionKey: 'onboarding.searchDescription',
    shortcut: 'Ctrl + F',
  },
] as const

const dialogPanel = ref<HTMLElement | null>(null)
const completeButton = ref<HTMLButtonElement | null>(null)
let originElement: HTMLElement | null = null
let previousBodyOverflow = ''
let previousHtmlOverflow = ''
let scrollLocked = false

const finish = () => emit('complete')

const focusableElements = () => (
  dialogPanel.value
    ? Array.from(dialogPanel.value.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
    : []
)

const trapFocus = (event: KeyboardEvent) => {
  const focusable = focusableElements()
  if (!focusable.length) {
    event.preventDefault()
    dialogPanel.value?.focus()
    return
  }

  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  const active = document.activeElement
  if (event.shiftKey && (active === first || !dialogPanel.value?.contains(active))) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && active === last) {
    event.preventDefault()
    first.focus()
  }
}

const handleKeydown = (event: KeyboardEvent) => {
  if (!props.open) return

  if (event.key === 'Escape') {
    event.preventDefault()
    event.stopPropagation()
    finish()
  } else if (event.key === 'Tab') {
    trapFocus(event)
  }
}

const lockDocumentScroll = () => {
  if (scrollLocked) return
  previousBodyOverflow = document.body.style.overflow
  previousHtmlOverflow = document.documentElement.style.overflow
  document.body.style.overflow = 'hidden'
  document.documentElement.style.overflow = 'hidden'
  scrollLocked = true
}

const restoreDocumentScroll = () => {
  if (!scrollLocked) return
  document.body.style.overflow = previousBodyOverflow
  document.documentElement.style.overflow = previousHtmlOverflow
  scrollLocked = false
}

watch(
  () => props.open,
  async (open) => {
    if (open) {
      originElement = document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null
      lockDocumentScroll()
      document.addEventListener('keydown', handleKeydown, true)
      await nextTick()
      completeButton.value?.focus({ preventScroll: true })
      return
    }

    document.removeEventListener('keydown', handleKeydown, true)
    restoreDocumentScroll()
    await nextTick()
    if (originElement?.isConnected) {
      originElement.focus({ preventScroll: true })
    }
    originElement = null
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleKeydown, true)
  restoreDocumentScroll()
  if (originElement?.isConnected) originElement.focus({ preventScroll: true })
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-[140] flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-sm sm:p-6"
      role="presentation"
      @mousedown.self="finish"
    >
      <section
        ref="dialogPanel"
        class="max-h-[calc(100vh-2rem)] w-full max-w-3xl overflow-y-auto rounded-2xl border border-[var(--shell-line)] bg-[var(--shell-frame-bg)] shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="first-run-guide-title"
        aria-describedby="first-run-guide-description"
        tabindex="-1"
      >
        <div class="relative overflow-hidden border-b border-[var(--shell-line)] px-6 py-6 sm:px-8 sm:py-7">
          <div class="pointer-events-none absolute -right-12 -top-20 h-48 w-48 rounded-full bg-[var(--color-primary-soft)] opacity-70" aria-hidden="true"></div>
          <div class="relative pr-10">
            <p class="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--color-primary)]">
              {{ t('onboarding.eyebrow') }}
            </p>
            <h1 id="first-run-guide-title" class="mt-2 text-2xl font-semibold tracking-[-0.02em] text-[var(--shell-ink)]">
              {{ t('onboarding.title') }}
            </h1>
            <p id="first-run-guide-description" class="mt-2 max-w-2xl text-sm text-[var(--shell-muted)]">
              {{ t('onboarding.description') }}
            </p>
          </div>

          <button
            type="button"
            class="absolute right-4 top-4 rounded-md p-2 text-[var(--shell-muted)] transition hover:bg-[var(--shell-control-hover)] hover:text-[var(--shell-ink)]"
            :aria-label="t('onboarding.dismiss')"
            @click="finish"
          >
            <XMarkIcon class="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        <div class="p-6 sm:p-8">
          <ol class="grid gap-4 sm:grid-cols-3">
            <li
              v-for="(item, index) in guideItems"
              :key="item.titleKey"
              class="relative rounded-xl border border-[var(--shell-line)] bg-[var(--shell-control-bg)] p-4"
            >
              <span class="absolute right-3.5 top-3 text-xs font-semibold tabular-nums text-[var(--shell-muted)]">
                0{{ index + 1 }}
              </span>
              <div class="flex h-11 w-11 items-center justify-center rounded-lg bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
                <component :is="item.icon" class="h-5 w-5" aria-hidden="true" />
              </div>
              <h2 class="mt-4 text-sm font-semibold text-[var(--shell-ink)]">
                {{ t(item.titleKey) }}
              </h2>
              <p class="mt-1.5 text-sm text-[var(--shell-muted)]">
                {{ t(item.descriptionKey) }}
              </p>
              <kbd
                v-if="item.shortcut"
                class="mt-3 inline-flex rounded-md border border-[var(--shell-line)] bg-[var(--shell-frame-bg)] px-2 py-1 text-xs font-semibold text-[var(--shell-ink)] shadow-sm"
              >
                {{ item.shortcut }}
              </kbd>
            </li>
          </ol>

          <div class="mt-5 flex items-start gap-3 rounded-xl bg-[var(--color-primary-soft)] px-4 py-3.5">
            <Cog6ToothIcon class="mt-0.5 h-5 w-5 flex-none text-[var(--color-primary)]" aria-hidden="true" />
            <p class="text-sm text-[var(--shell-ink)]">
              <span class="font-semibold">{{ t('onboarding.aiTitle') }}</span>
              {{ t('onboarding.aiDescription') }}
            </p>
          </div>

          <div class="mt-6 flex justify-end">
            <button
              ref="completeButton"
              data-testid="first-run-complete"
              type="button"
              class="btn-primary inline-flex h-10 items-center gap-2 px-5"
              @click="finish"
            >
              {{ t('onboarding.start') }}
              <ArrowRightIcon class="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      </section>
    </div>
  </Teleport>
</template>
