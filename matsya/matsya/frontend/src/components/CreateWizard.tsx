
import { useState, useEffect } from "react"
import type { Simulation } from "../types/simulation"
import HydroBadge from "./HydroBadge"
import { API_BASE } from "../hooks/useSimulation"
import { 
  X, 
  MapPin, 
  CloudRain, 
  Layers, 
  Sliders, 
  Search, 
  CheckCircle2, 
  AlertTriangle, 
  ArrowRight, 
  ArrowLeft, 
  Zap, 
  Compass, 
  Database
} from "lucide-react"

interface Props {
  open: boolean
  onClose: () => void
  onCreated: (sim: Simulation) => void
  editSim?: Simulation | null
}

const PRESETS = [
  { label: "Cyclone Michaung (2023)", rate: 75, duration: 3, desc: "High intensity storm surge event" },
  { label: "Chennai 2015 Cloudburst", rate: 100, duration: 2, desc: "Catastrophic urban inundation" },
  { label: "Severe Depression (50mm)", rate: 50, duration: 1, desc: "Standard GCC monsoon design storm" },
  { label: "Moderate Monsoon (25mm)", rate: 25, duration: 2, desc: "Operational test scenario" },
]

const HOTSPOTS = [
  { name: "Central Chennai (Big Square)", bbox: ["80.15", "13.08", "80.20", "13.13"] },
  { name: "Velachery & Pallikaranai", bbox: ["80.19", "12.96", "80.24", "13.01"] },
  { name: "Adyar River Basin", bbox: ["80.21", "13.00", "80.26", "13.05"] },
  { name: "OMR IT Corridor", bbox: ["80.22", "12.92", "80.27", "12.97"] },
]

