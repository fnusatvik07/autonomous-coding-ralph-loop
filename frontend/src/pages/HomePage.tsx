import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion, useScroll, useTransform } from 'framer-motion'
import {
  FileText, Eye, ListChecks, Code2, CheckCircle, Shield, Brain, Zap,
  GitBranch, BarChart3, Wrench, Sparkles, PlayCircle, ArrowDown, ArrowRight,
  RotateCcw, ChevronDown
} from 'lucide-react'
import { api } from '@/api/client'
import { useStore } from '@/stores/run-store'
import { cn } from '@/lib/utils'

const fadeUp = { hidden: { opacity: 0, y: 40 }, show: { opacity: 1, y: 0 } }
const stagger = { show: { transition: { staggerChildren: 0.1 } } }
const scaleIn = { hidden: { opacity: 0, scale: 0.9 }, show: { opacity: 1, scale: 1 } }

export default function HomePage() {
  const nav = useNavigate()
  const { scrollYProgress } = useScroll()
  const heroOpacity = useTransform(scrollYProgress, [0, 0.12], [1, 0])
  const heroScale = useTransform(scrollYProgress, [0, 0.12], [1, 0.97])
  const [existingPrd, setExistingPrd] = useState<any>(null)
  const reset = useStore(s => s.reset)

  useEffect(() => { api.prd().then(p => { if (p.tasks?.length) setExistingPrd(p) }).catch(() => {}) }, [])

  return (
    <div className="h-full overflow-y-auto scroll-smooth">
      {/* ═══ HERO ═══ */}
      <motion.section style={{ opacity: heroOpacity, scale: heroScale }}
        className="relative min-h-[92vh] flex flex-col items-center justify-center px-6 overflow-hidden">
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          <motion.div animate={{ x: [0, 30, 0], y: [0, -20, 0] }} transition={{ duration: 20, repeat: Infinity }}
            className="absolute top-20 left-[10%] w-[500px] h-[500px] bg-blue-400/8 dark:bg-blue-400/15 rounded-full blur-[120px]" />
          <motion.div animate={{ x: [0, -20, 0], y: [0, 30, 0] }} transition={{ duration: 25, repeat: Infinity }}
            className="absolute bottom-20 right-[10%] w-[400px] h-[400px] bg-emerald-400/8 dark:bg-emerald-400/12 rounded-full blur-[100px]" />
        </div>
        <div className="absolute inset-0 opacity-[0.03] dark:opacity-[0.05]" style={{
          backgroundImage: 'radial-gradient(circle, currentColor 1px, transparent 1px)', backgroundSize: '24px 24px',
        }} />

        <motion.div initial="hidden" animate="show" variants={stagger} className="relative z-10 text-center max-w-3xl">
          <motion.div variants={fadeUp} transition={{ duration: 0.6 }}>
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border bg-surface-1 text-xs text-muted mb-8">
              <Sparkles size={11} className="text-brand-600" /> Open Source Autonomous Coding Agent
            </span>
          </motion.div>
          <motion.h1 variants={fadeUp} transition={{ duration: 0.7, delay: 0.1 }}
            className="text-5xl sm:text-6xl lg:text-[4.5rem] font-extrabold tracking-tight leading-[1.05] mb-6">
            Describe it.{' '}
            <span className="relative">
              <span className="text-brand-600">Ralph builds it.</span>
              <motion.div initial={{ width: 0 }} animate={{ width: '100%' }} transition={{ delay: 1.2, duration: 0.8 }}
                className="absolute bottom-1 left-0 h-[3px] bg-brand-500/30 rounded-full" />
            </span>
          </motion.h1>
          <motion.p variants={fadeUp} transition={{ duration: 0.6, delay: 0.2 }}
            className="text-lg sm:text-xl text-muted max-w-xl mx-auto mb-10 leading-relaxed">
            From a single task description to tested, committed code.<br className="hidden sm:block" />
            Spec → human review → tasks → autonomous coding → QA → shipped.
          </motion.p>
          <motion.div variants={fadeUp} transition={{ duration: 0.5, delay: 0.3 }} className="flex items-center justify-center gap-3 flex-wrap">
            <Link to="/new" className="px-7 py-3.5 bg-brand-600 hover:bg-brand-700 text-white font-semibold rounded-2xl flex items-center gap-2 shadow-lg shadow-brand-600/20 transition-all hover:-translate-y-0.5">
              <PlayCircle size={18} /> Start Building <ArrowRight size={14} />
            </Link>
            <a href="#how" className="px-5 py-3.5 border rounded-2xl flex items-center gap-2 text-sm hover:bg-surface-1 transition-colors font-medium">
              See how it works <ArrowDown size={14} />
            </a>
          </motion.div>
          {existingPrd && (
            <motion.div variants={fadeUp} transition={{ delay: 0.5 }} className="mt-6">
              <button onClick={() => { reset(); nav('/dashboard') }}
                className="text-sm text-muted hover:text-foreground flex items-center gap-1.5 mx-auto transition-colors">
                <RotateCcw size={13} /> Resume: {existingPrd.project_name}
              </button>
            </motion.div>
          )}
        </motion.div>
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 0.4 }} transition={{ delay: 2.5 }} className="absolute bottom-8">
          <ChevronDown size={20} className="text-muted animate-bounce" />
        </motion.div>
      </motion.section>

      {/* ═══ HOW IT WORKS ═══ */}
      <section id="how" className="py-24 px-6 bg-surface-1">
        <div className="max-w-4xl mx-auto">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="text-center mb-16">
            <p className="text-sm font-semibold text-brand-600 uppercase tracking-wider mb-2">How It Works</p>
            <h2 className="text-3xl sm:text-4xl font-bold">Five steps. Fully autonomous.</h2>
            <p className="text-muted mt-3 max-w-lg mx-auto">Human approval at every critical gate.</p>
          </motion.div>
          <div className="space-y-0">
            {[
              { icon: FileText, t: 'Generate Specification', d: 'LLM analyzes your task, examines the workspace, writes a detailed spec.md — architecture, data models, API design, testing strategy.', b: 'spec.md', c: 'bg-blue-500', lc: 'bg-blue-50 dark:bg-blue-500/10' },
              { icon: Eye, t: 'You Review & Approve', d: 'Full-screen markdown viewer. Read every detail. Approve to proceed, or reject and regenerate.', b: 'approval', c: 'bg-cyan-500', lc: 'bg-cyan-50 dark:bg-cyan-500/10' },
              { icon: ListChecks, t: 'Break Into Tasks', d: 'Approved spec → atomic tasks. Each fits one coding session, ordered by dependency, with testable acceptance criteria.', b: 'prd.json', c: 'bg-teal-500', lc: 'bg-teal-50 dark:bg-teal-500/10' },
              { icon: Code2, t: 'Code, Test, Commit', d: 'Fresh context per task. Code → tests → QA sentinel review → healer fixes failures → git commit. Repeat.', b: 'loop', c: 'bg-emerald-500', lc: 'bg-emerald-50 dark:bg-emerald-500/10' },
              { icon: CheckCircle, t: 'Delivered', d: 'All tasks pass QA. Clean git history. Full analytics: cost, duration, test coverage. Ready to deploy.', b: 'shipped', c: 'bg-green-500', lc: 'bg-green-50 dark:bg-green-500/10' },
            ].map((s, i) => (
              <motion.div key={s.b} initial={{ opacity: 0, x: -20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.1 }} className="flex gap-5 group">
                <div className="flex flex-col items-center">
                  <motion.div whileHover={{ scale: 1.1 }} className={cn('w-12 h-12 rounded-2xl flex items-center justify-center text-white shadow-md', s.c)}><s.icon size={20} /></motion.div>
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
            <h2 className="text-3xl sm:text-4xl font-bold">Everything you need</h2>
          </motion.div>
          <motion.div initial="hidden" whileInView="show" viewport={{ once: true }} variants={stagger} className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {[
              { icon: Zap, t: 'Multi-Model Routing', d: 'Haiku for scaffolding. Sonnet for features. Opus for architecture.' },
              { icon: Shield, t: 'QA Sentinel', d: 'Separate LLM reviews every change. Blocks failures and security holes.' },
              { icon: Wrench, t: 'Healer Loop', d: 'Auto-fixes QA failures up to 5 times. Rolls back on final failure.' },
              { icon: Brain, t: 'Reflexion', d: 'Learns from mistakes. Injects lessons into subsequent iterations.' },
              { icon: GitBranch, t: 'Git Checkpoints', d: 'Tag before each task. Rollback on failure. Clean squash on success.' },
              { icon: BarChart3, t: 'Observability', d: 'Per-session cost. Analytics dashboard. Structured logs. Run IDs.' },
            ].map((f) => (
              <motion.div key={f.t} variants={scaleIn} transition={{ duration: 0.4 }}
                className="p-6 rounded-2xl border bg-surface-0 hover:shadow-card transition-all group">
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

      {/* ═══ STATS ═══ */}
      <section className="py-16 px-6 bg-surface-1">
        <motion.div initial="hidden" whileInView="show" viewport={{ once: true }} variants={stagger}
          className="max-w-3xl mx-auto grid grid-cols-2 sm:grid-cols-4 gap-8 text-center">
          {[{ v: '158', l: 'Tests Pass' }, { v: '35/35', l: 'Real Tasks' }, { v: '98%', l: 'Coverage' }, { v: '$0.48', l: 'Avg/Task' }].map((s) => (
            <motion.div key={s.l} variants={fadeUp}>
              <div className="text-3xl font-bold font-mono text-brand-600">{s.v}</div>
              <div className="text-xs text-muted mt-1">{s.l}</div>
            </motion.div>
          ))}
        </motion.div>
      </section>

      {/* ═══ CTA ═══ */}
      <section className="py-20 px-6 bg-brand-600 dark:bg-brand-700 text-white">
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="max-w-2xl mx-auto text-center">
          <h2 className="text-3xl font-bold mb-4">Ready to ship faster?</h2>
          <p className="text-blue-100 mb-8 text-lg">From idea to tested code in minutes.</p>
          <Link to="/new" className="inline-flex items-center gap-2 px-7 py-3.5 bg-white text-brand-700 font-semibold rounded-2xl shadow-lg hover:shadow-xl transition-all hover:-translate-y-0.5">
            <Zap size={16} /> Start Building Now
          </Link>
        </motion.div>
      </section>

      <footer className="py-8 text-center text-xs text-muted border-t">Ralph Loop — Open Source Autonomous Coding Agent</footer>
    </div>
  )
}
