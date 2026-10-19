import { describe, expect, it, vi } from 'vitest'

// 用自定义 adapter 捕获 axios 实际发出的 URL（getUri 走与生产完全相同的
// paramsSerializer 路径），验证 tag_ids 是重复参数而非 axios 默认的 key[]=1。
const capturedUrls: string[] = []

vi.mock('axios', async (importOriginal) => {
  const actual = await importOriginal<typeof import('axios')>()
  const captureAdapter = async (config: Parameters<typeof actual.default.getUri>[0]) => {
    capturedUrls.push(actual.default.getUri(config))
    return {
      data: { memories: [], total: 0, query: '', source: 'all' },
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    }
  }
  return {
    ...actual,
    default: {
      ...actual.default,
      create: (config?: object) =>
        actual.default.create({ ...config, adapter: captureAdapter }),
    },
  }
})

import { memoriesApi, searchApi } from '@/api/client'

describe('api client: tag_ids serialization', () => {
  it('sends list tag filters as repeated tag_ids params', async () => {
    await memoriesApi.list({ tagIds: [1, 2] })

    expect(capturedUrls[0]).toContain('tag_ids=1&tag_ids=2')
    expect(capturedUrls[0]).not.toContain('tag_ids%5B%5D')
    expect(capturedUrls[0]).not.toContain('tag_ids[]')
  })

  it('sends search tag filters as repeated tag_ids params', async () => {
    await searchApi.search('会议', 'all', { tagIds: [3, 4] })

    const url = capturedUrls[capturedUrls.length - 1]
    expect(url).toContain('tag_ids=3&tag_ids=4')
    expect(url).not.toContain('tag_ids%5B%5D')
  })

  it('omits tag_ids entirely when no tag filter is set', async () => {
    await memoriesApi.list({})

    const url = capturedUrls[capturedUrls.length - 1]
    expect(url).not.toContain('tag_ids')
  })
})
