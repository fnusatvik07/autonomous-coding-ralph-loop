import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  Loader2, Check, X, ChevronDown, ChevronRight, Terminal,
  FileText, ListChecks, Code2, DollarSign, Wrench, Activity,
  CheckCircle2, XCircle, Clock, ThumbsUp, ThumbsDown, Eye
} from 'lucide-react'
import { api } from '@/api/client'
import { useStore } from '@/stores/run-store'
import { cn, formatCost, statusConfig } from '@/lib/utils'

/* ─── Step Indicator ─── */
function Steps({ current }: { current: number }) {
  const steps = [
    { label: 'Spec', icon: FileText },
    { label: 'Tasks', icon: ListChecks },
    { label: 'Coding', icon: Code2 },
    { label: 'Done', icon: CheckCircle2 },
  ]
  return (
    <div className="flex items-center gap-1 mb-6">
      {steps.map((s, i) => {
        const done = i < current
        const active = i === current
        return (
          <div key={i} className="flex items-center gap-1">
            <div className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
              done && 'bg-success/10 text-success',
              active && 'bg-brand-50 dark:bg-brand-700/20 text-brand-700 dark:text-brand-200 shadow-sm',
              !done && !active && 'text-muted'
            )}>
              {done ? <Check size={12} /> : <s.icon size={12} />}
              {s.label}
            </div>
            {i < steps.length - 1 && <ChevronRight size={14} className="text-muted/40" />}
          </div>
        )
      })}
    </div>
  )
}

/* ─── Main Dashboard ─── */
export default function DashboardPage() {
  const { phase, prd, specContent, runId, tasks, error } = useStore()
  const nav = useNavigate()

  // Load initial data
  const { data: state } = useQuery({ queryKey: ['state'], queryFn: api.state, refetchInterval: 3000 })
  const setTasks = useStore(s => s.setTasks)
  const setPrd = useStore(s => s.setPrd)
  useEffect(() => {
    if (state?.prd?.tasks && tasks.length === 0) {
      setTasks(state.prd.tasks)
      setPrd(state.prd)
    }
  }, [state])

  if (phase === 'idle' && !state?.prd) {
    return <Empty />
  }
  if (phase === 'generating_spec') return <Loading step={0} title="Generating Application Spec" sub="Analyzing your task, reading workspace, writing spec.md..." />
  if (phase === 'approve_spec') return <SpecReview content={specContent} runId={runId} />
  if (phase === 'generating_prd') return <Loading step={1} title="Breaking Down into Tasks" sub="Converting approved spec into atomic coding tasks (prd.json)..." />
  if (phase === 'approve_prd') return <PRDReview prd={prd} runId={runId} />
  if (phase === 'error') return <Error message={error} />
  return <CodingView />
}

/* ─── Empty State ─── */
function Empty() {
  const nav = useNavigate()
  return (
    <div className="h-full flex items-center justify-center">
      <div className="text-center">
        <div className="w-12 h-12 rounded-xl bg-surface-1 flex items-center justify-center mx-auto mb-4">
          <Terminal size={20} className="text-muted" />
        </div>
        <p className="text-muted mb-3">No active run</p>
        <button onClick={() => nav('/')} className="text-sm text-brand-600 hover:underline">Start a new project</button>
      </div>
    </div>
  )
}

/* ─── Loading Spinner ─── */
function Loading({ step, title, sub }: { step: number; title: string; sub: string }) {
  return (
    <div className="h-full flex items-center justify-center p-6">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="max-w-md w-full">
        <Steps current={step} />
        <div className="text-center py-12">
          <Loader2 size={36} className="text-brand-500 animate-spin mx-auto mb-5" />
          <h2 className="text-xl font-bold mb-2">{title}</h2>
          <p className="text-sm text-muted leading-relaxed">{sub}</p>
        </div>
      </motion.div>
    </div>
  )
}

