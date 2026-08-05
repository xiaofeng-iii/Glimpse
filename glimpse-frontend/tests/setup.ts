import { afterEach } from 'vitest'
import { enableAutoUnmount } from '@vue/test-utils'

enableAutoUnmount(afterEach)

afterEach(() => {
  document.body.replaceChildren()
  document.body.style.overflow = ''
  document.documentElement.style.overflow = ''
})
