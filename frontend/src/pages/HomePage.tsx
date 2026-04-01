import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion, useScroll, useTransform, useMotionValue, useSpring } from 'framer-motion'
import {
  FileText, Eye, ListChecks, Code2, CheckCircle, Shield, Brain, Zap,
  GitBranch, BarChart3, Wrench, Sparkles, PlayCircle, ArrowDown, ArrowRight,
  RotateCcw, ChevronDown, Terminal, Check, Clock, DollarSign, TestTubes,
  Cpu, Globe, Lock
} from 'lucide-react'
import { api } from '@/api/client'
import { useStore } from '@/stores/run-store'
import { cn } from '@/lib/utils'

const fadeUp = { hidden: { opacity: 0, y: 40 }, show: { opacity: 1, y: 0 } }
const stagger = { show: { transition: { staggerChildren: 0.1 } } }
const scaleIn = { hidden: { opacity: 0, scale: 0.9 }, show: { opacity: 1, scale: 1 } }

/* ═══ Animated Terminal Mockup ═══ */
function TerminalMockup() {
  const lines = [
    { type: 'cmd', text: '$ ralph run "Build a FastAPI todo app with tests"' },
    { type: 'info', text: '' },
    { type: 'phase', text: 'Step 1: Generating specification (spec.md)...' },
    { type: 'tool', text: '  > Glob **/*.py' },
    { type: 'tool', text: '  > Read pyproject.toml' },
    { type: 'tool', text: '  > Write .ralph/spec.md' },
    { type: 'success', text: '  ✓ spec.md ready (8,853 bytes)' },
    { type: 'info', text: '' },
    { type: 'phase', text: 'Step 2: Generating task list (prd.json)...' },
    { type: 'success', text: '  ✓ 12 tasks created' },
    { type: 'info', text: '' },
    { type: 'iter', text: '>>> TASK-001: Project scaffolding' },
    { type: 'tool', text: '  > Write pyproject.toml' },
    { type: 'tool', text: '  > Write app/__init__.py' },
    { type: 'tool', text: '  > Bash pip install -e .' },
    { type: 'qa', text: '  QA Sentinel: PASSED ✓' },
    { type: 'cost', text: '  $0.29 | 20 tools | 70s' },
    { type: 'info', text: '' },
    { type: 'iter', text: '>>> TASK-002: Todo data model' },
    { type: 'tool', text: '  > Write app/models.py' },
    { type: 'tool', text: '  > Bash pytest tests/ -v' },
    { type: 'qa', text: '  QA Sentinel: PASSED ✓' },
    { type: 'info', text: '' },
    { type: 'done', text: 'ALL TASKS COMPLETE — 12/12 passed — $5.73' },
  ]

  const [visibleLines, setVisibleLines] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => {
      setVisibleLines(prev => {
        if (prev >= lines.length) {
          // Reset after pause
          setTimeout(() => setVisibleLines(0), 3000)
          clearInterval(timer)
          return prev
        }
        return prev + 1
      })
    }, 200)
    return () => clearInterval(timer)
  }, [visibleLines === 0])

  const colorMap: Record<string, string> = {
    cmd: 'text-green-400',
    phase: 'text-blue-400 font-semibold',
    tool: 'text-gray-500',
    success: 'text-emerald-400',
    iter: 'text-cyan-400 font-semibold',
    qa: 'text-green-400',
    cost: 'text-gray-500 text-xs',
    done: 'text-green-400 font-bold',
    info: '',
  }

  return (
    <div className="rounded-2xl overflow-hidden shadow-elevated border bg-[#0f172a] dark:bg-[#0a0f1a]">
      {/* Window chrome */}
      <div className="flex items-center gap-1.5 px-4 py-2.5 bg-[#1e293b] border-b border-[#334155]">
        <div className="w-3 h-3 rounded-full bg-red-500/80" />
        <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
        <div className="w-3 h-3 rounded-full bg-green-500/80" />
        <span className="ml-3 text-[11px] text-gray-500 font-mono">ralph — terminal</span>
      </div>
      {/* Terminal content */}
      <div className="p-4 font-mono text-[12px] leading-[1.8] h-[320px] overflow-hidden">
        {lines.slice(0, visibleLines).map((line, i) => (
          <motion.div key={i} initial={{ opacity: 0, x: -5 }} animate={{ opacity: 1, x: 0 }}
            className={colorMap[line.type] || 'text-gray-400'}>
            {line.text || '\u00A0'}
          </motion.div>
        ))}
        {visibleLines < lines.length && (
          <span className="inline-block w-2 h-4 bg-gray-400 animate-pulse ml-0.5" />
        )}
      </div>
    </div>
  )
}

