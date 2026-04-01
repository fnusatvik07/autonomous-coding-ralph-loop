import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Send, Sliders, MessageSquare, ChevronLeft, Link2, Upload,
  Sparkles, ArrowRight, FileText, Code2, Globe, Wrench,
  X, Plus, ExternalLink
} from 'lucide-react'
import { api } from '@/api/client'
import { useStore } from '@/stores/run-store'
import { cn } from '@/lib/utils'

const EXAMPLES = [
  { icon: Code2, label: 'REST API', color: 'bg-blue-500', prompt: 'Build a REST API with FastAPI for managing a todo app. Include SQLite database, full CRUD operations, input validation with Pydantic, error handling (404/422), health check endpoint, and comprehensive pytest tests with at least 20 test cases.' },
  { icon: Wrench, label: 'CLI Tool', color: 'bg-emerald-500', prompt: 'Build a Python CLI tool that converts between unit systems (length: meters/feet/inches/km/miles, weight: kg/lbs/oz/grams, temperature: C/F/K). Use argparse, proper package structure with pyproject.toml, and 20+ pytest tests covering all conversions and edge cases.' },
  { icon: Globe, label: 'URL Shortener', color: 'bg-purple-500', prompt: 'Build a URL shortener with FastAPI. Include click tracking with timestamps, in-memory TTL cache layer, rate limiting (10 req/min), statistics endpoint showing click counts, custom slug support, and 30+ comprehensive tests.' },
  { icon: FileText, label: 'Data Pipeline', color: 'bg-orange-500', prompt: 'Build a Python data processing pipeline that reads CSV files, cleans data (handle missing values, normalize formats), transforms columns, and outputs to JSON. Include a CLI interface, logging, error handling for malformed data, and pytest tests.' },
]

