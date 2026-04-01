import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Send, Sliders, MessageSquare, ChevronLeft, Paperclip,
  Sparkles, ArrowRight
} from 'lucide-react'
import { api } from '@/api/client'
import { useStore } from '@/stores/run-store'
import { cn } from '@/lib/utils'

const EXAMPLES = [
  { label: 'REST API', prompt: 'Build a REST API with FastAPI for managing a todo app. Include SQLite database, full CRUD, input validation, error handling, and pytest tests.' },
  { label: 'CLI Tool', prompt: 'Build a Python CLI tool that converts between unit systems (length, weight, temperature). Use argparse, proper package structure, and 20+ pytest tests.' },
  { label: 'URL Shortener', prompt: 'Build a URL shortener with FastAPI. Include click tracking, in-memory cache, rate limiting, statistics endpoint, and comprehensive tests.' },
  { label: 'Web Scraper', prompt: 'Build a Python web scraper that extracts product data from a given URL. Support pagination, output to JSON/CSV, retry logic, and pytest tests.' },
]

export default function NewRunPage() {
  const nav = useNavigate()
  const reset = useStore(s => s.reset)
  const [cfg, setCfg] = useState<any>(null)

  const [task, setTask] = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const [provider, setProvider] = useState('claude-sdk')
  const [model, setModel] = useState('')
  const [budget, setBudget] = useState('')
  const [maxIter, setMaxIter] = useState('50')
  const [loading, setLoading] = useState(false)

  useEffect(() => { api.config().then(setCfg).catch(() => {}) }, [])

  const start = async () => {
    if (!task.trim()) return
    setLoading(true); reset()
    try {
      const r = await api.startRun({
        task, provider, model: model || undefined,
        budget: budget ? +budget : undefined,
        max_iterations: +maxIter || 50,
      })
      useStore.getState().dispatch({
        type: 'run_started', timestamp: '',
        data: { run_id: r.run_id, phase: 'generating_spec' },
      })
      nav('/dashboard')
    } catch (e: any) { alert(e.message) }
    finally { setLoading(false) }
  }

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); start() }
  }

  return (
    <div className="h-full flex flex-col">

      {/* Top bar */}
      <div className="px-6 py-3 border-b flex items-center gap-3">
        <button onClick={() => nav('/')} className="text-muted hover:text-foreground transition-colors">
          <ChevronLeft size={18} />
        </button>
        <h1 className="font-semibold">New Project</h1>
      </div>

      {/* Main content - vertically centered */}
      <div className="flex-1 flex items-center justify-center p-6 overflow-y-auto">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
          className="w-full max-w-3xl">

          {/* Header */}
          <div className="text-center mb-8">
            <motion.div initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay: 0.1 }}
              className="w-14 h-14 rounded-2xl bg-brand-600 flex items-center justify-center mx-auto mb-5 shadow-lg shadow-brand-600/20">
              <MessageSquare size={24} className="text-white" />
            </motion.div>
            <h2 className="text-3xl font-bold mb-2">What do you want to build?</h2>
            <p className="text-muted max-w-md mx-auto">
              Describe your project in plain English. Include features, tech stack, and testing requirements.
            </p>
          </div>

          {/* Input card */}
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
            className="bg-surface-0 rounded-3xl border shadow-elevated overflow-hidden">

            {/* Main textarea */}
            <div className="p-6">
              <textarea
                value={task}
                onChange={e => setTask(e.target.value)}
                onKeyDown={handleKey}
                autoFocus
                rows={7}
                placeholder="Build a REST API with FastAPI for managing a todo app. Include user authentication with JWT tokens, SQLite database, full CRUD operations, input validation, error handling, and comprehensive pytest tests with 20+ test cases..."
                className="w-full text-[15px] leading-relaxed resize-none bg-transparent focus:outline-none placeholder:text-muted/40"
              />
            </div>

            {/* Example prompts */}
            <div className="px-6 pb-4">
              <p className="text-[11px] text-muted mb-2 font-medium uppercase tracking-wider">Try an example</p>
              <div className="flex flex-wrap gap-2">
                {EXAMPLES.map(ex => (
                  <button key={ex.label} onClick={() => setTask(ex.prompt)}
                    className={cn(
                      'text-xs px-3 py-1.5 rounded-full border transition-all',
                      task === ex.prompt
                        ? 'bg-brand-50 dark:bg-brand-700/20 border-brand-300 dark:border-brand-600 text-brand-700 dark:text-brand-300'
                        : 'bg-surface-1 text-muted hover:text-foreground hover:border-brand-200'
                    )}>
                    <Sparkles size={10} className="inline mr-1" />{ex.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Expandable settings */}
            <AnimatePresence>
              {showSettings && (
                <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden border-t">
                  <div className="p-6 grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div>
                      <label className="text-xs font-medium text-muted block mb-1.5">Provider</label>
                      <select value={provider} onChange={e => { setProvider(e.target.value); setModel('') }}
                        className="w-full border rounded-xl p-2.5 text-sm bg-surface-1 focus:outline-none focus:ring-2 focus:ring-brand-500/20">
                        {(cfg?.providers ?? ['claude-sdk']).map((p: string) => <option key={p}>{p}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="text-xs font-medium text-muted block mb-1.5">Model</label>
                      <select value={model} onChange={e => setModel(e.target.value)}
                        className="w-full border rounded-xl p-2.5 text-sm bg-surface-1 focus:outline-none focus:ring-2 focus:ring-brand-500/20">
                        <option value="">Default ({cfg?.default_model?.split('-').slice(0, 2).join('-') ?? 'auto'})</option>
                        {(cfg?.models?.[provider] ?? []).map((m: string) => <option key={m} value={m}>{m}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="text-xs font-medium text-muted block mb-1.5">Budget (USD)</label>
                      <input type="number" step="1" min="0" value={budget} onChange={e => setBudget(e.target.value)} placeholder="Unlimited"
                        className="w-full border rounded-xl p-2.5 text-sm bg-surface-1 focus:outline-none focus:ring-2 focus:ring-brand-500/20" />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-muted block mb-1.5">Max Iterations</label>
                      <input type="number" min="1" max="100" value={maxIter} onChange={e => setMaxIter(e.target.value)}
                        className="w-full border rounded-xl p-2.5 text-sm bg-surface-1 focus:outline-none focus:ring-2 focus:ring-brand-500/20" />
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Bottom toolbar */}
            <div className="px-5 py-3 border-t flex items-center gap-2 bg-surface-1/50">
              <button onClick={() => setShowSettings(!showSettings)}
                className={cn('flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium transition-colors',
                  showSettings ? 'bg-brand-50 dark:bg-brand-700/20 text-brand-700' : 'text-muted hover:text-foreground hover:bg-surface-1')}>
                <Sliders size={13} /> {showSettings ? 'Hide Settings' : 'Settings'}
              </button>

              <div className="flex-1" />

              <span className="text-[11px] text-muted mr-3 hidden sm:flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 rounded bg-surface-2 text-[10px] font-mono">⌘</kbd>
                <kbd className="px-1.5 py-0.5 rounded bg-surface-2 text-[10px] font-mono">↵</kbd>
                to send
              </span>

              <button onClick={start} disabled={!task.trim() || loading}
                className="px-6 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:opacity-30 text-white text-sm font-semibold rounded-xl flex items-center gap-2 shadow-sm transition-all hover:shadow-md active:scale-[0.98]">
                {loading
                  ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  : <><Send size={14} /> Start Building</>
                }
              </button>
            </div>
          </motion.div>

          {/* Helper text */}
          <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}
            className="text-center text-[11px] text-muted/50 mt-5 flex items-center justify-center gap-1.5">
            <ArrowRight size={10} /> Ralph generates spec.md → you approve → prd.json tasks → autonomous coding
          </motion.p>
        </motion.div>
      </div>
    </div>
  )
}