/* ─── Spec Review (full screen markdown) ─── */
function SpecReview({ content, runId }: { content: string; runId: string | null }) {
  const [loading, setLoading] = useState(false)
  const setPhase = useStore(s => s.setPhase)

  const approve = async () => {
    if (!runId) return; setLoading(true)
    try { await api.approveRun(runId) } catch (e: any) { alert(e.message) }
    finally { setLoading(false) }
  }

  return (
    <div className="h-full flex flex-col">
      <div className="px-6 pt-6"><Steps current={0} /></div>

      {/* Header */}
      <div className="px-6 pb-4 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold">Review Application Spec</h2>
          <p className="text-sm text-muted">Read through the specification below. Approve to proceed to task breakdown.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => { if (runId) api.rejectRun(runId); setPhase('idle') }}
            className="px-4 py-2 border rounded-xl text-sm text-danger hover:bg-danger/5 flex items-center gap-1.5 transition-colors">
            <ThumbsDown size={14} /> Reject
          </button>
          <button onClick={approve} disabled={loading}
            className="px-5 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-xl text-sm font-medium flex items-center gap-1.5 shadow-sm transition-colors">
            {loading ? <Loader2 size={14} className="animate-spin" /> : <ThumbsUp size={14} />}
            Approve Spec
          </button>
        </div>
      </div>

      {/* Full-screen spec viewer */}
      <div className="flex-1 overflow-y-auto px-6 pb-6">
        <div className="max-w-3xl mx-auto bg-surface-0 border rounded-2xl p-8 shadow-soft">
          <div className="md-spec">
            <Markdown remarkPlugins={[remarkGfm]}>{content || '*Generating spec...*'}</Markdown>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ─── PRD Review (task cards) ─── */
function PRDReview({ prd, runId }: { prd: any; runId: string | null }) {
  const [loading, setLoading] = useState(false)
  const setPhase = useStore(s => s.setPhase)

  const approve = async () => {
    if (!runId) return; setLoading(true)
    try { await api.approveRun(runId) } catch (e: any) { alert(e.message) }
    finally { setLoading(false) }
  }

  if (!prd) return <Loading step={1} title="Generating Tasks" sub="Almost there..." />

  return (
    <div className="h-full flex flex-col">
      <div className="px-6 pt-6"><Steps current={1} /></div>

      <div className="px-6 pb-4 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold">Review Task List</h2>
          <p className="text-sm text-muted">These {prd.tasks?.length} tasks will be coded autonomously, one at a time.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => { if (runId) api.rejectRun(runId); setPhase('idle') }}
            className="px-4 py-2 border rounded-xl text-sm text-danger hover:bg-danger/5 flex items-center gap-1.5">
            <ThumbsDown size={14} /> Reject
          </button>
          <button onClick={approve} disabled={loading}
            className="px-5 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-xl text-sm font-medium flex items-center gap-1.5 shadow-sm">
            {loading ? <Loader2 size={14} className="animate-spin" /> : <ThumbsUp size={14} />}
            Start Coding
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 pb-6">
        <div className="max-w-3xl mx-auto space-y-3">
          {/* Project header */}
          <div className="border rounded-2xl p-5 bg-surface-0 shadow-soft">
            <h3 className="font-bold text-lg text-brand-600">{prd.project_name}</h3>
            <p className="text-sm text-muted mt-1">{prd.description}</p>
          </div>

          {/* Task list */}
          {prd.tasks?.map((t: any) => <TaskCard key={t.id} task={t} />)}
        </div>
      </div>
    </div>
  )
}

