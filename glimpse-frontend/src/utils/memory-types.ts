import type { Memory } from '@/api/client'

export const isTextMemory = (memory: Pick<Memory, 'memory_type'>) =>
  memory.memory_type === 'text'

/** 展示给用户的文本：用户键入的说明优先，其次才是 AI 摘要。 */
export const getMemoryDisplayText = (
  memory: Pick<Memory, 'ai_summary' | 'user_text'>,
) => (memory.user_text?.trim() ? memory.user_text : memory.ai_summary)

/** 记忆是否携带用户键入的说明（此类记忆的 AI 摘要仅作检索资源，不展示）。 */
export const hasUserNote = (memory: Pick<Memory, 'user_text'>) =>
  Boolean(memory.user_text?.trim())
