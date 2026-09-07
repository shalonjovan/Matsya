import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import ZoneRain, { buildZone } from "../components/ZoneRain"
import type { RainfallZone } from "../types/simulation"

const west: RainfallZone = {
  id: "z1", amount: 200, unit: "rate",
  polygon: { type: "Polygon", coordinates: [[[80.15, 13.08], [80.175, 13.08], [80.175, 13.13], [80.15, 13.13], [80.15, 13.08]]] },
}

describe("buildZone", () => {
  it("assigns sequential ids and keeps valid zones", () => {
    const z = buildZone(200, "rate", west.polygon, [])
    expect(z).not.toBeNull()
    expect(z!.id).toBe("z1")
    expect(z!.amount).toBe(200)
  })
  it("rejects negative amounts and non-polygons", () => {
    expect(buildZone(-5, "rate", west.polygon, [])).toBeNull()
    expect(buildZone(10, "rate", { type: "Point", coordinates: [0, 0] } as any, [])).toBeNull()
    expect(buildZone(NaN, "rate", west.polygon, [])).toBeNull()
  })
  it("refuses a 13th zone (backend cap is 12)", () => {
    const full = Array.from({ length: 12 }, (_, i) => ({ ...west, id: `z${i + 1}` }))
    expect(buildZone(10, "rate", west.polygon, full)).toBeNull()
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

  it("shows the cap notice at 12 zones", () => {
    const full = Array.from({ length: 12 }, (_, i) => ({ ...west, id: `z${i + 1}` }))
    render(<ZoneRain zones={full} onChange={() => {}} bbox={[80.15, 13.08, 80.20, 13.13]} />)
    expect(screen.getByText(/maximum 12 zones/i)).toBeInTheDocument()
  })
})
