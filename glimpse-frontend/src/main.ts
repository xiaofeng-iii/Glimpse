import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import './styles/main.css'
import { initializeBackendRuntime } from './config/runtime'
import { applyThemePreference, getStoredThemePreference } from './utils/theme'
import { getStoredLanguagePreference, setLanguagePreference } from './utils/i18n'

const bootstrap = async () => {
  applyThemePreference(getStoredThemePreference())
  setLanguagePreference(getStoredLanguagePreference())
  await initializeBackendRuntime()

  const app = createApp(App)
  const pinia = createPinia()

  app.use(pinia)
  app.use(router)
  app.mount('#app')
}

void bootstrap()
