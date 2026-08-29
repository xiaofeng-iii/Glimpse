<script setup lang="ts">
import { nextTick, onUnmounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  PhotoIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline'
import { useImagePreviewStore } from '@/stores/imagePreview'
import { t } from '@/utils/i18n'
import ImageContextMenu from './ImageContextMenu.vue'

const FOCUSABLE_SELECTOR = [
  'button:not([disabled])',
  '[href]',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

const previewStore = useImagePreviewStore()
const {
  isOpen,
  images,
  currentIndex,
  currentImage,
  hasMultiple,
  originElement,
} = storeToRefs(previewStore)

const dialogPanel = ref<HTMLElement | null>(null)
const closeButton = ref<HTMLButtonElement | null>(null)
const failedImages = ref<Record<string, boolean>>({})
const imageMenu = ref({ x: 0, y: 0, token: 0 })
let previousBodyOverflow = ''
let previousHtmlOverflow = ''

const openImageMenu = (event: MouseEvent) => {
  if (!currentImage.value) return
  imageMenu.value = { x: event.clientX, y: event.clientY, token: imageMenu.value.token + 1 }
}

const closeImageMenu = () => {
  imageMenu.value = { ...imageMenu.value, token: 0 }
}

const lockDocumentScroll = () => {
  previousBodyOverflow = document.body.style.overflow
  previousHtmlOverflow = document.documentElement.style.overflow
  document.body.style.overflow = 'hidden'
  document.documentElement.style.overflow = 'hidden'
}

const restoreDocumentScroll = () => {
  document.body.style.overflow = previousBodyOverflow
  document.documentElement.style.overflow = previousHtmlOverflow
}

const restoreOriginFocus = async () => {
  const target = originElement.value
  await nextTick()
  if (target?.isConnected) {
    target.focus({ preventScroll: true })
  }
}

const getFocusableElements = () => {
  if (!dialogPanel.value) {
    return []
  }

  return Array.from(
    dialogPanel.value.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
  ).filter((element) => !element.hasAttribute('disabled') && element.offsetParent !== null)
}

const trapFocus = (event: KeyboardEvent) => {
  const focusable = getFocusableElements()
  if (focusable.length === 0) {
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
  if (!isOpen.value) {
    return
  }

  if (event.key === 'Escape') {
    event.preventDefault()
    event.stopPropagation()
    previewStore.close()
    return
  }

  if (event.key === 'ArrowLeft' && hasMultiple.value) {
    event.preventDefault()
    event.stopPropagation()
    previewStore.previous()
    return
  }

  if (event.key === 'ArrowRight' && hasMultiple.value) {
    event.preventDefault()
    event.stopPropagation()
    previewStore.next()
    return
  }

  if (event.key === 'Tab') {
    trapFocus(event)
  }
}

const markImageError = (url: string) => {
  failedImages.value = {
    ...failedImages.value,
    [url]: true,
  }
}

const markImageLoaded = (url: string) => {
  if (!failedImages.value[url]) {
    return
  }

  const nextFailedImages = { ...failedImages.value }
  delete nextFailedImages[url]
  failedImages.value = nextFailedImages
}

const preloadAdjacentImages = () => {
  if (!isOpen.value || images.value.length < 2) {
    return
  }

  const indexes = [
    (currentIndex.value - 1 + images.value.length) % images.value.length,
    (currentIndex.value + 1) % images.value.length,
  ]

  for (const index of indexes) {
    const url = images.value[index]
    if (url) {
      const preload = new Image()
      preload.src = url
    }
  }
}

watch(
  isOpen,
  async (open) => {
    if (open) {
      lockDocumentScroll()
      document.addEventListener('keydown', handleKeydown, true)
      await nextTick()
      closeButton.value?.focus({ preventScroll: true })
      preloadAdjacentImages()
      return
    }

    document.removeEventListener('keydown', handleKeydown, true)
    restoreDocumentScroll()
    await restoreOriginFocus()
  },
)

watch([images, currentIndex], () => {
  preloadAdjacentImages()
})

watch(images, () => {
  failedImages.value = {}
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown, true)
  if (isOpen.value) {
    restoreDocumentScroll()
  }
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="isOpen"
      class="image-preview-backdrop"
      @mousedown.self="previewStore.close"
    >
      <section
        ref="dialogPanel"
        class="image-preview-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="image-preview-title"
        tabindex="-1"
      >
        <header class="image-preview-dialog__header">
          <div class="image-preview-dialog__heading">
            <h2 id="image-preview-title">{{ t('preview.title') }}</h2>
            <span aria-live="polite">
              {{ currentIndex + 1 }} / {{ images.length }}
            </span>
          </div>
          <button
            ref="closeButton"
            type="button"
            class="modal-icon-button"
            :title="t('action.close')"
            :aria-label="t('action.close')"
            @click="previewStore.close"
          >
            <XMarkIcon class="h-6 w-6" aria-hidden="true" />
          </button>
        </header>

        <div class="image-preview-stage" @contextmenu.prevent="openImageMenu">
          <button
            v-if="hasMultiple"
            type="button"
            class="image-preview-stage__arrow image-preview-stage__arrow--previous"
            :title="t('preview.previous')"
            :aria-label="t('preview.previous')"
            @click="previewStore.previous"
          >
            <ChevronLeftIcon class="h-6 w-6" aria-hidden="true" />
          </button>

          <div
            v-if="failedImages[currentImage]"
            class="image-preview-error"
            role="status"
          >
            <PhotoIcon class="h-10 w-10" aria-hidden="true" />
            <p>{{ t('memory.previewFailed') }}</p>
          </div>
          <img
            v-else-if="currentImage"
            :key="currentImage"
            :src="currentImage"
            class="image-preview-stage__image"
            :alt="`${t('memory.previewAlt')} ${currentIndex + 1}`"
            draggable="false"
            @load="markImageLoaded(currentImage)"
            @error="markImageError(currentImage)"
          />

          <button
            v-if="hasMultiple"
            type="button"
            class="image-preview-stage__arrow image-preview-stage__arrow--next"
            :title="t('preview.next')"
            :aria-label="t('preview.next')"
            @click="previewStore.next"
          >
            <ChevronRightIcon class="h-6 w-6" aria-hidden="true" />
          </button>
        </div>

        <div v-if="hasMultiple" class="image-preview-thumbnails" role="list">
          <button
            v-for="(image, index) in images"
            :key="`${image}-${index}`"
            type="button"
            class="image-preview-thumbnail"
            :class="{ 'image-preview-thumbnail--active': index === currentIndex }"
            role="listitem"
            :aria-current="index === currentIndex ? 'true' : undefined"
            :aria-label="t('preview.thumbnail', { index: index + 1 })"
            @click="previewStore.goTo(index)"
          >
            <img
              :src="image"
              alt=""
              draggable="false"
              @error="markImageError(image)"
            />
          </button>
        </div>

      </section>
    </div>

    <ImageContextMenu
      :x="imageMenu.x"
      :y="imageMenu.y"
      :open-token="imageMenu.token"
      :index="currentIndex"
      :paths="previewStore.paths"
      :urls="images"
      @close="closeImageMenu"
    />
  </Teleport>
</template>
