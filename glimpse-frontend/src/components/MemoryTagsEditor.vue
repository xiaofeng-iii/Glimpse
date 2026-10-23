<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  PlusIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline'
import type { Memory } from '@/api/client'
import { useMemoriesStore } from '@/stores/memories'
import { useNotificationStore } from '@/stores/notification'
import { useUnsavedChangesStore } from '@/stores/unsavedChanges'
import { t } from '@/utils/i18n'

const TAG_NAME_MAX_LENGTH = 24
const TAGS_PER_MEMORY_LIMIT = 10

const props = withDefaults(defineProps<{
  memory: Memory
  compact?: boolean
}>(), {
  compact: false,
})

const emit = defineEmits<{
  (event: 'saved', memory: Memory): void
}>()

const memoriesStore = useMemoriesStore()
const notifications = useNotificationStore()
const unsavedChanges = useUnsavedChangesStore()

// 展示与提交都以 localNames 为准：操作先落到本地，再经串行保存链整体替换到服务端。
const localNames = ref<string[]>([])
const inputValue = ref('')
// 行尾添加入口：收起时是「＋」小方块，激活后就地展开行内输入框。
const inputActive = ref(false)
const inputHint = ref('')
const inputElement = ref<HTMLInputElement | null>(null)
const composing = ref(false)
// 点击 chip 进入「待删」态：该 chip 显示 ×，再点自身取消，点其他 chip 转移。
const armedTag = ref<string | null>(null)
// 拖动排序：dragover 时实时重排 localNames，drop/dragend 时按新顺序整体保存。
const draggingName = ref<string | null>(null)
let orderDirty = false
let unregisterGuard: (() => boolean) | null = null

const currentTagNames = computed(() =>
  (props.memory.tags ?? []).map((tag) => tag.name),
)

const normalizeTagName = (value: string) => value.trim().replace(/\s+/g, ' ')

// 已有标签建议：复用标签库现存标签，过滤掉已选，按输入片段收敛。
const suggestions = computed(() => {
  const selected = new Set(localNames.value.map((name) => name.toLowerCase()))
  const needle = normalizeTagName(inputValue.value).toLowerCase()
  return memoriesStore.tags
    .filter((tag) => !selected.has(tag.name.toLowerCase()))
    .filter((tag) => !needle || tag.name.toLowerCase().includes(needle))
})

watch(
  () => props.memory.id,
  () => {
    localNames.value = currentTagNames.value
    inputActive.value = false
    inputValue.value = ''
    inputHint.value = ''
    armedTag.value = null
    draggingName.value = null
  },
  { immediate: true },
)

// 外部（如其它客户端）更新标签且本地无在途保存时跟随最新值。
watch(
  currentTagNames,
  (names) => {
    if (pendingSaves === 0) localNames.value = [...names]
  },
)

const activateInput = async () => {
  inputActive.value = true
  inputHint.value = ''
  void memoriesStore.loadTags()
  await nextTick()
  inputElement.value?.focus({ preventScroll: true })
}

const collapseInput = () => {
  inputActive.value = false
  inputValue.value = ''
  inputHint.value = ''
}

// 串行保存链：每次操作入队时快照（目标记忆 + 完整名单），逐个执行，
// 连续快速操作不会互相覆盖，响应只采纳最新一次的规范化结果。
let saveChain: Promise<void> = Promise.resolve()
let pendingSaves = 0
let saveSeq = 0

const persist = () => {
  const memoryId = props.memory.id
  const names = [...localNames.value]
  const seq = ++saveSeq
  pendingSaves += 1
  saveChain = saveChain.then(async () => {
    try {
      const memory = await memoriesStore.updateTags(memoryId, names)
      if (seq === saveSeq && memory) {
        localNames.value = (memory.tags ?? []).map((tag) => tag.name)
        emit('saved', memory)
      }
    } catch {
      notifications.show(t('tags.saveFailed'), 'error', 3000)
      if (props.memory.id === memoryId) {
        // 回退到服务端已知状态；在途的后续操作会携带最新本地名单重写。
        localNames.value = [...currentTagNames.value]
      }
    } finally {
      pendingSaves -= 1
    }
  })
}

const addTag = (raw: string) => {
  const name = normalizeTagName(raw)
  inputHint.value = ''
  if (!name) return false
  if (name.length > TAG_NAME_MAX_LENGTH) {
    inputHint.value = t('tags.tooLong')
    return false
  }
  if (localNames.value.some((tag) => tag.toLowerCase() === name.toLowerCase())) {
    inputHint.value = t('tags.duplicate')
    return false
  }
  if (localNames.value.length >= TAGS_PER_MEMORY_LIMIT) {
    inputHint.value = t('tags.tooMany')
    return false
  }
  localNames.value = [...localNames.value, name]
  inputValue.value = ''
  persist()
  return true
}

