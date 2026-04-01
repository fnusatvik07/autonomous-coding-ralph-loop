import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  Loader2, Check, ChevronDown, ChevronRight, Terminal,
  FileText, ListChecks, Code2, DollarSign, Wrench, Activity,
  CheckCircle2, XCircle, Clock, ThumbsUp, ThumbsDown,
  Pencil, Download, Copy, MoreHorizontal, Search, Play,
  ArrowRight, Zap, Shield, Bot, RotateCw
} from 'lucide-react'
import { api } from '@/api/client'
import { useStore } from '@/stores/run-store'
import { cn, formatCost, statusConfig } from '@/lib/utils'

/* ═══ Horizontal Stepper ═══ */
const STEPS = [
  { key: 'spec', label: 'Generate Spec', icon: FileText },
  { key: 'review', label: 'Review Spec', icon: Search },
  { key: 'tasks', label: 'Create Tasks', icon: ListChecks },
  { key: 'approve', label: 'Approve Tasks', icon: ThumbsUp },
  { key: 'code', label: 'Code & QA', icon: Code2 },
  { key: 'done', label: 'Delivered', icon: CheckCircle2 },
]

function phaseToStep(phase: string): number {
  switch (phase) {
    case 'generating_spec': return 0
    case 'approve_spec': return 1
    case 'generating_prd': return 2
    case 'approve_prd': return 3
    case 'coding': return 4
    case 'completed': return 5
    default: return -1
  }
}

function Stepper({ phase }: { phase: string }) {
  const current = phaseToStep(phase)
  return (
    <div className="flex items-center gap-0 overflow-x-auto pb-1">
      {STEPS.map((s, i) => {
        const done = i < current
        const active = i === current
        const Icon = s.icon
        return (
          <div key={s.key} className="flex items-center shrink-0">
            <div className={cn(
              'flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium transition-all whitespace-nowrap',
              done && 'text-success',
              active && 'bg-brand-50 dark:bg-brand-700/20 text-brand-700 dark:text-brand-200 shadow-sm border border-brand-200 dark:border-brand-700',
              !done && !active && 'text-muted/50'
            )}>
              {done ? <Check size={13} className="text-success" /> : <Icon size={13} />}
              <span className="hidden sm:inline">{s.label}</span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={cn('w-6 h-px mx-0.5', done ? 'bg-success' : 'bg-border')} />
            )}
          </div>
        )
      })}
    </div>
  )
}

/* ═══ Dynamic Loading Messages ═══ */
const SPEC_MESSAGES = [
  'Analyzing your requirements...',
  'Scanning workspace for existing code...',
  'Designing application architecture...',
  'Planning data models and schemas...',
  'Defining API endpoints...',
  'Writing testing strategy...',
  'Finalizing specification document...',
]

const PRD_MESSAGES = [
  'Reading approved specification...',
  'Identifying atomic implementation steps...',
  'Ordering tasks by dependency...',
  'Writing acceptance criteria...',
  'Assigning test commands...',
  'Generating task breakdown...',
]

function AnimatedLoading({ messages, title }: { messages: string[]; title: string }) {
  const [idx, setIdx] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setIdx(i => (i + 1) % messages.length), 3000)
    return () => clearInterval(t)
  }, [])

  return (
    <div className="flex-1 flex items-center justify-center">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="text-center max-w-md">
        <div className="relative mx-auto mb-6 w-16 h-16">
          <div className="absolute inset-0 rounded-2xl bg-brand-500/20 animate-ping" />
          <div className="relative w-16 h-16 rounded-2xl bg-brand-600 flex items-center justify-center shadow-lg shadow-brand-600/20">
            <Loader2 size={28} className="text-white animate-spin" />
          </div>
        </div>
        <h2 className="text-xl font-bold mb-3">{title}</h2>
        <AnimatePresence mode="wait">
          <motion.p key={idx} initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }}
            className="text-sm text-muted">
            {messages[idx]}
          </motion.p>
        </AnimatePresence>
        {/* Progress dots */}
        <div className="flex items-center justify-center gap-1.5 mt-6">
          {messages.map((_, i) => (
            <div key={i} className={cn('w-1.5 h-1.5 rounded-full transition-all duration-300', i <= idx ? 'bg-brand-500' : 'bg-border')} />
          ))}
        </div>
      </motion.div>
    </div>
  )
}

