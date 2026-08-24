import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AppSelect from '@/components/AppSelect.vue'

describe('AppSelect', () => {
  it('renders an accessible authored trigger with the selected label', async () => {
    const wrapper = mount(AppSelect, {
      attachTo: document.body,
      props: {
        id: 'language-select',
        ariaLabelledby: 'language-label',
        modelValue: 'zh-CN',
        options: [
          { value: 'zh-CN', label: '中文' },
          { value: 'en-US', label: 'English' },
        ],
      },
    })

    const trigger = wrapper.get('#language-select')
    expect(trigger.element.tagName).toBe('BUTTON')
    expect(trigger.attributes('role')).toBe('combobox')
    expect(trigger.attributes('aria-labelledby')).toBe('language-label')
    expect(trigger.attributes('aria-expanded')).toBe('false')
    expect(trigger.text()).toContain('中文')

    await wrapper.setProps({ modelValue: 'en-US' })
    expect(trigger.text()).toContain('English')

    wrapper.unmount()
  })
})
