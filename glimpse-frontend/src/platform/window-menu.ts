import { t } from '@/utils/i18n'
import { getDesktopWindowMaximized, isDesktopShell } from './desktop'

export type WindowMenuOptions = {
  /** 关闭项需走应用的关闭流程（未保存守卫 + 关闭询问）。 */
  onCloseRequested: () => void
}

/**
 * 在光标处弹出系统样式的窗口菜单（还原/移动/大小/最小化/最大化/关闭）。
 * 仅桌面端有效；网页开发模式下返回 false。
 */
export const popupDesktopWindowMenu = async (options: WindowMenuOptions) => {
  if (!isDesktopShell()) return false

  try {
    const [menuModule, windowModule] = await Promise.all([
      import('@tauri-apps/api/menu'),
      import('@tauri-apps/api/window'),
    ])
    const currentWindow = windowModule.getCurrentWindow()
    const maximized = await getDesktopWindowMaximized()
    const menu = await menuModule.Menu.new({
      items: [
        {
          text: t('windowMenu.restore'),
          enabled: maximized,
          action: () => void currentWindow.toggleMaximize(),
        },
        {
          text: t('windowMenu.move'),
          enabled: !maximized,
          action: () => void currentWindow.startDragging(),
        },
        {
          text: t('windowMenu.size'),
          enabled: !maximized,
          action: () => void currentWindow.startResizeDragging('SouthEast'),
        },
        { item: 'Separator' },
        {
          text: t('windowMenu.minimize'),
          action: () => void currentWindow.minimize(),
        },
        {
          text: t('windowMenu.maximize'),
          enabled: !maximized,
          action: () => void currentWindow.toggleMaximize(),
        },
        { item: 'Separator' },
        {
          text: t('windowMenu.close'),
          accelerator: 'Alt+F4',
          action: () => options.onCloseRequested(),
        },
      ],
    })
    await menu.popup()
    return true
  } catch (error) {
    console.error('Failed to popup window menu:', error)
    return false
  }
}
