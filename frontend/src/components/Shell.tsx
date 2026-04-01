import { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Home, LayoutDashboard, FolderOpen, Sun, Moon, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTheme } from '@/lib/theme'
import { useStore } from '@/stores/run-store'

const NAV = [
  { to: '/', icon: Home, label: 'Home' },
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/results', icon: FolderOpen, label: 'Results' },
]

export default function Shell({ children }: { children: ReactNode }) {
  const loc = useLocation()
  const { dark, toggle } = useTheme()
  const phase = useStore((s) => s.phase)

  const isActive = phase === 'coding' || phase === 'generating_spec' || phase === 'generating_prd'
  const needsApproval = phase === 'approve_spec' || phase === 'approve_prd'

  return (
    <div className="h-screen flex flex-col">
      {/* Top nav bar */}
      <header className="h-14 border-b bg-surface-0 flex items-center px-6 gap-6 shrink-0">
        {/* Brand */}
        <Link to="/" className="flex items-center gap-2 font-bold text-lg">
          <div className="w-7 h-7 rounded-lg bg-brand-600 flex items-center justify-center">
            <Zap size={14} className="text-white" />
          </div>
          <span>Ralph<span className="text-muted font-normal ml-0.5">Loop</span></span>
        </Link>

        {/* Nav links */}
        <nav className="flex items-center gap-1 ml-4">
          {NAV.map(({ to, icon: Icon, label }) => (
            <Link
              key={to}
              to={to}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors',
                loc.pathname === to
                  ? 'bg-brand-50 dark:bg-brand-700/20 text-brand-700 dark:text-brand-200 font-medium'
                  : 'text-muted hover:text-foreground hover:bg-surface-1'
              )}
            >
              <Icon size={15} />
              {label}
            </Link>
          ))}
        </nav>

        <div className="flex-1" />

        {/* Status indicator */}
        {isActive && (
          <div className="flex items-center gap-2 text-xs text-brand-600 font-medium">
            <div className="w-2 h-2 rounded-full bg-brand-500 animate-pulse-slow" />
            Running
          </div>
        )}
        {needsApproval && (
          <div className="flex items-center gap-2 text-xs text-warning font-medium">
            <div className="w-2 h-2 rounded-full bg-warning animate-pulse-slow" />
            Awaiting Approval
          </div>
        )}
        {phase === 'completed' && (
          <div className="flex items-center gap-2 text-xs text-success font-medium">
            <div className="w-2 h-2 rounded-full bg-success" />
            Complete
          </div>
        )}

        {/* Theme toggle */}
        <button
          onClick={toggle}
          className="w-8 h-8 rounded-lg flex items-center justify-center text-muted hover:text-foreground hover:bg-surface-1 transition-colors"
        >
          {dark ? <Sun size={16} /> : <Moon size={16} />}
        </button>
      </header>

      {/* Main content */}
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  )
}