const removeTag = (name: string) => {
  localNames.value = localNames.value.filter((tag) => tag !== name)
  if (armedTag.value === name) armedTag.value = null
  inputHint.value = ''
  persist()
}

const toggleArm = (name: string) => {
  armedTag.value = armedTag.value === name ? null : name
}

const finishDrag = () => {
  if (draggingName.value && orderDirty) persist()
  draggingName.value = null
  orderDirty = false
}

// 拖动排序走 pointer 事件自实现，不用 HTML5 拖拽：WebView2 中原生拖拽的
// dragover 事件链不稳定，光标反馈（禁止符）和实时换位都会闪烁。
// 按下后移动超过阈值才开始拖；未超阈值视为点击（交给 click 出 ×）。
const chipsElement = ref<HTMLElement | null>(null)
const DRAG_THRESHOLD_PX = 4
let dragPointer: { name: string; startX: number; startY: number; active: boolean } | null = null
let suppressNextClick = false

// 槽区模型：分界线在每相邻两个 chip 的间隙中线（行首/行尾延伸到 chip 外缘），
// 每个 chip 占据自己前后两条中线之间的区域；光标落在哪个槽区，被拖标签就去哪个
// 槽位。几何包含被拖 chip 本身，换位前后分界线不动，来回拖动判定对称、无回差。
const reorderToPoint = (x: number, y: number) => {
  const container = chipsElement.value
  const dragging = draggingName.value
  if (!container || !dragging) return
  const chips = Array.from(container.querySelectorAll<HTMLElement>('.tags-editor__chip'))
    .map((chip) => ({ name: chip.dataset.tagName ?? '', rect: chip.getBoundingClientRect() }))
  if (!chips.length) return

  // 分行（flex-wrap），按光标 y 就近取行
  const rows: Array<typeof chips> = []
  for (const chip of chips) {
    const row = rows.find((candidate) => candidate[0].rect.top === chip.rect.top)
    if (row) row.push(chip)
    else rows.push([chip])
  }
  rows.sort((a, b) => a[0].rect.top - b[0].rect.top)
  for (const row of rows) row.sort((a, b) => a.rect.left - b.rect.left)
  let bestRow = rows[0]
  let bestDistance = Infinity
  for (const row of rows) {
    const { top, bottom } = row[0].rect
    const distance = y < top ? top - y : y > bottom ? y - bottom : 0
    if (distance < bestDistance) {
      bestDistance = distance
      bestRow = row
    }
  }

  const boundaries = [
    bestRow[0].rect.left,
    ...bestRow.slice(1).map((chip, index) => (bestRow[index].rect.right + chip.rect.left) / 2),
    bestRow[bestRow.length - 1].rect.right,
  ]
  const draggedInRow = bestRow.some((chip) => chip.name === dragging)
  const othersInRow = bestRow.length - (draggedInRow ? 1 : 0)
  const crossed = boundaries.filter((boundary) => x >= boundary).length
  const rowSlot = Math.min(Math.max(crossed - 1, 0), othersInRow)

  // 行内槽位换算成全列表下标：本行之前各行贡献的（不含被拖 chip 的）chip 数
  let rowStart = 0
  for (const row of rows) {
    if (row === bestRow) break
    rowStart += row.length - (row.some((chip) => chip.name === dragging) ? 1 : 0)
  }

  const names = chips.map((chip) => chip.name).filter((name) => name !== dragging)
  names.splice(rowStart + rowSlot, 0, dragging)
  if (names.some((tag, index) => tag !== localNames.value[index])) {
    localNames.value = names
    orderDirty = true
  }
}

const handleChipPointerDown = (name: string, event: PointerEvent) => {
  if (event.button !== 0) return
  dragPointer = { name, startX: event.clientX, startY: event.clientY, active: false }
  window.addEventListener('pointermove', handleWindowPointerMove, true)
  window.addEventListener('pointerup', handleWindowPointerUp, true)
  window.addEventListener('pointercancel', handleWindowPointerUp, true)
}

const handleWindowPointerMove = (event: PointerEvent) => {
  const drag = dragPointer
  if (!drag) return
  if (!drag.active) {
    const moved = Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY)
    if (moved < DRAG_THRESHOLD_PX) return
    drag.active = true
    draggingName.value = drag.name
    orderDirty = false
    armedTag.value = null
  }
  reorderToPoint(event.clientX, event.clientY)
}

