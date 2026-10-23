// 1320 同时是排版分界与侧栏交互分界：侧栏占位后墙面仍保底三列 290px 卡片；
// CSS 在 1319px 以下把侧栏面板变成右侧浮层（见 Home.vue 样式），点外/Esc 关闭
// 只在浮层形态生效。JS 与样式共用同一界线，新增消费方从这里取，不要再刻数字。
export const WIDE_LAYOUT_BREAKPOINT = 1320

export const isWideLayout = () => window.innerWidth >= WIDE_LAYOUT_BREAKPOINT