function TaskCard({ task }: { task: any }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border rounded-xl bg-surface-0 shadow-soft overflow-hidden">
      <button onClick={() => setOpen(!open)} className="w-full px-5 py-3.5 flex items-center gap-3 text-left hover:bg-surface-1 transition-colors">
        <span className="text-xs font-mono text-brand-600 bg-brand-50 dark:bg-brand-700/20 px-2 py-0.5 rounded">{task.id}</span>
        <span className="font-medium text-sm flex-1">{task.title}</span>
        <span className="text-[10px] text-muted">P{task.priority}</span>
        <ChevronDown size={14} className={cn('text-muted transition-transform', open && 'rotate-180')} />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }} className="overflow-hidden">
            <div className="px-5 pb-4 border-t pt-3 space-y-3 text-sm">
              <p className="text-muted">{task.description}</p>
              <div>
                <p className="text-xs font-semibold text-muted uppercase mb-1.5">Acceptance Criteria</p>
                {task.acceptance_criteria?.map((ac: string, i: number) => (
                  <div key={i} className="flex items-start gap-2 py-0.5 text-muted">
                    <CheckCircle2 size={13} className="mt-0.5 text-success/50 shrink-0" /> {ac}
                  </div>
                ))}
              </div>
              {task.test_command && (
                <div>
                  <p className="text-xs font-semibold text-muted uppercase mb-1">Test Command</p>
                  <code className="text-xs bg-surface-1 px-2.5 py-1 rounded-lg block font-mono">{task.test_command}</code>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

/* ─── Error ─── */
function Error({ message }: { message: string | null }) {
  const nav = useNavigate()
  return (
    <div className="h-full flex items-center justify-center">
      <div className="text-center max-w-md">
        <XCircle size={40} className="text-danger mx-auto mb-3" />
        <h2 className="text-lg font-bold mb-2">Something went wrong</h2>
        <p className="text-sm text-muted mb-4">{message}</p>
        <button onClick={() => nav('/')} className="text-sm text-brand-600 hover:underline">Try again</button>
      </div>
    </div>
  )
}

/* ─── Coding Dashboard (live) ─── */
function CodingView() {
  const { events, tasks, cost, iteration, currentTask, currentPhase, phase, prd } = useStore()
  const termRef = useRef<HTMLDivElement>(null)
  const { data: state } = useQuery({ queryKey: ['state'], queryFn: api.state, refetchInterval: 3000 })

  const displayTasks = tasks.length > 0 ? tasks : (state?.prd?.tasks ?? [])

  useEffect(() => { if (termRef.current) termRef.current.scrollTop = termRef.current.scrollHeight }, [events.length])

  const termEvents = events.filter(e => ['agent_text', 'agent_tool_call', 'iteration_started', 'session_complete', 'qa_result', 'run_completed'].includes(e.type))
  const passed = displayTasks.filter((t: any) => t.status === 'passed').length
  const total = displayTasks.length
  const pct = total > 0 ? (passed / total) * 100 : 0

  return (
    <div className="h-full flex flex-col">
      <div className="px-6 pt-4 pb-2"><Steps current={phase === 'completed' ? 3 : 2} /></div>

      <div className="flex-1 flex overflow-hidden">
        {/* Left: Tasks */}
        <div className="w-64 border-r overflow-y-auto p-4 space-y-1.5 shrink-0">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-muted uppercase tracking-wider">Tasks</span>
            <span className="text-xs font-mono text-muted">{passed}/{total}</span>
          </div>
          {/* Progress bar */}
          <div className="h-1.5 bg-surface-2 rounded-full mb-3 overflow-hidden">
            <div className="h-full bg-success rounded-full transition-all duration-700" style={{ width: `${pct}%` }} />
          </div>
          {displayTasks.map((t: any) => {
            const sc = statusConfig[t.status] ?? statusConfig.pending
            return (
              <div key={t.id} className={cn('flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors',
                t.id === currentTask ? 'bg-brand-50 dark:bg-brand-700/20 border border-brand-200 dark:border-brand-700' : 'hover:bg-surface-1')}>
                <div className={cn('w-2 h-2 rounded-full shrink-0', sc.dot, t.id === currentTask && 'animate-pulse-slow')} />
                <span className="truncate text-xs">{t.title}</span>
              </div>
            )
          })}
        </div>

        {/* Center: Terminal */}
        <div className="flex-1 flex flex-col">
          <div className="px-4 py-2 border-b flex items-center gap-2 text-xs text-muted">
            <Terminal size={12} /> Live Output
            {phase === 'coding' && <span className="ml-auto text-brand-600">Streaming...</span>}
            {phase === 'completed' && <span className="ml-auto text-success font-medium">Complete</span>}
          </div>
          <div ref={termRef} className="flex-1 overflow-y-auto p-4 terminal rounded-none">
            {termEvents.length === 0 && <span className="text-gray-500">Waiting for events...</span>}
            {termEvents.map((e, i) => (
              <div key={i}>
                {e.type === 'iteration_started' && <div className="text-blue-400 font-semibold mt-4 mb-1 border-t border-gray-700 pt-2">{'>>> '}{e.data.task_id}: {e.data.task_title}</div>}
                {e.type === 'agent_text' && <span className="text-gray-200">{e.data.text}</span>}
                {e.type === 'agent_tool_call' && <span className="text-gray-500">{'  > '}{e.data.tool_name}</span>}
                {e.type === 'session_complete' && <div className="text-gray-500 text-xs mt-1">[{e.data.phase}] {formatCost(e.data.cost_usd ?? 0)} | {e.data.tool_calls ?? 0} tools</div>}
                {e.type === 'qa_result' && <div className={e.data.passed ? 'text-green-400 text-xs mt-1' : 'text-red-400 text-xs mt-1'}>QA: {e.data.passed ? 'PASSED' : 'FAILED'}</div>}
                {e.type === 'run_completed' && <div className="text-green-400 font-bold mt-4">ALL TASKS COMPLETE — {formatCost(e.data.total_cost ?? 0)}</div>}
              </div>
            ))}
          </div>
        </div>

        {/* Right: Metrics */}
        <div className="w-52 border-l p-4 space-y-3 overflow-y-auto shrink-0">
          <p className="text-xs font-semibold text-muted uppercase tracking-wider">Metrics</p>
          <Metric icon={DollarSign} label="Cost" value={formatCost(cost)} />
          <Metric icon={Activity} label="Iteration" value={String(iteration)} />
          <Metric icon={Wrench} label="Tools" value={String(events.filter(e => e.type === 'agent_tool_call').length)} />
          {currentPhase && <div className="border rounded-lg p-2.5"><p className="text-[10px] text-muted">Phase</p><p className="text-xs font-semibold capitalize">{currentPhase}</p></div>}
        </div>
      </div>
    </div>
  )
}

function Metric({ icon: I, label, value }: { icon: any; label: string; value: string }) {
  return (
    <div className="border rounded-lg p-2.5 flex items-center gap-2.5">
      <I size={14} className="text-muted" />
      <div><p className="text-[10px] text-muted">{label}</p><p className="text-sm font-semibold font-mono">{value}</p></div>
    </div>
  )
}