export default function NewRunPage() {
  const nav = useNavigate()
  const reset = useStore(s => s.reset)
  const [cfg, setCfg] = useState<any>(null)

  const [task, setTask] = useState('')
  const [contextLinks, setContextLinks] = useState<string[]>([])
  const [newLink, setNewLink] = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const [provider, setProvider] = useState('claude-sdk')
  const [model, setModel] = useState('')
  const [budget, setBudget] = useState('')
  const [maxIter, setMaxIter] = useState('50')
  const [loading, setLoading] = useState(false)
  const [dragOver, setDragOver] = useState(false)

  useEffect(() => { api.config().then(setCfg).catch(() => {}) }, [])

  const start = async () => {
    if (!task.trim()) return
    setLoading(true); reset()
    const fullTask = contextLinks.length > 0
      ? `${task}\n\nContext links:\n${contextLinks.map(l => `- ${l}`).join('\n')}`
      : task
    try {
      const r = await api.startRun({
        task: fullTask, provider, model: model || undefined,
        budget: budget ? +budget : undefined, max_iterations: +maxIter || 50,
      })
      useStore.getState().dispatch({ type: 'run_started', timestamp: '', data: { run_id: r.run_id, phase: 'generating_spec' } })
      nav('/dashboard')
    } catch (e: any) { alert(e.message) }
    finally { setLoading(false) }
  }

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); start() }
  }

  const addLink = () => {
    if (newLink.trim() && !contextLinks.includes(newLink.trim())) {
      setContextLinks([...contextLinks, newLink.trim()])
      setNewLink('')
    }
  }

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false)
    const files = Array.from(e.dataTransfer.files)
    if (files.length > 0) {
      const file = files[0]
      const reader = new FileReader()
      reader.onload = (ev) => {
        const content = ev.target?.result as string
        setTask(prev => prev + (prev ? '\n\n' : '') + `--- Uploaded: ${file.name} ---\n${content.slice(0, 5000)}`)
      }
      reader.readAsText(file)
    }
  }, [])

  const charCount = task.length

  return (
    <div className="h-full flex flex-col">
      {/* Top bar */}
      <div className="px-6 py-3 border-b flex items-center gap-3 shrink-0">
        <button onClick={() => nav('/')} className="text-muted hover:text-foreground transition-colors"><ChevronLeft size={18} /></button>
        <h1 className="font-semibold">New Project</h1>
        <div className="flex-1" />
        {charCount > 0 && <span className="text-[11px] text-muted tabular-nums">{charCount} chars</span>}
      </div>

      {/* Main */}
      <div className="flex-1 flex items-center justify-center p-6 overflow-y-auto">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="w-full max-w-3xl">

          {/* Header */}
          <div className="text-center mb-8">
            <motion.div initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay: 0.1 }}
              className="w-14 h-14 rounded-2xl bg-brand-600 flex items-center justify-center mx-auto mb-5 shadow-lg shadow-brand-600/20">
              <MessageSquare size={24} className="text-white" />
            </motion.div>
            <h2 className="text-3xl font-bold mb-2">What do you want to build?</h2>
            <p className="text-muted max-w-md mx-auto text-sm">Describe your project, upload spec files, or provide reference links for context.</p>
          </div>

          {/* Input card */}
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
            className={cn('bg-surface-0 rounded-3xl border shadow-elevated overflow-hidden transition-colors',
              dragOver && 'border-brand-400 bg-brand-50/50 dark:bg-brand-900/20')}
            onDragOver={e => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}>

            {/* Textarea */}
            <div className="p-6 pb-2">
              <textarea value={task} onChange={e => setTask(e.target.value)} onKeyDown={handleKey} autoFocus rows={7}
                placeholder="Build a REST API with FastAPI for managing a todo app. Include user authentication with JWT tokens, SQLite database, full CRUD operations, input validation, error handling, and comprehensive pytest tests with 20+ test cases..."
                className="w-full text-[15px] leading-relaxed resize-none bg-transparent focus:outline-none placeholder:text-muted/40" />
              {dragOver && (
                <div className="text-center py-4 text-brand-600 text-sm font-medium">
                  <Upload size={20} className="mx-auto mb-1" /> Drop file to add as context
                </div>
              )}
            </div>

            {/* Context links */}
            {contextLinks.length > 0 && (
              <div className="px-6 pb-2 flex flex-wrap gap-2">
                {contextLinks.map((link, i) => (
                  <span key={i} className="inline-flex items-center gap-1 text-xs bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-300 px-2.5 py-1 rounded-full border border-brand-200 dark:border-brand-700">
                    <Link2 size={10} /> {link.length > 40 ? link.slice(0, 40) + '...' : link}
                    <button onClick={() => setContextLinks(contextLinks.filter((_, j) => j !== i))}><X size={10} /></button>
                  </span>
                ))}
              </div>
            )}

            {/* Add link row */}
            <div className="px-6 pb-3 flex gap-2">
              <div className="flex-1 flex items-center gap-2 border rounded-xl px-3 py-1.5 bg-surface-1">
                <Link2 size={13} className="text-muted shrink-0" />
                <input value={newLink} onChange={e => setNewLink(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addLink() } }}
                  placeholder="Add a reference link (GitHub, docs, etc.)"
                  className="flex-1 text-xs bg-transparent focus:outline-none placeholder:text-muted/40" />
                {newLink && <button onClick={addLink} className="text-brand-600"><Plus size={14} /></button>}
              </div>
              <label className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border bg-surface-1 text-xs text-muted hover:text-foreground cursor-pointer transition-colors">
                <Upload size={13} /> Upload
                <input type="file" className="hidden" accept=".txt,.md,.py,.json,.yaml,.yml,.toml"
                  onChange={e => {
                    const file = e.target.files?.[0]
                    if (file) {
                      const reader = new FileReader()
                      reader.onload = ev => setTask(prev => prev + (prev ? '\n\n' : '') + `--- ${file.name} ---\n${(ev.target?.result as string).slice(0, 5000)}`)
                      reader.readAsText(file)
                    }
                  }} />
              </label>
            </div>

            {/* Example prompts */}
            <div className="px-6 pb-4">
              <p className="text-[11px] text-muted mb-2.5 font-medium uppercase tracking-wider">Quick Start Templates</p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {EXAMPLES.map(ex => (
                  <button key={ex.label} onClick={() => setTask(ex.prompt)}
                    className={cn('flex items-center gap-2 text-xs px-3 py-2.5 rounded-xl border transition-all text-left',
                      task === ex.prompt
                        ? 'bg-brand-50 dark:bg-brand-700/20 border-brand-300 dark:border-brand-600 text-brand-700 dark:text-brand-300 shadow-sm'
                        : 'bg-surface-1 text-muted hover:text-foreground hover:border-brand-200 hover:shadow-sm')}>
                    <div className={cn('w-6 h-6 rounded-lg flex items-center justify-center text-white shrink-0', ex.color)}>
                      <ex.icon size={12} />
                    </div>
                    <span className="font-medium">{ex.label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Expandable settings */}
            <AnimatePresence>
              {showSettings && (
                <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden border-t">
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
              </span>
              <button onClick={start} disabled={!task.trim() || loading}
                className="px-6 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:opacity-30 text-white text-sm font-semibold rounded-xl flex items-center gap-2 shadow-sm transition-all hover:shadow-md active:scale-[0.98]">
                {loading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <><Send size={14} /> Start Building</>}
              </button>
            </div>
          </motion.div>

          <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}
            className="text-center text-[11px] text-muted/50 mt-5 flex items-center justify-center gap-1.5">
            <ArrowRight size={10} /> Ralph generates spec.md → you approve → prd.json tasks → autonomous coding with QA
          </motion.p>
        </motion.div>
      </div>
    </div>
  )
}
