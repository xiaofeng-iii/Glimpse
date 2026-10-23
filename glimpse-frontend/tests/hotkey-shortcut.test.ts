import { describe, expect, it } from 'vitest'
import { pynputToAccelerator } from '@/platform/global-shortcut'

describe('pynputToAccelerator', () => {
  it('converts the stored pynput format to a Tauri accelerator', () => {
    expect(pynputToAccelerator('<ctrl>+<shift>+g')).toBe('Ctrl+Shift+G')
    expect(pynputToAccelerator('ctrl+shift+g')).toBe('Ctrl+Shift+G')
    expect(pynputToAccelerator('<alt>+<f4>')).toBe('Alt+F4')
    expect(pynputToAccelerator('<cmd>+<space>')).toBe('Super+Space')
    expect(pynputToAccelerator('win+p')).toBe('Super+P')
    expect(pynputToAccelerator('<ctrl>+<page_up>')).toBe('Ctrl+PageUp')
    expect(pynputToAccelerator('<shift>+1')).toBe('Shift+1')
    expect(pynputToAccelerator('  <ctrl> + f  ')).toBe('Ctrl+F')
  })

  it('supports the full function-key range', () => {
    expect(pynputToAccelerator('<f1>')).toBe('F1')
    expect(pynputToAccelerator('<f12>')).toBe('F12')
    expect(pynputToAccelerator('<f24>')).toBe('F24')
  })

  it('rejects invalid combinations', () => {
    // 只有修饰键
    expect(pynputToAccelerator('<ctrl>+<shift>')).toBeNull()
    // 多个非修饰键
    expect(pynputToAccelerator('<ctrl>+g+h')).toBeNull()
    // 未知键名
    expect(pynputToAccelerator('<ctrl>+nomatch>')).toBeNull()
    // 空串/全空白
    expect(pynputToAccelerator('')).toBeNull()
    expect(pynputToAccelerator('   ')).toBeNull()
    expect(pynputToAccelerator('+++')).toBeNull()
  })
})
