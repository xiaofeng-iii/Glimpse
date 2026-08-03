<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { PhotoIcon } from '@heroicons/vue/24/outline'
import type { Memory } from '@/api/client'
import { useImagePreviewStore } from '@/stores/imagePreview'
import { getMemoryImageUrls } from '@/utils/memory-images'
import { t } from '@/utils/i18n'

const props = withDefaults(defineProps<{
  memory: Memory
  compact?: boolean
}>(), {
  compact: false,
})

const imagePreview = useImagePreviewStore()
const failedImages = ref<Record<string, boolean>>({})
const activeIndex = ref(0)
const images = computed(() => getMemoryImageUrls(props.memory))
const activeImage = computed(() => images.value[activeIndex.value] ?? '')

watch(
  () => props.memory.id,
  () => {
    activeIndex.value = 0
    failedImages.value = {}
  },
)

const openPreview = (origin?: HTMLElement | null) => {
  if (!images.value.length) return
  imagePreview.open(images.value, activeIndex.value, origin)
}

const handleImageKeydown = (event: KeyboardEvent) => {
  if (event.key !== 'Enter' && event.key !== ' ') return
  event.preventDefault()
  openPreview(event.currentTarget as HTMLElement)
}

const markImageError = (url: string) => {
  failedImages.value = { ...failedImages.value, [url]: true }
}
</script>

<template>
  <section>
    <div
      class="group relative flex w-full items-center justify-center overflow-hidden rounded-2xl border border-[var(--shell-line)] bg-slate-100/70 outline-none transition focus-visible:ring-2 focus-visible:ring-blue-500"
      :class="compact ? 'h-64' : 'h-[min(54vh,560px)] min-h-80'"
      role="button"
      tabindex="0"
      :aria-label="t('preview.hint')"
      @dblclick="openPreview($event.currentTarget as HTMLElement)"
      @keydown="handleImageKeydown"
    >
      <img
        v-if="activeImage && !failedImages[activeImage]"
        :src="activeImage"
        :alt="memory.ai_summary"
        class="object-contain"
        :class="compact ? 'h-full w-full' : 'max-h-[80%] max-w-[86%]'"
        @error="markImageError(activeImage)"
      />
      <div v-else class="flex flex-col items-center gap-2 text-[var(--shell-muted)]">
        <PhotoIcon class="h-9 w-9" aria-hidden="true" />
        <span class="text-sm">{{ t('memory.previewFailed') }}</span>
      </div>
      <span
        v-if="activeImage"
        class="pointer-events-none absolute bottom-3 rounded-full bg-slate-950/55 px-3 py-1.5 text-xs text-white opacity-0 backdrop-blur transition group-hover:opacity-100 group-focus-visible:opacity-100"
      >
        {{ t('preview.hint') }}
      </span>
    </div>

    <p v-if="activeImage && !compact" class="mt-3 text-center text-sm text-[var(--shell-muted)]">
      {{ t('preview.hint') }}
    </p>

    <div v-if="images.length > 1" class="mt-3 flex items-center gap-3">
      <span class="w-11 flex-none text-sm tabular-nums text-[var(--shell-muted)]">
        {{ activeIndex + 1 }} / {{ images.length }}
      </span>
      <div class="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto px-1 py-1">
        <button
          v-for="(image, index) in images"
          :key="`${image}-${index}`"
          type="button"
          class="media-gallery__thumbnail flex h-14 w-[4.5rem] flex-none items-center justify-center overflow-hidden rounded-xl border bg-slate-100/70 p-1 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          :class="activeIndex === index ? 'border-blue-600 ring-1 ring-inset ring-blue-600' : 'border-[var(--shell-line)]'"
          :aria-label="t('preview.thumbnail', { index: index + 1 })"
          @click="activeIndex = index"
        >
          <img
            v-if="!failedImages[image]"
            :src="image"
            :alt="`${memory.ai_summary} ${index + 1}`"
            class="block max-h-full max-w-full object-contain"
            loading="lazy"
            @error="markImageError(image)"
          />
          <PhotoIcon v-else class="mx-auto h-6 w-6 text-[var(--shell-muted)]" aria-hidden="true" />
        </button>
      </div>
    </div>
  </section>
</template>
