export const isDesktopShell = () =>
  typeof window !== 'undefined' &&
  ('__TAURI__' in window || '__TAURI_INTERNALS__' in window)

const invokeDesktopCommand = async (command: string) => {
  if (!isDesktopShell()) {
    return false
  }

  try {
    const module = await import('@tauri-apps/api/core')
    await module.invoke(command)
    return true
  } catch (error) {
    console.error(`Failed to invoke desktop command "${command}":`, error)
    return false
  }
}

const invokeDesktopCommandWithResult = async <T>(command: string) => {
  if (!isDesktopShell()) {
    return null
  }

  try {
    const module = await import('@tauri-apps/api/core')
    return await module.invoke<T>(command)
  } catch (error) {
    console.error(`Failed to invoke desktop command "${command}":`, error)
    return null
  }
}

const getWindowApi = async () => {
  if (!isDesktopShell()) {
    return null
  }

  try {
    const module = await import('@tauri-apps/api/window')
    return module.getCurrentWindow()
  } catch (error) {
    console.error('Failed to load Tauri window API:', error)
    return null
  }
}

export const hideDesktopWindow = async () => {
  if (await invokeDesktopCommand('hide_window')) {
    return
  }

  const currentWindow = await getWindowApi()
  if (!currentWindow) {
    return
  }
  await currentWindow.hide()
}

export const minimizeDesktopWindow = async () => {
  if (await invokeDesktopCommand('minimize_window')) {
    return
  }

  const currentWindow = await getWindowApi()
  if (!currentWindow) {
    return
  }
  await currentWindow.minimize()
}

export const startDesktopWindowDrag = async () => {
  if (await invokeDesktopCommand('start_drag_window')) {
    return
  }

  const currentWindow = await getWindowApi()
  if (!currentWindow) {
    return
  }
  await currentWindow.startDragging()
}

export const toggleDesktopMaximize = async () => {
  if (await invokeDesktopCommand('toggle_maximize_window')) {
    return
  }

  const currentWindow = await getWindowApi()
  if (!currentWindow) {
    return
  }
  await currentWindow.toggleMaximize()
}

export const getDesktopWindowMaximized = async () => {
  const result = await invokeDesktopCommandWithResult<boolean>('is_window_maximized')
  if (typeof result === 'boolean') {
    return result
  }

  const currentWindow = await getWindowApi()
  if (!currentWindow) {
    return false
  }
  return await currentWindow.isMaximized()
}

export const closeDesktopWindow = async () => {
  if (!isDesktopShell()) {
    return
  }

  try {
    const module = await import('@tauri-apps/api/core')
    await module.invoke('quit_app')
    return
  } catch (error) {
    console.error('Failed to quit app via Tauri command:', error)
  }

  const currentWindow = await getWindowApi()
  if (currentWindow) {
    await currentWindow.close()
  }
}

export const focusDesktopWindow = async () => {
  if (await invokeDesktopCommand('focus_window')) {
    return
  }

  const currentWindow = await getWindowApi()
  if (!currentWindow) {
    return
  }
  await currentWindow.show()
  await currentWindow.setFocus()
}

export const listenForDesktopCloseRequests = async (
  handler: () => void,
) => {
  if (!isDesktopShell()) {
    return () => {}
  }

  try {
    const module = await import('@tauri-apps/api/event')
    return await module.listen('glimpse://close-requested', () => {
      handler()
    })
  } catch (error) {
    console.error('Failed to listen for desktop close requests:', error)
    return () => {}
  }
}

export const openExternalTarget = async (target: string) => {
  if (isDesktopShell()) {
    try {
      const module = await import('@tauri-apps/plugin-shell')
      await module.open(target)
      return
    } catch (error) {
      console.error('Failed to open external target via Tauri shell:', error)
    }
  }

  window.open(target, '_blank', 'noopener,noreferrer')
}
