import { isDesktopShell } from './desktop'
import { getImageUrl } from '@/config/runtime'

/**
 * 把单张图片写入系统剪贴板。
 * 桌面端把相对路径交给 Rust 直接读后端数据目录并原生写入（无网页权限/CORS）；
 * 网页开发模式走同源 API 取图后退回 navigator API。
 */
export const copyImageFileToClipboard = async (path: string): Promise<void> => {
  if (isDesktopShell()) {
    const { invoke } = await import('@tauri-apps/api/core')
    await invoke('copy_image_file_to_clipboard', { path })
    return
  }

  const blob = await (await fetch(getImageUrl(path))).blob()
  const pngBlob = blob.type === 'image/png' ? blob : await convertToPng(blob)
  await navigator.clipboard.write([new ClipboardItem({ 'image/png': pngBlob })])
}

/** 把整组图片以文件列表形式写入剪贴板（仅桌面端；粘贴到资源管理器得到独立文件）。 */
export const copyImageFilesToClipboard = async (paths: string[]): Promise<void> => {
  if (!isDesktopShell()) {
    throw new Error('file list clipboard is only supported in the desktop shell')
  }
  const { invoke } = await import('@tauri-apps/api/core')
  await invoke('copy_image_files_to_clipboard', { paths })
}

/** 把位图转成 PNG Blob（网页回退路径使用）。 */
const convertToPng = async (source: Blob): Promise<Blob> => {
  const bitmap = await createImageBitmap(source)
  const canvas = document.createElement('canvas')
  canvas.width = bitmap.width
  canvas.height = bitmap.height
  canvas.getContext('2d')?.drawImage(bitmap, 0, 0)
  const pngBlob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, 'image/png'),
  )
  bitmap.close()
  if (!pngBlob) throw new Error('canvas toBlob returned null')
  return pngBlob
}
