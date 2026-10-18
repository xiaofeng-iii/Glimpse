<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import {
  ArrowPathIcon,
  CheckIcon,
  ChevronDownIcon,
  ClipboardDocumentIcon,
} from '@heroicons/vue/24/outline'
import { memoriesApi, type Memory } from '@/api/client'
import { useNotificationStore } from '@/stores/notification'
import { t } from '@/utils/i18n'

const props = withDefaults(
  defineProps<{
    text?: string
    /** 侧栏内嵌形态：去描边、subtle 底，与摘要块同饰；详情页保持白底线框 */
    compact?: boolean
    memoryId?: string
  }>(),
  { compact: false },
)

const emit = defineEmits<{
  (event: 'updated', memory: Memory): void
}>()

const notifications = useNotificationStore()
const copied = ref(false)
const menuOpen = ref(false)
const reocring = ref(false)
const menuTrigger = ref<HTMLElement | null>(null)
const menuPanel = ref<HTMLElement | null>(null)
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

const toggleMenu = () => {
  if (!props.memoryId || reocring.value) return
  menuOpen.value = !menuOpen.value
}

const closeMenu = () => {
  menuOpen.value = false
}

const reocr = async () => {
  if (!props.memoryId || reocring.value) return
  reocring.value = true
  closeMenu()
  try {
    const updated = await memoriesApi.reocr(props.memoryId)
    emit('updated', updated)
    notifications.show(t('message.ocrReocrDone'), 'success', 1800)
  } catch (error) {
    const status = (error as { response?: { status?: number } })?.response?.status
    notifications.show(
      t(status === 409 ? 'message.maintenanceConflict' : 'message.ocrReocrFailed'),
      'error',
      2800,
    )
  } finally {
    reocring.value = false
  }
}

const handlePointerDown = (event: PointerEvent) => {
  if (!menuOpen.value) return
  const target = event.target as Node | null
  if (menuPanel.value?.contains(target) || menuTrigger.value?.contains(target)) return
  closeMenu()
}

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && menuOpen.value) closeMenu()
}

onMounted(() => {
  document.addEventListener('pointerdown', handlePointerDown)
  document.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', handlePointerDown)
  document.removeEventListener('keydown', handleKeydown)
  if (copiedTimer) window.clearTimeout(copiedTimer)
})
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
      <div v-if="text || memoryId" class="relative flex items-center">
        <span
          v-if="reocring"
          class="inline-flex h-7 items-center gap-1.5 text-sm text-[var(--color-primary)]"
          role="status"
          aria-live="polite"
        >
          <ArrowPathIcon class="h-4 w-4 flex-none animate-spin" aria-hidden="true" />
          {{ t('action.reRecognizing') }}
        </span>
        <div v-else class="inline-flex h-7 items-center overflow-hidden rounded-md">
          <button
            v-if="text"
            type="button"
            class="ocr-text__copy inline-flex h-full items-center gap-2 px-2 text-sm text-[var(--shell-muted)] transition duration-[160ms] ease-[ease] hover:bg-[var(--shell-control-hover)]"
            @click="copyText"
          >
            <CheckIcon v-if="copied" class="h-4 w-4 flex-none text-emerald-600" aria-hidden="true" />
            <ClipboardDocumentIcon v-else class="h-4 w-4 flex-none" aria-hidden="true" />
            {{ copied ? t('action.copied') : t('action.copyText') }}
          </button>
          <button
            v-if="memoryId"
            ref="menuTrigger"
            type="button"
            class="ocr-text__copy inline-flex h-full w-7 items-center justify-center border-l border-[var(--shell-line)] text-[var(--shell-muted)] transition duration-[160ms] ease-[ease] hover:bg-[var(--shell-control-hover)]"
            :aria-label="t('action.moreOptions')"
            aria-haspopup="menu"
            :aria-expanded="menuOpen"
            @click.stop="toggleMenu"
          >
            <ChevronDownIcon class="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
        <Transition name="ocr-menu">
          <div
            v-if="menuOpen"
            ref="menuPanel"
            role="menu"
            class="ocr-text__menu absolute right-0 top-full z-[var(--z-dropdown)] mt-1 w-full min-w-max overflow-hidden rounded-md"
          >
            <button
              type="button"
              role="menuitem"
              class="ocr-text__menu-item flex h-7 w-full items-center gap-2 whitespace-nowrap px-2 text-left text-sm text-[var(--shell-ink)] transition duration-[160ms] ease-[ease] disabled:opacity-60"
              :disabled="reocring"
              @click="reocr"
            >
              <ArrowPathIcon
                class="h-4 w-4 flex-none"
                :class="{ 'animate-spin': reocring }"
                aria-hidden="true"
              />
              {{ reocring ? t('action.reRecognizing') : t('action.reRecognize') }}
            </button>
          </div>
        </Transition>
      </div>
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

.ocr-text__menu {
  /* 四周对称光晕，与分段器滑块同策略；不用向下偏移的投影 */
  background: var(--color-surface-raised);
  box-shadow: 0 0 16px rgba(0, 0, 0, 0.12);
  transform-origin: top right;
}

.ocr-text__menu-item:hover:not(:disabled) {
  /* 浅色弹出项采用灰底按钮同款的最灰档 */
  background: rgb(224, 228, 237);
}

/* 弹出菜单不描边、不额外加阴影：深色下把菜单表面提高一档建立边界。 */
:root[data-theme='dark'] .ocr-text__menu {
  background: var(--color-surface-hover);
  box-shadow: 0 0 18px rgba(0, 0, 0, 0.45);
}

:root[data-theme='dark'] .ocr-text__menu-item:hover:not(:disabled) {
  background: var(--color-surface-raised);
}

.ocr-menu-enter-active,
.ocr-menu-leave-active {
  /* 与设置页 AppSelect 的 app-select-in 保持同一组参数 */
  transition: opacity 140ms ease-out, transform 140ms ease-out;
}

.ocr-menu-enter-from,
.ocr-menu-leave-to {
  opacity: 0;
  transform: translateY(-3px) scale(0.985);
}

@media (prefers-reduced-motion: reduce) {
  .ocr-menu-enter-active,
  .ocr-menu-leave-active {
    transition: none;
  }

  .ocr-menu-enter-from,
  .ocr-menu-leave-to {
    transform: none;
  }
}
</style>
