import { useEffect } from 'react'
import { create } from 'zustand'

export type Theme = 'dark' | 'light'

interface ThemeStore {
  theme: Theme
  setTheme: (t: Theme) => void
  toggle: () => void
}

const STORAGE_KEY = 'dbsherpa:theme'

function readInitial(): Theme {
  if (typeof window === 'undefined') return 'dark'
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    if (saved === 'dark' || saved === 'light') return saved
  } catch {
    // ignore; fall back to default
  }
  return 'dark'
}

export const useThemeStore = create<ThemeStore>((set, get) => ({
  theme: readInitial(),
  setTheme: (t) => {
    try { window.localStorage.setItem(STORAGE_KEY, t) } catch { /* noop */ }
    set({ theme: t })
  },
  toggle: () => {
    const next: Theme = get().theme === 'dark' ? 'light' : 'dark'
    get().setTheme(next)
  },
}))

/** Call this once near the root; keeps <html data-theme> in sync. */
export function useApplyTheme(): void {
  const theme = useThemeStore((s) => s.theme)
  useEffect(() => {
    if (typeof document === 'undefined') return
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])
}
