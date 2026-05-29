import type { Memory } from '@/api/client'
import { getImageUrl } from '@/config/runtime'

const normalizeImagePath = (value: unknown) =>
  typeof value === 'string' && value.trim() ? value.trim() : ''

const parseExtraImages = (extraImages?: string) => {
  const normalized = normalizeImagePath(extraImages)
  if (!normalized) {
    return []
  }

  try {
    const parsed = JSON.parse(normalized)
    if (Array.isArray(parsed)) {
      return parsed
        .map((item) => normalizeImagePath(item))
        .filter(Boolean)
    }
  } catch (error) {
    if (normalized.includes(',')) {
      return normalized
        .split(',')
        .map((item) => normalizeImagePath(item))
        .filter(Boolean)
    }
  }

  return [normalized]
}

export const getMemoryImagePaths = (memory: Memory) => {
  const paths = [normalizeImagePath(memory.image_path), ...parseExtraImages(memory.extra_images)]
  return Array.from(new Set(paths.filter(Boolean)))
}

export const getMemoryImageUrls = (memory: Memory) =>
  getMemoryImagePaths(memory).map((path) => getImageUrl(path))