/* ═══ Trust Badges ═══ */
function TrustBadges() {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.5 }}
      className="flex flex-wrap items-center justify-center gap-4 mt-12">
      {[
        { icon: Check, text: '158 tests pass' },
        { icon: TestTubes, text: '98% coverage' },
        { icon: DollarSign, text: '$0.48 avg/task' },
        { icon: Clock, text: '~2min per task' },
        { icon: Lock, text: '15 safety patterns' },
        { icon: Globe, text: 'Open source' },
      ].map(b => (
        <div key={b.text} className="flex items-center gap-1.5 text-[11px] text-muted">
          <b.icon size={12} className="text-brand-500" /> {b.text}
        </div>
      ))}
    </motion.div>
  )
}

export default function HomePage() {
  const nav = useNavigate()
  const { scrollYProgress } = useScroll()
  const heroOpacity = useTransform(scrollYProgress, [0, 0.15], [1, 0])
  const heroScale = useTransform(scrollYProgress, [0, 0.15], [1, 0.96])
  const terminalY = useTransform(scrollYProgress, [0, 0.2], [0, 40])
  const [existingPrd, setExistingPrd] = useState<any>(null)
  const reset = useStore(s => s.reset)

  useEffect(() => { api.prd().then(p => { if (p.tasks?.length) setExistingPrd(p) }).catch(() => {}) }, [])

  return (
    <div className="h-full overflow-y-auto scroll-smooth">

      {/* ═══ HERO ═══ */}
      <section className="relative px-6 pt-16 pb-24 overflow-hidden">
        {/* Background */}
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          <motion.div animate={{ x: [0, 30, 0], y: [0, -20, 0] }} transition={{ duration: 20, repeat: Infinity }}
            className="absolute top-20 left-[5%] w-[500px] h-[500px] bg-blue-400/8 dark:bg-blue-400/15 rounded-full blur-[120px]" />
          <motion.div animate={{ x: [0, -20, 0], y: [0, 30, 0] }} transition={{ duration: 25, repeat: Infinity }}
            className="absolute bottom-20 right-[5%] w-[400px] h-[400px] bg-emerald-400/8 dark:bg-emerald-400/12 rounded-full blur-[100px]" />
        </div>
        <div className="absolute inset-0 opacity-[0.03] dark:opacity-[0.05]" style={{
          backgroundImage: 'radial-gradient(circle, currentColor 1px, transparent 1px)', backgroundSize: '24px 24px',
        }} />

        <div className="relative z-10 max-w-6xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-12 items-center min-h-[70vh]">
            {/* Left: Text */}
            <motion.div style={{ opacity: heroOpacity, scale: heroScale }}>
              <motion.div initial="hidden" animate="show" variants={stagger}>
                <motion.div variants={fadeUp}>
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border bg-surface-1 text-xs text-muted mb-6">
                    <Sparkles size={11} className="text-brand-600" /> Open Source Autonomous Coding Agent
                  </span>
                </motion.div>
                <motion.h1 variants={fadeUp}
                  className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.08] mb-5">
                  Describe it.<br />
                  <span className="relative">
                    <span className="text-brand-600">Ralph builds it.</span>
                    <motion.div initial={{ width: 0 }} animate={{ width: '100%' }} transition={{ delay: 1, duration: 0.8 }}
                      className="absolute bottom-0.5 left-0 h-[3px] bg-brand-500/30 rounded-full" />
                  </span>
                </motion.h1>
                <motion.p variants={fadeUp}
                  className="text-base sm:text-lg text-muted max-w-md mb-8 leading-relaxed">
                  From a single task description to tested, committed, production-ready code.
                  With human approval at every step.
                </motion.p>
                <motion.div variants={fadeUp} className="flex items-center gap-3 flex-wrap">
                  <Link to="/new" className="px-6 py-3 bg-brand-600 hover:bg-brand-700 text-white font-semibold rounded-2xl flex items-center gap-2 shadow-lg shadow-brand-600/20 transition-all hover:-translate-y-0.5">
                    <PlayCircle size={16} /> Start Building <ArrowRight size={14} />
                  </Link>
                  <a href="#how" className="px-5 py-3 border rounded-2xl flex items-center gap-2 text-sm hover:bg-surface-1 transition-colors font-medium">
                    How it works <ArrowDown size={14} />
                  </a>
                </motion.div>
                {existingPrd && (
                  <motion.div variants={fadeUp} className="mt-4">
                    <button onClick={() => { reset(); nav('/dashboard') }}
                      className="text-sm text-muted hover:text-foreground flex items-center gap-1.5 transition-colors">
                      <RotateCcw size={12} /> Resume: {existingPrd.project_name}
                    </button>
                  </motion.div>
                )}
                <TrustBadges />
              </motion.div>
            </motion.div>

            {/* Right: Terminal mockup */}
            <motion.div style={{ y: terminalY }} initial={{ opacity: 0, x: 30 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.5, duration: 0.7 }}>
              <TerminalMockup />
            </motion.div>
          </div>
        </div>
      </section>

      {/* ═══ HOW IT WORKS ═══ */}
      <section id="how" className="py-24 px-6 bg-surface-1">
        <div className="max-w-4xl mx-auto">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="text-center mb-16">
            <p className="text-sm font-semibold text-brand-600 uppercase tracking-wider mb-2">Architecture</p>
            <h2 className="text-3xl sm:text-4xl font-bold mb-3">Five steps. Fully autonomous.</h2>
            <p className="text-muted max-w-lg mx-auto">Human approval at every critical gate. Nothing runs without your sign-off.</p>
          </motion.div>

          <div className="space-y-0">
            {[
              { icon: FileText, t: 'Generate Specification', d: 'LLM analyzes your task, examines the workspace, and writes a comprehensive spec.md — architecture, data models, API endpoints, testing strategy, implementation steps.', b: 'spec.md', c: 'bg-blue-500', lc: 'bg-blue-50 dark:bg-blue-500/10' },
              { icon: Eye, t: 'You Review & Approve', d: 'Full-screen markdown viewer with syntax-highlighted code blocks. Read every detail. Approve to proceed, or reject and try again.', b: 'approval', c: 'bg-cyan-500', lc: 'bg-cyan-50 dark:bg-cyan-500/10' },
              { icon: ListChecks, t: 'Break Into Tasks', d: 'Approved spec is decomposed into atomic tasks. Each fits one coding session, ordered by dependency, with testable acceptance criteria and verification commands.', b: 'prd.json', c: 'bg-teal-500', lc: 'bg-teal-50 dark:bg-teal-500/10' },
              { icon: Code2, t: 'Code, Test, Commit', d: 'Fresh agent context per task. Reads the spec, implements code, writes tests, verifies everything passes. A separate QA sentinel reviews every change. Healer auto-fixes failures.', b: 'loop', c: 'bg-emerald-500', lc: 'bg-emerald-50 dark:bg-emerald-500/10' },
              { icon: CheckCircle, t: 'Delivered', d: 'All tasks pass QA. Clean git history with one commit per feature. Full analytics dashboard shows cost per phase, tool usage, duration, and test coverage.', b: 'shipped', c: 'bg-green-500', lc: 'bg-green-50 dark:bg-green-500/10' },
            ].map((s, i) => (
              <motion.div key={s.b} initial={{ opacity: 0, x: -20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.08 }} className="flex gap-5 group">
                <div className="flex flex-col items-center">
                  <motion.div whileHover={{ scale: 1.1, rotate: 5 }} transition={{ type: 'spring', stiffness: 300 }}
                    className={cn('w-12 h-12 rounded-2xl flex items-center justify-center text-white shadow-md', s.c)}>
                    <s.icon size={20} />
                  </motion.div>
                  {i < 4 && <div className="w-px flex-1 bg-border my-2 min-h-[16px]" />}
                </div>
                <div className="pb-8">
                  <div className="flex items-center gap-2.5 mb-1.5">
                    <span className="text-[10px] font-mono font-bold text-muted">0{i + 1}</span>
                    <h3 className="font-semibold text-lg">{s.t}</h3>
                    <span className={cn('text-[10px] px-2 py-0.5 rounded-full font-mono font-medium', s.lc)}>{s.b}</span>
                  </div>
                  <p className="text-sm text-muted leading-relaxed max-w-xl">{s.d}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ FEATURES ═══ */}
      <section className="py-24 px-6">
        <div className="max-w-5xl mx-auto">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="text-center mb-14">
            <p className="text-sm font-semibold text-brand-600 uppercase tracking-wider mb-2">Features</p>
            <h2 className="text-3xl sm:text-4xl font-bold mb-3">Everything you need</h2>
            <p className="text-muted max-w-md mx-auto">Built on real testing with 35 completed API tasks and 158 passing tests.</p>
          </motion.div>
          <motion.div initial="hidden" whileInView="show" viewport={{ once: true }} variants={stagger} className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {[
              { icon: Zap, t: 'Multi-Model Routing', d: 'Haiku for scaffolding. Sonnet for features. Opus for architecture. Automatic complexity-based routing saves 60% on costs.' },
              { icon: Shield, t: 'QA Sentinel', d: 'A separate LLM session reviews every code change. Blocks on failing tests, security vulnerabilities, or missing test coverage.' },
              { icon: Wrench, t: 'Healer Loop', d: 'When QA fails, a debugging specialist iterates up to 5 times to fix the issue. Auto-rollback to last checkpoint on final failure.' },
              { icon: Brain, t: 'Reflexion Pattern', d: 'After failures, the LLM analyzes WHY it failed and stores the lesson. Future iterations read these reflections before starting.' },
              { icon: GitBranch, t: 'Git Checkpoints', d: 'Creates a tag before each task starts. If the task fails permanently, rolls back to the last good state automatically.' },
              { icon: BarChart3, t: 'Full Observability', d: 'Per-session cost tracking in sessions.jsonl. Structured logging. Run correlation IDs. Analytics CLI and web dashboard.' },
            ].map(f => (
              <motion.div key={f.t} variants={scaleIn} transition={{ duration: 0.4 }}
                className="p-6 rounded-2xl border bg-surface-0 hover:shadow-card hover:border-brand-200 dark:hover:border-brand-700 transition-all group">
                <div className="w-10 h-10 rounded-xl bg-brand-50 dark:bg-brand-700/15 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                  <f.icon size={18} className="text-brand-600" />
                </div>
                <h3 className="font-semibold mb-1.5">{f.t}</h3>
                <p className="text-sm text-muted leading-relaxed">{f.d}</p>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ═══ REAL RESULTS ═══ */}
      <section className="py-20 px-6 bg-surface-1">
        <div className="max-w-5xl mx-auto">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="text-center mb-12">
            <p className="text-sm font-semibold text-brand-600 uppercase tracking-wider mb-2">Proven Results</p>
            <h2 className="text-3xl font-bold mb-3">Tested with real API calls</h2>
            <p className="text-muted max-w-md mx-auto">Every number below comes from actual runs, not benchmarks or mocks.</p>
          </motion.div>

          {/* Stats grid */}
          <motion.div initial="hidden" whileInView="show" viewport={{ once: true }} variants={stagger}
            className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-10">
            {[
              { v: '158', l: 'Tests Pass', sub: 'Mock + unit + integration' },
              { v: '35/35', l: 'Real API Tasks', sub: 'Zero failures' },
              { v: '98%', l: 'Test Coverage', sub: 'Unit converter project' },
              { v: '$5.73', l: '12-Task Project', sub: '66 tests generated' },
            ].map(s => (
              <motion.div key={s.l} variants={fadeUp}
                className="bg-surface-0 border rounded-2xl p-5 text-center hover:shadow-card transition-shadow">
                <div className="text-3xl font-bold font-mono text-brand-600 mb-1">{s.v}</div>
                <div className="text-sm font-medium">{s.l}</div>
                <div className="text-[11px] text-muted mt-0.5">{s.sub}</div>
              </motion.div>
            ))}
          </motion.div>

          {/* Real project examples */}
          <motion.div initial="hidden" whileInView="show" viewport={{ once: true }} variants={stagger}
            className="grid sm:grid-cols-3 gap-4">
            {[
              { name: 'Todo API', tasks: '10/10', tests: '47 tests', cost: '$2.48', time: '20m', desc: 'FastAPI + SQLite + CRUD + validation + error handling' },
              { name: 'URL Shortener', tasks: '6/6', tests: '35 tests', cost: '$2.81', time: '20m', desc: 'Cache layer + rate limiting + click tracking + statistics' },
              { name: 'Unit Converter', tasks: '12/12', tests: '66 tests', cost: '$5.73', time: '30m', desc: 'Length/weight/temp + CLI + 98% coverage + registry pattern' },
            ].map(p => (
              <motion.div key={p.name} variants={scaleIn}
                className="bg-surface-0 border rounded-2xl p-5 hover:shadow-card transition-shadow">
                <h4 className="font-semibold mb-1">{p.name}</h4>
                <p className="text-xs text-muted mb-3">{p.desc}</p>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div><span className="text-muted">Tasks:</span> <span className="font-mono text-success">{p.tasks}</span></div>
                  <div><span className="text-muted">Tests:</span> <span className="font-mono">{p.tests}</span></div>
                  <div><span className="text-muted">Cost:</span> <span className="font-mono">{p.cost}</span></div>
                  <div><span className="text-muted">Time:</span> <span className="font-mono">{p.time}</span></div>
                </div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ═══ CTA ═══ */}
      <section className="py-20 px-6 bg-brand-600 dark:bg-brand-700 text-white">
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="max-w-2xl mx-auto text-center">
          <h2 className="text-3xl font-bold mb-4">Ready to ship faster?</h2>
          <p className="text-blue-100 mb-8 text-lg">From idea to tested code in minutes. Not hours.</p>
          <Link to="/new" className="inline-flex items-center gap-2 px-7 py-3.5 bg-white text-brand-700 font-semibold rounded-2xl shadow-lg hover:shadow-xl transition-all hover:-translate-y-0.5">
            <Zap size={16} /> Start Building Now
          </Link>
        </motion.div>
      </section>

      <footer className="py-8 text-center text-xs text-muted border-t">
        Ralph Loop — Open Source Autonomous Coding Agent — <a href="https://github.com/satvik/autonomous-coding-ralph-loop" className="text-brand-600 hover:underline">GitHub</a>
      </footer>
    </div>
  )
}
