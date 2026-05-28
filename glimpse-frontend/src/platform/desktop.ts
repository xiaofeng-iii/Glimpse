export const isDesktopShell = () =>
  typeof window !== 'undefined' &&
  ('__TAURI__' in window || '__TAURI_INTERNALS__' in window)

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
  const currentWindow = await getWindowApi()
  if (!currentWindow) {
    return
  }
  await currentWindow.hide()
}

export const closeDesktopWindow = async () => {
  const currentWindow = await getWindowApi()
  if (!currentWindow) {
    return
  }
  await currentWindow.close()
}

export const focusDesktopWindow = async () => {
  const currentWindow = await getWindowApi()
  if (!currentWindow) {
    return
  }
  await currentWindow.show()
  await currentWindow.setFocus()
}
