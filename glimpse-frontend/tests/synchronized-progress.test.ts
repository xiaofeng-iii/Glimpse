import { describe, expect, it } from 'vitest'
import {
  MEMORY_ANALYSIS_PROGRESS_DURATION_MS,
  calculateSynchronizedStartTime,
} from '@/utils/synchronized-progress'

describe('synchronized progress clock', () => {
  it('maps independently mounted bars to the same wall-clock phase', () => {
    const firstWallTime = 10_000
    const secondWallTime = 10_420
    const firstTimelineTime = 2_000
    const secondTimelineTime = 2_420
    const firstStart = calculateSynchronizedStartTime(firstTimelineTime, firstWallTime)
    const secondStart = calculateSynchronizedStartTime(secondTimelineTime, secondWallTime)

    const firstPhaseAtSecondMount = (
      secondTimelineTime - firstStart
    ) % MEMORY_ANALYSIS_PROGRESS_DURATION_MS
    const secondPhase = (secondTimelineTime - secondStart) % MEMORY_ANALYSIS_PROGRESS_DURATION_MS

    expect(secondPhase).toBe(secondWallTime % MEMORY_ANALYSIS_PROGRESS_DURATION_MS)
    expect(firstPhaseAtSecondMount).toBe(secondPhase)
  })
})
