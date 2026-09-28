// Pure helpers for the live rain-grid overlay + cell inspector.
// No Leaflet, no React: every export is unit-testable.

export interface RainPoint { time: number; amount: number }

export interface RampStop { upTo: number; color: string }

// mm/hr ramp, ordered low -> high. `upTo` is a fraction of the grid peak.
/**
 * Absolute mm/hr stops. Absolute (not peak-relative) so a city-wide drizzle
 * still shows spatial structure instead of saturating every cell at the
 * top colour: with a relative ramp the max cell always hit "red" and the
 * differences between 0.4 and 1.3 mm/hr were invisible.
 */
export const RATE_RAMP: RampStop[] = [
  { upTo: 0.0, color: "#22d3ee" },
  { upTo: 0.25, color: "#38bdf8" },
  { upTo: 1.0, color: "#3b82f6" },
  { upTo: 2.5, color: "#a78bfa" },
  { upTo: 7.5, color: "#fbbf24" },
  { upTo: 20.0, color: "#fb7185" },
  { upTo: 100.0, color: "#ef4444" },
]

export function rateColor(rate: number, peak?: number): { color: string; fillOpacity: number } {
  const r = Math.max(0, Number(rate) || 0)
  if (r <= 0) return { color: RATE_RAMP[0].color, fillOpacity: 0 }
  for (const stop of RATE_RAMP) {
    if (r <= stop.upTo) return { color: stop.color, fillOpacity: 0.45 }
  }
  return { color: RATE_RAMP[RATE_RAMP.length - 1].color, fillOpacity: 0.45 }
}

/** mm/hr at a window-relative hour. Linear interp, clamped at both ends. */
export function rateAtHour(points: RainPoint[] | null | undefined, hour: number): number {
  if (!Array.isArray(points) || points.length === 0) return 0
  const h = Number(hour)
  if (!isFinite(h)) return 0
  const sorted = [...points]
    .filter(p => p && isFinite(Number(p.time)) && isFinite(Number(p.amount)))
    .sort((a, b) => Number(a.time) - Number(b.time))
  if (sorted.length === 0) return 0
  if (h <= Number(sorted[0].time)) return Math.max(0, Number(sorted[0].amount))
  const last = sorted[sorted.length - 1]
  if (h >= Number(last.time)) return Math.max(0, Number(last.amount))
  for (let i = 0; i < sorted.length - 1; i++) {
    const p0 = sorted[i], p1 = sorted[i + 1]
    const t0 = Number(p0.time), t1 = Number(p1.time)
    if (t0 <= h && h <= t1) {
      const span = t1 - t0
      const frac = span === 0 ? 0 : (h - t0) / span
      return Math.max(0, Number(p0.amount) * (1 - frac) + Number(p1.amount) * frac)
    }
  }
  return Math.max(0, Number(last.amount))
}

/** Slider frame -> hours since windowStart. */
export function frameToWindowHour(frame: number, minutesPerFrame: number): number {
  const mpf = Number(minutesPerFrame)
  if (!isFinite(mpf) || mpf <= 0) return 0
  return Math.max(0, Number(frame) || 0) * mpf / 60.0
}

/** NOW as hours since windowStart, from results.live meta. Null when unknown. */
export function liveNowHour(live: any): number | null {
  try {
    const w0 = Date.parse(String(live?.windowStart))
    const tick = Date.parse(String(live?.tickAt))
    if (!isFinite(w0) || !isFinite(tick) || tick < w0) return null
    return (tick - w0) / 3600000.0
  } catch {
    return null
  }
}

/** Signed minute offset -> "-06:20" / "+05:40" / "NOW". */
export function formatSignedOffset(minutes: number): string {
  const m = Math.round(Number(minutes) || 0)
  if (m === 0) return "NOW"
  const sign = m < 0 ? "−" : "+"
  const a = Math.abs(m)
  const hh = String(Math.floor(a / 60)).padStart(2, "0")
  const mm = String(a % 60).padStart(2, "0")
  return `${sign}${hh}:${mm}`
}

/**
 * Badge for a window-relative hour: "NOW" at the tick, else a signed
 * offset with past/future wording. Falls back to T+HH:MM without meta.
 */
export function cellWhenBadge(hour: number, minutesPerFrame: number, live: any): string {
  const h = Number(hour)
  const mpf = Number(minutesPerFrame) || 5
  const now = liveNowHour(live)
  if (!isFinite(h) || now == null) {
    const t = Math.max(0, isFinite(h) ? h : 0)
    return `T+${String(Math.floor(t)).padStart(2, "0")}:${String(Math.floor((t % 1) * 60)).padStart(2, "0")}`
  }
  const diffMin = (h - now) * 60
  if (Math.abs(diffMin) <= mpf / 2) return "NOW"
  return `${formatSignedOffset(diffMin)}${diffMin < 0 ? " ago" : " ahead"}`
}

/** Leaflet path style for one grid cell at the current playhead. */
export function rainGridStyle(
  props: { rate: number },
  opacity: number,
): { color: string; weight: number; fillColor: string; fillOpacity: number; opacity: number } {
  const rate = Math.max(0, Number(props?.rate) || 0)
  const op = Math.max(0, Math.min(1, Number(opacity) || 0))
  const c = rateColor(rate)
  return {
    color: c.color,
    weight: 1,
    fillColor: c.color,
    fillOpacity: rate <= 0 ? 0 : c.fillOpacity * op,
    opacity: op,
  }
}

