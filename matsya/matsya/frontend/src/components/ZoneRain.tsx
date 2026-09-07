import { useState, useEffect, useRef } from "react"
import type { RainfallZone } from "../types/simulation"
import { ZONE_PALETTE, MAX_RAIN_ZONES } from "../types/simulation"
import { CloudRain, Trash2, AlertTriangle } from "lucide-react"

export function buildZone(
  amount: number,
  unit: "rate" | "total",
  polygon: any,
  existing: RainfallZone[]
): RainfallZone | null {
  try {
    if (!isFinite(amount) || amount < 0) return null
    if ((existing?.length ?? 0) >= MAX_RAIN_ZONES) return null
    if (!polygon || polygon.type !== "Polygon") return null
    const ring = polygon.coordinates?.[0]
    if (!Array.isArray(ring) || ring.length < 4) return null
    const taken = new Set((existing ?? []).map(z => z.id))
    let n = 1
    while (taken.has(`z${n}`) && n <= MAX_RAIN_ZONES) n++
    if (n > MAX_RAIN_ZONES) return null
    return { id: `z${n}`, amount, unit, polygon: { type: "Polygon", coordinates: polygon.coordinates } }
  } catch {
    return null
  }
}

export function polygonIntersectsBbox(
  polygon: any,
  bbox: [number, number, number, number]
): boolean {
  try {
    const ring = polygon?.coordinates?.[0]
    if (!Array.isArray(ring) || ring.length < 4) return false
    const [minLon, minLat, maxLon, maxLat] = bbox
    if (!(minLon < maxLon && minLat < maxLat)) return false
    const inBox = ([lon, lat]: any) => lon >= minLon && lon <= maxLon && lat >= minLat && lat <= maxLat
    // any polygon vertex inside the bbox
    for (const pt of ring) {
      if (inBox(pt)) return true
    }
    // any bbox corner inside the polygon (engulf case) — ray cast
    const corners: [number, number][] = [[minLon, minLat], [maxLon, minLat], [maxLon, maxLat], [minLon, maxLat]]
    const inPoly = ([x, y]: [number, number]) => {
      let inside = false
      for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        const [xi, yi] = ring[i], [xj, yj] = ring[j]
        if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside
      }
      return inside
    }
    for (const c of corners) {
      if (inPoly(c)) return true
    }
    // edge crossings (straddle case) — orientation test
    const orient = (a: any, b: any, c: any) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    const crosses = (p1: any, p2: any, p3: any, p4: any) => {
      const d1 = orient(p3, p4, p1), d2 = orient(p3, p4, p2), d3 = orient(p1, p2, p3), d4 = orient(p1, p2, p4)
      return ((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) && ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0))
    }
    const edges: [[number, number], [number, number]][] = [
      [corners[0], corners[1]], [corners[1], corners[2]], [corners[2], corners[3]], [corners[3], corners[0]],
    ]
    for (let i = 0; i < ring.length - 1; i++) {
      for (const [e1, e2] of edges) {
        if (crosses(ring[i], ring[i + 1], e1, e2)) return true
      }
    }
    return false
  } catch {
    return false
  }
}

interface Props {
  zones: RainfallZone[]
  onChange: (zones: RainfallZone[]) => void
  bbox: [number, number, number, number]
}

