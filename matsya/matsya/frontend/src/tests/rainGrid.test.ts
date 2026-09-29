import { describe, it, expect } from "vitest"
import {
  RATE_RAMP,
  rateColor,
  rateAtHour,
  frameToWindowHour,
  liveNowHour,
  formatSignedOffset,
  cellWhenBadge,
  rainGridStyle,
  cellTooltip,
  zoneAtPoint,
  findCellZone,
  inferGridSize,
  cellIndexToRowCol,
  cellAccumulation,
  buildRainGridFeatures,
} from "../utils/rainGrid"

function ring(x0: number, y0: number, x1: number, y1: number) {
  return { type: "Polygon", coordinates: [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]] }
}

function zone(id: string, pts: { time: number; amount: number }[], x0 = 0, y0 = 0) {
  return {
    id, mode: "variable", unit: "rate", totalTime: 24.0,
    maxRain: Math.max(...pts.map(p => p.amount)),
    points: pts, polygon: ring(x0, y0, x0 + 1, y0 + 1),
  }
}

const PTS = [
  { time: 0.25, amount: 0.0 },
  { time: 1.25, amount: 2.0 },
  { time: 23.25, amount: 4.0 },
]

describe("rateAtHour", () => {
  it("clamps below the first point to the first value", () => {
    expect(rateAtHour(PTS, 0.0)).toBe(0.0)
  })
  it("interpolates between points", () => {
    // halfway between (0.25,0) and (1.25,2) -> 1.0
    expect(rateAtHour(PTS, 0.75)).toBeCloseTo(1.0, 9)
  })
  it("clamps above the last point to the last value", () => {
    expect(rateAtHour(PTS, 24.0)).toBe(4.0)
  })
  it("returns 0 for empty or missing points", () => {
    expect(rateAtHour([], 5)).toBe(0)
    expect(rateAtHour(null as any, 5)).toBe(0)
  })
})

describe("frameToWindowHour", () => {
  it("maps slider frames onto window hours", () => {
    const mpf = 19.726027397260275 // live 24h / 73 steps
    expect(frameToWindowHour(0, mpf)).toBe(0)
    // last slider frame (tmax = steps-1) lands just short of the window end
    expect(frameToWindowHour(72, mpf)).toBeCloseTo(72 * mpf / 60, 9)
    expect(frameToWindowHour(72, mpf)).toBeCloseTo(23.67123287671233, 9)
    expect(frameToWindowHour(36, mpf)).toBeCloseTo(11.835616438356165, 9)
  })
})

describe("liveNowHour", () => {
  it("derives NOW from windowStart/tickAt", () => {
    const live = { windowStart: "2026-09-14T20:44:48+00:00", tickAt: "2026-09-15T08:44:48+00:00", windowEnd: "2026-09-15T20:44:48+00:00" }
    expect(liveNowHour(live)).toBeCloseTo(12.0, 6)
  })
  it("returns null without usable meta", () => {
    expect(liveNowHour(null)).toBeNull()
    expect(liveNowHour({})).toBeNull()
  })
})

describe("formatSignedOffset", () => {
  it("renders past and future minute offsets as signed HH:MM", () => {
    expect(formatSignedOffset(-380)).toBe("−06:20")
    expect(formatSignedOffset(340)).toBe("+05:40")
    expect(formatSignedOffset(0)).toBe("NOW")
  })
})

describe("cellWhenBadge", () => {
  const MPF = 19.726027397260275
  const LIVE = {
    windowStart: "2026-09-14T20:44:48+00:00",
    tickAt: "2026-09-15T08:44:48+00:00",
    windowEnd: "2026-09-15T20:44:48+00:00",
  }
  it("badges the tick hour as NOW", () => {
    expect(cellWhenBadge(12.0, MPF, LIVE)).toBe("NOW")
  })
  it("badges past and future hours with signed offsets", () => {
    expect(cellWhenBadge(0, MPF, LIVE)).toBe("−12:00 ago")
    expect(cellWhenBadge(23.67123287671233, MPF, LIVE)).toBe("+11:40 ahead")
  })
  it("falls back to window-relative time without live meta", () => {
    expect(cellWhenBadge(5.5, MPF, null)).toBe("T+05:30")
  })
})

describe("rainGridStyle", () => {
  it("hides dry cells and tints wet ones by the ramp", () => {
    const dry = rainGridStyle({ rate: 0 }, 0.55)
    expect(dry.fillOpacity).toBe(0)
    expect(dry.weight).toBe(1)
    const wet = rainGridStyle({ rate: 1.6 }, 0.55)
    expect(wet.fillOpacity).toBeGreaterThan(0)
    expect(wet.fillOpacity).toBeLessThanOrEqual(0.55)
    expect(wet.fillColor).toBe(rateColor(1.6).color)
    expect(wet.opacity).toBe(0.55)
  })
  it("keeps cell borders readable at any opacity", () => {
    expect(rainGridStyle({ rate: 1.6 }, 0).opacity).toBe(0)
    expect(rainGridStyle({ rate: 1.6 }, 0.2).opacity).toBeCloseTo(0.2, 9)
  })
})

describe("cellTooltip", () => {
  it("labels a cell with id, position, rate and badge", () => {
    expect(cellTooltip({ id: "om-57", row: 9, col: 4, rate: 5.82 }, "+05:40 ahead"))
      .toBe("om-57 r9c4: 5.8 mm/hr · +05:40 ahead")
  })
  it("omits position and badge when unknown", () => {
    expect(cellTooltip({ id: "om-3", row: null, col: null, rate: 0 })).toBe("om-3: 0.0 mm/hr")
  })
})

