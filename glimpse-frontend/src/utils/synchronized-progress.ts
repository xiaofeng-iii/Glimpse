export const MEMORY_ANALYSIS_PROGRESS_DURATION_MS = 1350

export const calculateSynchronizedStartTime = (
  timelineTime: number,
  wallTime: number,
  duration = MEMORY_ANALYSIS_PROGRESS_DURATION_MS,
) => timelineTime - (wallTime % duration)

export const startSynchronizedProgress = (element: HTMLElement): Animation | null => {
  if (
    typeof element.animate !== 'function'
    || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  ) {
    return null
  }

  const animation = element.animate(
    [
      { transform: 'translateX(-110%)' },
      { transform: 'translateX(240%)' },
    ],
    {
      duration: MEMORY_ANALYSIS_PROGRESS_DURATION_MS,
      easing: 'ease-in-out',
      iterations: Infinity,
    },
  )
  const timelineTime = Number(document.timeline.currentTime ?? performance.now())
  animation.startTime = calculateSynchronizedStartTime(timelineTime, Date.now())
  return animation
}