export default function CreateWizard({ open, onClose, onCreated, editSim }: Props) {
  const isEdit = !!editSim
  const [step, setStep] = useState(1)
  const [name, setName] = useState(editSim?.name ?? "Chennai Flood Scenario")
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

  // Keyboard Escape listener to close wizard
  useEffect(() => {
    if (!open) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose()
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [open, onClose])

  if (!open) return null

  const bbox: [number,number,number,number] = [parseFloat(minLon), parseFloat(minLat), parseFloat(maxLon), parseFloat(maxLat)]
  const bboxValid = bbox.every(n=>!isNaN(n)) && bbox[0] < bbox[2] && bbox[1] < bbox[3]
  const rainfallValid = !isNaN(parseFloat(rate)) && !isNaN(parseFloat(duration)) && parseFloat(rate)>0 && parseFloat(duration)>0
  const nameValid = name.trim().length>0

  const drainMissing = !(editSim as any)?.drainage?.uri

  const applyPreset = (p: typeof PRESETS[0]) => {
    setRate(String(p.rate))
    setDuration(String(p.duration))
    if (!name.trim()) setName(`Chennai ${p.label}`)
  }

  const applyHotspot = (h: typeof HOTSPOTS[0]) => {
    setMinLon(h.bbox[0])
    setMinLat(h.bbox[1])
    setMaxLon(h.bbox[2])
    setMaxLat(h.bbox[3])
  }

  const handleSearch = async () => {
    if (!search.trim()) return
    setSearching(true)
    setError(null)
    try {
      const res = await fetch(`https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(search)}&format=json&limit=1`)
      if (!res.ok) throw new Error("search failed")
      const data = await res.json()
      if (data[0]?.boundingbox) {
        const south = parseFloat(data[0].boundingbox[0])
        const north = parseFloat(data[0].boundingbox[1])
        const west = parseFloat(data[0].boundingbox[2])
        const east = parseFloat(data[0].boundingbox[3])
        setMinLon(String(west))
        setMaxLon(String(east))
        setMinLat(String(south))
        setMaxLat(String(north))
      } else setError("No geographic coordinates found for that location")
    } catch (e:any) { 
      setError(e.message) 
    } finally { 
      setSearching(false) 
    }
  }

  const handleSubmit = async () => {
    if (!nameValid || !bboxValid || !rainfallValid) { 
      setError("Please fix validation errors before proceeding"); 
      return 
    }
    setSaving(true)
    setError(null)
    try {
      const payload: any = {
        name: name.trim(),
        area: { bbox, crs: "EPSG:4326" },
        rainfall: { rateMmHr: parseFloat(rate), durationHr: parseFloat(duration) },
        parameters: { cfl: parseFloat(cfl) || 0.7 }
      }
      let res: Response
      if (isEdit && editSim) {
        res = await fetch(`${API_BASE}/simulations/${editSim.id}`, { 
          method:"PATCH", 
          headers:{"Content-Type":"application/json"}, 
          body: JSON.stringify(payload)
        })
      } else {
        res = await fetch(`${API_BASE}/simulations`, { 
          method:"POST", 
          headers:{"Content-Type":"application/json"}, 
          body: JSON.stringify(payload)
        })
      }
      if (!res.ok) {
        const txt = await res.text()
        throw new Error(txt || `save failed ${res.status}`)
      }
      const sim = await res.json()
      onCreated(sim)
      onClose()
      setStep(1)
    } catch (e:any) { 
      setError(e.message) 
    } finally { 
      setSaving(false) 
    }
  }

  const stepMeta = [
    { num: 1, label: "Scenario", icon: CloudRain },
    { num: 2, label: "Area Bounds", icon: MapPin },
    { num: 3, label: "Datasets", icon: Layers },
    { num: 4, label: "Physics", icon: Sliders },
  ]

  return (
    <div 
      className="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center z-[9999] p-3 sm:p-4 animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div 
        role="dialog"
        aria-modal="true"
        aria-labelledby="wizard-dialog-title"
        className="glass-panel rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col border border-slate-700/80 overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        
        {/* Header */}
        <div className="p-4 sm:p-6 border-b border-slate-800 flex justify-between items-center bg-slate-950/40">
          <div>
            <span className="text-[10px] font-mono text-cyan-400 font-semibold tracking-wider uppercase">SCENARIO CONFIGURATOR</span>
            <h3 id="wizard-dialog-title" className="text-lg sm:text-xl font-bold text-white tracking-tight">
              {isEdit ? "Edit Simulation" : "Create Simulation"}
            </h3>
          </div>
          <button 
            type="button"
            onClick={onClose} 
            aria-label="Close dialog"
            className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800/80 transition focus-ring"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Stepper Tabs */}
        <div className="flex border-b border-slate-800 bg-slate-950/60 p-1.5 sm:p-2 gap-1 sm:gap-1.5 overflow-x-auto">
          {stepMeta.map(s => {
            const Icon = s.icon
            const active = step === s.num
            const completed = step > s.num
            return (
              <button
                key={s.num}
                type="button"
                onClick={() => setStep(s.num)}
                aria-label={`Step ${s.num}: ${s.label}`}
                aria-current={active ? "step" : undefined}
                className={`flex-1 min-w-[70px] flex items-center justify-center gap-1.5 sm:gap-2 py-2 px-2 sm:px-3 rounded-xl text-xs font-semibold transition focus-ring ${
                  active 
                    ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm" 
                    : completed 
                    ? "bg-slate-800/60 text-slate-300 hover:text-white" 
                    : "text-slate-400 hover:text-slate-300"
                }`}
              >
                <Icon className="w-3.5 h-3.5 shrink-0" />
                <span className="truncate">Step {s.num}</span>
              </button>
            )
          })}
        </div>

        {/* Modal Body */}
        <div className="p-4 sm:p-6 space-y-5 sm:space-y-6 flex-1 overflow-y-auto">
          {error && (
            <div className="p-3.5 bg-rose-950/50 border border-rose-800 text-rose-300 rounded-xl text-xs flex items-center gap-2.5">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* STEP 1: Scenario Identification */}
          {step === 1 && (
            <div className="space-y-5">
              <div>
                <label htmlFor="wizard-sim-name" className="block text-xs font-medium text-slate-300 mb-1.5">
                  Name <span className="text-rose-400">*</span>
                </label>
                <input 
                  id="wizard-sim-name"
                  value={name} 
                  onChange={e => setName(e.target.value)} 
                  placeholder="e.g., Chennai Monsoon 2026 High Intensity" 
                  className="w-full bg-slate-950 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus-ring transition"
                  autoFocus
                />
                {!nameValid && <span className="text-rose-400 text-xs mt-1 block">Name required</span>}
              </div>

              <div>
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-2">Historical & Design Storm Presets</span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {PRESETS.map((p, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => applyPreset(p)}
                      className="p-3 rounded-xl border border-slate-800 bg-slate-900/50 hover:border-cyan-500/40 hover:bg-slate-900 text-left transition group focus-ring"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-bold text-white group-hover:text-cyan-300 transition">{p.label}</span>
                        <Zap className="w-3.5 h-3.5 text-cyan-400" />
                      </div>
                      <div className="text-[11px] text-cyan-400/90 font-mono">{p.rate} mm/hr × {p.duration} hr</div>
                      <div className="text-[10px] text-slate-400 mt-1">{p.desc}</div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* STEP 2: Geographic Bounding Box */}
          {step === 2 && (
            <div className="space-y-4">

              <div>
                <h4 className="font-semibold text-sm text-white flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-cyan-400" />
                  Geographic Area & Domain Limits
                </h4>
                <p className="text-xs text-slate-400 mt-0.5">Define your rectangular domain in WGS84 coordinates (EPSG:4326).</p>
              </div>

              {/* Nominatim Search */}
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input 
                    id="wizard-search-loc"
                    value={search} 
                    onChange={e => setSearch(e.target.value)} 
                    placeholder="Search place (e.g., Velachery, Adyar, Chennai)" 
                    aria-label="Search Chennai location"
                    className="w-full bg-slate-950 border border-slate-700/80 rounded-xl pl-9 pr-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus-ring transition" 
                    onKeyDown={e => e.key === "Enter" && handleSearch()}
                  />
                </div>
                <button 
                  type="button"
                  onClick={handleSearch} 
                  disabled={searching} 
                  aria-label="Search coordinates for location"
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-semibold border border-slate-700 transition disabled:opacity-50 focus-ring"
                >
                  {searching ? "Searching..." : "Search"}
                </button>
              </div>

              {/* Quick Hotspot Chips */}
              <div>
                <span className="text-[11px] text-slate-400 mb-1.5 block">Quick Chennai Metropolitan Hotspots:</span>
                <div className="flex flex-wrap gap-1.5">
                  {HOTSPOTS.map((h, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => applyHotspot(h)}
                      aria-label={`Apply bounds for ${h.name}`}
                      className="px-2.5 py-1 rounded-lg bg-slate-800/80 hover:bg-cyan-500/20 text-slate-300 hover:text-cyan-300 border border-slate-700/60 hover:border-cyan-500/40 text-[11px] transition focus-ring"
                    >
                      {h.name}
                    </button>
                  ))}
                </div>
              </div>

              {/* Coordinate Grid */}
              <div className="grid grid-cols-2 gap-3 p-4 bg-slate-950/60 rounded-xl border border-slate-800">
                <label htmlFor="wizard-min-lon" className="text-xs text-slate-300">
                  Min Lon (West)
                  <input 
                    id="wizard-min-lon"
                    value={minLon} 
                    onChange={e => setMinLon(e.target.value)} 
                    className="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white font-mono text-xs focus:border-cyan-500 focus-ring focus:outline-none" 
                  />
                </label>
                <label htmlFor="wizard-max-lon" className="text-xs text-slate-300">
                  Max Lon (East)
                  <input 
                    id="wizard-max-lon"
                    value={maxLon} 
                    onChange={e => setMaxLon(e.target.value)} 
                    className="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white font-mono text-xs focus:border-cyan-500 focus-ring focus:outline-none" 
                  />
                </label>
                <label htmlFor="wizard-min-lat" className="text-xs text-slate-300">
                  Min Lat (South)
                  <input 
                    id="wizard-min-lat"
                    value={minLat} 
                    onChange={e => setMinLat(e.target.value)} 
                    className="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white font-mono text-xs focus:border-cyan-500 focus-ring focus:outline-none" 
                  />
                </label>
                <label htmlFor="wizard-max-lat" className="text-xs text-slate-300">
                  Max Lat (North)
                  <input 
                    id="wizard-max-lat"
                    value={maxLat} 
                    onChange={e => setMaxLat(e.target.value)} 
                    className="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white font-mono text-xs focus:border-cyan-500 focus-ring focus:outline-none" 
                  />
                </label>
              </div>

              {!bboxValid && (
                <div className="text-rose-400 text-xs flex items-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  <span>Invalid bbox: must be minLon &lt; maxLon and minLat &lt; maxLat (e.g., 80.15,13.08,80.20,13.13)</span>
                </div>
              )}
              <p className="text-[11px] text-slate-400">Bounding box coordinates in EPSG:4326 (WGS84). Use the Chennai preset chips above for quick selection.</p>
            </div>
          )}

          {/* STEP 3: Datasets & Precipitation */}
          {step === 3 && (
            <div className="space-y-4">
              <div>
                <h4 className="font-semibold text-sm text-white flex items-center gap-2">
                  <Database className="w-4 h-4 text-cyan-400" />
                  GIS Datasets & Hydro Checklist
                </h4>
                <p className="text-xs text-slate-400 mt-0.5">Verify GIS assets and hydro inputs before calculation.</p>
              </div>

              <div className="space-y-2 border border-slate-800 rounded-xl p-4 bg-slate-950/60 text-xs">
                <div className="flex items-center justify-between py-1 border-b border-slate-800/80">
                  <span className="text-slate-400">Terrain / DEM</span>
                  <span className="text-emerald-400 flex items-center gap-1 font-medium">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    seeded (dem_clipped.tif 180×180 @30m)
                  </span>
                </div>

                <div className="flex items-center justify-between py-1 border-b border-slate-800/80">
                  <span className="text-slate-400">Rainfall Parameters</span>
                  {rainfallValid ? (
                    <span className="text-emerald-400 flex items-center gap-1 font-medium font-mono">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      {rate} mm/hr × {duration} hr
                    </span>
                  ) : (
                    <span className="text-rose-400 flex items-center gap-1 font-medium">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      invalid
                    </span>
                  )}
                </div>

                <div className="flex items-center justify-between py-1 border-b border-slate-800/80">
                  <span className="text-slate-400">GCC Stormwater Drainage</span>
                  {drainMissing ? (
                    <span className="text-amber-400 flex items-center gap-1 font-medium">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      missing — simulation will run without drainage (micro/macro/storm)
                    </span>
                  ) : (
                    <span className="text-emerald-400 flex items-center gap-1 font-medium">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      connected (10,276 SWD lines)
                    </span>
                  )}
                </div>

                <div className="flex items-center justify-between py-1">
                  <span className="text-slate-400">Rivers / Waterbodies / Roads</span>
                  <span className="text-cyan-400">seeded from test/ assets</span>
                </div>
              </div>

              <HydroBadge />

              {drainMissing && (
                <p className="text-[11px] text-amber-300/90 bg-amber-950/40 border border-amber-800/80 p-3 rounded-xl">
                  Missing datasets noted: simulation will compute surface overland flow without sub-surface drainage.
                </p>
              )}

              <div className="grid grid-cols-2 gap-3 pt-2">
                <label htmlFor="wizard-rain-rate" className="text-xs text-slate-300">
                  Rainfall rate (mm/hr)
                  <input 
                    id="wizard-rain-rate"
                    value={rate} 
                    onChange={e => setRate(e.target.value)} 
                    className="mt-1 w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono text-xs focus:border-cyan-500 focus-ring focus:outline-none" 
                  />
                </label>
                <label htmlFor="wizard-rain-duration" className="text-xs text-slate-300">
                  Duration (hours)
                  <input 
                    id="wizard-rain-duration"
                    value={duration} 
                    onChange={e => setDuration(e.target.value)} 
                    className="mt-1 w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono text-xs focus:border-cyan-500 focus-ring focus:outline-none" 
                  />
                </label>
              </div>
            </div>
          )}

          {/* STEP 4: Numerical Physics */}
          {step === 4 && (
            <div className="space-y-4">
              <div>
                <h4 className="font-semibold text-sm text-white flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-cyan-400" />
                  Advanced Simulation Physics
                </h4>
                <p className="text-xs text-slate-400 mt-0.5">Numerical stability and timestep constraints.</p>
              </div>

              <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800 space-y-3">
                <label htmlFor="wizard-cfl" className="block text-xs text-slate-300">
                  Courant-Friedrichs-Lewy (CFL) Number
                  <input 
                    id="wizard-cfl"
                    value={cfl} 
                    onChange={e => setCfl(e.target.value)} 
                    className="mt-1.5 w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono text-xs focus:border-cyan-500 focus-ring focus:outline-none" 
                  />
                  <span className="text-[11px] text-slate-400 mt-1 block">Default: 0.7 (recommended range: 0.5 - 0.9)</span>
                </label>
              </div>

              <p className="text-xs text-slate-400">Numerical hydrodynamic CFL convergence threshold and solver constraints.</p>
            </div>
          )}
        </div>

        {/* Footer Navigation */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/60 flex justify-between items-center">
          <button 
            onClick={() => setStep(Math.max(1, step - 1))} 
            disabled={step === 1} 
            className="flex items-center gap-1.5 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold transition disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back
          </button>

          <div className="flex items-center gap-2">
            {/* Quick Run option available from any step when parameters are valid */}
            {nameValid && bboxValid && rainfallValid && step < 4 && (
              <button 
                onClick={handleSubmit} 
                disabled={saving} 
                className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/40 rounded-xl text-xs font-bold transition shadow-sm"
                title="Launch simulation immediately with current settings"
              >
                <Zap className="w-3.5 h-3.5 text-emerald-400" />
                {saving ? "Simulating..." : "Quick Run"}
              </button>
            )}

            {step < 4 ? (
              <button 
                onClick={() => setStep(step + 1)} 
                className="flex items-center gap-1.5 px-5 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-cyan-900/30 transition"
              >
                Next
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            ) : (
              <button 
                onClick={handleSubmit} 
                disabled={saving || !nameValid || !bboxValid} 
                className="flex items-center gap-1.5 px-6 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-emerald-900/30 transition disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {saving ? "Simulating..." : isEdit ? "Save Changes" : "Run Simulation"}
              </button>
            )}
          </div>
        </div>

      </div>
    </div>
  )
}

