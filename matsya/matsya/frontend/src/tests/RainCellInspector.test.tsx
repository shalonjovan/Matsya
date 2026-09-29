import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import RainCellInspector from "../components/RainCellInspector"
import { rateAtHour } from "../utils/rainGrid"

// Triangular 24h hyetograph, peak 6.0 mm/hr at hour 12.25, total 66.5 mm.
const PTS = Array.from({ length: 24 }, (_, i) => ({
  time: 0.25 + i,
  amount: i === 12 ? 6.0 : i < 12 ? i * 0.5 : (23 - i) * 0.5,
}))

function cell() {
  return {
    id: "om-57", mode: "variable", unit: "rate", totalTime: 24.0,
    maxRain: 6.0, points: PTS,
    polygon: { type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]] },
  }
}

const MPF = 19.726027397260275
const LIVE = {
  windowStart: "2026-09-14T20:44:48+00:00",
  tickAt: "2026-09-15T08:44:48+00:00",
  windowEnd: "2026-09-15T20:44:48+00:00",
}

function show(props: any = {}) {
  return render(
    <RainCellInspector cell={cell() as any} index={57} grid={12} time={36} mpf={MPF} live={LIVE} {...props} />
  )
}

describe("RainCellInspector", () => {
  it("shows an empty state with no cell", () => {
    render(<RainCellInspector cell={null} index={0} grid={12} time={0} mpf={MPF} live={LIVE} />)
    expect(screen.getByText(/click a rain grid cell/i)).toBeInTheDocument()
  })

  it("headers the cell id with its lattice position", () => {
    show()
    expect(screen.getByTestId("raincell-panel")).toHaveTextContent("om-57")
    expect(screen.getByTestId("raincell-panel")).toHaveTextContent(/row 9.*col 4/i)
  })

  it("reads zero at the window start (clamped to the first hourly value)", () => {
    show({ time: 0 })
    expect(screen.getByTestId("raincell-rate")).toHaveTextContent("0.0 mm/hr")
  })

  it("follows the slider: rate changes when the time prop changes", () => {
    const r = show({ time: 0 })
    const before = screen.getByTestId("raincell-rate").textContent
    r.rerender(
      <RainCellInspector cell={cell() as any} index={57} grid={12} time={60} mpf={MPF} live={LIVE} />
    )
    const after = screen.getByTestId("raincell-rate").textContent
    expect(after).toContain("mm/hr")
    expect(after).not.toBe(before)
    const hour = 60 * MPF / 60
    expect(after).toContain(rateAtHour(PTS, hour).toFixed(1))
  })

  it("badges past hours as ago", () => {
    show({ time: 0 })
    expect(screen.getByTestId("raincell-when")).toHaveTextContent(/ago/i)
  })

  it("badges future hours as ahead", () => {
    show({ time: 72 })
    expect(screen.getByTestId("raincell-when")).toHaveTextContent(/ahead/i)
  })

  it("badges the tick frame as NOW", () => {
    // tickAt exactly at frame 36's hour so NOW has margin
    const live = { ...LIVE, tickAt: "2026-09-15T08:34:56+00:00" }
    show({ time: 36, live })
    expect(screen.getByTestId("raincell-when")).toHaveTextContent("NOW")
  })

  it("shows peak and 24h accumulation", () => {
    show()
    expect(screen.getByTestId("raincell-panel")).toHaveTextContent(/6\.0 mm\/hr peak/i)
    expect(screen.getByTestId("raincell-panel")).toHaveTextContent(/66\.5 mm \/ 24h/i)
  })

  it("draws a sparkline with a NOW marker when live meta is known", () => {
    show()
    expect(screen.getByTestId("raincell-sparkline")).toBeInTheDocument()
    expect(screen.getByTestId("raincell-now-marker")).toBeInTheDocument()
  })

  it("omits the NOW marker without live meta", () => {
    show({ live: null })
    expect(screen.getByTestId("raincell-sparkline")).toBeInTheDocument()
    expect(screen.queryByTestId("raincell-now-marker")).toBeNull()
  })
})