const handleWindowPointerUp = () => {
  window.removeEventListener('pointermove', handleWindowPointerMove, true)
  window.removeEventListener('pointerup', handleWindowPointerUp, true)
  window.removeEventListener('pointercancel', handleWindowPointerUp, true)
  const drag = dragPointer
  dragPointer = null
  if (!drag?.active) return
  // 拖完松手会紧跟着触发 click，吞掉这一次，避免误触 × 的开关。
  suppressNextClick = true
  finishDrag()
}

const handleChipClick = (name: string) => {
  if (suppressNextClick) {
    suppressNextClick = false
    return
  }
  toggleArm(name)
}

// × 只在「待删」chip 上停留：点到别处（含其他 chip、面板空白）即收起。
const disarmOnOutsidePointerDown = (event: PointerEvent) => {
  if (!armedTag.value) return
  const target = event.target
  const chip = target instanceof Element ? target.closest<HTMLElement>('.tags-editor__chip') : null
  if (chip?.dataset.tagName === armedTag.value) return
  armedTag.value = null
}

// 点击空白（失焦）：有未确认输入则自动提交，空输入则收起；非法输入保留待改。
const handleInputBlur = () => {
  if (!inputActive.value) return
  const pending = normalizeTagName(inputValue.value)
  if (!pending) {
    collapseInput()
    return
  }
  if (addTag(pending)) collapseInput()
}

const handleInputKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape') {
    // Esc = 明确放弃：丢弃未确认输入并收起，不提交。
    event.preventDefault()
    collapseInput()
    return
  }
  // 中文输入法组词期间的 Enter/Backspace 是在编辑拼音串，不触发标签操作。
  if (composing.value || event.isComposing) return

  if (event.key === 'Enter') {
    event.preventDefault()
    // 回车保存并收起输入框，不连续进入下一个标签的编辑。
    if (addTag(inputValue.value)) collapseInput()
    return
  }

  // 输入为空时的 Backspace 删除最后一个标签。
  if (event.key === 'Backspace' && !inputValue.value && localNames.value.length) {
    removeTag(localNames.value[localNames.value.length - 1])
  }
}

// 离开前把未确认输入按失焦同款语义收尾（有效即提交），不存在被丢弃的草稿。
const canLeave = async () => {
  if (inputActive.value) {
    const pending = normalizeTagName(inputValue.value)
    if (pending) addTag(pending)
    collapseInput()
  }
  return true
}

onMounted(() => {
  unregisterGuard = unsavedChanges.register(canLeave)
  document.addEventListener('pointerdown', disarmOnOutsidePointerDown, true)
})

onBeforeUnmount(() => {
  unregisterGuard?.()
  document.removeEventListener('pointerdown', disarmOnOutsidePointerDown, true)
})

defineExpose({
  canLeave,
})
</script>

<template>
  <section class="tags-editor" :class="{ 'tags-editor--compact': compact }" :aria-label="t('tags.title')">
    <div class="tags-editor__header mb-2.5 flex min-h-8 items-center justify-between gap-3">
      <h3 class="flex-none text-sm font-semibold text-[var(--shell-ink)]">{{ t('tags.title') }}</h3>
    </div>

    <!-- 直接操作模型：点击 chip 出 × 删除、拖动 chip 排序，行尾「＋」/输入框即点即加，无显式保存 -->
    <div
      ref="chipsElement"
      class="tags-editor__chips"
      data-testid="tags-chips"
    >
      <span
        v-for="name in localNames"
        :key="name"
        class="tags-editor__chip"
        :class="{ 'tags-editor__chip--dragging': draggingName === name }"
        :data-tag-name="name"
        @pointerdown="handleChipPointerDown(name, $event)"
        @click="handleChipClick(name)"
      >
        <span class="tags-editor__chip-text">{{ name }}</span>
        <button
          v-if="armedTag === name"
          type="button"
          class="tags-editor__chip-remove"
          :aria-label="t('tags.deleteTag')"
          @click.stop="removeTag(name)"
          @pointerdown.stop
        >
          <XMarkIcon class="h-3 w-3" aria-hidden="true" />
        </button>
      </span>
      <input
        v-if="inputActive"
        ref="inputElement"
        v-model="inputValue"
        type="text"
        class="tags-editor__input"
        :aria-label="t('tags.placeholder')"
        :maxlength="TAG_NAME_MAX_LENGTH * 2"
        @keydown="handleInputKeydown"
        @blur="handleInputBlur"
        @compositionstart="composing = true"
        @compositionend="composing = false"
      />
      <button
        v-else
        v-hint-tooltip="t('tags.add')"
        type="button"
        class="tags-editor__add"
        :aria-label="t('tags.add')"
        @click="activateInput"
      >
        <PlusIcon class="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    </div>

    <p
      v-if="inputHint"
      class="tags-editor__feedback mt-1.5 text-xs text-red-600"
    >
      {{ inputHint }}
    </p>

    <div v-if="inputActive && suggestions.length" class="tags-editor__suggestions mt-2">
      <p class="tags-editor__suggestions-label text-xs text-[var(--shell-muted)]">
        {{ t('tags.suggestions') }}
      </p>
      <div class="tags-editor__suggestions-list">
        <button
          v-for="tag in suggestions"
          :key="tag.id"
          type="button"
          class="tags-editor__suggestion"
          @mousedown.prevent
          @click="addTag(tag.name)"
        >
          {{ tag.name }}
        </button>
      </div>
    </div>
    <p
      v-else-if="inputActive && normalizeTagName(inputValue)"
      class="tags-editor__suggestions-label mt-2 text-xs text-[var(--shell-muted)]"
    >
      {{ t('tags.noMatch') }}
    </p>
  </section>
