<script setup lang="ts">
import { computed, watch } from 'vue'

const props = withDefaults(defineProps<{
  open: boolean
  images: string[]
  startIndex?: number
}>(), {
  startIndex: 0,
})

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'update:startIndex', value: number): void
}>()

watch(
  () => props.startIndex,
  (value) => {
    if (value < 0 || value >= props.images.length) {
      emit('update:startIndex', 0)
    }
  },
)

const currentImage = computed(() => props.images[props.startIndex] || '')
const hasMultiple = computed(() => props.images.length > 1)

const showPrevious = () => {
  if (!props.images.length) {
    return
  }
  emit('update:startIndex', (props.startIndex - 1 + props.images.length) % props.images.length)
}

const showNext = () => {
  if (!props.images.length) {
    return
  }
  emit('update:startIndex', (props.startIndex + 1) % props.images.length)
}
</script>

<template>
  <teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/72 p-6 backdrop-blur-sm"
      @click.self="emit('close')"
    >
      <button
        class="absolute right-6 top-6 rounded-full bg-white/14 p-3 text-white transition hover:bg-white/22"
        @click="emit('close')"
      >
        <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>

      <button
        v-if="hasMultiple"
        class="absolute left-6 top-1/2 -translate-y-1/2 rounded-full bg-white/14 p-3 text-white transition hover:bg-white/22"
        @click.stop="showPrevious"
      >
        <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
        </svg>
      </button>

      <img
        v-if="currentImage"
        :src="currentImage"
        class="max-h-[85vh] max-w-[88vw] rounded-3xl border border-white/12 bg-white/8 object-contain shadow-2xl"
        alt="记忆图片预览"
      />

      <button
        v-if="hasMultiple"
        class="absolute right-6 top-1/2 -translate-y-1/2 rounded-full bg-white/14 p-3 text-white transition hover:bg-white/22"
        @click.stop="showNext"
      >
        <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
        </svg>
      </button>
    </div>
  </teleport>
</template>
