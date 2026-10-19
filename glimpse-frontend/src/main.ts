import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import './styles/main.css'
import { initializeBackendRuntime } from './config/runtime'
import { hintTooltip, installNativeTooltipGuard } from './directives/hint-tooltip'
import { applyThemePreference, getStoredThemePreference } from './utils/theme'
import { getStoredLanguagePreference, setLanguagePreference } from './utils/i18n'

// 应用层铁幕：无条件拦截 WebView 原生右键菜单。引擎侧已在 WebView2 settings
// 里关闭默认菜单（main.rs），这里是双保险，注册于应用挂载前以保证顺序最早。
window.addEventListener(
  'contextmenu',
  (event) => event.preventDefault(),
  { capture: true },
)

installNativeTooltipGuard()

const bootstrap = async () => {
  applyThemePreference(getStoredThemePreference())
  setLanguagePreference(getStoredLanguagePreference())

  const app = createApp(App)
  const pinia = createPinia()

  app.use(pinia)
  app.use(router)
  app.directive('hint-tooltip', hintTooltip)
  app.mount('#app')

  void initializeBackendRuntime()
}

void bootstrap()
