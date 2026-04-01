import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileCode, TestTube, BarChart3, GitBranch, ChevronRight, File, Folder } from 'lucide-react'
import { api } from '@/api/client'
import { cn, formatCost, formatDuration } from '@/lib/utils'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const TABS = ['Code', 'Spec', 'Progress', 'Analytics', 'Git'] as const

export default function ResultsPage() {
  const [tab, setTab] = useState<typeof TABS[number]>('Code')
  const [selectedFile, setSelectedFile] = useState('')

  return (
    <div className="h-full flex flex-col">
      {/* Tab bar */}
      <div className="flex border-b px-6 bg-surface-0">
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={cn('px-4 py-3 text-sm font-medium border-b-2 transition-colors',
              tab === t ? 'border-brand-600 text-brand-700 dark:text-brand-300' : 'border-transparent text-muted hover:text-foreground')}>
            {t}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-hidden">
        {tab === 'Code' && <CodeTab file={selectedFile} onSelect={setSelectedFile} />}
        {tab === 'Spec' && <SpecTab />}
        {tab === 'Progress' && <ProgressTab />}
        {tab === 'Analytics' && <AnalyticsTab />}
        {tab === 'Git' && <GitTab />}
      </div>
    </div>
  )
}

function CodeTab({ file, onSelect }: { file: string; onSelect: (f: string) => void }) {
  const { data: files } = useQuery({ queryKey: ['files'], queryFn: api.files })
  const { data: content } = useQuery({ queryKey: ['file', file], queryFn: () => api.fileContent(file), enabled: !!file })

  return (
    <div className="h-full flex">
      <div className="w-64 border-r overflow-y-auto p-3">
        <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-2 px-2">Files</p>
        {files?.map((n: any) => <TreeNode key={n.path} node={n} depth={0} selected={file} onSelect={onSelect} />)}
        {!files?.length && <p className="text-sm text-muted px-2">No files</p>}
      </div>
      <div className="flex-1 overflow-auto">
        {content ? (
          <>
            <div className="px-5 py-2.5 border-b flex items-center gap-2 text-sm text-muted sticky top-0 bg-surface-0 z-10">
              <FileCode size={14} /> {content.path}
              <span className="ml-auto text-xs">{content.language}</span>
            </div>
            <pre className="p-5 text-[13px] font-mono leading-relaxed overflow-x-auto" style={{ background: 'var(--code-bg)' }}>
              {content.content.split('\n').map((line: string, i: number) => (
                <div key={i} className="flex hover:bg-surface-1/50">
                  <span className="text-muted/40 w-10 text-right mr-5 select-none shrink-0 text-xs leading-relaxed">{i + 1}</span>
                  <span>{line || ' '}</span>
                </div>
              ))}
            </pre>
          </>
        ) : (
          <div className="h-full flex items-center justify-center text-muted text-sm">Select a file to view</div>
        )}
      </div>
    </div>
  )
}

function TreeNode({ node, depth, selected, onSelect }: { node: any; depth: number; selected: string; onSelect: (f: string) => void }) {
  const [open, setOpen] = useState(depth < 2)
  if (node.is_dir) {
    return (
      <div>
        <button onClick={() => setOpen(!open)} className="flex items-center gap-1.5 py-1 px-2 text-sm w-full hover:bg-surface-1 rounded-lg text-muted" style={{ paddingLeft: depth * 14 + 8 }}>
          <ChevronRight size={12} className={cn('transition-transform', open && 'rotate-90')} />
          <Folder size={13} className="text-brand-500" /> {node.name}
        </button>
        {open && node.children?.map((c: any) => <TreeNode key={c.path} node={c} depth={depth + 1} selected={selected} onSelect={onSelect} />)}
      </div>
    )
  }
  return (
    <button onClick={() => onSelect(node.path)}
      className={cn('flex items-center gap-1.5 py-1 px-2 text-sm w-full rounded-lg transition-colors',
        selected === node.path ? 'bg-brand-50 dark:bg-brand-700/20 text-brand-700 dark:text-brand-300' : 'text-muted hover:bg-surface-1')}
      style={{ paddingLeft: depth * 14 + 24 }}>
      <File size={13} /> {node.name}
    </button>
  )
}

