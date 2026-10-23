// 全局热键的注册与格式转换。监听方是 Tauri 壳（global-shortcut 插件，
// RegisterHotKey 机制）而非 Python sidecar 的 pynput 低级钩子：不给全系统
// 按键注入延迟、无杀软误报，且先于后端就绪即可触发（触发后的后端状态检查
// 与降级提示由 Home.handleScreenshot 承担）。
// 设置里存的是 pynput 风格字符串（"<ctrl>+<shift>+g"），注册前转成插件的
// 加速器格式（"Ctrl+Shift+G"）。
import { isDesktopShell } from './desktop'

const MODIFIER_MAP: Record<string, string> = {
  ctrl: 'Ctrl',
  shift: 'Shift',
  alt: 'Alt',
  cmd: 'Super',
  win: 'Super',
}

const SPECIAL_KEY_MAP: Record<string, string> = {
  escape: 'Escape',
  enter: 'Enter',
  tab: 'Tab',
  space: 'Space',
  backspace: 'Backspace',
  delete: 'Delete',
  insert: 'Insert',
  home: 'Home',
  end: 'End',
  page_up: 'PageUp',
  page_down: 'PageDown',
  up: 'Up',
  down: 'Down',
  left: 'Left',
  right: 'Right',
}

const FUNCTION_KEY_PATTERN = /^f([1-9]|1[0-9]|2[0-4])$/

export const pynputToAccelerator = (hotkey: string): string | null => {
  const parts = hotkey
    .trim()
    .toLowerCase()
    .split('+')
    .map((part) => part.trim().replace(/^<|>$/g, '').trim())
    .filter(Boolean)
  if (!parts.length) return null

  const modifiers: string[] = []
  let mainKey: string | null = null
  for (const part of parts) {
    if (MODIFIER_MAP[part]) {
      modifiers.push(MODIFIER_MAP[part])
      continue
    }
    // 多于一个非修饰键不是合法组合
    if (mainKey) return null
    if (SPECIAL_KEY_MAP[part]) {
      mainKey = SPECIAL_KEY_MAP[part]
      continue
    }
    if (FUNCTION_KEY_PATTERN.test(part)) {
      mainKey = part.toUpperCase()
      continue
    }
    if (part.length === 1) {
      mainKey = part.toUpperCase()
      continue
    }
    return null
  }
  // 只有修饰键不成热键
  if (!mainKey) return null
  return [...modifiers, mainKey].join('+')
}

export type ShortcutRegistrationResult =
  | { ok: true }
  | { ok: false; error: string }

// 应用当前设置的截图热键：先清空全部注册再重挂（页面重载/HMR 后 Rust 侧
// 注册仍在但 JS handler 已失联，全量重挂保证两者一致）。空热键只清不注。
// 触发沿用既有 CustomEvent 契约，Home 挂载期间的完整交互链保持不变。
export const applyScreenshotShortcut = async (hotkey: string): Promise<ShortcutRegistrationResult> => {
  if (!isDesktopShell()) return { ok: true }
  const { unregisterAll, register } = await import('@tauri-apps/plugin-global-shortcut')
  await unregisterAll()
  const accelerator = pynputToAccelerator(hotkey)
  if (!accelerator) {
    return hotkey.trim() ? { ok: false, error: 'invalid hotkey' } : { ok: true }
  }
  try {
    await register(accelerator, () => {
      window.dispatchEvent(new CustomEvent('glimpse:shortcut-screenshot'))
    })
    return { ok: true }
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : String(error) }
  }
}
