// 源码启动（tauri dev）专用的假更新通道：只提供 1.0.0 的版本信息与更新日志，
// 没有可下载的安装包，用于检查更新相关页面的呈现。
// 通道标识见 @/stores/updates 的 DEV_UPDATE_CHANNEL；本模块只在 import.meta.env.DEV
// 分支里被动态导入，生产构建不会产出它。
import { compareKeys, versionKey, type ReleaseNotes } from '@/utils/updateNotes'

export const DEV_UPDATE_VERSION = '1.0.0'

// 让"下载并安装"的忙碌态可见，随后按无安装包失败。
const INSTALL_SIMULATION_MS = 900

export interface DevAvailableUpdate {
  version: string
  notes: string
}

const release = (version: string, notes: string): ReleaseNotes => ({
  version,
  preview: version.includes('-preview'),
  notes,
  sortKey: versionKey(version)!,
})

// 目标版本正文，同时充当假索引不可用时的原始日志兜底。
const targetNotes = `**新特性**
- 记忆墙支持自定义排序
- 详情页支持整段复制

**优化**
- 搜索与筛选切换更顺滑

**修复**
- 修复长摘要偶尔显示不全的问题`

// 假索引故意混入一条被最新正式版覆盖的预览条目：聚合结果里不该出现它。
export const devReleaseNotes = (): ReleaseNotes[] => [
  release(DEV_UPDATE_VERSION, targetNotes),
  release('0.5.1-preview.20260101', '**新特性**\n- 仅预览版测试条目（聚合时应被剔除）'),
  release('0.5.0', '**新特性**\n- 新增记忆连拍合并开关\n\n**优化**\n- 启动速度更快'),
]

export const devCheckForUpdate = (currentVersion: string): DevAvailableUpdate | null => {
  const current = versionKey(currentVersion)
  const target = versionKey(DEV_UPDATE_VERSION)
  // 仓库版本真的到 1.0.0 后不再谎报有更新。
  if (!target || (current && compareKeys(current, target) >= 0)) return null
  return { version: DEV_UPDATE_VERSION, notes: targetNotes }
}

export const devInstallUpdate = async (): Promise<never> => {
  await new Promise((resolve) => setTimeout(resolve, INSTALL_SIMULATION_MS))
  throw new Error('Dev test channel provides no installable package')
}
