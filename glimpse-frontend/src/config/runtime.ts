import { isDesktopShell } from '@/platform/desktop'

type BackendRuntime = {
  origin: string
  token?: string | null
}

const defaultDesktopApiOrigin = 'http://127.0.0.1:8000'

const runtimeState: BackendRuntime = {
  origin:
    (typeof window !== 'undefined' &&
      (window as typeof window & { __GLIMPSE_API_ORIGIN__?: string }).__GLIMPSE_API_ORIGIN__) ||
    defaultDesktopApiOrigin,
  token: null,
}

export const initializeBackendRuntime = async () => {
  if (!isDesktopShell()) {
    return
  }

  try {
    const module = await import('@tauri-apps/api/core')
    const backendRuntime = await module.invoke<BackendRuntime>('get_backend_runtime')
    if (backendRuntime.origin) {
      runtimeState.origin = backendRuntime.origin.replace(/\/$/, '')
    }
    runtimeState.token = backendRuntime.token || null
  } catch (error) {
    console.error('Failed to load backend runtime:', error)
  }
}

export const getApiOrigin = () => runtimeState.origin

export const getBackendAuthToken = () => runtimeState.token || ''

export const getApiBaseUrl = () => (isDesktopShell() ? `${runtimeState.origin}/api` : '/api')

export const getWsBaseUrl = () => (isDesktopShell() ? `${runtimeState.origin.replace(/^http/, 'ws')}/ws` : '/ws')

export const appendBackendAuthToken = (url: string) => {
  const token = getBackendAuthToken()
  if (!token) {
    return url
  }

  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}auth_token=${encodeURIComponent(token)}`
}

export const getImageUrl = (imagePath: string) => appendBackendAuthToken(
  `${getApiBaseUrl()}/images?path=${encodeURIComponent(imagePath)}`,
)
