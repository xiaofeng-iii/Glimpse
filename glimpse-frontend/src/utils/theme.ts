export type ThemePreference = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

const themePreferences = new Set<ThemePreference>(['light', 'dark', 'system'])
const systemDarkQuery = '(prefers-color-scheme: dark)'
const storageKey = 'glimpse.themePreference'

export const normalizeThemePreference = (value: unknown): ThemePreference => {
  return typeof value === 'string' && themePreferences.has(value as ThemePreference)
    ? (value as ThemePreference)
    : 'light'
}

export const resolveThemePreference = (preference: ThemePreference): ResolvedTheme => {
  if (preference === 'system') {
    return window.matchMedia(systemDarkQuery).matches ? 'dark' : 'light'
  }

  return preference
}

export const applyThemePreference = (value: unknown): ResolvedTheme => {
  const preference = normalizeThemePreference(value)
  const resolved = resolveThemePreference(preference)
  const root = document.documentElement

  root.dataset.themePreference = preference
  root.dataset.theme = resolved
  root.style.colorScheme = resolved
  window.localStorage.setItem(storageKey, preference)

  return resolved
}

export const getStoredThemePreference = (): ThemePreference => {
  return normalizeThemePreference(window.localStorage.getItem(storageKey))
}

export const watchSystemTheme = (onChange: () => void) => {
  const media = window.matchMedia(systemDarkQuery)
  media.addEventListener('change', onChange)

  return () => {
    media.removeEventListener('change', onChange)
  }
}
