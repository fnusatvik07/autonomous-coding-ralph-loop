const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`)
  return res.json()
}

async function post<T>(path: string, body?: Record<string, any>): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  })
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`)
  return res.json()
}

export const api = {
  health: () => get<any>('/health'),
  config: () => get<any>('/config'),
  state: () => get<any>('/state'),
  prd: () => get<any>('/prd'),
  sessions: () => get<any[]>('/sessions'),
  analytics: () => get<any>('/analytics'),
  progress: () => get<{ content: string }>('/progress'),
  guardrails: () => get<{ content: string }>('/guardrails'),
  reflections: () => get<{ content: string }>('/reflections'),
  files: () => get<any[]>('/files'),
  fileContent: (path: string) => get<any>(`/files/${path}`),
  gitLog: () => get<any[]>('/git/log'),
  startRun: (params: any) => post<{ run_id: string; status: string }>('/runs', params),
  approveRun: (id: string) => post<any>(`/runs/${id}/approve`),
  rejectRun: (id: string) => post<any>(`/runs/${id}/reject`),
  stopRun: (id: string) => post<any>(`/runs/${id}/stop`),
}
