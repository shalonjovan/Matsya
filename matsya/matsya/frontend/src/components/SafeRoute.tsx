import { useState, useEffect } from "react"
import { Navigation, AlertTriangle, Footprints, Mountain } from "lucide-react"

/** API lon/lat pairs -> Leaflet lat/lon pairs. */
export function toLatLngs(path: any): [number, number][] {
  try {
    if (!Array.isArray(path)) return []
    return path
      .filter(p => Array.isArray(p) && p.length >= 2)
      .map(p => [Number(p[1]), Number(p[0])] as [number, number])
  } catch {
    return []
  }
}

interface Props {
  simulation: any
  timeMin: number
  origin: { lat: number; lon: number } | null
  onSelectRoute: (route: { safest: [number, number][]; fastest: [number, number][] | null; dest: { lat: number; lon: number } } | null) => void
}

export default function SafeRoute({ simulation, timeMin, origin, onSelectRoute }: Props) {
  const [lat, setLat] = useState(origin?.lat != null ? String(origin.lat) : "")
  const [lon, setLon] = useState(origin?.lon != null ? String(origin.lon) : "")
  const [threshold, setThreshold] = useState("15")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [spaces, setSpaces] = useState<any[] | null>(null)
  const [reason, setReason] = useState<string | null>(null)
  const [snapped, setSnapped] = useState<{ lat: number; lon: number; distanceM: number } | null>(null)

  const friendlyError = (raw: string) => {
    try {
      const detail = JSON.parse(raw)?.detail
      if (typeof detail === "string" && detail) {
        if (detail.includes("routable network (200m)"))
          return "No mapped roads within 200 m of that point — try clicking near a road."
        if (detail.includes("within 2 km"))
          return "No mapped roads within 2 km of that point — try a point near a road."
        return detail
      }
    } catch {}
    return raw || "Search failed."
  }

  useEffect(() => {
    if (origin?.lat != null) setLat(String(origin.lat))
    if (origin?.lon != null) setLon(String(origin.lon))
  }, [origin?.lat, origin?.lon])

  const find = async () => {
    const olat = parseFloat(lat), olon = parseFloat(lon)
    if (!isFinite(olat) || !isFinite(olon)) {
      setError("Enter a valid origin — or click the map first.")
      return
    }
    if (!simulation?.id) {
      setError("No simulation selected.")
      return
    }
    setLoading(true)
    setError(null)
    setSpaces(null)
    setReason(null)
    setSnapped(null)
    onSelectRoute(null)
    try {
      const res = await fetch("/api/v1/safe-spaces", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          simId: simulation.id,
          origin: { lat: olat, lon: olon },
          departAtMin: timeMin ?? 0,
          thresholdCm: parseFloat(threshold) || 15,
          limit: 3,
        }),
      })
      if (!res.ok) {
        const txt = await res.text()
        throw new Error(friendlyError(txt) || `search failed (${res.status})`)
      }
      const j = await res.json()
      setSpaces(j?.data?.spaces ?? [])
      setReason(j?.data?.reason ?? null)
      setSnapped(j?.data?.originSnapped ?? null)
    } catch (e: any) {
      setError(e?.message ?? "Search failed.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-3.5 border-b border-slate-800/80 bg-slate-950/60 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs uppercase text-slate-400 font-mono font-semibold tracking-wider flex items-center gap-1.5">
          <Navigation className="w-3.5 h-3.5 text-emerald-400" />
          Safe Route
        </h3>
        <span className="text-[10px] text-slate-500 font-mono">nearest refuge + route</span>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <label className="text-xs text-slate-300">
          Origin lat
          <input
            data-testid="saferoute-lat"
            type="number"
            value={lat}
            onChange={e => setLat(e.target.value)}
            placeholder="13.10"
            className="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white font-mono text-xs focus:border-emerald-500 focus:outline-none"
          />
        </label>
        <label className="text-xs text-slate-300">
          Origin lon
          <input
            data-testid="saferoute-lon"
            type="number"
            value={lon}
            onChange={e => setLon(e.target.value)}
            placeholder="80.19"
            className="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white font-mono text-xs focus:border-emerald-500 focus:outline-none"
          />
        </label>
      </div>

      <label className="text-xs text-slate-300 block">
        Passable below (cm)
        <select
          data-testid="saferoute-threshold"
          value={threshold}
          onChange={e => setThreshold(e.target.value)}
          className="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1.5 text-white text-xs focus:border-emerald-500 focus:outline-none"
        >
          <option value="5">5 cm (strict)</option>
          <option value="15">15 cm (car-safe)</option>
          <option value="30">30 cm (emergency)</option>
        </select>
      </label>

      <button
        type="button"
        onClick={find}
        disabled={loading}
        className="w-full py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition disabled:opacity-50"
      >
        {loading ? "Searching…" : "Find safe space"}
      </button>

      {error && (
        <div className="text-rose-300 text-xs flex items-center gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5" />
          <span>{error}</span>
        </div>
      )}

      {snapped && spaces !== null && spaces.length > 0 && (
        <p className="text-[11px] text-amber-200/90 font-mono">
          Routing from nearest mapped road, {Math.round(snapped.distanceM)} m away.
        </p>
      )}

      {spaces !== null && spaces.length === 0 && (
        <p className="text-[11px] text-slate-400">
          {reason ? `No reachable safe space — ${reason}. Try a higher threshold.` : "No reachable safe space — try a higher threshold."}
        </p>
      )}

      {spaces !== null && spaces.length > 0 && (
        <ul className="space-y-1.5">
          {spaces.map((s: any) => (
            <li key={`${s.rank}-${s.name}`}>
              <button
                type="button"
                onClick={() => onSelectRoute({
                  safest: toLatLngs(s.route?.path),
                  fastest: null,
                  dest: { lat: s.lat, lon: s.lon },
                })}
                className="w-full text-left px-2.5 py-2 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-emerald-500/50 transition"
              >
                <div className="flex items-center gap-1.5 text-xs font-semibold text-white">
                  {s.kind === "road"
                    ? <Footprints className="w-3.5 h-3.5 text-cyan-400" />
                    : <Mountain className="w-3.5 h-3.5 text-emerald-400" />}
                  <span>{s.rank}. {s.name}</span>
                  <span className="ml-auto font-mono text-emerald-300">{s.route?.etaMin} min</span>
                </div>
                <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                  peak {s.peakCm} cm • {s.elevationM} m • {s.kind}
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