export default function ZoneRain({ zones, onChange, bbox }: Props) {
  const [amount, setAmount] = useState("100")
  const [zunit, setZunit] = useState<"rate" | "total">("rate")
  const [drawError, setDrawError] = useState<string | null>(null)
  const mapRef = useRef<HTMLDivElement>(null)
  const mapInstance = useRef<any>(null)
  const drawLayerRef = useRef<any>(null)
  const zonesRef = useRef(zones)
  zonesRef.current = zones
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange

  const capped = (zones?.length ?? 0) >= MAX_RAIN_ZONES

  // Draw map: polygon tool only. Drawn region pairs with the amount above;
  // the layer clears after each add so the flow repeats: amount → draw → repeat.
  useEffect(() => {
    if (!mapRef.current) return
    let cancelled = false
    const init = async () => {
      await import("leaflet")
      await import("leaflet-draw")
      // @ts-ignore
      await import("leaflet/dist/leaflet.css")
      // @ts-ignore
      await import("leaflet-draw/dist/leaflet.draw.css")
      if (cancelled || !mapRef.current) return
      const L = ((window as any).L ?? {}) as any
      if (!L.map || !L.Draw || !L.Control || !(L.Control as any).Draw) {
        if (!cancelled) setDrawError("Map drawing library failed to load. Reload and retry.")
        return
      }
      if (mapInstance.current) {
        try { mapInstance.current.remove() } catch {}
      }
      const [minLon, minLat, maxLon, maxLat] = bbox
      const map = L.map(mapRef.current).fitBounds([[minLat, minLon], [maxLat, maxLon]])
      L.tileLayer("https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OSM" }).addTo(map)
      // simulation domain marking — zones only take effect inside this box
      try {
        ;(L as any).rectangle([[minLat, minLon], [maxLat, maxLon]], {
          color: "#06b6d4", weight: 2, dashArray: "6, 6", fill: false, interactive: false,
        }).addTo(map).bindTooltip("Simulation domain", { sticky: true })
      } catch {}
      const drawn = new (L as any).FeatureGroup()
      map.addLayer(drawn)
      drawLayerRef.current = drawn
      // reference: already-added zones (read-only, palette colors)
      try {
        zonesRef.current?.forEach((z, i) => {
          const latlngs = z.polygon.coordinates[0].map((c: any) => [c[1], c[0]])
          ;(L as any).polygon(latlngs, {
            color: ZONE_PALETTE[i % ZONE_PALETTE.length], weight: 2,
            fillColor: ZONE_PALETTE[i % ZONE_PALETTE.length], fillOpacity: 0.35,
            interactive: false,
          }).addTo(map)
        })
      } catch {}
      const drawControl = new (L as any).Control.Draw({
        draw: { polygon: { showArea: true }, rectangle: false, circle: false, marker: false, circlemarker: false, polyline: false },
        edit: false,
      })
      map.addControl(drawControl)
      map.on((L as any).Draw.Event.CREATED, (e: any) => {
        if (e.layerType !== "polygon") return
        try {
          const gj = e.layer.toGeoJSON().geometry
          if (!polygonIntersectsBbox(gj, bbox)) {
            setDrawError("Region is outside the simulation domain (cyan box) — draw inside it.")
            drawn.clearLayers()
            return
          }
          const amt = parseFloat((document.getElementById("zone-amount") as HTMLInputElement)?.value ?? "")
          const unt = ((document.getElementById("zone-unit") as HTMLSelectElement)?.value ?? "rate") as "rate" | "total"
          const z = buildZone(amt, unt, gj, zonesRef.current ?? [])
          if (!z) {
            setDrawError("Zone rejected: check amount ≥ 0 and fewer than 12 zones.")
            return
          }
          setDrawError(null)
          onChangeRef.current?.([...(zonesRef.current ?? []), z])
          drawn.clearLayers()
        } catch {
          setDrawError("Could not read the drawn region. Try again.")
        }
      })
      setTimeout(() => { try { map.invalidateSize() } catch {} }, 200)
      mapInstance.current = map
    }
    init()
    return () => {
      cancelled = true
      if (mapInstance.current) {
        try { mapInstance.current.remove() } catch {}
        mapInstance.current = null
      }
    }
    // re-init on bbox change only; zone adds re-render via reference layer skip
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bbox[0], bbox[1], bbox[2], bbox[3]])

  const amountNum = parseFloat(amount)
  const amountValid = isFinite(amountNum) && amountNum >= 0

  return (
    <div className="space-y-3 rounded-xl border border-slate-800 bg-slate-950/60 p-4">
      <div>
        <h5 className="font-semibold text-xs text-white flex items-center gap-2">
          <CloudRain className="w-3.5 h-3.5 text-cyan-400" />
          Spatial rain zones (optional)
        </h5>
        <p className="text-[11px] text-slate-400 mt-0.5">
          Amount → draw region → repeat. Draw inside the cyan domain box — regions outside it are rejected. Each zone overrides the base rate inside its area; last-drawn wins overlaps. Base rate applies everywhere else.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <label className="text-xs text-slate-300">
          Zone amount {zunit === "rate" ? "(mm/hr)" : "(mm total)"}
          <input
            id="zone-amount"
            data-testid="zone-amount"
            value={amount}
            onChange={e => setAmount(e.target.value)}
            placeholder="e.g. 200"
            className="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white font-mono text-xs focus:border-cyan-500 focus:outline-none"
          />
        </label>
        <label className="text-xs text-slate-300">
          Unit
          <select
            id="zone-unit"
            data-testid="zone-unit"
            value={zunit}
            onChange={e => setZunit(e.target.value as any)}
            className="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1.5 text-white text-xs focus:border-cyan-500 focus:outline-none"
          >
            <option value="rate">Rate mm/hr</option>
            <option value="total">Total mm</option>
          </select>
        </label>
      </div>
      {!amountValid && <span className="text-rose-400 text-xs block">Amount must be a number ≥ 0</span>}

      <div ref={mapRef} data-testid="zone-map" className="w-full h-[220px] rounded-xl border border-slate-800 bg-slate-950" />
      {drawError && (
        <div className="text-amber-300 text-xs flex items-center gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5" />
          <span>{drawError}</span>
        </div>
      )}

      {(zones?.length ?? 0) === 0 ? (
        <p className="text-[11px] text-slate-500">No spatial zones — base rate applies everywhere.</p>
      ) : (
        <ul className="space-y-1.5">
          {zones.map((z, i) => (
            <li key={z.id} className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800 text-xs">
              <span
                className="w-3 h-3 rounded-sm shrink-0"
                style={{ backgroundColor: ZONE_PALETTE[i % ZONE_PALETTE.length] }}
                aria-hidden
              />
              <span className="font-mono text-slate-200 font-semibold">{z.id}</span>
              <span className="font-mono text-cyan-300">
                {z.amount} {z.unit === "rate" ? "mm/hr" : "mm total"}
              </span>
              <button
                type="button"
                aria-label={`Remove zone ${z.id}`}
                onClick={() => onChange(zones.filter(zz => zz.id !== z.id))}
                className="ml-auto p-1 rounded-md text-slate-400 hover:text-rose-300 hover:bg-slate-800 transition"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}

      {capped && (
        <p className="text-[11px] text-amber-300/90">Maximum 12 zones per simulation — remove one to add another.</p>
      )}
    </div>
  )
}
