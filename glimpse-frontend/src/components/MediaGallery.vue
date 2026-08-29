<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { PhotoIcon } from '@heroicons/vue/24/outline'
import type { Memory } from '@/api/client'
import { useImagePreviewStore } from '@/stores/imagePreview'
import { getMemoryImagePaths, getMemoryImageUrls } from '@/utils/memory-images'
import { t } from '@/utils/i18n'
import ImageContextMenu from './ImageContextMenu.vue'

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
const imagePaths = computed(() => getMemoryImagePaths(props.memory))
const activeImage = computed(() => images.value[activeIndex.value] ?? '')
const imageMenu = ref({ x: 0, y: 0, index: 0, token: 0 })

watch(
  () => props.memory.id,
  () => {
    activeIndex.value = 0
    failedImages.value = {}
  },
)

const openPreview = (origin?: HTMLElement | null) => {
  if (!images.value.length) return
  imagePreview.open(images.value, activeIndex.value, origin, imagePaths.value)
}

const openImageMenu = (event: MouseEvent, index: number) => {
  if (!images.value.length) return
  imageMenu.value = { x: event.clientX, y: event.clientY, index, token: imageMenu.value.token + 1 }
}

const closeImageMenu = () => {
  imageMenu.value = { ...imageMenu.value, token: 0 }
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
      class="group relative flex w-full items-center justify-center overflow-hidden rounded-lg border border-[var(--shell-line)] bg-slate-100/70 outline-none transition"
      :class="compact ? 'h-64' : 'h-[min(54vh,560px)] min-h-80'"
      role="button"
      tabindex="0"
      :aria-label="t('preview.hint')"
      @dblclick="openPreview($event.currentTarget as HTMLElement)"
      @contextmenu.prevent="openImageMenu($event, activeIndex)"
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
        class="pointer-events-none absolute bottom-3 rounded-md bg-slate-950/55 px-2.5 py-1 text-xs text-white opacity-0 backdrop-blur transition group-hover:opacity-100 group-focus-visible:opacity-100"
      >
        {{ t('preview.hint') }}
      </span>
    </div>

    <p v-if="activeImage && !compact" class="mt-3 text-center text-sm text-[var(--shell-muted)]">
      {{ t('preview.hint') }}
    </p>

    <div v-if="images.length > 1" class="mt-2.5 flex items-center gap-2.5">
      <span class="w-11 flex-none text-sm tabular-nums text-[var(--shell-muted)]">
        {{ activeIndex + 1 }} / {{ images.length }}
      </span>
      <div class="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto px-1 py-1">
        <button
          v-for="(image, index) in images"
          :key="`${image}-${index}`"
          type="button"
          class="media-gallery__thumbnail flex h-14 w-[4.5rem] flex-none items-center justify-center overflow-hidden rounded-md border bg-slate-100/70 p-1 transition"
          :class="activeIndex === index ? 'border-[var(--color-primary)] ring-1 ring-inset ring-[var(--color-primary)]' : 'border-[var(--shell-line)]'"
          :aria-label="t('preview.thumbnail', { index: index + 1 })"
          @click="activeIndex = index"
          @contextmenu.prevent.stop="openImageMenu($event, index)"
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

    <ImageContextMenu
      :x="imageMenu.x"
      :y="imageMenu.y"
      :open-token="imageMenu.token"
      :index="imageMenu.index"
      :paths="imagePaths"
      :urls="images"
      show-open
      @close="closeImageMenu"
    />
  </section>
</template>
