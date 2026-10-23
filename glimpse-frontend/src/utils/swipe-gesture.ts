// 通知浮层（swipe toast）的拖拽判定纯函数：数值常量与几何/速度判定集中于此，
// 组件只做事件接线；所有函数无副作用，可在 jsdom 下全量单测。
// 交互构造与参数取自 vue-bits micro/swipe-toast 的组件源码（registry JSON），
// 视觉与集成本地化，见 THIRD_PARTY_NOTICES。

/** 按下后位移超过该值才算拖拽，小于则为点击（不触发手势）。 */
export const DRAG_DEAD_ZONE_PX = 3
/** 向上拖的橡皮筋阻尼尺度（px）。 */
export const RUBBERBAND_RESIST_PX = 24
/** 橡皮筋曲线常数。 */
export const RUBBERBAND_CONSTANT = 0.55
/** 松手瞬间的向下速度超过该值即视为轻弹关闭（px/ms）。 */
export const FLICK_VELOCITY_PX_PER_MS = 0.11
/** 向下位移达到该值即视为拖拽关闭。 */
export const DISMISS_DISTANCE_PX = 40
/** 速度样本上限（只保留最近若干采样）。 */
export const VELOCITY_SAMPLE_LIMIT = 4

export type SwipeSample = [time: number, offset: number]

/** 原始纵向位移（向下为正、向上为负）→ 应用后的位移：向下直通，向上按
 * 有理函数阻尼（(over·d·c)/(d+c·|over|)，d=24、c=0.55，渐近 -24px），
 * 小位移段比指数曲线更跟手。 */
export const rubberband = (over: number): number => {
  if (over >= 0) return over
  const magnitude = Math.abs(over)
  return (
    (over * RUBBERBAND_RESIST_PX * RUBBERBAND_CONSTANT)
    / (RUBBERBAND_RESIST_PX + RUBBERBAND_CONSTANT * magnitude)
  )
}

/** 松手时的关闭判定：整体在向下（dy > 0），且要么轻弹够快，要么位移够远。 */
export const shouldDismiss = (dy: number, downwardVelocity: number): boolean =>
  dy > 0
  && (downwardVelocity > FLICK_VELOCITY_PX_PER_MS
    || (dy >= DISMISS_DISTANCE_PX && downwardVelocity >= 0))

/**
 * 由采样序列求向下速度（px/ms）：首尾作差。末样本距当前超过 100ms 视为
 * 停滞，速度归零。样本记录的是「应用后的卡片位移」，向上拖时阻尼会同步
 * 衰减向上速度（demo 同构）。
 */
export const velocityOf = (samples: SwipeSample[], now: number): number => {
  if (samples.length < 2) return 0
  const [t0, y0] = samples[0]
  const [t1, y1] = samples[samples.length - 1]
  if (now - t1 > 100) return 0
  return (y1 - y0) / Math.max(1, t1 - t0)
}

/** 追加采样并裁剪到窗口上限。 */
export const pushSample = (samples: SwipeSample[], time: number, offset: number): void => {
  samples.push([time, offset])
  if (samples.length > VELOCITY_SAMPLE_LIMIT) samples.shift()
}