function SpecTab() {
  const { data } = useQuery({ queryKey: ['progress'], queryFn: () => api.fileContent('.ralph/spec.md').catch(() => ({ content: 'No spec.md found' })) })
  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-3xl mx-auto bg-surface-0 border rounded-2xl p-8 shadow-soft">
        <div className="md-spec">
          <Markdown remarkPlugins={[remarkGfm]}>{data?.content || 'Loading...'}</Markdown>
        </div>
      </div>
    </div>
  )
}

function ProgressTab() {
  const { data: progress } = useQuery({ queryKey: ['progress'], queryFn: api.progress })
  const { data: guardrails } = useQuery({ queryKey: ['guardrails'], queryFn: api.guardrails })
  const { data: reflections } = useQuery({ queryKey: ['reflections'], queryFn: api.reflections })

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-3xl mx-auto space-y-6">
        <Section title="Progress Log" content={progress?.content} />
        <Section title="Guardrails" content={guardrails?.content} />
        <Section title="Reflections" content={reflections?.content} />
      </div>
    </div>
  )
}

function Section({ title, content }: { title: string; content?: string }) {
  if (!content) return null
  return (
    <div>
      <h3 className="font-semibold mb-2">{title}</h3>
      <div className="bg-surface-0 border rounded-xl p-5 shadow-soft">
        <div className="md-spec text-sm">
          <Markdown remarkPlugins={[remarkGfm]}>{content}</Markdown>
        </div>
      </div>
    </div>
  )
}

function AnalyticsTab() {
  const { data } = useQuery({ queryKey: ['analytics'], queryFn: api.analytics })
  if (!data) return <div className="p-6 text-muted">Loading...</div>

  const phases = Object.entries(data.cost_by_phase ?? {}).filter(([, v]) => (v as number) > 0)

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div className="grid grid-cols-4 gap-4">
        {[
          { l: 'Total Cost', v: formatCost(data.total_cost) },
          { l: 'Sessions', v: String(data.sessions) },
          { l: 'Tool Calls', v: String(data.total_tool_calls) },
          { l: 'Duration', v: formatDuration(data.total_duration_ms) },
        ].map((s, i) => (
          <div key={i} className="border rounded-xl p-4 bg-surface-0 shadow-soft">
            <p className="text-xs text-muted">{s.l}</p>
            <p className="text-xl font-bold font-mono mt-1">{s.v}</p>
          </div>
        ))}
      </div>
      {phases.length > 0 && (
        <div>
          <h3 className="font-semibold mb-3">Cost by Phase</h3>
          <div className="space-y-2">
            {phases.map(([phase, cost]) => (
              <div key={phase} className="flex items-center gap-3">
                <span className="text-sm w-24 text-muted capitalize">{phase}</span>
                <div className="flex-1 h-6 bg-surface-1 rounded-lg overflow-hidden">
                  <div className="h-full bg-brand-500/30 rounded-lg" style={{ width: `${((cost as number) / data.total_cost) * 100}%` }} />
                </div>
                <span className="text-sm font-mono w-20 text-right">{formatCost(cost as number)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function GitTab() {
  const { data } = useQuery({ queryKey: ['gitLog'], queryFn: api.gitLog })
  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h3 className="font-semibold mb-3">Git History</h3>
      <div className="space-y-1">
        {data?.map((c: any, i: number) => (
          <div key={i} className="flex items-center gap-3 py-2.5 border-b">
            <code className="text-xs font-mono text-brand-600 bg-brand-50 dark:bg-brand-700/20 px-2 py-0.5 rounded">{c.hash}</code>
            <span className="text-sm">{c.message}</span>
          </div>
        ))}
        {!data?.length && <p className="text-muted text-sm">No commits</p>}
      </div>
    </div>
  )
}
