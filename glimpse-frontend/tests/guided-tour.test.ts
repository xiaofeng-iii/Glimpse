import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import GuidedTour from '@/components/GuidedTour.vue'
import { useMemoriesStore } from '@/stores/memories'
import { setLanguagePreference } from '@/utils/i18n'

const routerMocks = vi.hoisted(() => ({
  push: vi.fn(() => Promise.resolve()),
}))

const routeMockRef = vi.hoisted(() => ({
  current: null as null | { name: string; fullPath: string; query: Record<string, string> },
}))

vi.mock('vue-router', async () => {
  const { reactive } = await import('vue')
  routeMockRef.current = reactive({ name: 'home', fullPath: '/', query: {} })
  return {
    useRoute: () => routeMockRef.current,
    useRouter: () => ({ push: routerMocks.push }),
  }
})

const tourSampleMocks = vi.hoisted(() => ({
  inject: vi.fn().mockResolvedValue(undefined),
  remove: vi.fn().mockResolvedValue(undefined),
  sweep: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('@/utils/tour-samples', () => ({
  injectTourSamples: tourSampleMocks.inject,
  removeTourSamples: tourSampleMocks.remove,
  sweepTourSamples: tourSampleMocks.sweep,
}))

const createFixture = (name: string) => {
  const element = document.createElement('div')
  element.dataset.tour = name
  document.body.appendChild(element)
  return element
}

const tourCard = () => document.querySelector<HTMLElement>('[data-testid="tour-card"]')
const tourButton = (testid: string) =>
  document.querySelector<HTMLButtonElement>(`[data-testid="${testid}"]`)

const clickTour = async (testid: string) => {
  tourButton(testid)!.click()
  await flushPromises()
}

const advanceTo = async (times: number) => {
  for (let index = 0; index < times; index += 1) await clickTour('tour-next')
}

const mountTour = () => {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(GuidedTour, {
    props: { open: true },
    attachTo: document.body,
    global: { plugins: [pinia] },
  })
}

describe('GuidedTour', () => {
  beforeAll(() => {
    Element.prototype.scrollIntoView = vi.fn()
  })

  beforeEach(() => {
    vi.clearAllMocks()
    setLanguagePreference('zh-CN')
    routeMockRef.current!.name = 'home'
    routeMockRef.current!.fullPath = '/'
    routeMockRef.current!.query = {}
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts at the welcome card and steps through with counters', async () => {
    createFixture('capture-button')
    mountTour()
    await flushPromises()

    expect(tourCard()!.textContent).toContain('欢迎使用 Glimpse')
    expect(tourCard()!.textContent).not.toContain('/ 7')

    // 欢迎标题为逐字描边书写动画：SVG 双层文字、逐字 tspan、可访问名完整
    const welcomeTitle = document.getElementById('guided-tour-title')!
    expect(welcomeTitle.querySelector('[role="img"]')?.getAttribute('aria-label'))
      .toBe('欢迎使用 Glimpse')
    expect(welcomeTitle.querySelectorAll('.stroke-text__stroke-char'))
      .toHaveLength(Array.from('欢迎使用 Glimpse').length)
    expect(tourButton('tour-prev')).toBeNull()
    expect(tourButton('tour-skip')).toBeNull()

    await clickTour('tour-next')
    expect(tourCard()!.textContent).toContain('随手截图')
    expect(tourCard()!.textContent).toContain('1 / 7')
    expect(tourCard()!.textContent).toContain('Ctrl + Shift + G')
    expect(document.querySelector('.guided-tour__hole')).not.toBeNull()
    expect(document.querySelectorAll('.guided-tour__blocker')).toHaveLength(4)
    expect(document.querySelector('.guided-tour__card--centered')).toBeNull()

    await clickTour('tour-prev')
    expect(tourCard()!.textContent).toContain('欢迎使用 Glimpse')
  })

  it('completes from a middle step via the skip button or Escape', async () => {
    createFixture('capture-button')
    createFixture('add-memory-button')
    const wrapper = mountTour()
    await advanceTo(2)

    expect(tourCard()!.textContent).toContain('2 / 7')
    await clickTour('tour-skip')
    expect(wrapper.emitted('complete')).toHaveLength(1)
    wrapper.unmount()

    const escapeWrapper = mountTour()
    await flushPromises()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await flushPromises()
    expect(escapeWrapper.emitted('complete')).toHaveLength(1)
    escapeWrapper.unmount()
  })

  it('lets the user keep trying searches without auto-advancing', async () => {
    createFixture('capture-button')
    createFixture('add-memory-button')
    createFixture('search-input')
    mountTour()
    await advanceTo(3)

    expect(tourCard()!.textContent).toContain('找回记忆')
    expect(tourCard()!.textContent).toContain('几条示例记忆')

    const memories = useMemoriesStore()
    memories.searchQuery = '第一个词'
    await flushPromises()
    memories.searchQuery = '换个词再试试'
    await new Promise((resolve) => { setTimeout(resolve, 700) })
    expect(tourCard()!.textContent).toContain('找回记忆')
    expect(tourCard()!.textContent).toContain('3 / 7')
  })

  it('auto-advances the add-memory gate after the dialog closes', async () => {
    createFixture('capture-button')
    createFixture('add-memory-button')
    mountTour()
    await advanceTo(2)

    expect(tourCard()!.textContent).toContain('添加记忆')
    const dialog = createFixture('add-memory-dialog')
    await flushPromises()
    dialog.remove()
    await vi.waitFor(() => {
      expect(tourCard()!.textContent).toContain('找回记忆')
    }, { timeout: 2500 })
  })

  it('routes to the settings AI section for the AI step', async () => {
    createFixture('capture-button')
    createFixture('add-memory-button')
    createFixture('search-input')
    createFixture('search-source')
    createFixture('settings-entry')
    createFixture('settings-ai-fields')
    mountTour()
    await advanceTo(5)

    expect(tourCard()!.textContent).toContain('关键配置')
    await clickTour('tour-next')

    expect(routerMocks.push).toHaveBeenCalledWith({
      name: 'settings',
      query: { section: 'ai' },
    })
    await vi.waitFor(() => {
      expect(tourCard()!.textContent).toContain('AI 摘要（可选）')
      expect(tourCard()!.textContent).toContain('6 / 7')
    }, { timeout: 2500 })
  })

  it('auto-advances the settings-entry gate when the user opens settings', async () => {
    createFixture('capture-button')
    createFixture('add-memory-button')
    createFixture('search-input')
    createFixture('search-source')
    createFixture('settings-entry')
    createFixture('settings-ai-fields')
    mountTour()
    await advanceTo(5)

    expect(tourCard()!.textContent).toContain('关键配置')
    expect(tourCard()!.textContent).toContain('试着点这个齿轮进入设置')

    routeMockRef.current!.name = 'settings'
    routeMockRef.current!.fullPath = '/settings'
    await vi.waitFor(() => {
      expect(tourCard()!.textContent).toContain('AI 摘要（可选）')
      expect(tourCard()!.textContent).toContain('6 / 7')
    }, { timeout: 2500 })
  })

  it('falls back to a centered card when the anchor never appears', async () => {
    vi.useFakeTimers()
    mountTour()
    await flushPromises()
    await advanceTo(1)

    await vi.advanceTimersByTimeAsync(5200)
    expect(tourCard()!.textContent).toContain('随手截图')
    expect(document.querySelector('.guided-tour__card--centered')).not.toBeNull()
  })

  it('blocks wheel scrolling on covered areas but allows layers above the tour', async () => {
    createFixture('capture-button')
    mountTour()
    await flushPromises()
    await clickTour('tour-next')

    const blocked = new WheelEvent('wheel', { bubbles: true, cancelable: true })
    document.body.dispatchEvent(blocked)
    expect(blocked.defaultPrevented).toBe(true)

    const dialog = document.createElement('div')
    dialog.style.zIndex = '600'
    const inner = document.createElement('div')
    dialog.appendChild(inner)
    document.body.appendChild(dialog)
    const allowed = new WheelEvent('wheel', { bubbles: true, cancelable: true })
    inner.dispatchEvent(allowed)
    expect(allowed.defaultPrevented).toBe(false)
  })

  it('injects samples when opened and removes them when finished', async () => {
    mountTour()
    await flushPromises()
    expect(tourSampleMocks.inject).toHaveBeenCalledTimes(1)

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await flushPromises()
    expect(tourSampleMocks.remove).toHaveBeenCalledTimes(1)
  })

  it('ends on the fold-text display card with a round check button', async () => {
    createFixture('capture-button')
    createFixture('add-memory-button')
    createFixture('search-input')
    createFixture('search-source')
    createFixture('settings-entry')
    createFixture('settings-ai-fields')
    mountTour()
    await advanceTo(7)

    const finishTitle = document.getElementById('guided-tour-title')!
    expect(tourCard()!.textContent).toContain('一切就绪')
    expect(finishTitle.querySelector('[role="img"]')?.getAttribute('aria-label')).toBe('一切就绪！')
    expect(finishTitle.querySelectorAll('.fold-text__char'))
      .toHaveLength(Array.from('一切就绪！').length)
    expect(tourButton('tour-next')!.getAttribute('aria-label')).toBe('完成')
  })
})
