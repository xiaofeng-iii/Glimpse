import { afterEach } from 'vitest'
import { config, enableAutoUnmount } from '@vue/test-utils'
import { hintTooltip } from '../src/directives/hint-tooltip'

enableAutoUnmount(afterEach)

config.global.directives['hint-tooltip'] = hintTooltip

afterEach(() => {
  document.body.replaceChildren()
  document.body.style.overflow = ''
  document.documentElement.style.overflow = ''
})
