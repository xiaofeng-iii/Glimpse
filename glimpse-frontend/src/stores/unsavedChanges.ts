import { defineStore } from 'pinia'

type LeaveGuard = () => boolean | Promise<boolean>

export const useUnsavedChangesStore = defineStore('unsaved-changes', () => {
  const guards = new Map<symbol, LeaveGuard>()

  const register = (guard: LeaveGuard) => {
    const id = Symbol('leave-guard')
    guards.set(id, guard)
    return () => guards.delete(id)
  }

  const canLeave = async () => {
    for (const guard of guards.values()) {
      if (!(await guard())) return false
    }
    return true
  }

  return {
    register,
    canLeave,
  }
})
