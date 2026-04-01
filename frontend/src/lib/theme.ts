import { create } from 'zustand'

interface ThemeStore {
  dark: boolean
  toggle: () => void
}

export const useTheme = create<ThemeStore>((set) => ({
  dark: false, // Light by default
  toggle: () =>
    set((s) => {
      const next = !s.dark
      document.documentElement.classList.toggle('dark', next)
      localStorage.setItem('ralph-theme', next ? 'dark' : 'light')
      return { dark: next }
    }),
}))

// Init from localStorage
const saved = typeof window !== 'undefined' && localStorage.getItem('ralph-theme')
if (saved === 'dark') {
  document.documentElement.classList.add('dark')
  useTheme.setState({ dark: true })
}
