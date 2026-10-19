<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  ArrowPathIcon,
  PencilSquareIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline'
import type { Memory } from '@/api/client'
import { useMemoriesStore } from '@/stores/memories'
import { useNotificationStore } from '@/stores/notification'
import { useUnsavedChangesStore } from '@/stores/unsavedChanges'
import { t } from '@/utils/i18n'
import ConfirmDialog from './ConfirmDialog.vue'

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
const editing = ref(false)
const draftTags = ref<string[]>([])
const inputValue = ref('')
const saving = ref(false)
const errorMessage = ref('')
const inputHint = ref('')
const discardDialogOpen = ref(false)
const inputElement = ref<HTMLInputElement | null>(null)
const composing = ref(false)
let discardResolver: ((confirmed: boolean) => void) | null = null
let pendingDiscardPromise: Promise<boolean> | null = null
let unregisterGuard: (() => boolean) | null = null

const currentTagNames = computed(() =>
  (props.memory.tags ?? []).map((tag) => tag.name),
)

const normalizeTagName = (value: string) => value.trim().replace(/\s+/g, ' ')

const sortedNames = (names: string[]) =>
  [...names].map((name) => name.toLowerCase()).sort()

const dirty = computed(() => {
  const draft = sortedNames(draftTags.value)
  const current = sortedNames(currentTagNames.value)
  return (
    draft.length !== current.length
    || draft.some((name, index) => name !== current[index])
  )
})

// 输入框里躺着未回车确认的内容也算“可保存”：保存时会先收下它。
const canSave = computed(() =>
  (dirty.value || Boolean(normalizeTagName(inputValue.value))) && !saving.value,
)

// 已有标签建议：复用标签库现存标签，过滤掉已选，按输入片段收敛。
const suggestions = computed(() => {
  const selected = new Set(draftTags.value.map((name) => name.toLowerCase()))
  const needle = normalizeTagName(inputValue.value).toLowerCase()
  return memoriesStore.tags
    .filter((tag) => !selected.has(tag.name.toLowerCase()))
    .filter((tag) => !needle || tag.name.toLowerCase().includes(needle))
})

watch(
  () => props.memory.id,
  () => {
    editing.value = false
    draftTags.value = currentTagNames.value
    inputValue.value = ''
    errorMessage.value = ''
    inputHint.value = ''
  },
)

// 外部（如其它客户端）改了标签且本地无草稿时，跟随最新值。
watch(
  currentTagNames,
  (names) => {
    if (!editing.value || !dirty.value) {
      draftTags.value = [...names]
    }
  },
)

const startEditing = async () => {
  draftTags.value = [...currentTagNames.value]
  inputValue.value = ''
  errorMessage.value = ''
  inputHint.value = ''
  editing.value = true
  void memoriesStore.loadTags()
  await nextTick()
  inputElement.value?.focus({ preventScroll: true })
}

const cancelEditing = () => {
  draftTags.value = [...currentTagNames.value]
  inputValue.value = ''
  errorMessage.value = ''
  inputHint.value = ''
  editing.value = false
  if (inputElement.value && document.activeElement === inputElement.value) {
    inputElement.value.blur()
  }
}

const addTag = (raw: string) => {
  const name = normalizeTagName(raw)
  inputHint.value = ''
  if (!name) return false
  if (name.length > TAG_NAME_MAX_LENGTH) {
    inputHint.value = t('tags.tooLong')
    return false
  }
  if (draftTags.value.some((tag) => tag.toLowerCase() === name.toLowerCase())) {
    inputHint.value = t('tags.duplicate')
    return false
  }
  if (draftTags.value.length >= TAGS_PER_MEMORY_LIMIT) {
    inputHint.value = t('tags.tooMany')
    return false
  }
  draftTags.value = [...draftTags.value, name]
  inputValue.value = ''
  errorMessage.value = ''
  return true
}

const removeTag = (name: string) => {
  draftTags.value = draftTags.value.filter((tag) => tag !== name)
  inputHint.value = ''
}

const commitPendingInput = () => {
  // 保存前把输入框里尚未回车确认的内容一并收下；非法输入则拦下保存。
  const pending = normalizeTagName(inputValue.value)
  if (!pending) return true
  return addTag(pending)
}

