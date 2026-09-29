import "@testing-library/jest-dom/vitest"
import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent, within } from "@testing-library/react"
import SelectSimulation from "../components/SelectSimulation"
global.fetch = vi.fn(() =>
  Promise.resolve({
    ok: true,
    json: () =>
      Promise.resolve([
        {
          id: "1",
          name: "Chennai",
          area: { bbox: [80.15, 13.08, 80.2, 13.13], crs: "EPSG:4326" },
          rainfall: { rateMmHr: 50, durationHr: 1 },
          status: "Ready",
          metadata: { updated: "2026-08-30T00:00:00Z" },
        },
      ]),
  })
) as any
describe("SelectSimulation", () => {
  it("renders cards", async () => {
    render(<SelectSimulation />)
    expect(await screen.findByText("Chennai")).toBeInTheDocument()
    expect(screen.getByText("Ready")).toBeInTheDocument()
    // should have Open button
    expect(screen.getByText("Open")).toBeInTheDocument()
  })

  it("pins a singular live entry that opens the live sim", async () => {
    const live = {
      id: "realtime-chennai-01",
      name: "Live — Chennai",
      area: { bbox: [80.15, 13.08, 80.2, 13.13], crs: "EPSG:4326" },
      rainfall: { rateMmHr: 0.6, durationHr: 24 },
      status: "Completed",
      live: true,
      metadata: { updated: "2026-09-09T06:00:00Z" },
    }
    const normal = {
      id: "2", name: "Normal storm", area: { bbox: [80.15, 13.08, 80.2, 13.13], crs: "EPSG:4326" },
      rainfall: { rateMmHr: 50, durationHr: 1 }, status: "Ready", metadata: { updated: "2026-09-09T06:00:00Z" },
    }
    ;(global.fetch as any).mockResolvedValueOnce({
      ok: true, json: () => Promise.resolve([normal, live]),
    })
    // bust the 30s sim list cache so this render refetches
    const nowSpy = vi.spyOn(Date, "now").mockReturnValue(Date.now() + 31000)
    const onOpen = vi.fn()
    const { container } = render(<SelectSimulation onOpen={onOpen} />)
    const hero = await screen.findByTestId("live-hero")
    nowSpy.mockRestore()
    expect(hero).toBeInTheDocument()
    expect(hero.textContent).toMatch(/LIVE/)
    // live sim excluded from the normal grid (only one entry)
    const grid = container.querySelector("[data-testid='sim-grid']")
    expect(grid?.textContent).not.toMatch(/Live — Chennai/)
    expect(grid?.textContent).toMatch(/Normal storm/)
    fireEvent.click(within(hero).getByText("Open"))
    expect(onOpen).toHaveBeenCalledWith("realtime-chennai-01")
  })
  it("hides the live entry when no live sim exists", async () => {
    ;(global.fetch as any).mockResolvedValueOnce({
      ok: true, json: () => Promise.resolve([{
        id: "1", name: "Chennai",
        area: { bbox: [80.15, 13.08, 80.2, 13.13], crs: "EPSG:4326" },
        rainfall: { rateMmHr: 50, durationHr: 1 },
        status: "Ready", metadata: { updated: "2026-08-30T00:00:00Z" },
      }]),
    })
    const nowSpy = vi.spyOn(Date, "now").mockReturnValue(Date.now() + 62000)
    render(<SelectSimulation />)
    await screen.findByText("Chennai")
    nowSpy.mockRestore()
    expect(screen.queryByTestId("live-hero")).not.toBeInTheDocument()
  })

  it("shows the zonal peak on the live hero when the base rate is zero", async () => {
    const live = {
      id: "realtime-chennai-01",
      name: "Live — Chennai",
      area: { bbox: [80.15, 13.08, 80.2, 13.13], crs: "EPSG:4326" },
      // Open-Meteo ticks stamp a numeric 0.0 base rate; the headline must
      // still come from the 144 variable cells, not the base rate.
      rainfall: {
        rateMmHr: 0, durationHr: 24,
        zones: [
          { id: "om-0", maxRain: 0.4, points: [{ time: 0.25, amount: 0.4 }] },
          { id: "om-1", maxRain: 1.3, points: [{ time: 0.25, amount: 1.3 }] },
        ],
      },
      status: "Completed",
      live: true,
      metadata: { updated: "2026-09-29T06:00:00Z" },
    }
    ;(global.fetch as any).mockResolvedValueOnce({
      ok: true, json: () => Promise.resolve([live]),
    })
    const nowSpy = vi.spyOn(Date, "now").mockReturnValue(Date.now() + 93000)
    render(<SelectSimulation onOpen={() => {}} />)
    const hero = await screen.findByTestId("live-hero")
    nowSpy.mockRestore()
    expect(hero.textContent).toMatch(/1\.3 mm\/hr \(zonal\)/)
  })
})
