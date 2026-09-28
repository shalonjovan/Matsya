import { describe, it, expect, vi, afterEach, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import MapShell from "../components/MapShell"

afterEach(() => { vi.unstubAllGlobals() })

const sim: any = {
  id: "1", name: "t",
  area: { bbox: [80.15, 13.08, 80.20, 13.13], crs: "EPSG:4326" },
  rainfall: { rateMmHr: 50, durationHr: 1 },
  flood: { stats: { steps: 6, minutesPerFrame: 5 } },
}

describe("MapShell Safe Route tab", () => {
  it("opens the safe route panel with origin from a map click", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: true,
      json: async () => ({ lat: 13.10, lon: 80.19, elevation: 15.5, floodDepth: 0.1, velocity: 0.1 }),
    } as any)))
    render(<MapShell simulation={sim} />)
    fireEvent.click(screen.getByRole("tab", { name: /safe route/i }))
    expect(await screen.findByText(/nearest refuge \+ route/i)).toBeInTheDocument()
    expect(screen.getByTestId("saferoute-lat")).toBeInTheDocument()
  })
})

function liveSim() {
  const zones = Array.from({ length: 13 }, (_, i) => ({
    id: `om-${i}`, mode: "variable", unit: "rate", totalTime: 24.0, maxRain: 1.0,
    points: [{ time: 0.25, amount: 0.5 }, { time: 23.25, amount: 0.5 }],
    polygon: { type: "Polygon", coordinates: [[[80.14, 13.02], [80.15, 13.02], [80.15, 13.03], [80.14, 13.03], [80.14, 13.02]]] },
  }))
  return {
    id: "live", name: "Live — Chennai", live: true,
    area: { bbox: [80.13968, 13.01593, 80.28967, 13.14146], crs: "EPSG:4326" },
    rainfall: { rateMmHr: 0, durationHr: 24, zones },
    flood: { floodUri: "/api/simulations/live/flood?time=0", stats: { steps: 73, minutesPerFrame: 19.726, maxDepth: 0.5 } },
    results: { live: { windowStart: "2026-09-14T20:44:48+00:00", tickAt: "2026-09-15T08:44:48+00:00", windowEnd: "2026-09-15T20:44:48+00:00" } },
  } as any
}

describe("MapShell live rain grid", () => {
  // jsdom has no 2D canvas: hand Leaflet's Canvas renderer a no-op
  // context so the grid layer's redraws stay silent.
  const origGetContext = HTMLCanvasElement.prototype.getContext
  beforeEach(() => {
    HTMLCanvasElement.prototype.getContext = (() =>
      new Proxy({}, { get: () => () => undefined })) as any
  })
  afterEach(() => {
    HTMLCanvasElement.prototype.getContext = origGetContext
  })
  function stubFetches() {
    vi.stubGlobal("fetch", vi.fn(async (url: any) => {
      const u = String(url)
      if (u.includes("/api/hydro/summary"))
        return { ok: true, json: async () => ({ drains: 1, waterbodies: 1, rivers: 0, snapped_to_waterbody: 1, to_river: 0, to_sea: 0 }) } as any
      return { ok: true, json: async () => ({ drains: { features: [] }, waterbodies: { features: [] } }) } as any
    }))
  }
  it("shows the rain grid toggle on the layers tab for live sims", async () => {
    stubFetches()
    render(<MapShell simulation={liveSim()} />)
    expect(await screen.findByLabelText(/Rain grid/)).toBeInTheDocument()
  })
  it("shows the cell inspector empty state on the inspector tab", async () => {
    stubFetches()
    render(<MapShell simulation={liveSim()} />)
    fireEvent.click(screen.getByRole("tab", { name: "Inspect" }))
    expect(await screen.findByText(/click a rain grid cell/i)).toBeInTheDocument()
  })
})