const save = async () => {
  if (saving.value) return
  if (!commitPendingInput()) return
  if (!dirty.value) {
    cancelEditing()
    return
  }

  saving.value = true
  errorMessage.value = ''
  try {
    const memory = await memoriesStore.updateTags(props.memory.id, draftTags.value)
    // 以服务端规范化后的标签为准（去重/大小写合并可能与草稿不同）。
    draftTags.value = (memory?.tags ?? []).map((tag) => tag.name)
    inputValue.value = ''
    editing.value = false
    if (inputElement.value && document.activeElement === inputElement.value) {
      inputElement.value.blur()
    }
    if (memory) emit('saved', memory)
  } catch {
    errorMessage.value = t('tags.saveFailed')
    notifications.show(t('tags.saveFailed'), 'error', 3000)
  } finally {
    saving.value = false
  }
}

const handleInputKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape') {
    event.preventDefault()
    cancelEditing()
    return
  }
  // 中文输入法组词期间的 Enter/Backspace 是在编辑拼音串，不触发标签操作。
  if (composing.value || event.isComposing) return

  if (event.key === 'Enter') {
    event.preventDefault()
    if (event.ctrlKey || event.metaKey) {
      void save()
      return
    }
    addTag(inputValue.value)
    return
  }

  // 输入为空时的 Backspace 删除最后一个草稿标签。
  if (event.key === 'Backspace' && !inputValue.value && draftTags.value.length) {
    removeTag(draftTags.value[draftTags.value.length - 1])
  }
}

const resolveDiscard = (confirmed: boolean) => {
  discardDialogOpen.value = false
  if (confirmed) cancelEditing()
  discardResolver?.(confirmed)
  discardResolver = null
  pendingDiscardPromise = null
}

const canLeave = async () => {
  if (!editing.value || !dirty.value) return true
  if (pendingDiscardPromise) return pendingDiscardPromise
  discardDialogOpen.value = true
  pendingDiscardPromise = new Promise<boolean>((resolve) => {
    discardResolver = resolve
  })
  return pendingDiscardPromise
}

onMounted(() => {
  unregisterGuard = unsavedChanges.register(canLeave)
})

onBeforeUnmount(() => {
  unregisterGuard?.()
  discardResolver?.(false)
})

defineExpose({
  canLeave,
  isDirty: dirty,
})
</script>

<template>
  <section class="tags-editor" :class="{ 'tags-editor--compact': compact }" :aria-label="t('tags.title')">
    <div class="tags-editor__header mb-2.5 flex min-h-8 items-center justify-between gap-3">
      <h3 class="flex-none text-sm font-semibold text-[var(--shell-ink)]">{{ t('tags.title') }}</h3>
      <button
        v-if="!editing"
        type="button"
        class="tags-editor__edit-action inline-flex h-8 items-center gap-1.5 rounded-[var(--radius-md)] px-3 text-sm font-normal text-[var(--shell-muted)] transition duration-[160ms] ease-[ease] hover:bg-[var(--shell-control-hover)] hover:text-[var(--shell-ink)]"
        @click="startEditing"
      >
        <PencilSquareIcon class="h-3.5 w-3.5 flex-none" aria-hidden="true" />
        {{ t('tags.edit') }}
      </button>
      <div v-else class="tags-editor__edit-actions flex flex-none items-center gap-2">
        <button
          type="button"
          class="tags-editor__edit-action btn-secondary !h-8 !min-h-8 px-2.5 text-sm"
          :disabled="saving"
          @click="cancelEditing"
        >
          {{ t('action.cancel') }}
        </button>
        <button
          type="button"
          class="tags-editor__edit-action btn-primary !h-8 !min-h-8 gap-1.5 px-3 text-sm"
          :disabled="!canSave"
          @click="save"
        >
          <ArrowPathIcon v-if="saving" class="h-4 w-4 flex-none animate-spin" aria-hidden="true" />
          {{ saving ? t('tags.saving') : t('tags.save') }}
        </button>
      </div>
    </div>

    <div v-if="!editing" class="tags-editor__readonly" data-testid="tags-readonly">
      <div v-if="currentTagNames.length" class="tags-editor__chips">
        <span
          v-for="name in currentTagNames"
          :key="name"
          class="tags-editor__chip"
        >{{ name }}</span>
      </div>
      <p v-else class="tags-editor__empty text-sm">{{ t('tags.empty') }}</p>
    </div>

    <div v-else class="tags-editor__editing">
      <div class="tags-editor__input-row">
        <div v-if="draftTags.length" class="tags-editor__chips">
          <span
            v-for="name in draftTags"
            :key="name"
            class="tags-editor__chip tags-editor__chip--editable"
          >
            <span class="tags-editor__chip-text">{{ name }}</span>
            <button
              type="button"
              class="tags-editor__chip-remove"
              :aria-label="`${t('tags.removeTag')} ${name}`"
              :disabled="saving"
              @click="removeTag(name)"
            >
              <XMarkIcon class="h-3 w-3" aria-hidden="true" />
            </button>
          </span>
        </div>
        <input
          ref="inputElement"
          v-model="inputValue"
          type="text"
          class="tags-editor__input"
          :placeholder="t('tags.placeholder')"
          :aria-label="t('tags.placeholder')"
          :disabled="saving"
          :maxlength="TAG_NAME_MAX_LENGTH * 2"
          @keydown="handleInputKeydown"
          @compositionstart="composing = true"
          @compositionend="composing = false"
        />
      </div>

      <p
        v-if="inputHint || errorMessage"
        class="tags-editor__feedback mt-1.5 text-xs text-red-600"
      >
        {{ inputHint || errorMessage }}
      </p>

      <div v-if="suggestions.length" class="tags-editor__suggestions mt-2">
        <p class="tags-editor__suggestions-label text-xs text-[var(--shell-muted)]">
          {{ t('tags.suggestions') }}
        </p>
        <div class="tags-editor__suggestions-list">
          <button
            v-for="tag in suggestions"
            :key="tag.id"
            type="button"
            class="tags-editor__suggestion"
            :disabled="saving"
            @click="addTag(tag.name)"
          >
            {{ tag.name }}
          </button>
        </div>
      </div>
      <p
        v-else-if="normalizeTagName(inputValue)"
        class="tags-editor__suggestions-label mt-2 text-xs text-[var(--shell-muted)]"
      >
        {{ t('tags.noMatch') }}
      </p>
    </div>

    <ConfirmDialog
      id="discard-tags"
      :open="discardDialogOpen"
      :title="t('tags.discardTitle')"
      :description="t('tags.discardDescription')"
      :confirm-label="t('tags.discard')"
      :cancel-label="t('tags.keepEditing')"
      destructive
      @confirm="resolveDiscard(true)"
      @cancel="resolveDiscard(false)"
    />
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
  background: var(--color-surface-subtle);
  color: var(--shell-ink);
  font-size: 0.75rem;
  line-height: 1.25rem;
}

