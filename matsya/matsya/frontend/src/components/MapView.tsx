import { useEffect, useRef } from "react"
import type { Simulation } from "../types/simulation"
import "leaflet/dist/leaflet.css"
import { drainColor } from "../utils/hydro"

export default function MapView({ simulation, layers, time, onPointSelect, onWaterbodySelect }: any) {
  const divRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<any>(null)
  const layerRefs = useRef<any>({})
  // Track current simulation id to detect changes
  const prevSimIdRef = useRef<string | null>(null)
  useEffect(()=>{
    if (!divRef.current) return
    // If map exists but simulation changed, teardown and recreate
    const simId = simulation?.id ?? "default"
    if (mapRef.current) {
      if (prevSimIdRef.current === simId) {
        // same sim, just update bounds
        const bbox = simulation?.area?.bbox ?? [80.15,13.08,80.20,13.13]
        const bounds: any = [[bbox[1], bbox[0]], [bbox[3], bbox[2]]]
        try { mapRef.current.fitBounds(bounds) } catch {}
        return
      } else {
        // different sim - teardown old map
        try { mapRef.current.remove() } catch {}
        mapRef.current = null
        layerRefs.current = {}
        // will fall through to create new map
      }
    }
    prevSimIdRef.current = simId
    let cancelled = false
    let map: any = null
    const init = async () => {
      const L = await import("leaflet")
      if (cancelled || !divRef.current) return
      ;(window as any).L = L
      const bbox = simulation?.area?.bbox ?? [80.15,13.08,80.20,13.13]
      const bounds: any = [[bbox[1], bbox[0]], [bbox[3], bbox[2]]]
      try {
        map = L.map(divRef.current!, { zoomControl:true, preferCanvas:true }).fitBounds(bounds)
        L.tileLayer("https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",{maxZoom:19, attribution:"© OSM Hot"}).addTo(map)
        // Show loading if simulation is still processing (elevation/flood not yet ready)
        const isProcessing = (simulation as any)?.status === "Running" || !(simulation as any)?.elevation?.stats || !(simulation as any)?.flood?.stats
        if (isProcessing) {
          const loadingDiv = document.createElement("div")
          loadingDiv.innerHTML = '<div style="background: rgba(255,255,255,0.95); padding: 10px 16px; border-radius: 6px; font-size: 13px; color: #1e293b; border: 1px solid #cbd5e1; box-shadow: 0 2px 8px rgba(0,0,0,0.15); text-align: center;">Processing elevation & flood...<br><span style="font-size: 11px; color: #64748b;">This may take a few seconds for new simulations</span><br><span style="display:inline-block; width:16px; height:16px; border:2px solid #3b82f6; border-top-color: transparent; border-radius:50%; animation: spin 1s linear infinite; margin-top: 6px;"></span></div><style>@keyframes spin { to { transform: rotate(360deg); } }</style>'
          loadingDiv.style.position = "absolute"
          loadingDiv.style.top = "50%"
          loadingDiv.style.left = "50%"
          loadingDiv.style.transform = "translate(-50%, -50%)"
          loadingDiv.style.zIndex = "1000"
          loadingDiv.id = "processing-overlay"
          divRef.current.appendChild(loadingDiv)
          // Poll until ready
          const poll = setInterval(async () => {
            try {
              const res = await fetch(`/api/simulations/${simulation.id}`)
              const sim = await res.json()
              if (sim.elevation?.stats && sim.flood?.stats) {
                clearInterval(poll)
                const el = document.getElementById("processing-overlay")
                if (el) el.remove()
                // Optionally reload the map overlays
                try {
                  const newElevUri = sim.elevation.elevationUri + `?v=${sim.elevation.stats.mean}`
                  if (layerRefs.current.terrainOverlay) {
                    layerRefs.current.terrainOverlay.setUrl(newElevUri)
                    if (layers?.terrain?.visible) layerRefs.current.terrainOverlay.addTo(map)
                  }
                  const newFloodUri = sim.flood.floodUri.split("?")[0] + `?time=${time}&v=${sim.flood.stats.maxDepth}`
                  if (layerRefs.current.floodOverlay) {
                    layerRefs.current.floodOverlay.setUrl(newFloodUri)
                  }
                } catch {}
              }
            } catch {}
          }, 1500)
          setTimeout(() => clearInterval(poll), 30000)
        }
        // flood overlay from TIF per simulation + time — Flood depth §9
        const timeIdx = time ?? 0
        const floodVersion = (simulation as any)?.flood?.stats?.maxDepth ?? (simulation as any)?.metadata?.updated ?? Date.now()
        const baseFloodUri = (simulation as any)?.flood?.floodUri ? (simulation as any).flood.floodUri.split("?")[0] : `/api/simulations/${simulation.id}/flood`
        const floodUri = `${baseFloodUri}?time=${timeIdx}&v=${encodeURIComponent(String(floodVersion))}`
        try {
          try { fetch(floodUri).catch(()=>{}) } catch {}
          const floodOverlay = (L as any).imageOverlay(floodUri, bounds, {opacity: layers?.depth?.opacity ?? 0.6})
          if (layers?.depth?.visible ?? true) floodOverlay.addTo(map)
          layerRefs.current.floodOverlay = floodOverlay
        } catch {
          // fallback to mock if fetch fails (offline) per prd §21
          const canvas = document.createElement("canvas"); canvas.width=180; canvas.height=180
          const ctx = canvas.getContext("2d")
          if (ctx) {
            const img = ctx.createImageData(180,180)
            for(let i=0;i<180*180;i++){ const d = Math.random()*0.3; const c = d>0.05? [56,189,248,180]:[0,0,0,0]; img.data[i*4]=c[0]; img.data[i*4+1]=c[1]; img.data[i*4+2]=c[2]; img.data[i*4+3]=c[3]}
            ctx.putImageData(img,0,0)
            const overlay = (L as any).imageOverlay(canvas.toDataURL(), bounds, {opacity: layers?.depth?.opacity ?? 0.6})
            if (layers?.depth?.visible ?? true) overlay.addTo(map)
            layerRefs.current.floodOverlay = overlay
          }
        }
        // terrain/elevation overlay — hypsometric from TIF per simulation §9
        // Fetch stored hypsometric PNG for this simulation with cache busting via updated timestamp
        const elevVersion = (simulation as any)?.elevation?.stats?.mean ?? (simulation as any)?.metadata?.updated ?? Date.now()
        const baseElevUri = (simulation as any)?.elevation?.elevationUri ?? `/api/simulations/${simulation.id}/elevation`
        const elevUri = `${baseElevUri}${baseElevUri.includes("?") ? "&" : "?"}v=${encodeURIComponent(String(elevVersion))}`
        try {
          const terrainOverlay = (L as any).imageOverlay(elevUri, bounds, {opacity: layers?.terrain?.opacity ?? 0.7})
          // Only add if terrain visible, but keep reference for toggling
          if (layers?.terrain?.visible) terrainOverlay.addTo(map)
          layerRefs.current.terrainOverlay = terrainOverlay
          // Also handle error fallback: if image fails to load, keep placeholder
          // Add error handling for offline: fetch will 404, but overlay will still try
        } catch {
          // fallback to mock if fetch fails (offline)
          const terrainCanvas = document.createElement("canvas"); terrainCanvas.width=180; terrainCanvas.height=180
          const tctx = terrainCanvas.getContext("2d")
          if (tctx) {
            const timg = tctx.createImageData(180,180)
            for(let y=0;y<180;y++){
              for(let x=0;x<180;x++){
                const i=(y*180+x)*4
                const elev = 4 + (x/180)*20 + (y/180)*10 + Math.random()*5
                const norm = Math.min(1, Math.max(0, (elev-4)/20))
                const r = 160 - norm*60, g = 120 + norm*80, b = 60 + norm*20
                timg.data[i]=r; timg.data[i+1]=g; timg.data[i+2]=b; timg.data[i+3]=180
              }
            }
            tctx.putImageData(timg,0,0)
            const terrainOverlay2 = (L as any).imageOverlay(terrainCanvas.toDataURL(), bounds, {opacity: layers?.terrain?.opacity ?? 0.7})
            if (layers?.terrain?.visible) terrainOverlay2.addTo(map)
            layerRefs.current.terrainOverlay = terrainOverlay2
          }
        }
        // create layer groups — separate for each layer type per §9
        layerRefs.current.drainsGroup = (L as any).layerGroup() // Drains: all 10257 from drains.kml
        layerRefs.current.hydroDrainsGroup = (L as any).layerGroup() // Hydro: micro+macro 52
        layerRefs.current.hydroWaterbodyLayers = (L as any).layerGroup() // Hydro waterbodies sample 50
        layerRefs.current.waterGroup = (L as any).layerGroup() // Water: chennai_waterbodies 4086
        layerRefs.current.riverLayers = (L as any).layerGroup()
        layerRefs.current.waterbodyLayers = layerRefs.current.hydroWaterbodyLayers // alias for backward compat
        layerRefs.current.drainLayers = layerRefs.current.drainsGroup // alias
        layerRefs.current.infraGroup = (L as any).layerGroup()
        // add groups to map initially based on visibility
        if (layers?.drainage?.visible ?? true) {
          layerRefs.current.drainsGroup.addTo(map)
        }
        if (layers?.hydro?.visible ?? true) {
          layerRefs.current.hydroDrainsGroup.addTo(map)
          layerRefs.current.hydroWaterbodyLayers.addTo(map)
          layerRefs.current.riverLayers.addTo(map)
        }
        if (layers?.water?.visible ?? true) {
          layerRefs.current.waterGroup.addTo(map)
        }
        const terrainVisibleInit = layers?.terrain?.visible ?? false
        if (terrainVisibleInit && layerRefs.current.terrainOverlay) {
          // already added above if visible
        }
        map.on("click", (e:any)=>{
          const lat=e.latlng.lat, lon=e.latlng.lng
          fetch(`/api/simulations/${simulation.id}/point?lat=${lat}&lon=${lon}&time=${time}`).then(r=>r.json()).then(j=>onPointSelect?.(j)).catch(()=>onPointSelect?.({lat,lon, elevation:15.5, floodDepth:0.42, velocity:0.3}))
        })
        mapRef.current = map
        // Drains layer: all drains from drains.kml 10257 — for Drainage group
        fetch("/api/layers/drains?limit=10257").then(r=>r.json()).then(g=>{
          try{
            const feats = g.features || []
            feats.forEach((f:any)=>{
              let latlngs: any[] = []
              if (f.geometry.type==="LineString") latlngs = f.geometry.coordinates.map((c:any)=>[c[1], c[0]])
              else if (f.geometry.type==="MultiLineString") latlngs = f.geometry.coordinates[0].map((c:any)=>[c[1], c[0]])
              if(latlngs.length) (L as any).polyline(latlngs, {color:"#6366f1", weight:1.5, opacity:0.6}).addTo(layerRefs.current.drainsGroup)
            })
          }catch{}
        }).catch(()=>{})
        // Hydro layer: micro+macro 52 drains→waterbodies — for Hydro group
        fetch("/api/hydro/graph").then(r=>r.json()).then(g=>{
          try{
            const drains = g.drains?.features || []
            const wbs = g.waterbodies?.features || []
            // hydro waterbodies (small sample) — add to hydroWaterbody group
            wbs.slice(0,50).forEach((f:any)=>{
              const latlngs = f.geometry.coordinates[0].map((c:any)=>[c[1], c[0]])
              const poly = (L as any).polygon(latlngs, {color:"#3b82f6", weight:1, fillColor:"#3b82f6", fillOpacity:0.2})
              poly.on("click", ()=> onWaterbodySelect?.(String(f.properties.id)))
              poly.addTo(layerRefs.current.hydroWaterbodyLayers)
            })
            // hydro drains with arrow color by target — add to hydroDrains group
            drains.slice(0,100).forEach((f:any)=>{
              const target = f.properties.target || "sea"
              const color = drainColor(target)
              let latlngs: any[] = []
              if (f.geometry.type==="LineString") latlngs = f.geometry.coordinates.map((c:any)=>[c[1], c[0]])
              else if (f.geometry.type==="MultiLineString") latlngs = f.geometry.coordinates[0].map((c:any)=>[c[1], c[0]])
              if(latlngs.length) (L as any).polyline(latlngs, {color, weight:2, opacity:0.7}).addTo(layerRefs.current.hydroDrainsGroup)
            })
          }catch{}
        }).catch(()=>{})
        // Water layer: all waterbodies 4086 from chennai_waterbodies.kml — for Water group
        fetch("/api/layers/waterbodies?limit=4086").then(r=>r.json()).then(g=>{
          try{
            const feats = g.features || []
            feats.forEach((f:any)=>{
              let latlngs: any[] = []
              // waterbodies are Polygon
              if (f.geometry.type==="Polygon") latlngs = f.geometry.coordinates[0].map((c:any)=>[c[1], c[0]])
              else if (f.geometry.type==="MultiPolygon") latlngs = f.geometry.coordinates[0][0].map((c:any)=>[c[1], c[0]])
              if(latlngs.length) (L as any).polygon(latlngs, {color:"#0ea5e9", weight:1, fillColor:"#0ea5e9", fillOpacity:0.15}).addTo(layerRefs.current.waterGroup)
            })
          }catch{}
        }).catch(()=>{})
        // critical: invalidateSize after container has size (flex layout)
        const invalidate = () => { try { map.invalidateSize() } catch {} }
        setTimeout(invalidate, 100)
        setTimeout(invalidate, 500)
        setTimeout(invalidate, 1000)
        // also on window resize
        window.addEventListener("resize", invalidate)
        // use ResizeObserver for container
        const RO = (window as any).ResizeObserver
        const ro = RO ? new RO(()=>invalidate()) : null
        if (ro && divRef.current) ro.observe(divRef.current)
      } catch (err) {
        console.warn("Map init skipped", err)
      }
    }
    init()
    return ()=>{ 
      cancelled = true; 
      if (map) { try{ map.remove() }catch{} }
      // also cleanup mapRef if this is unmount
      if (mapRef.current === map) {
        mapRef.current = null
        layerRefs.current = {}
      }
    }
  },[simulation?.id])

  // react to layers visibility/opacity and time
  useEffect(()=>{
    if (!mapRef.current) return
    const map = mapRef.current
    const L = (window as any).L
    if (!L || !layerRefs.current) return
    // toggle flood depth overlay + update URL per time — §9 Flood
    if (layerRefs.current.floodOverlay) {
      try {
        const timeIdx2 = time ?? 0
        const floodVersion2 = (simulation as any)?.flood?.stats?.maxDepth ?? (simulation as any)?.metadata?.updated ?? Date.now()
        const newUri = (simulation as any)?.flood?.floodUri ? `${(simulation as any).flood.floodUri.split("?")[0]}?time=${timeIdx2}&v=${encodeURIComponent(String(floodVersion2))}` : `/api/simulations/${simulation.id}/flood?time=${timeIdx2}&v=${encodeURIComponent(String(floodVersion2))}`
        if (layerRefs.current.floodOverlay._url !== newUri) {
          try { fetch(newUri).catch(()=>{}) } catch {}
          try { layerRefs.current.floodOverlay.setUrl(newUri) } catch {}
        }
      } catch {}
      const visible = layers?.depth?.visible ?? true
      const opacity = layers?.depth?.opacity ?? 0.6
      try {
        if (visible) {
          if (!map.hasLayer(layerRefs.current.floodOverlay)) layerRefs.current.floodOverlay.addTo(map)
          layerRefs.current.floodOverlay.setOpacity(opacity)
        } else {
          if (map.hasLayer(layerRefs.current.floodOverlay)) map.removeLayer(layerRefs.current.floodOverlay)
        }
      } catch {}
    }
    // terrain/elevation — §9 Terrain
    if (layerRefs.current.terrainOverlay) {
      const visible = layers?.terrain?.visible ?? false
      const opacity = layers?.terrain?.opacity ?? 0.7
      try {
        if (visible) {
          if (!map.hasLayer(layerRefs.current.terrainOverlay)) layerRefs.current.terrainOverlay.addTo(map)
          layerRefs.current.terrainOverlay.setOpacity(opacity)
        } else {
          if (map.hasLayer(layerRefs.current.terrainOverlay)) map.removeLayer(layerRefs.current.terrainOverlay)
        }
      } catch {}
    }
    // drainage: drainsGroup (10257) — §9 Drainage
    const drainageVisible = layers?.drainage?.visible ?? true
    const drainageOpacity = layers?.drainage?.opacity ?? 0.7
    if (layerRefs.current.drainsGroup) {
      try {
        if (drainageVisible) {
          if (!map.hasLayer(layerRefs.current.drainsGroup)) layerRefs.current.drainsGroup.addTo(map)
          layerRefs.current.drainsGroup.eachLayer((l:any)=>{ if(l.setStyle) l.setStyle({opacity: drainageOpacity}) })
        } else {
          if (map.hasLayer(layerRefs.current.drainsGroup)) map.removeLayer(layerRefs.current.drainsGroup)
        }
      } catch {}
    }
    // keep alias drainLayers in sync
    if (layerRefs.current.drainLayers && layerRefs.current.drainLayers !== layerRefs.current.drainsGroup) {
      try {
        if (drainageVisible) {
          if (!map.hasLayer(layerRefs.current.drainLayers)) layerRefs.current.drainLayers.addTo(map)
        } else {
          if (map.hasLayer(layerRefs.current.drainLayers)) map.removeLayer(layerRefs.current.drainLayers)
        }
      } catch {}
    }
    // hydro: hydroDrains + hydroWaterbody + river flow — §9 Hydro
    const hydroVisible = layers?.hydro?.visible ?? true
    const hydroOpacity = layers?.hydro?.opacity ?? 0.7
    ;["hydroDrainsGroup","hydroWaterbodyLayers","riverLayers","waterbodyLayers"].forEach(key=>{
      const group = layerRefs.current[key]
      if (!group) return
      try {
        if (hydroVisible) {
          if (!map.hasLayer(group)) group.addTo(map)
          group.eachLayer((l:any)=>{
            if (l.setStyle) {
              if (l.options.fillOpacity !== undefined) l.setStyle({fillOpacity: hydroOpacity*0.3, opacity: hydroOpacity})
              else l.setStyle({opacity: hydroOpacity})
            }
          })
        } else {
          if (map.hasLayer(group)) map.removeLayer(group)
        }
      } catch {}
    })
    // water group (rivers/canals/sea) — for now tied to hydro, but could be separate
    const waterVisible = layers?.water?.visible ?? true
    if (layerRefs.current.waterGroup) {
      try {
        if (waterVisible && hydroVisible) {
          if (!map.hasLayer(layerRefs.current.waterGroup)) layerRefs.current.waterGroup.addTo(map)
        } else {
          if (map.hasLayer(layerRefs.current.waterGroup)) map.removeLayer(layerRefs.current.waterGroup)
        }
      } catch {}
    }
    // infra (roads etc.) — placeholder, no actual road layer yet, but handle
    const infraVisible = layers?.infra?.visible ?? true
    if (layerRefs.current.infraGroup) {
      try {
        if (infraVisible) {
          if (!map.hasLayer(layerRefs.current.infraGroup)) layerRefs.current.infraGroup.addTo(map)
        } else {
          if (map.hasLayer(layerRefs.current.infraGroup)) map.removeLayer(layerRefs.current.infraGroup)
        }
      } catch {}
    }
  },[layers, time])
  return <div ref={divRef} className="w-full h-full min-h-[500px] bg-slate-900 leaflet-container" data-testid="map-view" style={{width:"100%", height:"100%", minHeight:"500px"}} />
}
