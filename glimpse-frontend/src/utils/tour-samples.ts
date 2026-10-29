import { memoriesApi } from '@/api/client'
import { whenBackendRuntimeReady } from '@/config/runtime'
import { useBackendStatusStore } from '@/stores/backendStatus'
import { useMemoriesStore } from '@/stores/memories'
import { createLogger } from '@/utils/logger'
import { languagePreference } from '@/utils/i18n'
import { shouldShowOnboarding } from '@/utils/onboarding'

const logger = createLogger('utils/tour-samples')

export const TOUR_SAMPLE_IDS_STORAGE_KEY = 'glimpse.tourSampleIds'

// 样例只服务于引导期的搜索体验：内容覆盖精确关键词（周会/睡眠/公积金/pyperclip）
// 与语义查询（"怎么睡得更好""会议说了什么"），中英各一套、按界面语言取用。
const SAMPLE_CONTENTS_ZH = [
  '周会纪要：新版本定在 11 月 14 日发布，重点是搜索提速和安装包瘦身。',
  '睡眠研究：成年人每晚需要 7-9 小时，深睡集中在前半夜，睡前一小时远离屏幕。',
  '公积金租房提取额度今年提高了，下个月记得在 App 上办理。',
  'Python 操作剪贴板：pip install pyperclip，copy() 写入，paste() 读出。',
] as const

const SAMPLE_CONTENTS_EN = [
  'Weekly meeting notes: the new release ships November 14, focusing on faster search and a smaller installer.',
  'Sleep research: adults need 7-9 hours per night; deep sleep concentrates in the first half, and screens should be off an hour before bed.',
  'The housing fund rental withdrawal limit went up this year — remember to renew in the app next month.',
  'Python clipboard: pip install pyperclip; copy() to write, paste() to read.',
] as const

export const sampleContents = () => (
  languagePreference.value === 'en-US' ? [...SAMPLE_CONTENTS_EN] : [...SAMPLE_CONTENTS_ZH]
)

const wait = (milliseconds: number) =>
  new Promise<void>((resolve) => { window.setTimeout(resolve, milliseconds) })

const readSampleIds = (): string[] => {
  try {
    const parsed: unknown = JSON.parse(
      window.localStorage.getItem(TOUR_SAMPLE_IDS_STORAGE_KEY) ?? '[]',
    )
    return Array.isArray(parsed) ? parsed.filter((id): id is string => typeof id === 'string') : []
  } catch {
    return []
  }
}

const writeSampleIds = (ids: string[]) => {
  try {
    window.localStorage.setItem(TOUR_SAMPLE_IDS_STORAGE_KEY, JSON.stringify(ids))
  } catch {
    // 受限 webview 写不进 localStorage 时照常注入，删除退化为本次会话内存兜底
  }
}

const clearSampleIds = () => {
  try {
    window.localStorage.removeItem(TOUR_SAMPLE_IDS_STORAGE_KEY)
  } catch {
    // 同上，静默
  }
}

const waitForBackend = async (timeoutMs = 30_000) => {
  const deadline = Date.now() + timeoutMs
  const backendStatus = useBackendStatusStore()
  while (Date.now() < deadline) {
    if (await backendStatus.check()) return true
    await wait(500)
  }
  return false
}

// 引导开始时后台注入：只有库为空才注入（DEV 重放走用户已有数据）；
// 任何失败都静默放弃——引导本身不依赖样例存在。
export const injectTourSamples = async () => {
  try {
    await whenBackendRuntimeReady()
    if (!await waitForBackend()) return

    const existing = await memoriesApi.list({ limit: 1 })
    if (existing.memories.length) return

    const ids: string[] = []
    for (const content of sampleContents()) {
      const memory = await memoriesApi.createText(content)
      ids.push(memory.id)
    }
    writeSampleIds(ids)
    await useMemoriesStore().load()
  } catch (error) {
    logger.warn('Tour sample injection skipped: %s', error)
  }
}

// 引导结束时删除本次注入的样例：404 视为已删；其他失败保留 IDs 供下次清扫重试。
// 只按 localStorage 记录的 IDs 删，绝不触碰用户自建的记忆。
export const removeTourSamples = async () => {
  const ids = readSampleIds()
  if (!ids.length) return
  try {
    await whenBackendRuntimeReady()
    let allRemoved = true
    for (const id of ids) {
      try {
        await memoriesApi.delete(id)
      } catch (error) {
        const status = (error as { response?: { status?: number } })?.response?.status
        if (status !== 404) allRemoved = false
      }
    }
    if (allRemoved) clearSampleIds()
    await useMemoriesStore().load()
  } catch (error) {
    logger.warn('Tour sample removal skipped: %s', error)
  }
}

// 启动兜底：引导中途退出时版本未标记、下次会重播，样例保留待用；
// 只有引导不会再自动播时才清掉残留样例。
export const sweepTourSamples = async () => {
  if (!readSampleIds().length) return
  if (shouldShowOnboarding()) return
  await removeTourSamples()
}
