import { ref } from 'vue'
import type { WallLayoutMode } from '@/utils/memory-grouping'

const storageKey = 'glimpse.wallLayout'

const normalizeWallLayoutMode = (value: unknown): WallLayoutMode =>
  value === 'month' || value === 'all' ? value : 'day'

// 模块级 ref + localStorage 镜像（与语言偏好同一模式）：首帧同步读取，避免记忆墙布局闪烁。
// 布局模式不进设置页，墙头切换器是唯一入口。
export const wallLayoutMode = ref<WallLayoutMode>(
  normalizeWallLayoutMode(window.localStorage.getItem(storageKey)),
)

export const setWallLayoutMode = (mode: WallLayoutMode) => {
  wallLayoutMode.value = mode
  window.localStorage.setItem(storageKey, mode)
}
