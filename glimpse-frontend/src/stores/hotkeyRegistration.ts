import { defineStore } from 'pinia'
import { ref } from 'vue'

// 全局热键的注册结果状态：失败信息供设置页热键行显示持续异常标记，
// 下一次注册成功即自动清除。
export const useHotkeyRegistrationStore = defineStore('hotkeyRegistration', () => {
  const hotkey = ref<string | null>(null)
  const error = ref<string | null>(null)

  const reportSuccess = (value: string) => {
    hotkey.value = value
    error.value = null
  }

  const reportFailure = (value: string, reason: string) => {
    hotkey.value = value
    error.value = reason
  }

  return { hotkey, error, reportSuccess, reportFailure }
})
