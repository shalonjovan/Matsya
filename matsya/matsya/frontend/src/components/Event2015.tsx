import { useState, useEffect } from "react"
import { History, Play, AlertTriangle, FlaskConical } from "lucide-react"

function Donut({ value }: { value: number }) {
  const r = 44
  const c = 2 * Math.PI * r
  const frac = Math.max(0, Math.min(100, value)) / 100
  return (
    <div className="relative w-32 h-32" data-testid="similarity-donut">
      <svg viewBox="0 0 100 100" className="w-32 h-32 -rotate-90">
        <circle cx="50" cy="50" r={r} fill="none" stroke="#1e293b" strokeWidth="10" />
        <circle cx="50" cy="50" r={r} fill="none" stroke="#22d3ee" strokeWidth="10"
          strokeDasharray={`${(c * frac).toFixed(1)} ${c.toFixed(1)}`} strokeLinecap="round" />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center font-mono text-2xl font-bold text-white">
        {Math.round(value)}%
      </div>
    </div>
  )
}

export default function Event2015() {
  const [facts, setFacts] = useState<any>(null)
  const [running, setRunning] = useState(false)
  const [status, setStatus] = useState<string | null>(null)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch("/api/v1/event/2015/facts").then(r => r.json()).then(j => setFacts(j?.data ?? j)).catch(() => setFacts(null))
  }, [])

  const run = async () => {
    setRunning(true)
    setError(null)
    setResult(null)
    try {
      const rr = await fetch("/api/v1/event/2015/replay", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })
      if (!rr.ok) throw new Error(`replay failed (${rr.status})`)
      const simId = (await rr.json())?.data?.simId
      if (!simId) throw new Error("replay returned no simulation")
      setStatus("Running Dec-1 storm through the flood pipeline…")
      for (let i = 0; i < 150; i++) {
        await new Promise(r => setTimeout(r, 2000))
        const s = await (await fetch(`/api/simulations/${simId}`)).json()
        if (s?.status === "Completed") break
      }
      setStatus("Comparing against reported 2015 outcomes…")
      const cr = await fetch(`/api/v1/event/2015/compare?simId=${simId}`)
      if (!cr.ok) throw new Error(`compare failed (${cr.status})`)
      setResult((await cr.json())?.data)
      setStatus(null)
    } catch (e: any) {
      setError(e?.message ?? "Replay failed.")
      setStatus(null)
    } finally {
      setRunning(false)
    }
  }

  const stations = facts?.rainfallStations ?? []
  const release = facts?.release ?? {}
  const excluded = facts?.excludedLocalities ?? []

  return (
    <div className="max-w-4xl mx-auto w-full p-4 sm:p-6 space-y-5">
      <div>
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <History className="w-5 h-5 text-cyan-400" />
          Chennai Dec 2015 — Replay
        </h2>
        <p className="text-xs text-slate-400 mt-1">
          Observed record vs this model's Dec-1 storm replay. Reported facts are labeled; modeled numbers come from the live pipeline.
        </p>
      </div>

      <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
        <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Observed record (reported)</h3>
        <ul className="text-xs font-mono text-slate-300 space-y-1">
          {stations.map((s: any) => (
            <li key={s.station}>{s.station}: {s.mm24h}mm / 24h <span className="text-slate-500">({s.source ?? "IMD"})</span></li>
          ))}
          {release?.cusecs && (
            <li>Chembarambakkam release: {release.cusecs.toLocaleString()} cusecs × {release.hours}h into the Adyar{" "}
              <span className="text-amber-300">(context only — not modeled)</span>
            </li>
          )}
        </ul>
      </div>

      <button
        type="button"
        onClick={run}
        disabled={running}
        className="flex items-center gap-2 px-5 py-2.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded-xl text-sm font-bold transition disabled:opacity-50"
      >
        <Play className="w-4 h-4" />
        {running ? "Replaying…" : "Run replay"}
      </button>
      {status && <p className="text-xs text-slate-400 font-mono">{status}</p>}
      {error && <p className="text-xs text-rose-300 flex items-center gap-1.5"><AlertTriangle className="w-3.5 h-3.5" />{error}</p>}

      {result && (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4 space-y-4">
          <div className="flex items-center gap-5">
            <Donut value={result.similarityPct} />
            <div className="text-xs text-slate-400 font-mono space-y-1">
              <div>recall {result.recall} • band agreement {result.bandAgreement}</div>
              <div className="text-slate-500">{result.formula}</div>
            </div>
          </div>
          <table className="text-xs w-full text-left font-mono">
            <thead className="text-[10px] uppercase text-slate-500 border-b border-slate-800">
              <tr><th className="py-1.5 pr-2">Locality</th><th className="py-1.5 pr-2">Reported</th><th className="py-1.5 pr-2">Modeled</th><th className="py-1.5">Match</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {(result.localities ?? []).map((l: any) => (
                <tr key={l.name}>
                  <td className="py-1.5 pr-2 text-white">{l.name}</td>
                  <td className="py-1.5 pr-2">{l.reportedBand}</td>
                  <td className="py-1.5 pr-2">{l.modeledBand} ({l.modeledMaxCm} cm)</td>
                  <td className="py-1.5">{l.match ? "✓" : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-[11px] text-slate-500 flex items-start gap-1.5">
            <FlaskConical className="w-3.5 h-3.5 shrink-0 mt-0.5" />
            <span>Replay runs the Dec-1 storm pattern (490mm south / 300mm north, synthetic hourly shape) on the validated domain with live physics. Excluded (outside DEM tile): {(excluded.map((e: any) => e.name) ?? []).join(", ")}. Chembarambakkam inflow, blocked drains and brimful lakes are not modeled — depth gaps vs 2015 reflect those missing amplifiers.</span>
          </p>
        </div>
      )}
    </div>
  )
}