/* ═══ Main Dashboard ═══ */
export default function DashboardPage() {
  const { phase, prd, specContent, runId, tasks, error } = useStore()
  const nav = useNavigate()

  const { data: state } = useQuery({ queryKey: ['state'], queryFn: api.state, refetchInterval: 3000 })
  const setTasks = useStore(s => s.setTasks)
  const setPrd = useStore(s => s.setPrd)
  useEffect(() => {
    if (state?.prd?.tasks && tasks.length === 0) { setTasks(state.prd.tasks); setPrd(state.prd) }
  }, [state])

  if (phase === 'idle' && !state?.prd) return <Empty />
  if (phase === 'error') return <Error message={error} />

  return (
    <div className="h-full flex flex-col">
      {/* Stepper at top */}
      <div className="px-6 pt-4 pb-2 border-b bg-surface-0 shrink-0">
        <Stepper phase={phase} />
      </div>

      {/* Content based on phase */}
      {phase === 'generating_spec' && <AnimatedLoading messages={SPEC_MESSAGES} title="Generating Specification" />}
      {phase === 'approve_spec' && <SpecReview content={specContent} runId={runId} />}
      {phase === 'generating_prd' && <AnimatedLoading messages={PRD_MESSAGES} title="Breaking Down Into Tasks" />}
      {phase === 'approve_prd' && <PRDReview prd={prd} runId={runId} />}
      {(phase === 'coding' || phase === 'completed') && <CodingView />}
    </div>
  )
}

function Empty() {
  const nav = useNavigate()
  return (
    <div className="h-full flex items-center justify-center">
      <div className="text-center">
        <div className="w-14 h-14 rounded-2xl bg-surface-1 flex items-center justify-center mx-auto mb-4">
          <Terminal size={22} className="text-muted" />
        </div>
        <p className="text-muted mb-3 font-medium">No active run</p>
        <p className="text-xs text-muted/60 mb-4">Start a new project to see the autonomous coding dashboard</p>
        <button onClick={() => nav('/new')} className="px-5 py-2 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium rounded-xl transition-colors">
          Start a Project
        </button>
      </div>
    </div>
  )
}

