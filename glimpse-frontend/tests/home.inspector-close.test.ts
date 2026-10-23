import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import Home from '@/views/Home.vue'
import { useMemoriesStore } from '@/stores/memories'
import type { Memory } from '@/api/client'

const mocks = vi.hoisted(() => ({
  getSettings: vi.fn(),
  listMemories: vi.fn(),
  listTags: vi.fn(),
  createText: vi.fn(),
  healthCheck: vi.fn(),
}))

vi.mock('@/api/client', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/api/client')>()
  return {
    ...original,
    memoriesApi: {
      ...original.memoriesApi,
      list: mocks.listMemories,
      createText: mocks.createText,
    },
    tagsApi: {
      ...original.tagsApi,
      list: mocks.listTags,
    },
    settingsApi: {
      ...original.settingsApi,
      get: mocks.getSettings,
    },
    healthApi: {
      ...original.healthApi,
      check: mocks.healthCheck,
    },
  }
})

vi.mock('@/config/runtime', () => ({
  whenBackendRuntimeReady: vi.fn().mockReturnValue(new Promise(() => {})),
}))

vi.mock('@/platform/desktop', () => ({
  getDesktopWindowMinimized: vi.fn(),
  isDesktopShell: () => false,
  minimizeDesktopWindow: vi.fn(),
}))

const createMemory = (overrides: Partial<Memory> = {}): Memory => ({
  id: 'memory-1',
  created_at: '2026-10-22T10:00:00',
  image_path: 'C:\\captures\\memory.png',
  ai_summary: 'A payment screen',
  app_name: 'Design Tool',
  text_content: 'Payment failed',
  extra_images: '[]',
  sync_status: 'SYNCED',
  match_sources: [],
  ...overrides,
})

const mountHome = async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', name: 'home', component: Home }],
  })
  await router.push('/')
  await router.isReady()
  const wrapper = mount({ template: '<router-view />' }, {
    attachTo: document.body,
    global: {
      plugins: [createPinia(), router],
      stubs: {
        SearchToolbar: {
          name: 'SearchToolbar',
          methods: { focus() {}, clear() {} },
          template: '<div />',
        },
        MemoryWall: { name: 'MemoryWall', template: '<div data-testid="memory-wall" />' },
        ClusterBar: true,
        MemoryInspector: {
          name: 'MemoryInspector',
          props: ['memory'],
          methods: { canLeave: () => Promise.resolve(true) },
          template: '<div />',
        },
        SideDecorPanel: true,
        AddTextMemoryDialog: {
          name: 'AddTextMemoryDialog',
          props: ['open', 'busy', 'errorMessage'],
          emits: ['cancel', 'submit'],
          template: '<div />',
        },
      },
    },
  })
  await flushPromises()
  return wrapper
}

const pointerDownOn = (target: Element) => {
  target.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, button: 0 }))
}

describe('Home inspector close behavior (floating layout)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('innerWidth', 800)
    setActivePinia(createPinia())
    mocks.getSettings.mockResolvedValue({ hotkeys: {}, cluster: {} })
    mocks.listMemories.mockResolvedValue({ memories: [], total: 0 })
    mocks.listTags.mockResolvedValue({ tags: [] })
    mocks.healthCheck.mockResolvedValue({ status: 'healthy', ai: { configured: true, reachable: true } })
  })

  it('keeps the inspector open when the pointerdown lands in a teleported menu', async () => {
    await mountHome()
    const store = useMemoriesStore()
    store.upsert(createMemory())
    store.select(store.entities['memory-1'])
    await flushPromises()

    // 右键标签菜单 Teleport 到 body，DOM 上不在侧栏面板内
    const menu = document.createElement('div')
    menu.setAttribute('role', 'menu')
    const item = document.createElement('button')
    menu.appendChild(item)
    document.body.appendChild(menu)

    pointerDownOn(item)
    await flushPromises()

    expect(store.selectedId).toBe('memory-1')
    menu.remove()
  })

  it('still closes the inspector when the pointerdown lands on the wall', async () => {
    const wrapper = await mountHome()
    const store = useMemoriesStore()
    store.upsert(createMemory())
    store.select(store.entities['memory-1'])
    await flushPromises()

    pointerDownOn(wrapper.find('[data-testid="memory-wall"]').element)
    await flushPromises()

    expect(store.selectedId).toBeNull()
  })

  it('does not auto-select after adding a text memory in floating layout', async () => {
    const created = createMemory({ id: 'memory-new', memory_type: 'text' })
    mocks.createText.mockResolvedValue(created)
    const wrapper = await mountHome()
    const store = useMemoriesStore()

    wrapper.findComponent({ name: 'AddTextMemoryDialog' }).vm.$emit('submit', {
      content: 'hello',
      images: [],
    })
    await flushPromises()

    expect(store.entities['memory-new']).toBeTruthy()
    expect(store.selectedId).toBeNull()
  })

  it('auto-selects after adding a text memory in docked layout', async () => {
    vi.stubGlobal('innerWidth', 1600)
    const created = createMemory({ id: 'memory-new', memory_type: 'text' })
    mocks.createText.mockResolvedValue(created)
    const wrapper = await mountHome()
    const store = useMemoriesStore()

    wrapper.findComponent({ name: 'AddTextMemoryDialog' }).vm.$emit('submit', {
      content: 'hello',
      images: [],
    })
    await flushPromises()

    expect(store.selectedId).toBe('memory-new')
  })
})
