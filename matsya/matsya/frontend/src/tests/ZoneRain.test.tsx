import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import ZoneRain, { buildZone, polygonIntersectsBbox } from "../components/ZoneRain"
import type { RainfallZone } from "../types/simulation"

const west: RainfallZone = {
  id: "z1", amount: 200, unit: "rate",
  polygon: { type: "Polygon", coordinates: [[[80.15, 13.08], [80.175, 13.08], [80.175, 13.13], [80.15, 13.13], [80.15, 13.08]]] },
}

describe("buildZone", () => {
  it("assigns sequential ids and keeps valid value zones", () => {
    const z = buildZone({ kind: "value", amount: 200, unit: "rate", polygon: west.polygon }, [])
    expect(z).not.toBeNull()
    expect(z!.id).toBe("z1")
    expect(z!.amount).toBe(200)
  })
  it("rejects negative amounts and non-polygons", () => {
    expect(buildZone({ kind: "value", amount: -5, unit: "rate", polygon: west.polygon }, [])).toBeNull()
    expect(buildZone({ kind: "value", amount: 10, unit: "rate", polygon: { type: "Point", coordinates: [0, 0] } as any }, [])).toBeNull()
    expect(buildZone({ kind: "value", amount: NaN, unit: "rate", polygon: west.polygon }, [])).toBeNull()
  })
  it("refuses a 13th zone (backend cap is 12)", () => {
    const full = Array.from({ length: 12 }, (_, i) => ({ ...west, id: `z${i + 1}` }))
    expect(buildZone({ kind: "value", amount: 10, unit: "rate", polygon: west.polygon }, full)).toBeNull()
  })
  it("accepts valid curve zones and rejects short ones", () => {
    const pts = [{ time: 0, amount: 0 }, { time: 1, amount: 150 }]
    const z = buildZone({ kind: "curve", points: pts, totalTime: 2, maxRain: 150, unit: "rate", polygon: west.polygon }, [])
    expect(z).not.toBeNull()
    expect(z!.mode).toBe("variable")
    expect(z!.points).toEqual(pts)
    expect(buildZone({ kind: "curve", points: [{ time: 0, amount: 5 }], totalTime: 2, maxRain: 150, unit: "rate", polygon: west.polygon }, [])).toBeNull()
    expect(buildZone({ kind: "curve", points: pts, totalTime: 0, maxRain: 150, unit: "rate", polygon: west.polygon }, [])).toBeNull()
  })
})

describe("ZoneRain", () => {
  it("renders amount entry, draw map slot, and empty hint", () => {
    render(<ZoneRain zones={[]} onChange={() => {}} bbox={[80.15, 13.08, 80.20, 13.13]} />)
    expect(screen.getByTestId("zone-amount")).toBeInTheDocument()
    expect(screen.getByTestId("zone-unit")).toBeInTheDocument()
    expect(screen.getByTestId("zone-map")).toBeInTheDocument()
    expect(screen.getByText(/no spatial zones/i)).toBeInTheDocument()
  })

  it("lists zones with amount labels and removes on click", () => {
    const onChange = vi.fn()
    render(<ZoneRain zones={[west]} onChange={onChange} bbox={[80.15, 13.08, 80.20, 13.13]} />)
    expect(screen.getByText(/200.*mm\/hr/i)).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText("Remove zone z1"))
    expect(onChange).toHaveBeenCalledWith([])
  })

  it("labels curve zones with their peak", () => {
    const curve = { ...west, id: "z2", mode: "variable" as const,
      points: [{ time: 0, amount: 0 }, { time: 1, amount: 150 }], totalTime: 2, maxRain: 150 }
    render(<ZoneRain zones={[curve]} onChange={() => {}} bbox={[80.15, 13.08, 80.20, 13.13]} />)
    expect(screen.getByText(/var curve peak 150/i)).toBeInTheDocument()
  })

  it("shows the cap notice at 12 zones", () => {
    const full = Array.from({ length: 12 }, (_, i) => ({ ...west, id: `z${i + 1}` }))
    render(<ZoneRain zones={full} onChange={() => {}} bbox={[80.15, 13.08, 80.20, 13.13]} />)
    expect(screen.getByText(/maximum 12 zones/i)).toBeInTheDocument()
  })
})

describe("polygonIntersectsBbox", () => {
  const BBOX: [number, number, number, number] = [80.15, 13.08, 80.20, 13.13]
  const inside = { type: "Polygon", coordinates: [[[80.16, 13.09], [80.17, 13.09], [80.17, 13.10], [80.16, 13.10], [80.16, 13.09]]] }
  const outside = { type: "Polygon", coordinates: [[[80.30, 13.30], [80.31, 13.30], [80.31, 13.31], [80.30, 13.31], [80.30, 13.30]]] }
  const straddle = { type: "Polygon", coordinates: [[[80.19, 13.09], [80.25, 13.09], [80.25, 13.10], [80.19, 13.10], [80.19, 13.09]]] }
  const engulf = { type: "Polygon", coordinates: [[[80.10, 13.00], [80.30, 13.00], [80.30, 13.20], [80.10, 13.20], [80.10, 13.00]]] }

  it("classifies inside/straddle/engulf as intersecting, outside as not", () => {
    expect(polygonIntersectsBbox(inside, BBOX)).toBe(true)
    expect(polygonIntersectsBbox(straddle, BBOX)).toBe(true)
    expect(polygonIntersectsBbox(engulf, BBOX)).toBe(true)
    expect(polygonIntersectsBbox(outside, BBOX)).toBe(false)
    expect(polygonIntersectsBbox(null, BBOX)).toBe(false)
  })
})
