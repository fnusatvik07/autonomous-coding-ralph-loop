export type TaskStatus = 'pending' | 'in_progress' | 'passed' | 'failed'

export interface Task {
  id: string
  title: string
  description: string
  acceptance_criteria: string[]
  priority: number
  status: TaskStatus
  test_command: string
  notes: string
}

export interface PRD {
  project_name: string
  branch_name: string
  description: string
  tasks: Task[]
}

export interface Session {
  timestamp: string
  run_id: string
  iteration: number
  phase: string
  task_id: string
  success?: boolean
  passed?: boolean
  error?: string | null
  tool_calls: number
  cost_usd: number
  duration_ms: number
  issues?: string[]
  event?: string
}

export interface Analytics {
  sessions: number
  total_cost: number
  total_duration_ms: number
  total_tool_calls: number
  failures: number
  cost_by_phase: Record<string, number>
}

export interface FileNode {
  name: string
  path: string
  is_dir: boolean
  size: number
  children: FileNode[]
}

export interface FileContent {
  path: string
  content: string
  language: string
  size: number
}

export interface GitCommit {
  hash: string
  message: string
}

export interface StreamEvent {
  type: string
  timestamp: string
  data: Record<string, any>
}

export interface ConfigResponse {
  providers: string[]
  default_provider: string
  default_model: string
  models: Record<string, string[]>
}
