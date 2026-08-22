export const CURRENT_ONBOARDING_VERSION = 1
export const ONBOARDING_VERSION_STORAGE_KEY = 'glimpse.onboardingVersion'

const readStoredOnboardingVersion = () => {
  if (typeof window === 'undefined') return CURRENT_ONBOARDING_VERSION

  try {
    const storedVersion = Number.parseInt(
      window.localStorage.getItem(ONBOARDING_VERSION_STORAGE_KEY) ?? '',
      10,
    )
    return Number.isFinite(storedVersion) ? storedVersion : 0
  } catch {
    return CURRENT_ONBOARDING_VERSION
  }
}

export const shouldShowOnboarding = () => (
  readStoredOnboardingVersion() < CURRENT_ONBOARDING_VERSION
)

export const completeOnboarding = () => {
  if (typeof window === 'undefined') return

  try {
    window.localStorage.setItem(
      ONBOARDING_VERSION_STORAGE_KEY,
      String(CURRENT_ONBOARDING_VERSION),
    )
  } catch {
    // Storage can be unavailable in restricted webviews. The guide still closes
    // for the current session even when its completion cannot be persisted.
  }
}
