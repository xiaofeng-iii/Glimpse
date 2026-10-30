// 引导展示大字共用的粗体栈：全局 --font-ui 里的 'YaHei UI Adjusted' 度量
// 覆盖面只有 400 档（更粗字重会退化成合成加粗），此栈绕开它让中文落到
// 有真实 Bold 字面的 'Microsoft YaHei'。StrokeText 与 FoldText 共用。
export const DISPLAY_FONT_STACK = "'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
