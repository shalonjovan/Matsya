import { describe, it, expect, vi, afterEach } from "vitest"
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
