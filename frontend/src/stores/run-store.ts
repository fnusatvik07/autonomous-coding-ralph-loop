import { create } from 'zustand'
import type { StreamEvent, Task } from '@/api/types'

export type Phase =
  | 'idle'
  | 'generating_spec'
  | 'approve_spec'
  | 'generating_prd'
  | 'approve_prd'
  | 'coding'
  | 'completed'
  | 'error'

interface Store {
  runId: string | null
  phase: Phase
  events: StreamEvent[]
  tasks: Task[]
  prd: any
  specContent: string
  cost: number
  iteration: number
  currentTask: string | null
  currentPhase: string | null
  error: string | null

  dispatch: (event: StreamEvent) => void
  setTasks: (t: Task[]) => void
  setPrd: (p: any) => void
  setPhase: (p: Phase) => void
  reset: () => void
}

const INIT = {
  runId: null, phase: 'idle' as Phase, events: [] as StreamEvent[], tasks: [] as Task[],
  prd: null, specContent: '', cost: 0, iteration: 0,
  currentTask: null, currentPhase: null, error: null,
}

export const useStore = create<Store>((set) => ({
  ...INIT,

  dispatch: (e) => set((s) => {
    const events = [...s.events, e].slice(-2000)
    const u: Partial<Store> = { events }

    switch (e.type) {
      case 'run_started':
        u.runId = e.data.run_id ?? s.runId
        u.phase = e.data.phase === 'generating_spec' ? 'generating_spec'
          : e.data.phase === 'generating_prd' ? 'generating_prd' : 'coding'
        break
      case 'spec_awaiting_approval':
        if (e.data.phase === 'spec') {
          u.phase = 'approve_spec'
          u.specContent = e.data.spec_content ?? ''
        } else {
          u.phase = 'approve_prd'
          u.prd = e.data.prd
          u.tasks = e.data.prd?.tasks ?? s.tasks
        }
        break
      case 'run_completed':
        u.phase = e.data.rejected ? 'idle' : 'completed'
        if (e.data.total_cost) u.cost = e.data.total_cost
        break
      case 'run_error':
        u.phase = 'error'; u.error = e.data.error
        break
      case 'iteration_started':
        u.phase = 'coding'; u.iteration = e.data.iteration; u.currentTask = e.data.task_id
        break
      case 'task_status_changed':
        u.tasks = s.tasks.map(t => t.id === e.data.task_id ? { ...t, status: e.data.new_status } : t)
        break
      case 'session_complete':
        u.currentPhase = e.data.phase
        if (e.data.cost_usd) u.cost = s.cost + e.data.cost_usd
        break
    }
    return u
  }),

  setTasks: (tasks) => set({ tasks }),
  setPrd: (prd) => set({ prd, tasks: prd?.tasks ?? [] }),
  setPhase: (phase) => set({ phase }),
  reset: () => set(INIT),
}))