.tags-editor__chip-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tags-editor__chip-remove {
  display: inline-flex;
  width: 1rem;
  height: 1rem;
  flex: none;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 0;
  border-radius: var(--radius-sm);
  color: var(--shell-muted);
  background: transparent;
  cursor: pointer;
  transition: background-color 160ms ease, color 160ms ease;
}

/* chip 本体是 surface-subtle 灰底：hover 走灰底档（224），暗色用 token 覆盖 */
.tags-editor__chip-remove:hover {
  color: var(--shell-ink);
  background: rgb(224, 228, 237);
}

:root[data-theme='dark'] .tags-editor__chip-remove:hover {
  background: var(--color-surface-hover);
}

.tags-editor__empty {
  margin: 0;
  color: var(--shell-muted);
}

.tags-editor__input-row {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 0.5rem;
}

.tags-editor__input {
  width: 100%;
  height: var(--control-h-md);
  min-height: var(--control-h-md);
  padding: 0 0.75rem;
  border: 1px solid var(--shell-line);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  color: var(--shell-ink);
  font-size: 0.875rem;
  outline: none;
  transition: border-color 160ms ease;
}

.tags-editor__input:focus {
  border-color: var(--color-focus);
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
  background: var(--color-surface-subtle);
  color: var(--shell-muted);
  cursor: pointer;
  font-size: 0.75rem;
  line-height: 1.25rem;
  transition: background-color 160ms ease, color 160ms ease;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 建议按钮同 chip：灰底控件 hover 走 224 档 */
.tags-editor__suggestion:hover {
  background: rgb(224, 228, 237);
  color: var(--shell-ink);
}

:root[data-theme='dark'] .tags-editor__suggestion:hover {
  background: var(--color-surface-hover);
}

.tags-editor__feedback {
  margin-bottom: 0;
}

/* 侧栏紧凑形态：与摘要/识别文本块同构平铺，标题与 chips 顶到侧栏内容缘；
   块头行内操作降 28px 档。 */
.tags-editor--compact .tags-editor__header {
  margin-bottom: 0.375rem;
}

.tags-editor--compact .tags-editor__edit-action {
  height: 1.75rem;
  min-height: 1.75rem;
  padding-inline: 0.625rem;
}
</style>
