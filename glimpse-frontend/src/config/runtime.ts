import { isDesktopShell } from '@/platform/desktop'

const desktopApiOrigin =
  (typeof window !== 'undefined' && (window as typeof window & { __GLIMPSE_API_ORIGIN__?: string }).__GLIMPSE_API_ORIGIN__) ||
  'http://127.0.0.1:8000'

export const getApiOrigin = () => desktopApiOrigin

export const getApiBaseUrl = () => (isDesktopShell() ? `${desktopApiOrigin}/api` : '/api')

export const getWsBaseUrl = () => (isDesktopShell() ? `${desktopApiOrigin.replace(/^http/, 'ws')}/ws` : '/ws')

export const getImageUrl = (imagePath: string) => `${getApiBaseUrl()}/images?path=${encodeURIComponent(imagePath)}`
