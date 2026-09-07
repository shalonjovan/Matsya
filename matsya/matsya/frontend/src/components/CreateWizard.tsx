import { useState, useEffect, useRef } from "react"
import type { Simulation } from "../types/simulation"
import type { RainfallZone } from "../types/simulation"
import { API_BASE } from "../hooks/useSimulation"
import RainfallGraph from "./RainfallGraph"
import ZoneRain from "./ZoneRain"
import { randomPreset } from "../utils/rainfall"
import HydroBadge from "./HydroBadge"
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

function bboxFromPolygon(poly: any): [number,number,number,number] {
  try {
    const coords = poly.coordinates[0] as [number,number][]
    let minLon = Infinity, minLat = Infinity, maxLon = -Infinity, maxLat = -Infinity
    for (const [lon, lat] of coords) {
      if (lon < minLon) minLon = lon
      if (lon > maxLon) maxLon = lon
      if (lat < minLat) minLat = lat
      if (lat > maxLat) maxLat = lat
    }
    return [minLon, minLat, maxLon, maxLat]
  } catch { return [80.15,13.08,80.20,13.13] }
}
function areaKm2(poly: any): number {
  try {
    // simple shoelace for EPSG:4326 approx, convert to km2 via 111km per degree
    const coords = poly.coordinates[0] as [number,number][]
    let area = 0
    for (let i=0;i<coords.length-1;i++) {
      const [x1,y1]=coords[i], [x2,y2]=coords[i+1]
      area += (x1*y2 - x2*y1)
    }
    area = Math.abs(area)/2
    // 1 degree ~111km, area in deg2 → km2
    return area * 111*111 * Math.cos(((coords[0][1]+coords[coords.length/2|0][1])/2)*Math.PI/180)
  } catch { return 0 }
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

export function boundsToBboxStrings(bounds: any): { minLon: string, maxLon: string, minLat: string, maxLat: string } {
  return {
    minLon: String(bounds.getWest().toFixed(5)),
    maxLon: String(bounds.getEast().toFixed(5)),
    minLat: String(bounds.getSouth().toFixed(5)),
    maxLat: String(bounds.getNorth().toFixed(5)),
  }
}

export default function CreateWizard({ open, onClose, onCreated, editSim }: Props) {
  const isEdit = !!editSim
  const [step, setStep] = useState(1)
  const [name, setName] = useState(editSim?.name ?? "")
  const [minLon, setMinLon] = useState(String(editSim?.area?.bbox?.[0] ?? "80.15"))
  const [minLat, setMinLat] = useState(String(editSim?.area?.bbox?.[1] ?? "13.08"))
  const [maxLon, setMaxLon] = useState(String(editSim?.area?.bbox?.[2] ?? "80.20"))
  const [maxLat, setMaxLat] = useState(String(editSim?.area?.bbox?.[3] ?? "13.13"))
  const [polygon, setPolygon] = useState<any>(editSim?.area?.polygon ?? null)
  const [rate, setRate] = useState(String(editSim?.rainfall?.rateMmHr ?? (editSim?.rainfall as any)?.constantRate ?? "50"))
  const [duration, setDuration] = useState(String(editSim?.rainfall?.durationHr ?? "1"))
  const [rainfallMode, setRainfallMode] = useState<"constant"|"variable">(editSim?.rainfall?.mode === "variable" ? "variable" : "constant")
  const [totalTime, setTotalTime] = useState(String(editSim?.rainfall?.totalTime ?? "6"))
  const [maxRain, setMaxRain] = useState(String(editSim?.rainfall?.maxRain ?? "100"))
  const [unit, setUnit] = useState<"rate"|"total">(editSim?.rainfall?.unit === "total" ? "total" : "rate")
  const [points, setPoints] = useState<{time:number,amount:number}[]>(editSim?.rainfall?.points ?? [{time:0,amount:0},{time:3,amount:50}])
  const [zones, setZones] = useState<RainfallZone[]>(editSim?.rainfall?.zones ?? [])
  const [cfl, setCfl] = useState(String((editSim as any)?.parameters?.cfl ?? "0.7"))
  const [initialFill, setInitialFill] = useState(String((editSim as any)?.parameters?.initialFillPct ?? "75"))
  const [search, setSearch] = useState("")
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [areaMode, setAreaMode] = useState<"search"|"rect"|"chennai">("search")
  const [hydroSummary, setHydroSummary] = useState<any>(null)
  const rectMapRef = useRef<HTMLDivElement>(null)
  const rectMapInstance = useRef<any>(null)
  const rectLayerRef = useRef<any>(null)

  // Sync when editSim changes
  useEffect(()=>{
    if (editSim) {
      setName(editSim.name ?? "")
      setMinLon(String(editSim.area?.bbox?.[0] ?? "80.15"))
      setMinLat(String(editSim.area?.bbox?.[1] ?? "13.08"))
      setMaxLon(String(editSim.area?.bbox?.[2] ?? "80.20"))
      setMaxLat(String(editSim.area?.bbox?.[3] ?? "13.13"))
      setPolygon(editSim.area?.polygon ?? null)
      setRate(String(editSim.rainfall?.rateMmHr ?? (editSim.rainfall as any)?.constantRate ?? "50"))
      setDuration(String(editSim.rainfall?.durationHr ?? "1"))
      setRainfallMode(editSim.rainfall?.mode === "variable" ? "variable" : "constant")
      setTotalTime(String(editSim.rainfall?.totalTime ?? "6"))
      setMaxRain(String(editSim.rainfall?.maxRain ?? "100"))
      setUnit(editSim.rainfall?.unit === "total" ? "total" : "rate")
      setPoints(editSim.rainfall?.points ?? [{time:0,amount:0},{time:3,amount:50}])
      setZones(editSim.rainfall?.zones ?? [])
      setInitialFill(String((editSim as any)?.parameters?.initialFillPct ?? "75"))
    }
  },[editSim])

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

  // Live drain availability from the backend asset store (micro/macro KML).
  // Falls back to the sim's attached dataset flag if the fetch fails (offline).
  useEffect(()=>{
    if (!open) return
    let alive = true
    fetch("/api/hydro/summary").then(r=>r.json()).then(j=>{ if (alive) setHydroSummary(j) }).catch(()=>{})
    return ()=>{ alive = false }
  },[open])

  // Initialize draw map when rect tab is active — rectangle draw
  useEffect(()=>{
    if (!open || areaMode!=="rect" || !rectMapRef.current) return
    let cancelled=false
    const init = async()=>{
      await import("leaflet")
      await import("leaflet-draw")
      // @ts-ignore
      await import("leaflet/dist/leaflet.css")
      // @ts-ignore
      await import("leaflet-draw/dist/leaflet.draw.css")
      if (cancelled || !rectMapRef.current) return
      // leaflet-draw ships as a UMD IIFE on (window, document): it mutates the
      // GLOBAL L (window.L), while `await import("leaflet")` returns a different
      // module object without the plugin. Always use the object the plugin
      // attached to — using the import object leaves Draw undefined and no map
      // event handlers (draw/edit/save) ever attach.
      const L = ((window as any).L ?? {}) as any
      if (!L.map || !L.Draw || !L.Control || !(L.Control as any).Draw) {
        if (!cancelled) setError("Map drawing library failed to load (leaflet-draw did not attach). Please reload and retry.")
        return
      }
      if (rectMapInstance.current) {
        try { rectMapInstance.current.remove() } catch {}
      }
      const map = L.map(rectMapRef.current).setView([13.08,80.17], 11)
      L.tileLayer("https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",{maxZoom:19, attribution:"© OSM"}).addTo(map)
      const drawnItems = new (L as any).FeatureGroup()
      map.addLayer(drawnItems)
      rectLayerRef.current = drawnItems
      // Restore existing bbox as rectangle if any and no polygon
      if (!polygon && bboxValid) {
        try {
          const bounds: any = [[parseFloat(minLat), parseFloat(minLon)], [parseFloat(maxLat), parseFloat(maxLon)]]
          const rect = (L as any).rectangle(bounds, {color:"#3388ff", weight:2})
          drawnItems.addLayer(rect)
        } catch {}
      }
      // Restore polygon (Chennai) if exists — show as overlay but not editable via rect
      if (polygon) {
        try {
          const layer = L.geoJSON({type:"Feature", geometry: polygon} as any, {style:{color:"#10b981", weight:2, fillOpacity:0.2}}).getLayers()[0]
          if (layer) drawnItems.addLayer(layer as any)
        } catch {}
      }
      const drawControl = new (L as any).Control.Draw({
        draw: { rectangle: { showArea: true }, polygon: false, circle: false, marker: false, circlemarker: false, polyline: false },
        edit: { featureGroup: drawnItems }
      })
      map.addControl(drawControl)
      map.on((L as any).Draw.Event.CREATED, (e:any)=>{
        // Only rectangle
        if (e.layerType === "rectangle") {
          drawnItems.clearLayers()
          drawnItems.addLayer(e.layer)
          const b = boundsToBboxStrings((e.layer as any).getBounds())
          setMinLon(b.minLon); setMaxLon(b.maxLon); setMinLat(b.minLat); setMaxLat(b.maxLat)
          setPolygon(null)
        }
      })
      // Live sync while dragging/resizing via the Edit toolbar: leaflet-draw only
      // fires draw:edited on Save, so without these the coords stay frozen mid-edit.
      const syncLiveBounds = (e:any)=>{
        try {
          const layer = e?.layer as any
          if (layer && layer.getBounds) {
            const b = boundsToBboxStrings(layer.getBounds())
            setMinLon(b.minLon); setMaxLon(b.maxLon); setMinLat(b.minLat); setMaxLat(b.maxLat)
            setPolygon(null)
          }
        } catch {}
      }
      map.on((L as any).Draw.Event.EDITMOVE, syncLiveBounds)
      map.on((L as any).Draw.Event.EDITRESIZE, syncLiveBounds)
      map.on((L as any).Draw.Event.EDITED, (e:any)=>{
        const layers = e.layers.getLayers()
        if (layers.length>0) {
          const layer = layers[0] as any
          if (layer.getBounds) {
            const b = boundsToBboxStrings(layer.getBounds())
            setMinLon(b.minLon); setMaxLon(b.maxLon); setMinLat(b.minLat); setMaxLat(b.maxLat)
            setPolygon(null)
          } else if (layer.toGeoJSON) {
            const gj = layer.toGeoJSON()
            const poly = gj.geometry
            if (poly.type==="Polygon") {
              setPolygon(poly)
              const bbox = bboxFromPolygon(poly)
              setMinLon(String(bbox[0].toFixed(5))); setMinLat(String(bbox[1].toFixed(5))); setMaxLon(String(bbox[2].toFixed(5))); setMaxLat(String(bbox[3].toFixed(5)))
            }
          }
        }
      })
      map.on((L as any).Draw.Event.DELETED, ()=>{
        // keep bbox as is, clear polygon if it was Chennai
        // don't clear bbox
      })
      setTimeout(()=>{ try{ map.invalidateSize()}catch{} },200)
      rectMapInstance.current = map
    }
    init()
    return ()=>{
      cancelled=true
      if (rectMapInstance.current) {
        try { rectMapInstance.current.remove() } catch {}
        rectMapInstance.current=null
      }
    }
  },[open, areaMode])

  if (!open) return null

  const bbox: [number,number,number,number] = [parseFloat(minLon), parseFloat(minLat), parseFloat(maxLon), parseFloat(maxLat)]
  const bboxValid = bbox.every(n=>!isNaN(n)) && bbox[0] < bbox[2] && bbox[1] < bbox[3]
  const rainfallValid = !isNaN(parseFloat(rate)) && !isNaN(parseFloat(duration)) && parseFloat(rate)>0 && parseFloat(duration)>0
  const nameValid = name.trim().length>0
  const polygonValid = polygon ? true : false
  const areaValid = polygonValid || bboxValid
  const isVariable = rainfallMode === "variable"
  const rainValid = isVariable ? (points.length>=2 && !isNaN(parseFloat(totalTime)) && !isNaN(parseFloat(maxRain))) : rainfallValid

  const drainMissing = hydroSummary ? (hydroSummary.drains ?? 0) === 0 : !(editSim as any)?.drainage?.uri
  const drainLine = hydroSummary && !drainMissing
    ? `connected (${hydroSummary.drains} micro/macro → ${hydroSummary.snapped_to_waterbody ?? 0} waterbodies, ${hydroSummary.to_river ?? 0} river, ${hydroSummary.to_sea ?? 0} sea)`
    : "connected (10,276 SWD lines)"

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
    setPolygon(null)
  }

  const handleSearch = async () => {
    if (!search.trim()) return
    setSearching(true)
    setError(null)
    setSearchResults([])
    try {
      const res = await fetch(`https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(search)}&format=json&limit=5&addressdetails=1`)
      if (!res.ok) throw new Error("search failed")
      const data = await res.json()
      // Nominatim results + local Chennai fuzzy
      const chennaiAreas = ["Velachery","T Nagar","Adyar","Guindy","Tambaram","Anna Nagar","Pallikaranai","Mylapore","Nungambakkam","Egmore","George Town","Thiruvanmiyur","Besant Nagar","Mandaveli","Kotturpuram","Saidapet","Porur","Mogappair","Ambattur","Perambur"]
      const local = chennaiAreas.filter(a=>a.toLowerCase().includes(search.toLowerCase())).slice(0,3).map(name=>({
        display_name: `${name}, Chennai, Tamil Nadu, India`,
        boundingbox: ["13.00","13.15","80.15","80.30"],
        type: "local",
        lat: "13.08", lon: "80.20"
      }))
      const combined = [...data.slice(0,5), ...local].slice(0,5)
      if (combined.length===0) setError("No results")
      setSearchResults(combined)
    } catch (e:any) { setError(e.message) } finally { setSearching(false) }
  }

  const handleSelectSearch = (item:any) => {
    try {
      if (item.boundingbox) {
        // Nominatim boundingbox [south, north, west, east]
        const south = parseFloat(item.boundingbox[0]); const north = parseFloat(item.boundingbox[1]); const west = parseFloat(item.boundingbox[2]); const east = parseFloat(item.boundingbox[3])
        setMinLon(String(west)); setMaxLon(String(east)); setMinLat(String(south)); setMaxLat(String(north))
        setPolygon(null)
        // optionally create polygon from bbox for free-form
        const poly = {type:"Polygon", coordinates:[[[west,south],[east,south],[east,north],[west,north],[west,south]]] }
        // Don't auto-set polygon, just bbox
      } else if (item.lat && item.lon) {
        const lat=parseFloat(item.lat), lon=parseFloat(item.lon)
        setMinLon(String(lon-0.02)); setMaxLon(String(lon+0.02)); setMinLat(String(lat-0.02)); setMaxLat(String(lat+0.02))
        setPolygon(null)
      }
      setSearchResults([])
    } catch {}
  }

  const handleChennai = async () => {
    setError(null)
    try {
      // Try to fetch from public assets, fallback to known bbox
      let gj:any = null
      try {
        const res = await fetch("/assets/chennai_border.geojson")
        if (res.ok) gj = await res.json()
      } catch {}
      if (!gj) {
        const res2 = await fetch("/chennai_border.geojson")
        if (res2.ok) gj = await res2.json()
      }
      if (!gj) {
        // fallback: use assets via API or known polygon
        gj = {type:"FeatureCollection",features:[{geometry:{type:"Polygon",coordinates:[[[80.15,13.08],[80.20,13.08],[80.20,13.13],[80.15,13.13],[80.15,13.08]]]}}]}
      }
      const poly = gj.features?.[0]?.geometry || gj.geometry || gj
      if (poly && poly.type==="Polygon") {
        setPolygon(poly)
        const bbox = bboxFromPolygon(poly)
        setMinLon(String(bbox[0].toFixed(5))); setMinLat(String(bbox[1].toFixed(5))); setMaxLon(String(bbox[2].toFixed(5))); setMaxLat(String(bbox[3].toFixed(5)))
        // Also show area
      } else {
        // fallback to known Chennai bbox
        setMinLon("80.08"); setMaxLon("80.30"); setMinLat("12.88"); setMaxLat("13.25")
        setPolygon(null)
      }
    } catch (e:any) { setError("Failed to load Chennai border: "+e.message) }
  }

  const handleSubmit = async () => {
    const rainOk = isVariable ? (points.length>=2 && !isNaN(parseFloat(totalTime)) && !isNaN(parseFloat(maxRain))) : rainfallValid
    if (!nameValid || !areaValid || !rainOk) { setError("Please fix validation errors"); return }
    setSaving(true); setError(null)
    try {
      const payload: any = {
        name: name.trim(),
        area: { bbox, crs: "EPSG:4326", polygon: polygon || undefined },
        rainfall: isVariable ? { mode:"variable", totalTime: parseFloat(totalTime), maxRain: parseFloat(maxRain), unit, points, zones: zones.length ? zones : undefined } : { mode:"constant", rateMmHr: parseFloat(rate), durationHr: parseFloat(duration), constantRate: parseFloat(rate), zones: zones.length ? zones : undefined },
        parameters: { cfl: parseFloat(cfl) || 0.7, initialFillPct: Math.min(100, Math.max(0, parseFloat(initialFill) || 75)) }
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
      setPolygon(null)
    } catch (e:any) { setError(e.message) } finally { setSaving(false) }
  }

  const polygonArea = polygon ? areaKm2(polygon).toFixed(2) : null

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
        className="glass-panel rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col border border-slate-700/80 overflow-hidden"
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

          {/* STEP 2: Geographic Area — free-form, search, or Chennai entirety */}
          {step === 2 && (
            <div className="space-y-4">
              <div>
                <h4 className="font-semibold text-sm text-white flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-cyan-400" />
                  Geographic Area & Domain Limits
                </h4>
                <p className="text-xs text-slate-400 mt-0.5">Free-form, search, or Chennai entirety — WGS84 coordinates (EPSG:4326).</p>
              </div>

              {/* Area mode tabs */}
              <div className="flex gap-1.5 p-1.5 bg-slate-950/60 border border-slate-800 rounded-xl text-xs font-semibold">
                {(["search","rect","chennai"] as const).map(m => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setAreaMode(m)}
                    className={`flex-1 py-2 rounded-xl capitalize transition focus-ring flex items-center justify-center gap-1.5 ${
                      areaMode === m
                        ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    {m === "search" && <Search className="w-3.5 h-3.5" />}
                    {m === "rect" && <MapPin className="w-3.5 h-3.5" />}
                    {m === "chennai" && <Compass className="w-3.5 h-3.5" />}
                    {m}
                  </button>
                ))}
              </div>

              {areaMode === "search" && (
                <div className="space-y-2">
                  <div className="flex gap-2">
                    <div className="relative flex-1">
                      <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                      <input
                        id="wizard-search-loc"
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                        onKeyDown={e => e.key === "Enter" && handleSearch()}
                        placeholder="Search Velachery, T Nagar, Adyar..."
                        aria-label="Search Chennai location"
                        className="w-full bg-slate-950 border border-slate-700/80 rounded-xl pl-9 pr-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus-ring transition"
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
                  {searchResults.length > 0 && (
                    <ul className="mt-2 border border-slate-800 rounded-xl bg-slate-950/80 max-h-48 overflow-auto divide-y divide-slate-800/80">
                      {searchResults.map((item: any, i: number) => (
                        <li key={i} onClick={() => handleSelectSearch(item)} className="px-3 py-2 hover:bg-slate-800/70 cursor-pointer">
                          <div className="text-xs text-white">{item.display_name}</div>
                          <div className="text-[11px] font-mono text-slate-400">{item.type || "place"} • {item.boundingbox ? `${item.boundingbox[2]},${item.boundingbox[0]} → ${item.boundingbox[3]},${item.boundingbox[1]}` : `${item.lat},${item.lon}`}</div>
                        </li>
                      ))}
                    </ul>
                  )}
                  <p className="text-[11px] text-slate-400">Search provides 5-item similarity list (Nominatim + local Chennai fuzzy). Selecting centers bbox.</p>
                </div>
              )}

              {areaMode === "rect" && (
                <div className="space-y-2">
                  <div className="grid grid-cols-2 gap-3 p-4 bg-slate-950/60 rounded-xl border border-slate-800">
                    <label className="text-xs text-slate-300">Min Lon (West)
                      <input value={minLon} onChange={e => { setMinLon(e.target.value); setPolygon(null) }} className="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white font-mono text-xs focus:border-cyan-500 focus-ring focus:outline-none" />
                    </label>
                    <label className="text-xs text-slate-300">Max Lon (East)
                      <input value={maxLon} onChange={e => { setMaxLon(e.target.value); setPolygon(null) }} className="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white font-mono text-xs focus:border-cyan-500 focus-ring focus:outline-none" />
                    </label>
                    <label className="text-xs text-slate-300">Min Lat (South)
                      <input value={minLat} onChange={e => { setMinLat(e.target.value); setPolygon(null) }} className="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white font-mono text-xs focus:border-cyan-500 focus-ring focus:outline-none" />
                    </label>
                    <label className="text-xs text-slate-300">Max Lat (North)
                      <input value={maxLat} onChange={e => { setMaxLat(e.target.value); setPolygon(null) }} className="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white font-mono text-xs focus:border-cyan-500 focus-ring focus:outline-none" />
                    </label>
                  </div>
                  {!bboxValid && (
                    <div className="text-rose-400 text-xs flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      <span>Invalid bbox: must be minLon &lt; maxLon and minLat &lt; maxLat (e.g., 80.15,13.08,80.20,13.13)</span>
                    </div>
                  )}
                  <div ref={rectMapRef} data-testid="rect-map" className="w-full h-[300px] rounded-xl border border-slate-800 bg-slate-950" />
                  <div className="flex justify-between text-[11px] text-slate-400">
                    <span>Draw rectangle on map (drag) or edit inputs — both set BBox. Use toolbar to draw/edit.</span>
                    <span className="font-mono text-cyan-400">BBox {bbox.map(n => n.toFixed(3)).join(", ")}</span>
                  </div>
                  <div className="flex gap-2 items-center">
                    <button type="button" onClick={() => { if (rectLayerRef.current) rectLayerRef.current.clearLayers() }} className="px-3 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700 border border-slate-700/60 text-[11px] text-slate-300">Clear map</button>
                    <span className="text-[11px] text-slate-400">Rectangle via coords or map — polygon cleared when using rectangle. Chennai polygon preserved in Chennai tab.</span>
                  </div>
                </div>
              )}

              {areaMode === "chennai" && (
                <div className="space-y-2">
                  <button type="button" onClick={handleChennai} className="w-full py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-sm transition focus-ring">Select Entire Chennai</button>
                  <p className="text-[11px] text-slate-400">Loads assets/chennai_border.geojson single Polygon (~200 coords, covers Chennai) → sets polygon + bbox</p>
                  {polygon && <div className="p-2.5 rounded-xl bg-emerald-950/40 border border-emerald-800 text-emerald-300 text-xs font-mono">Polygon set with {polygon.coordinates[0].length} points, bbox {bbox.map(n => n.toFixed(3)).join(", ")}</div>}
                </div>
              )}

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

              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 text-[11px] font-mono text-slate-300">
                Current: {polygon ? `Polygon ${polygon.coordinates[0].length} points • BBox ${bbox.map(n => n.toFixed(3)).join(", ")} • ~${polygonArea} km²` : `Rectangle BBox ${bbox.map(n => n.toFixed(3)).join(", ")}`}
                {!areaValid && <span className="text-rose-400"> — Invalid area</span>}
              </div>
              <p className="text-[11px] text-slate-400">Rectangular still works (bbox inputs). If polygon exists, it takes precedence for TIF clip via rasterio.mask.</p>
            </div>
          )}

          {/* STEP 3: Rainfall + Datasets */}
          {step === 3 && (
            <div className="space-y-4">
              <div>
                <h4 className="font-semibold text-sm text-white flex items-center gap-2">
                  <CloudRain className="w-4 h-4 text-cyan-400" />
                  Rainfall — Default vs Advanced (variable)
                </h4>
                <p className="text-xs text-slate-400 mt-0.5">Constant design storm or time-varying hyetograph.</p>
              </div>

              <div className="flex gap-1.5 p-1.5 bg-slate-950/60 border border-slate-800 rounded-xl text-xs font-semibold">
                <button
                  type="button"
                  onClick={() => setRainfallMode("constant")}
                  className={`flex-1 py-2 rounded-xl transition focus-ring ${
                    rainfallMode === "constant"
                      ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  Default (constant)
                </button>
                <button
                  type="button"
                  onClick={() => setRainfallMode("variable")}
                  className={`flex-1 py-2 rounded-xl transition focus-ring ${
                    rainfallMode === "variable"
                      ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  Advanced (graph)
                </button>
              </div>

              {rainfallMode === "constant" ? (
                <div className="grid grid-cols-2 gap-3">
                  <label className="text-xs text-slate-300">
                    Rainfall rate (mm/hr)
                    <input
                      value={rate}
                      onChange={e => setRate(e.target.value)}
                      className="mt-1 w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono text-xs focus:border-cyan-500 focus-ring focus:outline-none"
                    />
                  </label>
                  <label className="text-xs text-slate-300">
                    Duration (hours)
                    <input
                      value={duration}
                      onChange={e => setDuration(e.target.value)}
                      className="mt-1 w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono text-xs focus:border-cyan-500 focus-ring focus:outline-none"
                    />
                  </label>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="grid grid-cols-3 gap-2">
                    <label className="text-xs text-slate-300">Total time (hr)
                      <input value={totalTime} onChange={e => setTotalTime(e.target.value)} className="mt-1 w-full bg-slate-950 border border-slate-700 rounded-lg px-2 py-1.5 text-white font-mono text-xs focus:border-cyan-500 focus-ring focus:outline-none" />
                    </label>
                    <label className="text-xs text-slate-300">Max rain ({unit === "rate" ? "mm/hr" : "mm"})
                      <input value={maxRain} onChange={e => setMaxRain(e.target.value)} className="mt-1 w-full bg-slate-950 border border-slate-700 rounded-lg px-2 py-1.5 text-white font-mono text-xs focus:border-cyan-500 focus-ring focus:outline-none" />
                    </label>
                    <label className="text-xs text-slate-300">Unit
                      <select value={unit} onChange={e => setUnit(e.target.value as any)} className="mt-1 w-full bg-slate-950 border border-slate-700 rounded-lg px-2 py-1.5 text-white text-xs focus:border-cyan-500 focus-ring focus:outline-none">
                        <option value="rate">Rate mm/hr</option>
                        <option value="total">Total mm</option>
                      </select>
                    </label>
                  </div>
                  <div className="rounded-xl border border-slate-800 overflow-hidden">
                    <RainfallGraph totalTime={parseFloat(totalTime) || 6} maxRain={parseFloat(maxRain) || 100} unit={unit} points={points} onChange={setPoints} />
                  </div>
                  <div className="flex gap-2 items-center">
                    <button
                      type="button"
                      onClick={() => {
                        const presets = ["burst", "gradual", "double-peak", "random"]
                        const pick = presets[Math.floor(Math.random() * presets.length)]
                        setPoints(randomPreset(pick, parseFloat(totalTime) || 6, parseFloat(maxRain) || 100))
                      }}
                      className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-xl text-xs font-semibold transition focus-ring"
                    >
                      Random
                    </button>
                    <span className="text-[11px] text-slate-400">Random curve shapes: burst, gradual, double-peak, random (sorted, within 0→{totalTime}hr, 0→{maxRain}{unit === "rate" ? "mm/hr" : "mm"})</span>
                  </div>
                  <p className="text-[11px] text-slate-400">Points: {points.length} • Smooth spline y=spline(x) • Time on x (0→{totalTime}hr), Amount on y (0→{maxRain}) • Drag to move, double-click to delete, click to add.</p>
                </div>
              )}

              <ZoneRain zones={zones} onChange={setZones} bbox={bbox} />

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
                  {rainfallMode === "constant" ? (
                    rainfallValid ? (
                      <span className="text-emerald-400 flex items-center gap-1 font-medium font-mono">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        {rate} mm/hr × {duration} hr
                      </span>
                    ) : (
                      <span className="text-rose-400 flex items-center gap-1 font-medium">
                        <AlertTriangle className="w-3.5 h-3.5" />
                        invalid
                      </span>
                    )
                  ) : (
                    <span className="text-emerald-400 flex items-center gap-1 font-medium font-mono">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      ✓ {points.length} points, {totalTime}hr, {unit}
                    </span>
                  )}
                </div>
                <div className="flex items-center justify-between py-1 border-b border-slate-800/80">
                  <span className="text-slate-400">Area Polygon</span>
                  {polygon ? (
                    <span className="text-emerald-400 flex items-center gap-1 font-medium font-mono">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      ✓ {polygon.coordinates[0].length} points ~{polygonArea} km²
                    </span>
                  ) : (
                    <span className="text-slate-500">— using rectangle</span>
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
                      {drainLine}
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
                <label htmlFor="wizard-fill" className="block text-xs text-slate-300">
                  Lake initial fill (% of capacity)
                  <span className="flex items-center gap-3">
                    <input
                      id="wizard-fill"
                      type="range" min={0} max={100} step={5}
                      value={initialFill}
                      onChange={e => setInitialFill(e.target.value)}
                      className="flex-1 h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
                    />
                    <span className="font-mono text-xs text-cyan-300 w-12 text-right">{initialFill}%</span>
                  </span>
                  <span className="text-[11px] text-slate-400 mt-1 block">0% = lakes start empty, 100% = brimful (spills on first rain). Default 75% matches historic behavior.</span>
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
            {nameValid && areaValid && rainValid && step < 4 && (
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
                disabled={saving || !nameValid || !areaValid}
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
