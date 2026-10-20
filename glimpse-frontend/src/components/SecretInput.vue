<script setup lang="ts">
import { ref } from 'vue'
import { EyeIcon, EyeSlashIcon } from '@heroicons/vue/24/outline'

defineOptions({ inheritAttrs: false })

defineProps<{
  modelValue: string
  showLabel: string
  hideLabel: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

// 显隐是每个实例的内部状态：各密钥框各管各的，不做联动。
const visible = ref(false)

const onInput = (event: Event) => {
  emit('update:modelValue', (event.target as HTMLInputElement).value)
}
</script>

<template>
  <div class="relative w-full max-w-[320px]">
    <input
      v-bind="$attrs"
      class="setting-input secret-input"
      :value="modelValue"
      :type="visible ? 'text' : 'password'"
      autocomplete="off"
      @input="onInput"
    />
    <button
      type="button"
      class="absolute right-1 top-1/2 -translate-y-1/2 rounded-md p-1 text-[var(--shell-muted)] transition duration-[160ms] ease-[ease] hover:bg-[var(--shell-control-hover)]"
      :aria-label="visible ? hideLabel : showLabel"
      @click="visible = !visible"
    >
      <EyeSlashIcon v-if="visible" class="h-4 w-4" aria-hidden="true" />
      <EyeIcon v-else class="h-4 w-4" aria-hidden="true" />
    </button>
  </div>
</template>

<style scoped>
/* 右侧为显隐眼睛留位；scoped 属性选择器压过全局 .setting-input 的 padding 简写 */
.secret-input {
  padding-right: 2rem;
}
</style>
