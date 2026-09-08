import { useState, useEffect } from "react"
import { Radio, AlertTriangle, Droplets, Users } from "lucide-react"

interface Props {
  origin: { lat: number; lon: number } | null
  onReported?: () => void
}

export default function LiveRealtime({ origin, onReported }: Props) {
  const [status, setStatus] = useState<any>(null)
  const [reports, setReports] = useState<any[]>([])
  const [lat, setLat] = useState(origin?.lat != null ? String(origin.lat) : "")
  const [lon, setLon] = useState(origin?.lon != null ? String(origin.lon) : "")
  const [depth, setDepth] = useState("30")
  const [radius, setRadius] = useState("0")
  const [kind, setKind] = useState("flooded")
  const [note, setNote] = useState("")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)

  useEffect(() => {
    if (origin?.lat != null) setLat(String(origin.lat))
    if (origin?.lon != null) setLon(String(origin.lon))
  }, [origin?.lat, origin?.lon])

  const loadStatus = async () => {
    try {
      const j = await (await fetch("/api/live/status")).json()
      setStatus(j)
    } catch {}
  }

  const loadReports = async () => {
    try {
      const j = await (await fetch("/api/v1/crowd/reports")).json()
      setReports(j?.data?.reports ?? [])
    } catch {}
  }

  useEffect(() => {
    loadStatus()
    loadReports()
    const id = setInterval(() => { loadStatus(); loadReports() }, 60000)
    return () => clearInterval(id)
  }, [])

  const submit = async () => {
    const olat = parseFloat(lat), olon = parseFloat(lon), d = parseFloat(depth)
    const r = parseFloat(radius)
    if (!isFinite(olat) || !isFinite(olon) || !isFinite(d) || d < 0 || d > 500) {
      setError("Enter a valid origin and depth 0–500 cm — or click the map first.")
      return
    }
    if (!isFinite(r) || r < 0 || r > 1000) {
      setError("Radius must be 0–1000 m (0 = exact point).")
      return
    }
    setSaving(true)
    setError(null)
    setDone(null)
    try {
      const res = await fetch("/api/v1/crowd/reports", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lat: olat, lon: olon, depthCm: d, radiusM: r, kind, note }),
      })
      if (!res.ok) throw new Error(await res.text())
      setDone("Reported — applied to the live sim.")
      setNote("")
      onReported?.()
      loadReports()
    } catch (e: any) {
      setError(e?.message ?? "Report failed.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="p-3.5 border-b border-slate-800/80 bg-slate-950/60 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs uppercase text-slate-400 font-mono font-semibold tracking-wider flex items-center gap-1.5">
          <Radio className="w-3.5 h-3.5 text-emerald-400" />
          Live
        </h3>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-300">
          {status?.source ?? "…"}
        </span>
      </div>

      <div className="text-[11px] font-mono text-slate-300 space-y-0.5">
        <div>Sim: {status?.simId ?? "—"}</div>
        <div>Rain now: {status != null ? `${status.rainNowMmHr ?? 0} mm/hr` : "—"}</div>
        <div className="text-slate-500">tick {status?.lastTickAt ?? "—"} → {status?.nextTickAt ?? "—"}</div>
      </div>

      <div>
        <h4 className="text-xs font-semibold text-slate-200 flex items-center gap-1.5 mb-1.5">
          <Users className="w-3.5 h-3.5 text-cyan-400" />
          Crowd reports ({reports.length})
        </h4>
        {reports.length === 0 ? (
          <p className="text-[11px] text-slate-500">No reports yet — click the map, set a depth, report.</p>
        ) : (
          <ul className="space-y-1.5 max-h-40 overflow-auto">
            {reports.map((r: any) => (
              <li key={r.id} className="px-2.5 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800 text-xs">
                <span className="font-mono text-cyan-300">{r.depthCm} cm</span>
                <span className="text-slate-400 font-mono"> • {r.kind}</span>
                {r.note && <span className="text-slate-300"> — {r.note}</span>}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2">
        <label className="text-xs text-slate-300">
          Lat
          <input data-testid="crowd-lat" type="number" value={lat} onChange={e => setLat(e.target.value)}
            className="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white font-mono text-xs focus:border-cyan-500 focus:outline-none" />
        </label>
        <label className="text-xs text-slate-300">
          Lon
          <input data-testid="crowd-lon" type="number" value={lon} onChange={e => setLon(e.target.value)}
            className="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white font-mono text-xs focus:border-cyan-500 focus:outline-none" />
        </label>
        <label className="text-xs text-slate-300">
          Water depth (cm)
          <input data-testid="crowd-depth" type="number" value={depth} onChange={e => setDepth(e.target.value)}
            className="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white font-mono text-xs focus:border-cyan-500 focus:outline-none" />
        </label>
        <label className="text-xs text-slate-300">
          Kind
          <select data-testid="crowd-kind" value={kind} onChange={e => setKind(e.target.value)}
            className="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1.5 text-white text-xs focus:border-cyan-500 focus:outline-none">
            <option value="flooded">Flooded street</option>
            <option value="drain">Drain point</option>
            <option value="other">Other</option>
          </select>
        </label>
        <label className="text-xs text-slate-300 col-span-2">
          Radius (m, 0 = exact point)
          <input data-testid="crowd-radius" type="number" value={radius} onChange={e => setRadius(e.target.value)}
            className="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white font-mono text-xs focus:border-cyan-500 focus:outline-none" />
        </label>
      </div>
      <input data-testid="crowd-note" value={note} onChange={e => setNote(e.target.value)} placeholder="Note (optional)"
        className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white text-xs placeholder-slate-500 focus:border-cyan-500 focus:outline-none" />

      <button type="button" onClick={submit} disabled={saving}
        className="w-full py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold transition disabled:opacity-50 flex items-center justify-center gap-1.5">
        <Droplets className="w-3.5 h-3.5" />
        {saving ? "Reporting…" : "Report water"}
      </button>
      {error && <div className="text-rose-300 text-xs flex items-center gap-1.5"><AlertTriangle className="w-3.5 h-3.5" /><span>{error}</span></div>}
      {done && <div className="text-emerald-300 text-xs">{done}</div>}
    </div>
  )
}
