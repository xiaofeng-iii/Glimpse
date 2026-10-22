// 诊断队列要抢在一切业务日志之前就位，因此这行 import 排最前。
import './utils/diagnostics'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import './styles/main.css'
import { initializeBackendRuntime } from './config/runtime'
import { hintTooltip, installNativeTooltipGuard } from './directives/hint-tooltip'
import { logger } from './utils/logger'
import { applyThemePreference, getStoredThemePreference } from './utils/theme'
import { getStoredLanguagePreference, setLanguagePreference } from './utils/i18n'

// 启动早期与渲染期未捕获错误的最后防线；消息经统一脱敏后进诊断日志。
window.addEventListener('error', (event) => {
  if (event.error) {
    logger.error('Uncaught window error: %s', event.error)
  } else if (event.message) {
    logger.error(`Uncaught window error: ${event.message}`)
  }
})
window.addEventListener('unhandledrejection', (event) => {
  logger.error('Unhandled promise rejection: %s', event.reason)
})

// 应用层铁幕：无条件拦截 WebView 原生右键菜单。引擎侧已在 WebView2 settings
// 里关闭默认菜单（main.rs），这里是双保险，注册于应用挂载前以保证顺序最早。
window.addEventListener(
  'contextmenu',
  (event) => event.preventDefault(),
  { capture: true },
)

installNativeTooltipGuard()

// dragDropEnabled 关闭后（tauri.conf.json，为启用标签拖动排序等 HTML5 拖拽），
// 从资源管理器拖文件落到窗口非放置区的默认行为是把窗口导航到该文件、顶替整个
// 应用页面；这里全局拦掉文件类拖拽的默认行为，真正的放置目标（添加记忆对话框）
// 各自的处理器不受影响。标签排序等应用内拖拽 types 不含 Files，不会被波及。
const isFileDrag = (event: DragEvent) => event.dataTransfer?.types.includes('Files') ?? false
window.addEventListener('dragover', (event) => {
  if (isFileDrag(event)) event.preventDefault()
})
window.addEventListener('drop', (event) => {
  if (isFileDrag(event)) event.preventDefault()
})

const bootstrap = async () => {
  applyThemePreference(getStoredThemePreference())
  setLanguagePreference(getStoredLanguagePreference())

  const app = createApp(App)
  const pinia = createPinia()

  // 设置 errorHandler 后 Vue 不再默认 console.error，这里统一接管。
  app.config.errorHandler = (error, _instance, info) => {
    logger.error(`Vue error (${info}): %s`, error)
  }
  app.use(pinia)
  app.use(router)
  app.directive('hint-tooltip', hintTooltip)
  app.mount('#app')

  void initializeBackendRuntime().catch((error) => {
    logger.error('Backend runtime bootstrap failed: %s', error)
  })
}

void bootstrap().catch((error) => {
  logger.error('App bootstrap failed: %s', error)
})
