
import { useState } from "react"
import type { Simulation } from "../types/simulation"
import HydroBadge from "./HydroBadge"
import { API_BASE } from "../hooks/useSimulation"

interface Props {
  open: boolean
  onClose: () => void
  onCreated: (sim: Simulation) => void
  editSim?: Simulation | null
}

export default function CreateWizard({ open, onClose, onCreated, editSim }: Props) {
  const isEdit = !!editSim
  const [step, setStep] = useState(1)
  const [name, setName] = useState(editSim?.name ?? "")
  const [minLon, setMinLon] = useState(String(editSim?.area?.bbox?.[0] ?? "80.15"))
  const [minLat, setMinLat] = useState(String(editSim?.area?.bbox?.[1] ?? "13.08"))
  const [maxLon, setMaxLon] = useState(String(editSim?.area?.bbox?.[2] ?? "80.20"))
  const [maxLat, setMaxLat] = useState(String(editSim?.area?.bbox?.[3] ?? "13.13"))
  const [rate, setRate] = useState(String(editSim?.rainfall?.rateMmHr ?? "50"))
  const [duration, setDuration] = useState(String(editSim?.rainfall?.durationHr ?? "1"))
  const [cfl, setCfl] = useState(String((editSim as any)?.parameters?.cfl ?? "0.7"))
  const [search, setSearch] = useState("")
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  if (!open) return null

  const bbox: [number,number,number,number] = [parseFloat(minLon), parseFloat(minLat), parseFloat(maxLon), parseFloat(maxLat)]
  const bboxValid = bbox.every(n=>!isNaN(n)) && bbox[0] < bbox[2] && bbox[1] < bbox[3]
  const rainfallValid = !isNaN(parseFloat(rate)) && !isNaN(parseFloat(duration)) && parseFloat(rate)>0 && parseFloat(duration)>0
  const nameValid = name.trim().length>0

  const missing: string[] = []
  if (!bboxValid) missing.push("Geographic area (bbox invalid)")
  if (!nameValid) missing.push("Name")
  // drainage is optional for MVP, but we warn if conduitCount missing
  const drainMissing = !(editSim as any)?.drainage?.uri
  // show warning but not block

  const handleSearch = async () => {
    if (!search.trim()) return
    setSearching(true)
    setError(null)
    try {
      // Nominatim search
      const res = await fetch(`https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(search)}&format=json&limit=1`)
      if (!res.ok) throw new Error("search failed")
      const data = await res.json()
      if (data[0]?.boundingbox) {
        const [s,n,w,e] = data[0].boundingbox.map((x:string)=>parseFloat(x)) // s,n,w,e? Nominatim is [south, north, west, east]
        // Actually [minLat, maxLat, minLon, maxLon] -> convert
        // Nominatim: boundingbox [south, north, west, east]
        const south = parseFloat(data[0].boundingbox[0]); const north = parseFloat(data[0].boundingbox[1]); const west = parseFloat(data[0].boundingbox[2]); const east = parseFloat(data[0].boundingbox[3])
        setMinLon(String(west)); setMaxLon(String(east)); setMinLat(String(south)); setMaxLat(String(north))
      } else setError("No results")
    } catch (e:any) { setError(e.message) } finally { setSearching(false) }
  }

  const handleSubmit = async () => {
    if (!nameValid || !bboxValid || !rainfallValid) { setError("Please fix validation errors"); return }
    setSaving(true); setError(null)
    try {
      const payload: any = {
        name: name.trim(),
        area: { bbox, crs: "EPSG:4326" },
        rainfall: { rateMmHr: parseFloat(rate), durationHr: parseFloat(duration) },
        parameters: { cfl: parseFloat(cfl) || 0.7 }
      }
      let res: Response
      if (isEdit && editSim) {
        res = await fetch(`${API_BASE}/simulations/${editSim.id}`, { method:"PATCH", headers:{"Content-Type":"application/json"}, body: JSON.stringify(payload)})
      } else {
        res = await fetch(`${API_BASE}/simulations`, { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(payload)})
      }
      if (!res.ok) {
        const txt = await res.text(); throw new Error(txt || `save failed ${res.status}`)
      }
      const sim = await res.json()
      onCreated(sim)
      onClose()
      setStep(1)
    } catch (e:any) { setError(e.message) } finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-auto">
        <div className="p-6 border-b flex justify-between items-center">
          <h3 className="text-lg font-semibold">{isEdit ? "Edit Simulation" : "Create Simulation"}</h3>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-700">✕</button>
        </div>
        <div className="p-6 space-y-6">
          {/* Steps indicator */}
          <div className="flex gap-2 text-xs">
            {[1,2,3,4].map(n=> (
              <button key={n} onClick={()=>setStep(n)} className={`flex-1 py-2 rounded ${step===n ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600"}`}>Step {n}</button>
            ))}
          </div>
          {error && <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded text-sm">{error}</div>}
          {step===1 && (
            <div className="space-y-4">
              <label className="block">Name
                <input value={name} onChange={e=>setName(e.target.value)} placeholder="Chennai Monsoon 2026" className="mt-1 w-full border rounded px-3 py-2" />
                {!nameValid && <span className="text-red-500 text-xs">Name required</span>}
              </label>
            </div>
          )}
          {step===2 && (
            <div className="space-y-4">
              <h4 className="font-medium">Geographic area §5.1 — bbox or search</h4>
              <div className="flex gap-2">
                <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search place (e.g., Velachery)" className="flex-1 border rounded px-3 py-2" />
                <button onClick={handleSearch} disabled={searching} className="px-4 py-2 bg-slate-800 text-white rounded text-sm disabled:opacity-50">{searching ? "..." : "Search"}</button>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <label>Min Lon <input value={minLon} onChange={e=>setMinLon(e.target.value)} className="w-full border rounded px-2 py-1 font-mono" /></label>
                <label>Max Lon <input value={maxLon} onChange={e=>setMaxLon(e.target.value)} className="w-full border rounded px-2 py-1 font-mono" /></label>
                <label>Min Lat <input value={minLat} onChange={e=>setMinLat(e.target.value)} className="w-full border rounded px-2 py-1 font-mono" /></label>
                <label>Max Lat <input value={maxLat} onChange={e=>setMaxLat(e.target.value)} className="w-full border rounded px-2 py-1 font-mono" /></label>
              </div>
              {!bboxValid && <span className="text-red-500 text-xs">Invalid bbox: must be minLon&lt;maxLon and minLat&lt;maxLat (e.g., 80.15,13.08,80.20,13.13)</span>}
              <p className="text-xs text-slate-500">Also supports: Draw rectangle/polygon (stub — enter bbox manually), Admin boundary (stub)</p>
            </div>
          )}
          {step===3 && (
            <div className="space-y-4">
              <h4 className="font-medium">Data checklist §5.2</h4>
              <ul className="text-sm space-y-1 border rounded p-3 bg-slate-50">
                <li>Terrain / DEM: <span className="text-emerald-600">✓ seeded (dem_clipped.tif 180×180 @30m)</span></li>
                <li>Rainfall: {rainfallValid ? <span className="text-emerald-600">✓ {rate} mm/hr × {duration} hr</span> : <span className="text-red-500">✗ invalid</span>}</li>
                <li>Drainage: {drainMissing ? <span className="text-amber-600">⚠ missing — simulation will run without drainage (micro/macro/storm)</span> : <span className="text-emerald-600">✓</span>}</li>
                <li>Rivers/Canals/Water bodies/Roads/Buildings: <span className="text-slate-500">optional (seeded from test/)</span></li>
              </ul>
              <HydroBadge />
              {drainMissing && <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 p-2 rounded">Missing datasets indicated before run per §5.2 — you can still run, but flood will be surface-only.</p>}
              <label>Rainfall rate mm/hr <input value={rate} onChange={e=>setRate(e.target.value)} className="w-full border rounded px-2 py-1" /></label>
              <label>Duration hr <input value={duration} onChange={e=>setDuration(e.target.value)} className="w-full border rounded px-2 py-1" /></label>
            </div>
          )}
          {step===4 && (
            <div className="space-y-4">
              <h4 className="font-medium">Advanced Settings §26</h4>
              <label>CFL <input value={cfl} onChange={e=>setCfl(e.target.value)} className="w-full border rounded px-2 py-1 font-mono" /></label>
              <p className="text-xs text-slate-500">Technical params hidden from normal users per §31, visible here.</p>
            </div>
          )}
        </div>
        <div className="p-4 border-t flex justify-between">
          <button onClick={()=>setStep(Math.max(1, step-1))} disabled={step===1} className="px-4 py-2 border rounded disabled:opacity-50">Back</button>
          <div className="flex gap-2">
            {step<4 ? <button onClick={()=>setStep(step+1)} className="px-4 py-2 bg-blue-600 text-white rounded">Next</button> : <button onClick={handleSubmit} disabled={saving || !nameValid || !bboxValid} className="px-6 py-2 bg-emerald-600 text-white rounded disabled:opacity-50">{saving ? "Saving..." : isEdit ? "Save" : "Create"}</button>}
          </div>
        </div>
      </div>
    </div>
  )
}
