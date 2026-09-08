import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { ThemeProvider, useTheme } from "../components/ThemeContext"

function Probe() {
  const { theme, toggle } = useTheme()
  return (<><span data-testid="theme">{theme}</span><button onClick={toggle}>flip</button></>)
}

beforeEach(() => {
  const mem: Record<string, string> = {}
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => (k in mem ? mem[k] : null),
    setItem: (k: string, v: string) => { mem[k] = String(v) },
    removeItem: (k: string) => { delete mem[k] },
    clear: () => { for (const k of Object.keys(mem)) delete mem[k] },
  } as any)
  document.documentElement.removeAttribute("data-theme")
})

describe("ThemeContext", () => {
  it("defaults dark, toggles to light and persists", () => {
    render(<ThemeProvider><Probe /></ThemeProvider>)
    expect(screen.getByTestId("theme").textContent).toBe("dark")
    fireEvent.click(screen.getByText("flip"))
    expect(screen.getByTestId("theme").textContent).toBe("light")
    expect(document.documentElement.dataset.theme).toBe("light")
    expect(localStorage.getItem("matsya-theme")).toBe("light")
  })
  it("restores persisted theme", () => {
    localStorage.setItem("matsya-theme", "light")
    render(<ThemeProvider><Probe /></ThemeProvider>)
    expect(screen.getByTestId("theme").textContent).toBe("light")
  })
})
