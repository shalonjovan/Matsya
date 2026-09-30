import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import HomePage from "../components/HomePage"

function setup() {
  const onLaunch = vi.fn()
  const onReplay2015 = vi.fn()
  render(<HomePage onLaunch={onLaunch} onReplay2015={onReplay2015} />)
  return { onLaunch, onReplay2015 }
}

describe("HomePage", () => {
  it("identifies the problem statement", () => {
    setup()
    expect(screen.getAllByText(/SIH26085/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/NCMRWF/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Urban Flood Nowcasting System/).length).toBeGreaterThan(0)
  })

  it("states the core idea that rain is not flood", () => {
    setup()
    expect(screen.getByText(/rain does not equal flood/i)).toBeInTheDocument()
    expect(screen.getAllByText(/drains?/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/lakes?/i).length).toBeGreaterThan(0)
  })

  it("ties the problem to metropolitan cities and a city-independent design", () => {
    setup()
    expect(screen.getAllByText(/Mumbai/).length).toBeGreaterThan(0)
    expect(screen.getByText(/Not limited to Chennai/i)).toBeInTheDocument()
  })

  it("routes to the console and the 2015 replay", () => {
    const { onLaunch, onReplay2015 } = setup()
    fireEvent.click(screen.getByRole("button", { name: /launch console/i }))
    fireEvent.click(screen.getByRole("button", { name: /dec 2015 replay/i }))
    expect(onLaunch).toHaveBeenCalledTimes(1)
    expect(onReplay2015).toHaveBeenCalledTimes(1)
  })
})
