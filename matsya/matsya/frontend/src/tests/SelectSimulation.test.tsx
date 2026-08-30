import "@testing-library/jest-dom/vitest"
import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
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
})
