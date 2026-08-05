import { computed, ref, shallowRef } from 'vue'
import { defineStore } from 'pinia'

const clampIndex = (index: number, imageCount: number) => {
  if (imageCount <= 0) {
    return 0
  }

  return Math.min(Math.max(Math.trunc(index), 0), imageCount - 1)
}

export const useImagePreviewStore = defineStore('image-preview', () => {
  const isOpen = ref(false)
  const images = ref<string[]>([])
  const currentIndex = ref(0)
  const originElement = shallowRef<HTMLElement | null>(null)

  const currentImage = computed(() => images.value[currentIndex.value] ?? '')
  const hasMultiple = computed(() => images.value.length > 1)

  const open = (
    nextImages: string[],
    index = 0,
    origin?: HTMLElement | null,
  ) => {
    const validImages = nextImages.filter(
      (image): image is string => typeof image === 'string' && image.length > 0,
    )

    if (validImages.length === 0) {
      return
    }

    images.value = validImages
    currentIndex.value = clampIndex(index, validImages.length)
    originElement.value = origin === undefined
      ? document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null
      : origin
    isOpen.value = true
  }

  const close = () => {
    isOpen.value = false
  }

  const goTo = (index: number) => {
    currentIndex.value = clampIndex(index, images.value.length)
  }

  const next = () => {
    if (images.value.length === 0) {
      return
    }

    currentIndex.value = (currentIndex.value + 1) % images.value.length
  }

  const previous = () => {
    if (images.value.length === 0) {
      return
    }

    currentIndex.value = (
      currentIndex.value - 1 + images.value.length
    ) % images.value.length
  }

  return {
    isOpen,
    images,
    currentIndex,
    currentImage,
    hasMultiple,
    originElement,
    open,
    close,
    goTo,
    next,
    previous,
  }
})