/* ═══ Spec Review — Full Width, Editable ═══ */
function SpecReview({ content, runId }: { content: string; runId: string | null }) {
  const [loading, setLoading] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editContent, setEditContent] = useState(content)
  const setPhase = useStore(s => s.setPhase)

  useEffect(() => { setEditContent(content) }, [content])

  const approve = async () => {
    if (!runId) return; setLoading(true)
    try { await api.approveRun(runId) } catch (e: any) { alert(e.message) }
    finally { setLoading(false) }
  }

  const copySpec = () => { navigator.clipboard.writeText(content); }
  const downloadSpec = () => {
    const blob = new Blob([content], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'spec.md'; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Toolbar */}
      <div className="px-6 py-3 flex items-center gap-3 border-b shrink-0">
        <FileText size={16} className="text-brand-600" />
        <h2 className="font-semibold">Application Specification</h2>
        <span className="text-xs text-muted bg-surface-1 px-2 py-0.5 rounded-full">spec.md</span>
        <div className="flex-1" />
        <button onClick={() => setEditing(!editing)} className={cn('flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs transition-colors', editing ? 'bg-brand-50 text-brand-700' : 'text-muted hover:text-foreground hover:bg-surface-1')}>
          <Pencil size={12} /> {editing ? 'Preview' : 'Edit'}
        </button>
        <button onClick={copySpec} className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs text-muted hover:text-foreground hover:bg-surface-1"><Copy size={12} /> Copy</button>
        <button onClick={downloadSpec} className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs text-muted hover:text-foreground hover:bg-surface-1"><Download size={12} /> Download</button>
        <div className="w-px h-6 bg-border mx-1" />
        <button onClick={() => { if (runId) api.rejectRun(runId); setPhase('idle') }}
          className="px-3 py-1.5 rounded-lg text-xs text-danger hover:bg-danger/5 flex items-center gap-1"><ThumbsDown size={12} /> Reject</button>
        <button onClick={approve} disabled={loading}
          className="px-4 py-1.5 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-xs font-medium flex items-center gap-1 shadow-sm">
          {loading ? <Loader2 size={12} className="animate-spin" /> : <ThumbsUp size={12} />} Approve
        </button>
      </div>

      {/* Full-width content */}
      <div className="flex-1 overflow-y-auto p-6">
        {editing ? (
          <textarea value={editContent} onChange={e => setEditContent(e.target.value)}
            className="w-full h-full font-mono text-sm bg-surface-1 border rounded-xl p-6 resize-none focus:outline-none focus:ring-2 focus:ring-brand-500/20" />
        ) : (
          <div className="max-w-4xl mx-auto">
            <div className="md-spec text-[15px]">
              <Markdown remarkPlugins={[remarkGfm]}>{content || '*Generating...*'}</Markdown>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/* ═══ PRD Review — Full Width, Better Cards ═══ */
function PRDReview({ prd, runId }: { prd: any; runId: string | null }) {
  const [loading, setLoading] = useState(false)
  const setPhase = useStore(s => s.setPhase)

  const approve = async () => {
    if (!runId) return; setLoading(true)
    try { await api.approveRun(runId) } catch (e: any) { alert(e.message) }
    finally { setLoading(false) }
  }

  if (!prd) return <AnimatedLoading messages={PRD_MESSAGES} title="Generating Tasks" />

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Toolbar */}
      <div className="px-6 py-3 flex items-center gap-3 border-b shrink-0">
        <ListChecks size={16} className="text-brand-600" />
        <h2 className="font-semibold">Task List</h2>
        <span className="text-xs text-muted bg-surface-1 px-2 py-0.5 rounded-full">{prd.tasks?.length} tasks</span>
        <div className="flex-1" />
        <button onClick={() => { if (runId) api.rejectRun(runId); setPhase('idle') }}
          className="px-3 py-1.5 rounded-lg text-xs text-danger hover:bg-danger/5 flex items-center gap-1"><ThumbsDown size={12} /> Reject</button>
        <button onClick={approve} disabled={loading}
          className="px-4 py-1.5 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-xs font-medium flex items-center gap-1 shadow-sm">
          {loading ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />} Start Coding
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {/* Project header card */}
        <div className="max-w-4xl mx-auto">
          <div className="bg-gradient-to-r from-brand-600 to-brand-500 rounded-2xl p-6 text-white mb-6 shadow-lg">
            <h3 className="text-xl font-bold">{prd.project_name}</h3>
            <p className="text-blue-100 text-sm mt-1 leading-relaxed">{prd.description}</p>
            <div className="flex gap-4 mt-4 text-xs text-blue-200">
              <span>{prd.tasks?.length} tasks</span>
              <span>Ordered by dependency</span>
              <span>Each with acceptance criteria</span>
            </div>
          </div>

          {/* Task list */}
          <div className="space-y-3">
            {prd.tasks?.map((t: any, i: number) => (
              <TaskCard key={t.id} task={t} index={i} total={prd.tasks.length} />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function TaskCard({ task, index, total }: { task: any; index: number; total: number }) {
  const [open, setOpen] = useState(false)
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.05 }}
      className="border rounded-2xl bg-surface-0 shadow-soft overflow-hidden hover:shadow-card transition-shadow">
      <button onClick={() => setOpen(!open)} className="w-full px-5 py-4 flex items-center gap-3 text-left hover:bg-surface-1/50 transition-colors">
        <div className="w-8 h-8 rounded-lg bg-brand-50 dark:bg-brand-700/20 flex items-center justify-center shrink-0">
          <span className="text-xs font-bold text-brand-600">{index + 1}</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-muted">{task.id}</span>
            <span className="font-medium text-sm truncate">{task.title}</span>
          </div>
          <p className="text-xs text-muted truncate mt-0.5">{task.description}</p>
        </div>
        <span className="text-[10px] text-muted shrink-0 bg-surface-1 px-2 py-0.5 rounded">P{task.priority}</span>
        <ChevronDown size={14} className={cn('text-muted transition-transform shrink-0', open && 'rotate-180')} />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }} className="overflow-hidden">
            <div className="px-5 pb-4 border-t pt-3 space-y-3 text-sm">
              <p className="text-muted">{task.description}</p>
              <div>
                <p className="text-[11px] font-semibold text-muted uppercase tracking-wider mb-1.5">Acceptance Criteria</p>
                {task.acceptance_criteria?.map((ac: string, i: number) => (
                  <div key={i} className="flex items-start gap-2 py-1 text-muted">
                    <CheckCircle2 size={13} className="mt-0.5 text-success/40 shrink-0" /> <span className="text-xs">{ac}</span>
                  </div>
                ))}
              </div>
              {task.test_command && (
                <div>
                  <p className="text-[11px] font-semibold text-muted uppercase tracking-wider mb-1">Verification</p>
                  <code className="text-xs bg-surface-1 px-3 py-1.5 rounded-lg block font-mono text-muted">{task.test_command}</code>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

function Error({ message }: { message: string | null }) {
  const nav = useNavigate()
  return (
    <div className="h-full flex items-center justify-center">
      <div className="text-center max-w-md">
        <XCircle size={40} className="text-danger mx-auto mb-3" />
        <h2 className="text-lg font-bold mb-2">Something went wrong</h2>
        <p className="text-sm text-muted mb-4 font-mono bg-surface-1 rounded-xl p-3">{message}</p>
        <button onClick={() => nav('/new')} className="text-sm text-brand-600 hover:underline">Try again</button>
      </div>
    </div>
  )
}

/* ═══ Coding Dashboard — Rich Terminal ═══ */
function CodingView() {
  const { events, tasks, cost, iteration, currentTask, currentPhase: agentPhase, phase, prd } = useStore()
  const termRef = useRef<HTMLDivElement>(null)
  const { data: state } = useQuery({ queryKey: ['state'], queryFn: api.state, refetchInterval: 3000 })

  const displayTasks = tasks.length > 0 ? tasks : (state?.prd?.tasks ?? [])

  useEffect(() => { if (termRef.current) termRef.current.scrollTop = termRef.current.scrollHeight }, [events.length])

  const termEvents = events.filter(e => ['agent_text', 'agent_tool_call', 'iteration_started', 'session_complete', 'qa_result', 'run_completed'].includes(e.type))
  const passed = displayTasks.filter((t: any) => t.status === 'passed').length
  const total = displayTasks.length
  const pct = total > 0 ? (passed / total) * 100 : 0
  const currentTaskObj = displayTasks.find((t: any) => t.id === currentTask)

  return (
    <div className="flex-1 flex overflow-hidden">
      {/* Left: Tasks */}
      <div className="w-60 border-r overflow-y-auto p-4 space-y-1 shrink-0 bg-surface-0">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] font-semibold text-muted uppercase tracking-wider">Tasks</span>
          <span className="text-xs font-mono text-brand-600 font-bold">{passed}/{total}</span>
        </div>
        <div className="h-1.5 bg-surface-2 rounded-full mb-3 overflow-hidden">
          <motion.div animate={{ width: `${pct}%` }} className="h-full bg-success rounded-full" transition={{ duration: 0.7 }} />
        </div>
        {displayTasks.map((t: any) => {
          const sc = statusConfig[t.status] ?? statusConfig.pending
          const isCurrent = t.id === currentTask
          return (
            <div key={t.id} className={cn('flex items-center gap-2 px-3 py-2.5 rounded-xl text-xs transition-all',
              isCurrent ? 'bg-brand-50 dark:bg-brand-700/20 border border-brand-200 dark:border-brand-700 shadow-sm' : 'hover:bg-surface-1')}>
              <div className={cn('w-2 h-2 rounded-full shrink-0', sc.dot, isCurrent && 'animate-pulse-slow')} />
              <span className="truncate flex-1">{t.title}</span>
              {t.status === 'passed' && <Check size={12} className="text-success shrink-0" />}
            </div>
          )
        })}
      </div>

      {/* Center: Terminal with context banner */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Context banner */}
        <div className="px-4 py-2.5 border-b bg-surface-0 flex items-center gap-3 shrink-0">
          {currentTask && (
            <>
              <div className="flex items-center gap-1.5 text-xs font-medium">
                <div className="w-5 h-5 rounded bg-brand-600 flex items-center justify-center text-white text-[10px] font-bold">{iteration}</div>
                <span className="text-muted">Iteration</span>
              </div>
              <div className="w-px h-4 bg-border" />
              <div className="flex items-center gap-1.5 text-xs">
                <Code2 size={12} className="text-brand-500" />
                <span className="font-mono text-brand-600">{currentTask}</span>
                {currentTaskObj && <span className="text-muted truncate max-w-[200px]">— {currentTaskObj.title}</span>}
              </div>
              <div className="w-px h-4 bg-border" />
              {agentPhase && (
                <div className="flex items-center gap-1.5 text-xs">
                  {agentPhase === 'coding' && <><Bot size={12} className="text-brand-500" /><span className="text-brand-600 font-medium">Coding</span></>}
                  {agentPhase === 'qa' && <><Shield size={12} className="text-success" /><span className="text-success font-medium">QA Review</span></>}
                  {agentPhase?.startsWith('healer') && <><Wrench size={12} className="text-warning" /><span className="text-warning font-medium">Healing</span></>}
                </div>
              )}
            </>
          )}
          <div className="flex-1" />
          {phase === 'coding' && <span className="text-[11px] text-brand-600 font-medium flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse-slow" /> Live</span>}
          {phase === 'completed' && <span className="text-[11px] text-success font-medium flex items-center gap-1"><Check size={11} /> Complete</span>}
          <span className="text-[11px] text-muted font-mono">{formatCost(cost)}</span>
        </div>

        {/* Terminal */}
        <div ref={termRef} className="flex-1 overflow-y-auto p-4 terminal">
          {termEvents.length === 0 && <span className="text-gray-500">Waiting for agent...</span>}
          {termEvents.map((e, i) => (
            <div key={i}>
              {e.type === 'iteration_started' && (
                <div className="mt-4 mb-2 flex items-center gap-2">
                  <div className="h-px flex-1 bg-gray-700" />
                  <span className="text-blue-400 text-xs font-semibold shrink-0 flex items-center gap-1.5">
                    <Zap size={10} /> {e.data.task_id}: {e.data.task_title}
                  </span>
                  <div className="h-px flex-1 bg-gray-700" />
                </div>
              )}
              {e.type === 'agent_text' && <span className="text-gray-200">{e.data.text}</span>}
              {e.type === 'agent_tool_call' && <span className="text-cyan-600/60">{'  > '}{e.data.tool_name}</span>}
              {e.type === 'session_complete' && (
                <div className="text-gray-600 text-[11px] mt-1 flex items-center gap-2">
                  <span className="bg-gray-800 px-1.5 py-0.5 rounded">{e.data.phase}</span>
                  {formatCost(e.data.cost_usd ?? 0)} | {e.data.tool_calls ?? 0} tools
                </div>
              )}
              {e.type === 'qa_result' && (
                <div className={cn('text-xs mt-1.5 flex items-center gap-1.5 font-medium',
                  e.data.passed ? 'text-green-400' : 'text-red-400')}>
                  {e.data.passed ? <><CheckCircle2 size={12} /> QA PASSED</> : <><XCircle size={12} /> QA FAILED</>}
                </div>
              )}
              {e.type === 'run_completed' && (
                <div className="mt-4 p-3 bg-green-900/30 border border-green-800/50 rounded-xl text-green-400 font-bold flex items-center gap-2">
                  <CheckCircle2 size={16} /> ALL TASKS COMPLETE — {formatCost(e.data.total_cost ?? 0)}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Right: Metrics */}
      <div className="w-48 border-l p-4 space-y-3 overflow-y-auto shrink-0 bg-surface-0">
        <p className="text-[11px] font-semibold text-muted uppercase tracking-wider">Metrics</p>
        <Metric icon={DollarSign} label="Cost" value={formatCost(cost)} />
        <Metric icon={Activity} label="Iteration" value={`${iteration}/${total}`} />
        <Metric icon={Wrench} label="Tools" value={String(events.filter(e => e.type === 'agent_tool_call').length)} />
        <div className="border rounded-xl p-3">
          <p className="text-[10px] text-muted mb-1">Progress</p>
          <div className="text-lg font-bold font-mono text-brand-600">{Math.round(pct)}%</div>
          <div className="h-1 bg-surface-2 rounded-full mt-1.5 overflow-hidden">
            <motion.div animate={{ width: `${pct}%` }} className="h-full bg-success rounded-full" />
          </div>
        </div>
      </div>
    </div>
  )
}

function Metric({ icon: I, label, value }: { icon: any; label: string; value: string }) {
  return (
    <div className="border rounded-xl p-3 flex items-center gap-2.5">
      <I size={14} className="text-muted shrink-0" />
      <div><p className="text-[10px] text-muted">{label}</p><p className="text-sm font-semibold font-mono">{value}</p></div>
    </div>
  )
}