describe("zoneAtPoint", () => {
  const cells = [
    // two adjacent 1-degree boxes, index 0 and 1
    { id: "om-0", polygon: { type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]] } },
    { id: "om-1", polygon: { type: "Polygon", coordinates: [[[1, 0], [2, 0], [2, 1], [1, 1], [1, 0]]] } },
  ]
  it("returns the cell containing the point with its index", () => {
    expect(zoneAtPoint(cells as any, 0.5, 0.5)).toMatchObject({ zone: { id: "om-0" }, index: 0 })
    expect(zoneAtPoint(cells as any, 1.5, 0.25)).toMatchObject({ zone: { id: "om-1" }, index: 1 })
  })
  it("returns null outside every cell", () => {
    expect(zoneAtPoint(cells as any, 9, 9)).toBeNull()
    expect(zoneAtPoint([], 0.5, 0.5)).toBeNull()
    expect(zoneAtPoint(null as any, 0.5, 0.5)).toBeNull()
  })
  it("skips cells with broken polygons", () => {
    const bad = { id: "om-x", polygon: { type: "Polygon", coordinates: [] } }
    expect(zoneAtPoint([bad, cells[0]] as any, 0.5, 0.5)).toMatchObject({ zone: { id: "om-0" }, index: 1 })
  })
})

describe("findCellZone", () => {
  const zones = Array.from({ length: 144 }, (_, i) => ({ id: `om-${i}` }))
  const sim = { rainfall: { zones } }
  it("resolves a zone id to its zone, index and lattice size", () => {
    expect(findCellZone(sim, "om-57")).toEqual({ zone: { id: "om-57" }, index: 57, grid: 12 })
    expect(findCellZone(sim, "om-0")).toMatchObject({ index: 0, grid: 12 })
  })
  it("returns null for unknown ids or missing zones", () => {
    expect(findCellZone(sim, "nope")).toBeNull()
    expect(findCellZone({}, "om-1")).toBeNull()
    expect(findCellZone(null, "om-1")).toBeNull()
  })
})

describe("grid indexing", () => {
  it("infers square lattice sizes", () => {
    expect(inferGridSize(144)).toBe(12)
    expect(inferGridSize(9)).toBe(3)
    expect(inferGridSize(1)).toBe(1)
  })
  it("rejects non-square counts", () => {
    expect(inferGridSize(13)).toBeNull()
    expect(inferGridSize(0)).toBeNull()
  })
  it("maps a linear om- index to row/col", () => {
    // backend loops lon(i) outer, lat(j) inner: idx = i*grid + j
    expect(cellIndexToRowCol(57, 12)).toEqual({ row: 9, col: 4 })
    expect(cellIndexToRowCol(0, 12)).toEqual({ row: 0, col: 0 })
    expect(cellIndexToRowCol(143, 12)).toEqual({ row: 11, col: 11 })
  })
  it("returns nulls without a usable grid size", () => {
    expect(cellIndexToRowCol(5, 0)).toEqual({ row: null, col: null })
  })
})

describe("cellAccumulation", () => {
  it("sums hourly mm over the window", () => {
    expect(cellAccumulation(PTS)).toBeCloseTo(6.0, 9)
    expect(cellAccumulation([])).toBe(0)
  })
})

describe("rateColor", () => {
  it("is transparent at zero", () => {
    expect(RATE_RAMP.length).toBeGreaterThanOrEqual(4)
    expect(rateColor(0).fillOpacity).toBe(0)
  })
  it("uses absolute mm/hr stops, not peak-relative", () => {
    // a city-wide drizzle must not saturate: 1.3 and 0.4 mm/hr differ
    expect(rateColor(0.4).color).not.toBe(rateColor(1.3).color)
    // and the same rate always maps to the same colour regardless of peak
    expect(rateColor(1.3, 1.3).color).toBe(rateColor(1.3, 40).color)
  })
  it("steps up through the ramp with rate", () => {
    const idx = (r: number) => RATE_RAMP.findIndex(s => s.color === rateColor(r).color)
    expect(idx(0.1)).toBeLessThan(idx(0.6))
    expect(idx(0.6)).toBeLessThan(idx(1.6))
    expect(idx(1.6)).toBeLessThan(idx(5))
    expect(idx(5)).toBeLessThan(idx(30))
  })
  it("clamps above the top stop to the strongest colour", () => {
    expect(rateColor(999).color).toBe(RATE_RAMP[RATE_RAMP.length - 1].color)
  })
})

describe("buildRainGridFeatures", () => {
  it("emits one polygon feature per valid zone with row/col/rate props", () => {
    const zones = [zone("om-0", PTS, 0, 0), zone("om-1", PTS, 1, 0), zone("om-2", PTS, 0, 1), zone("om-3", PTS, 1, 1)]
    const fc = buildRainGridFeatures(zones as any, { hour: 0.75 })
    expect(fc.type).toBe("FeatureCollection")
    expect(fc.features).toHaveLength(4)
    const f0 = fc.features[0]
    expect(f0.geometry.type).toBe("Polygon")
    expect(f0.properties.id).toBe("om-0")
    expect(f0.properties.row).toBe(0)
    expect(f0.properties.col).toBe(0)
    expect(f0.properties.rate).toBeCloseTo(1.0, 9)
    expect(fc.features[3].properties).toMatchObject({ row: 1, col: 1 })
  })
  it("skips zones with broken polygons", () => {
    const bad = { ...zone("om-x", PTS), polygon: { type: "Polygon", coordinates: [] } }
    const fc = buildRainGridFeatures([bad] as any, { hour: 1 })
    expect(fc.features).toHaveLength(0)
  })
})