/** Sticky tooltip label for one grid cell. */
export function cellTooltip(
  props: { id: string; row: number | null; col: number | null; rate: number },
  when?: string | null,
): string {
  const pos = props.row != null && props.col != null ? ` r${props.row}c${props.col}` : ""
  const rate = `${(Math.max(0, Number(props?.rate) || 0)).toFixed(1)} mm/hr`
  return `${props?.id ?? "cell"}${pos}: ${rate}${when ? ` · ${when}` : ""}`
}

/** Ray-cast a [lon,lat] against a GeoJSON polygon ring. */
function ringContains(ring: number[][], lon: number, lat: number): boolean {
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = Number(ring[i]?.[0]), yi = Number(ring[i]?.[1])
    const xj = Number(ring[j]?.[0]), yj = Number(ring[j]?.[1])
    if (!isFinite(xi) || !isFinite(yi) || !isFinite(xj) || !isFinite(yj)) return false
    const hit = (yi > lat) !== (yj > lat) && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi
    if (hit) inside = !inside
  }
  return inside
}

/**
 * Cell under a lon/lat with its index. Last match wins, mirroring the
 * backend's last-painted-wins zone lookup. Null when nothing contains it.
 */
export function zoneAtPoint(
  zones: any[] | null | undefined,
  lon: number,
  lat: number,
): { zone: any; index: number } | null {
  if (!Array.isArray(zones)) return null
  const x = Number(lon), y = Number(lat)
  if (!isFinite(x) || !isFinite(y)) return null
  for (let i = zones.length - 1; i >= 0; i--) {
    try {
      if (validRing(zones[i]?.polygon) && ringContains(zones[i].polygon.coordinates[0], x, y)) {
        return { zone: zones[i], index: i }
      }
    } catch { /* skip one bad zone */ }
  }
  return null
}

/** Resolve a clicked cell id to its zone, index and lattice size. Null when unknown. */
export function findCellZone(
  simulation: any,
  zoneId: string,
): { zone: any; index: number; grid: number | null } | null {
  try {
    const zones = simulation?.rainfall?.zones
    if (!Array.isArray(zones)) return null
    const index = zones.findIndex((z: any) => String(z?.id) === String(zoneId))
    if (index < 0) return null
    return { zone: zones[index], index, grid: inferGridSize(zones.length) }
  } catch {
    return null
  }
}

/** Lattice size for a square zone count (144 -> 12). Null otherwise. */
export function inferGridSize(count: number): number | null {
  const n = Math.floor(Number(count))
  if (!isFinite(n) || n <= 0) return null
  const g = Math.round(Math.sqrt(n))
  return g * g === n ? g : null
}

/**
 * Linear zone index -> lattice position. Backend loops lon(i) outer,
 * lat(j) inner, so idx = col*grid + row.
 */
export function cellIndexToRowCol(index: number, grid: number): { row: number | null; col: number | null } {
  const g = Math.floor(Number(grid) || 0)
  if (!isFinite(g) || g <= 0) return { row: null, col: null }
  const i = Math.max(0, Math.floor(Number(index) || 0))
  return { row: i % g, col: Math.floor(i / g) }
}

/** Total mm over the window (hourly amounts summed). */
export function cellAccumulation(points: RainPoint[] | null | undefined): number {
  if (!Array.isArray(points)) return 0
  let s = 0
  for (const p of points) {
    const a = Number(p?.amount)
    if (isFinite(a) && a > 0) s += a
  }
  return s
}

export interface GridFeatureProps {
  id: string
  row: number | null
  col: number | null
  rate: number
  peak: number
  total: number
  totalTime: number
  unit: string
}

function validRing(polygon: any): boolean {
  try {
    const ring = polygon?.coordinates?.[0]
    return Array.isArray(ring) && ring.length >= 4 &&
      ring.every((c: any) => Array.isArray(c) && isFinite(Number(c[0])) && isFinite(Number(c[1])))
  } catch {
    return false
  }
}

/** Zones -> GeoJSON FeatureCollection for the Leaflet grid layer. Skips broken polygons. */
export function buildRainGridFeatures(zones: any[], opts: { hour: number }): {
  type: "FeatureCollection"
  features: { type: "Feature"; geometry: any; properties: GridFeatureProps }[]
} {
  const list = Array.isArray(zones) ? zones : []
  const grid = inferGridSize(list.length)
  const hour = Number(opts?.hour)
  const features: { type: "Feature"; geometry: any; properties: GridFeatureProps }[] = []
  list.forEach((z: any, i: number) => {
    try {
      if (!z || !validRing(z.polygon)) return
      const pts = (z.points || []) as RainPoint[]
      const { row, col } = grid == null ? { row: null, col: null } : cellIndexToRowCol(i, grid)
      const peak = Math.max(0, Number(z.maxRain ?? Math.max(0, ...pts.map(p => Number(p?.amount) || 0))) || 0)
      features.push({
        type: "Feature",
        geometry: { type: "Polygon", coordinates: z.polygon.coordinates },
        properties: {
          id: String(z.id ?? `z${i + 1}`),
          row, col,
          rate: rateAtHour(pts, hour),
          peak,
          total: cellAccumulation(pts),
          totalTime: Number(z.totalTime) || 0,
          unit: String(z.unit || "rate"),
        },
      })
    } catch { /* skip one bad zone, keep the grid */ }
  })
  return { type: "FeatureCollection", features }
}
