import { createContext, useContext, useEffect, useState } from "react"
import type { ReactNode } from "react"

export type UiTheme = "light" | "dark"

const STORAGE_KEY = "matsya-theme"

interface ThemeCtx {
  theme: UiTheme
  toggle: () => void
}

const Ctx = createContext<ThemeCtx>({ theme: "dark", toggle: () => {} })

export function useTheme(): ThemeCtx {
  return useContext(Ctx)
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<UiTheme>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      return saved === "light" ? "light" : "dark"
    } catch {
      return "dark"
    }
  })

  useEffect(() => {
    try {
      document.documentElement.dataset.theme = theme
      localStorage.setItem(STORAGE_KEY, theme)
    } catch {}
  }, [theme])

  return (
    <Ctx.Provider value={{ theme, toggle: () => setTheme(t => (t === "dark" ? "light" : "dark")) }}>
      {children}
    </Ctx.Provider>
  )
}
