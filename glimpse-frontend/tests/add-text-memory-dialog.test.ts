import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import AddTextMemoryDialog from '@/components/AddTextMemoryDialog.vue'
import { setLanguagePreference } from '@/utils/i18n'

const makeImageFile = (name: string, type = 'image/png') =>
  new File(['image-bytes'], name, { type })

const mountDialog = async (props: Record<string, unknown> = {}) => {
  const wrapper = mount(AddTextMemoryDialog, {
    attachTo: document.body,
    props: {
      open: true,
      ...props,
    },
  })
  await flushPromises()
  return wrapper
}

const getFileInput = () =>
  document.querySelector<HTMLInputElement>('input[type="file"]') as HTMLInputElement

const selectFiles = async (files: File[]) => {
  const input = getFileInput()
  Object.defineProperty(input, 'files', { value: files, configurable: true })
  input.dispatchEvent(new Event('change'))
  await flushPromises()
}

const submitForm = async () => {
  const form = document.querySelector('form') as HTMLFormElement
  form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
  await flushPromises()
}

const getFeedback = () =>
  document.querySelector('#text-memory-feedback')?.textContent?.trim() ?? ''

describe('AddTextMemoryDialog', () => {
  beforeAll(() => {
    URL.createObjectURL = vi.fn(() => `blob:mock-${Math.random()}`)
    URL.revokeObjectURL = vi.fn()
  })

  beforeEach(() => {
    vi.clearAllMocks()
    setLanguagePreference('zh-CN')
  })

  it('blocks submission without content when no image is attached', async () => {
    const wrapper = await mountDialog()

    await submitForm()

    expect(wrapper.emitted('submit')).toBeUndefined()
    expect(getFeedback()).toBe('请输入记忆内容')

    wrapper.unmount()
  })

  it('emits trimmed content with the selected images', async () => {
    const wrapper = await mountDialog()
    const first = makeImageFile('first.png')
    const second = makeImageFile('second.jpg', 'image/jpeg')

    await selectFiles([first, second])
    const textarea = document.querySelector<HTMLTextAreaElement>('#text-memory-content')
    textarea!.value = '  手动说明  '
    textarea!.dispatchEvent(new Event('input'))
    await flushPromises()

    await submitForm()

    expect(wrapper.emitted('submit')).toEqual([
      [{ content: '手动说明', images: [first, second] }],
    ])

    wrapper.unmount()
  })

  it('allows an empty note when images are attached', async () => {
    const wrapper = await mountDialog()

    await selectFiles([makeImageFile('only.png')])
    await submitForm()

    expect(wrapper.emitted('submit')).toEqual([
      [{ content: '', images: [expect.any(File)] }],
    ])

    wrapper.unmount()
  })

  it('rejects unsupported file types with a notice', async () => {
    const wrapper = await mountDialog()

    await selectFiles([new File(['text'], 'notes.txt', { type: 'text/plain' })])
    await submitForm()

    expect(getFeedback()).toContain('notes.txt')
    expect(wrapper.emitted('submit')).toBeUndefined()
    expect(document.querySelectorAll('img').length).toBe(0)

    wrapper.unmount()
  })

  it('caps the number of attached images at ten', async () => {
    const wrapper = await mountDialog()

    await selectFiles(
      Array.from({ length: 12 }, (_, index) => makeImageFile(`img-${index}.png`)),
    )

    expect(document.querySelectorAll('img').length).toBe(10)
    expect(getFeedback()).toBe('一条记忆最多添加 10 张图片')

    wrapper.unmount()
  })

  it('removes an image from its thumbnail button', async () => {
    const wrapper = await mountDialog()

    await selectFiles([makeImageFile('first.png'), makeImageFile('second.png')])
    const removeButtons = document.querySelectorAll<HTMLButtonElement>(
      '[aria-label^="移除"]',
    )
    expect(removeButtons.length).toBe(2)
    removeButtons[0].click()
    await flushPromises()

    expect(document.querySelectorAll('img').length).toBe(1)

    wrapper.unmount()
  })
})