</template>

<style scoped>
.tags-editor__chips {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  gap: 0.375rem;
}

.tags-editor__chip {
  display: inline-flex;
  max-width: 100%;
  align-items: center;
  gap: 0.25rem;
  padding: 0.125rem 0.5rem;
  border-radius: var(--radius-sm);
  background: var(--color-surface-control);
  color: var(--shell-ink);
  font-size: 0.75rem;
  line-height: 1.25rem;
  cursor: default;
}

.tags-editor__chip--dragging {
  opacity: 0.4;
}

.tags-editor__chip-remove {
  display: inline-flex;
  flex: none;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--shell-muted);
  cursor: default;
  transition: color 160ms ease;
}

.tags-editor__chip-remove:hover {
  color: var(--color-danger);
}

.tags-editor__chip-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 行内输入：与 chips 同排同高（24px）；基线宽 4 个中文字符，
   随内容弹性增长（field-sizing），上限不超出所在行 */
.tags-editor__input {
  min-width: calc(4em + 1rem + 2px);
  max-width: 100%;
  height: 1.5rem;
  min-height: 1.5rem;
  padding: 0 0.5rem;
  border: 1px solid var(--shell-line);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--shell-ink);
  font-size: 0.75rem;
  line-height: 1.25rem;
  outline: none;
  field-sizing: content;
  transition: border-color 160ms ease;
}

.tags-editor__input:focus {
  border-color: var(--color-focus);
}

/* 行尾添加入口：与 chip 同高同饰的圆角小方块，收起态即添加功能的锚点 */
.tags-editor__add {
  display: inline-flex;
  width: 1.5rem;
  height: 1.5rem;
  flex: none;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 0;
  border-radius: var(--radius-sm);
  background: var(--color-surface-control);
  color: var(--shell-muted);
  cursor: pointer;
  transition: background-color 160ms ease, color 160ms ease;
}

.tags-editor__add:hover {
  background: var(--color-surface-deep);
  color: var(--shell-ink);
}

:root[data-theme='dark'] .tags-editor__add:hover {
  background: var(--color-surface-deep);
}

.tags-editor__add:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 1px;
}

.tags-editor__suggestions-list {
  display: flex;
  min-width: 0;
  max-height: 4.5rem;
  flex-wrap: wrap;
  gap: 0.375rem;
  margin-top: 0.375rem;
  overflow-y: auto;
}

.tags-editor__suggestion {
  display: inline-flex;
  max-width: 100%;
  align-items: center;
  padding: 0.125rem 0.5rem;
  border: 0;
  border-radius: var(--radius-sm);
  background: var(--color-surface-control);
  color: var(--shell-muted);
  cursor: pointer;
  font-size: 0.75rem;
  line-height: 1.25rem;
  transition: background-color 160ms ease, color 160ms ease;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 建议按钮同 chip：静息控件档，hover 压到最深档 */
.tags-editor__suggestion:hover {
  background: var(--color-surface-deep);
  color: var(--shell-ink);
}

:root[data-theme='dark'] .tags-editor__suggestion:hover {
  background: var(--color-surface-deep);
}

.tags-editor__feedback {
  margin-bottom: 0;
}

/* 侧栏紧凑形态：与摘要/识别文本块同构平铺，标题与 chips 顶到侧栏内容缘。 */
.tags-editor--compact .tags-editor__header {
  margin-bottom: 0.25rem;
}
</style>
