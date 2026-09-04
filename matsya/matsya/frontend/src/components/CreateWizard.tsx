import { useState, useEffect, useRef } from "react"
import type { Simulation } from "../types/simulation"
import { API_BASE } from "../hooks/useSimulation"
import RainfallGraph from "./RainfallGraph"
import { randomPreset } from "../utils/rainfall"

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

export default function CreateWizard({ open, onClose, onCreated, editSim }: Props) {
  const isEdit = !!editSim
  const [step, setStep] = useState(1)
  const [name, setName] = useState(editSim?.name ?? "")
  const [minLon, setMinLon] = useState(String(editSim?.area?.bbox?.[0] ?? "80.15"))
  const [minLat, setMinLat] = useState(String(editSim?.area?.bbox?.[1] ?? "13.08"))
  const [maxLon, setMaxLon] = useState(String(editSim?.area?.bbox?.[2] ?? "80.20"))
  const [maxLat, setMaxLat] = useState(String(editSim?.area?.bbox?.[3] ?? "13.13"))
  const [polygon, setPolygon] = useState<any>(editSim?.area?.polygon ?? null)
  const [rate, setRate] = useState(String(editSim?.rainfall?.rateMmHr ?? editSim?.rainfall?.constantRate ?? "50"))
  const [duration, setDuration] = useState(String(editSim?.rainfall?.durationHr ?? "1"))
  const [rainfallMode, setRainfallMode] = useState<"constant"|"variable">(editSim?.rainfall?.mode === "variable" ? "variable" : "constant")
  const [totalTime, setTotalTime] = useState(String(editSim?.rainfall?.totalTime ?? "6"))
  const [maxRain, setMaxRain] = useState(String(editSim?.rainfall?.maxRain ?? "100"))
  const [unit, setUnit] = useState<"rate"|"total">(editSim?.rainfall?.unit === "total" ? "total" : "rate")
  const [points, setPoints] = useState<{time:number,amount:number}[]>(editSim?.rainfall?.points ?? [{time:0,amount:0},{time:3,amount:50}])
  const [cfl, setCfl] = useState(String((editSim as any)?.parameters?.cfl ?? "0.7"))
  const [search, setSearch] = useState("")
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [areaMode, setAreaMode] = useState<"search"|"rect"|"chennai">("search")
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
      setRate(String(editSim.rainfall?.rateMmHr ?? "50"))
      setDuration(String(editSim.rainfall?.durationHr ?? "1"))
    }
  },[editSim])

  // Initialize draw map when rect tab is active — rectangle draw
  useEffect(()=>{
    if (!open || areaMode!=="rect" || !rectMapRef.current) return
    let cancelled=false
    const init = async()=>{
      const L = await import("leaflet")
      await import("leaflet-draw")
      // @ts-ignore
      await import("leaflet/dist/leaflet.css")
      // @ts-ignore
      await import("leaflet-draw/dist/leaflet.draw.css")
      if (cancelled || !rectMapRef.current) return
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
          const bounds = (e.layer as any).getBounds()
          setMinLon(String(bounds.getWest().toFixed(5)))
          setMaxLon(String(bounds.getEast().toFixed(5)))
          setMinLat(String(bounds.getSouth().toFixed(5)))
          setMaxLat(String(bounds.getNorth().toFixed(5)))
          setPolygon(null)
        }
      })
      map.on((L as any).Draw.Event.EDITED, (e:any)=>{
        const layers = e.layers.getLayers()
        if (layers.length>0) {
          const layer = layers[0] as any
          if (layer.getBounds) {
            const bounds = layer.getBounds()
            setMinLon(String(bounds.getWest().toFixed(5)))
            setMaxLon(String(bounds.getEast().toFixed(5)))
            setMinLat(String(bounds.getSouth().toFixed(5)))
            setMaxLat(String(bounds.getNorth().toFixed(5)))
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
    const isVariable = rainfallMode==="variable"
    const rainValid = isVariable ? (points.length>=2 && !isNaN(parseFloat(totalTime)) && !isNaN(parseFloat(maxRain))) : rainfallValid
    if (!nameValid || !areaValid || !rainValid) { setError("Please fix validation errors"); return }
    setSaving(true); setError(null)
    try {
      const payload: any = {
        name: name.trim(),
        area: { bbox, crs: "EPSG:4326", polygon: polygon || undefined },
        rainfall: isVariable ? { mode:"variable", totalTime: parseFloat(totalTime), maxRain: parseFloat(maxRain), unit, points } : { mode:"constant", rateMmHr: parseFloat(rate), durationHr: parseFloat(duration), constantRate: parseFloat(rate) },
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
      setPolygon(null)
    } catch (e:any) { setError(e.message) } finally { setSaving(false) }
  }

  const polygonArea = polygon ? areaKm2(polygon).toFixed(2) : null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-3xl max-h-[90vh] overflow-auto">
        <div className="p-6 border-b flex justify-between items-center">
          <h3 className="text-lg font-semibold">{isEdit ? "Edit Simulation" : "Create Simulation"}</h3>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-700">✕</button>
        </div>
        <div className="p-6 space-y-6">
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
              <h4 className="font-medium">Geographic area — free-form, search, or Chennai entirety</h4>
              <div className="flex gap-2 text-xs">
                {["search","rect","chennai"].map(m=>(
                  <button key={m} onClick={()=>setAreaMode(m as any)} className={`flex-1 py-2 rounded capitalize ${areaMode===m ? "bg-emerald-600 text-white" : "bg-slate-100"}`}>{m}</button>
                ))}
              </div>

              {areaMode==="search" && (
                <div className="space-y-2">
                  <div className="flex gap-2">
                    <input value={search} onChange={e=>setSearch(e.target.value)} onKeyDown={e=>e.key==="Enter"&&handleSearch()} placeholder="Search Velachery, T Nagar, Adyar..." className="flex-1 border rounded px-3 py-2" />
                    <button onClick={handleSearch} disabled={searching} className="px-4 py-2 bg-slate-800 text-white rounded text-sm disabled:opacity-50">{searching ? "..." : "Search"}</button>
                  </div>
                  {searchResults.length>0 && (
                    <ul className="border rounded bg-white max-h-48 overflow-auto">
                      {searchResults.map((item:any, i:number)=>(
                        <li key={i} onClick={()=>handleSelectSearch(item)} className="px-3 py-2 hover:bg-blue-50 cursor-pointer border-b last:border-0">
                          <div className="font-medium text-sm">{item.display_name}</div>
                          <div className="text-xs text-slate-500">{item.type || "place"} • {item.boundingbox ? `${item.boundingbox[2]},${item.boundingbox[0]} → ${item.boundingbox[3]},${item.boundingbox[1]}` : `${item.lat},${item.lon}`}</div>
                        </li>
                      ))}
                    </ul>
                  )}
                  <p className="text-xs text-slate-500">Search provides 5-item similarity list (Nominatim + local Chennai fuzzy). Selecting centers bbox.</p>
                </div>
              )}

              {areaMode==="rect" && (
                <div className="space-y-2">
                  <div className="grid grid-cols-2 gap-3">
                    <label>Min Lon <input value={minLon} onChange={e=>{setMinLon(e.target.value); setPolygon(null)}} className="w-full border rounded px-2 py-1 font-mono" /></label>
                    <label>Max Lon <input value={maxLon} onChange={e=>{setMaxLon(e.target.value); setPolygon(null)}} className="w-full border rounded px-2 py-1 font-mono" /></label>
                    <label>Min Lat <input value={minLat} onChange={e=>{setMinLat(e.target.value); setPolygon(null)}} className="w-full border rounded px-2 py-1 font-mono" /></label>
                    <label>Max Lat <input value={maxLat} onChange={e=>{setMaxLat(e.target.value); setPolygon(null)}} className="w-full border rounded px-2 py-1 font-mono" /></label>
                  </div>
                  {!bboxValid && <span className="text-red-500 text-xs">Invalid bbox</span>}
                  <div ref={rectMapRef} data-testid="rect-map" className="w-full h-[300px] border rounded bg-slate-100" />
                  <div className="flex justify-between text-xs">
                    <span>Draw rectangle on map (drag) or edit inputs — both set BBox. Use toolbar to draw/edit.</span>
                    <span className="font-mono">BBox {bbox.map(n=>n.toFixed(3)).join(", ")}</span>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={()=>{ if(rectLayerRef.current) rectLayerRef.current.clearLayers()}} className="px-3 py-1 border rounded text-xs">Clear map</button>
                    <span className="text-xs text-slate-500">Rectangle via coords or map — polygon cleared when using rectangle. Chennai polygon preserved in Chennai tab.</span>
                  </div>
                </div>
              )}

              {areaMode==="chennai" && (
                <div className="space-y-2">
                  <button onClick={handleChennai} className="w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded font-medium">Select Entire Chennai</button>
                  <p className="text-xs text-slate-500">Loads {`assets/chennai_border.geojson`} single Polygon (~200 coords, covers Chennai) → sets polygon + bbox {bbox.join(", ")} {polygon && `• Area ~${polygonArea} km²`}</p>
                  {polygon && <div className="p-2 bg-emerald-50 border border-emerald-200 rounded text-xs">Polygon set with {polygon.coordinates[0].length} points, bbox {bbox.map(n=>n.toFixed(3)).join(", ")}</div>}
                </div>
              )}

              <div className="p-2 bg-slate-50 border rounded text-xs">
                Current: {polygon ? `Polygon ${polygon.coordinates[0].length} points • BBox ${bbox.map(n=>n.toFixed(3)).join(", ")} • ~${polygonArea} km²` : `Rectangle BBox ${bbox.map(n=>n.toFixed(3)).join(", ")}`}
                {!areaValid && <span className="text-red-500"> — Invalid area</span>}
              </div>
              <p className="text-xs text-slate-500">Rectangular still works (bbox inputs). If polygon exists, it takes precedence for TIF clip via rasterio.mask.</p>
            </div>
          )}
          {step===3 && (
            <div className="space-y-4">
              <h4 className="font-medium">Rainfall — Default vs Advanced (variable)</h4>
              <div className="flex gap-2 text-xs">
                <button onClick={()=>setRainfallMode("constant")} className={`flex-1 py-2 rounded ${rainfallMode==="constant" ? "bg-blue-600 text-white" : "bg-slate-100"}`}>Default (constant)</button>
                <button onClick={()=>setRainfallMode("variable")} className={`flex-1 py-2 rounded ${rainfallMode==="variable" ? "bg-emerald-600 text-white" : "bg-slate-100"}`}>Advanced (graph)</button>
              </div>
              {rainfallMode==="constant" ? (
                <div className="space-y-2">
                  <label>Rainfall rate mm/hr <input value={rate} onChange={e=>setRate(e.target.value)} className="w-full border rounded px-2 py-1" /></label>
                  <label>Duration hr <input value={duration} onChange={e=>setDuration(e.target.value)} className="w-full border rounded px-2 py-1" /></label>
                  <p className="text-xs text-slate-500">Constant rain over time (current model: 50 mm/hr ×1 hr). Rainfall: {rainfallValid ? `✓ ${rate} mm/hr × ${duration} hr` : `✗ invalid`}</p>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="grid grid-cols-3 gap-2">
                    <label>Total time (hr)<input value={totalTime} onChange={e=>setTotalTime(e.target.value)} className="w-full border rounded px-2 py-1" /></label>
                    <label>Max rain ({unit==="rate"?"mm/hr":"mm"})<input value={maxRain} onChange={e=>setMaxRain(e.target.value)} className="w-full border rounded px-2 py-1" /></label>
                    <label>Unit
                      <select value={unit} onChange={e=>setUnit(e.target.value as any)} className="w-full border rounded px-2 py-1">
                        <option value="rate">Rate mm/hr</option>
                        <option value="total">Total mm</option>
                      </select>
                    </label>
                  </div>
                  <RainfallGraph totalTime={parseFloat(totalTime)||6} maxRain={parseFloat(maxRain)||100} unit={unit} points={points} onChange={setPoints} />
                  <div className="flex gap-2">
                    <button onClick={()=>{
                      const presets=["burst","gradual","double-peak","random"]
                      const pick=presets[Math.floor(Math.random()*presets.length)]
                      setPoints(randomPreset(pick, parseFloat(totalTime)||6, parseFloat(maxRain)||100))
                    }} className="px-4 py-2 bg-purple-600 text-white rounded text-sm">Random</button>
                    <span className="text-xs text-slate-500 py-2">Random curve shapes: burst, gradual, double-peak, random (sorted, within 0→{totalTime}hr, 0→{maxRain}{unit==="rate"?"mm/hr":"mm"})</span>
                  </div>
                  <p className="text-xs text-slate-500">Points: {points.length} • Smooth spline y=spline(x) • Time on x (0→{totalTime}hr), Amount on y (0→{maxRain}) • Drag to move, double-click to delete, click to add.</p>
                </div>
              )}
              <ul className="text-sm space-y-1 border rounded p-3 bg-slate-50">
                <li>Terrain / DEM: <span className="text-emerald-600">✓ seeded</span></li>
                <li>Rainfall: {rainfallMode==="constant" ? (rainfallValid ? <span className="text-emerald-600">✓ {rate} mm/hr × {duration} hr</span> : <span className="text-red-500">✗ invalid</span>) : <span className="text-emerald-600">✓ {points.length} points, {totalTime}hr, {unit}</span>}</li>
                <li>Polygon: {polygon ? <span className="text-emerald-600">✓ {polygon.coordinates[0].length} points ~{polygonArea} km²</span> : <span className="text-slate-500">— using rectangle</span>}</li>
              </ul>
            </div>
          )}
          {step===4 && (
            <div className="space-y-4">
              <h4 className="font-medium">Advanced Settings §26</h4>
              <label>CFL <input value={cfl} onChange={e=>setCfl(e.target.value)} className="w-full border rounded px-2 py-1 font-mono" /></label>
              <p className="text-xs text-slate-500">Technical params hidden from normal users per §31.</p>
            </div>
          )}
        </div>
        <div className="p-4 border-t flex justify-between">
          <button onClick={()=>setStep(Math.max(1, step-1))} disabled={step===1} className="px-4 py-2 border rounded disabled:opacity-50">Back</button>
          <div className="flex gap-2">
            {step<4 ? <button onClick={()=>setStep(step+1)} className="px-4 py-2 bg-blue-600 text-white rounded">Next</button> : <button onClick={handleSubmit} disabled={saving || !nameValid || !areaValid} className="px-6 py-2 bg-emerald-600 text-white rounded disabled:opacity-50">{saving ? "Saving..." : isEdit ? "Save" : "Create"}</button>}
          </div>
        </div>
      </div>
    </div>
  )
}
