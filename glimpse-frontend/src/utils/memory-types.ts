import type { Memory } from '@/api/client'

export const isTextMemory = (memory: Pick<Memory, 'memory_type'>) =>
  memory.memory_type === 'text'
