import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCost(usd: number): string {
  if (usd === 0) return '$0'
  if (usd < 0.01) return `$${usd.toFixed(4)}`
  return `$${usd.toFixed(2)}`
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  const min = Math.floor(ms / 60000)
  const sec = Math.floor((ms % 60000) / 1000)
  return `${min}m ${sec}s`
}

export const statusConfig = {
  passed: { color: 'text-success', bg: 'bg-success/10 text-success', dot: 'bg-success' },
  failed: { color: 'text-danger', bg: 'bg-danger/10 text-danger', dot: 'bg-danger' },
  pending: { color: 'text-warning', bg: 'bg-warning/10 text-warning', dot: 'bg-warning' },
  in_progress: { color: 'text-brand-600', bg: 'bg-brand-100 text-brand-700', dot: 'bg-brand-500' },
} as Record<string, { color: string; bg: string; dot: string }>
