<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { HugeiconsIcon } from '@hugeicons/vue'
import { ChevronDownFreeIcons, ClipboardFreeIcons, Refresh01FreeIcons, Tick02FreeIcons } from '@hugeicons/core-free-icons'
import { memoriesApi, type Memory } from '@/api/client'
import { useNotificationStore } from '@/stores/notification'
import { t } from '@/utils/i18n'

const props = withDefaults(
  defineProps<{
    text?: string
    /** 侧栏使用紧凑的块头操作规格。 */
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
    class="ocr-text"
    :class="{ 'ocr-text--compact': compact }"
  >
    <div class="ocr-text__header mb-2.5 flex items-center justify-between gap-3">
      <h3 class="text-sm font-semibold text-[var(--shell-ink)]">{{ t('memory.text') }}</h3>
      <div v-if="text || memoryId" class="relative flex items-center">
        <span
          v-if="reocring"
          class="ocr-text__actions inline-flex items-center gap-1.5 text-sm text-[var(--color-primary)]"
          role="status"
          aria-live="polite"
        >
          <HugeiconsIcon :icon="Refresh01FreeIcons" class="h-4 w-4 flex-none animate-spin" aria-hidden="true" />
          {{ t('action.reRecognizing') }}
        </span>
        <div
          v-else
          class="ocr-text__actions ocr-text__actions--filled inline-flex items-center overflow-hidden rounded-md"
        >
          <button
            v-if="text"
            type="button"
            class="ocr-text__copy ocr-text__copy--text inline-flex h-full items-center gap-2 text-sm transition duration-[160ms] ease-[ease]"
            @click="copyText"
          >
            <HugeiconsIcon :icon="Tick02FreeIcons" v-if="copied" class="h-4 w-4 flex-none text-emerald-600" aria-hidden="true" />
            <HugeiconsIcon :icon="ClipboardFreeIcons" v-else class="h-4 w-4 flex-none" aria-hidden="true" />
            {{ copied ? t('action.copied') : t('action.copyText') }}
          </button>
          <button
            v-if="memoryId"
            ref="menuTrigger"
            type="button"
            class="ocr-text__copy inline-flex h-full w-7 items-center justify-center border-l border-[var(--shell-line)] transition duration-[160ms] ease-[ease]"
            :aria-label="t('action.moreOptions')"
            aria-haspopup="menu"
            :aria-expanded="menuOpen"
            @click.stop="toggleMenu"
          >
            <HugeiconsIcon :icon="ChevronDownFreeIcons" class="h-4 w-4" aria-hidden="true" />
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
              class="ocr-text__menu-item flex w-full items-center gap-2 whitespace-nowrap text-left text-sm transition duration-[160ms] ease-[ease] disabled:opacity-60"
              :disabled="reocring"
              @click="reocr"
            >
              <HugeiconsIcon :icon="Refresh01FreeIcons"
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
      class="ocr-text__body max-h-64 whitespace-pre-wrap text-sm text-[var(--shell-ink)] [overflow-wrap:anywhere]"
      :class="compact ? 'overflow-y-hidden' : 'overflow-y-auto'"
      :tabindex="compact ? 0 : undefined"
      :aria-label="compact ? t('memory.text') : undefined"
    >
      {{ text }}
    </p>
    <p v-else class="text-sm text-[var(--shell-muted)]">{{ t('memory.noRecognizedText') }}</p>
  </section>
</template>

<style scoped>
/* 侧栏只读文字点击获得焦点后才接管滚轮；独立详情页保留默认滚动。 */
.ocr-text--compact .ocr-text__body {
  padding-right: 8px;
  scrollbar-gutter: stable;
  scrollbar-width: thin;
}

.ocr-text--compact .ocr-text__body:focus {
  overflow-y: auto;
}

/* 紧凑形态与摘要/标签块同构平铺：无底色，标题行与正文顶到侧栏内容缘，
   三块的标题、按钮、文字左缘逐边对齐 */
.ocr-text--compact .ocr-text__header {
  min-height: 2rem;
  margin-bottom: 0.25rem;
}

.ocr-text__actions {
  height: var(--control-h-md);
}

/* 侧栏与详情页同饰：整组取控件档实底，文字回到正文色；
   悬停逐段压深一档，深色沿用 .btn-secondary 的既有取值。 */
.ocr-text__actions--filled {
  background: var(--color-surface-control);
  color: var(--color-text);
}

.ocr-text__actions--filled .ocr-text__copy {
  color: var(--color-text);
}

.ocr-text__actions--filled .ocr-text__copy--text {
  padding-inline: 0.9rem;
}

.ocr-text__actions--filled .ocr-text__copy:hover {
  background: var(--color-surface-deep-hover);
}

:root[data-theme='dark'] .ocr-text__actions--filled .ocr-text__copy:hover {
  background: var(--color-surface-deep);
}

/* 更多菜单跟随触发组：面板内衬与菜单项共用控件档实底，
   菜单项为 32px 次级按钮规格并保留自身圆角，悬停再压深一档。 */
.ocr-text__menu {
  padding: 0.25rem;
  /* 四周对称光晕，与分段器滑块同策略；不用向下偏移的投影 */
  background: var(--color-surface-control);
  border: 1px solid var(--shell-line);
  box-shadow: 0 0 16px rgba(0, 0, 0, 0.12);
  transform-origin: top right;
}

.ocr-text__menu-item {
  height: var(--control-h-md);
  padding-inline: 0.9rem;
  color: var(--color-text);
  border-radius: var(--radius-md);
}

.ocr-text__menu-item:hover:not(:disabled) {
  background: var(--color-surface-deep-hover);
}

:root[data-theme='dark'] .ocr-text__menu {
  background: var(--color-surface-hover);
  box-shadow: 0 0 18px rgba(0, 0, 0, 0.45);
}

:root[data-theme='dark'] .ocr-text__menu-item:hover:not(:disabled) {
  background: var(--color-surface-deep);
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
