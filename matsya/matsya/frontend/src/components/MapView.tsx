import { useEffect, useRef, useState } from "react"
import type { Simulation } from "../types/simulation"
import { ZONE_PALETTE } from "../types/simulation"
import "leaflet/dist/leaflet.css"
import { drainColor } from "../utils/hydro"

const BASEMAP_TILES: Record<string, { url: string, attr: string }> = {
  dark: {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    attr: "&copy; Esri &copy; OpenStreetMap"
  },
  hot: {
    url: "https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
    attr: "&copy; OpenStreetMap contributors, Humanitarian OpenStreetMap Team"
  },
  satellite: {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr: "&copy; Esri World Imagery"
  }
}

export default function MapView({ simulation, layers, time, onPointSelect, onWaterbodySelect, route, floodNonce }: any) {
  const divRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<any>(null)
  const layerRefs = useRef<any>({})
  const [basemap, setBasemap] = useState<"dark" | "hot" | "satellite">("hot")
  const [dataWarn, setDataWarn] = useState<string | null>(null)
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
        const bConfig = BASEMAP_TILES[basemap] || BASEMAP_TILES.dark
        const baseLayer = L.tileLayer(bConfig.url, { maxZoom: 19, attribution: bConfig.attr }).addTo(map)
        layerRefs.current.baseLayer = baseLayer
        // Show loading only while data is still pending AND the backend has not
        // settled. A Completed/Error sim with partial data (e.g. elevation
        // generation failed) must never strand the spinner: dismiss + warn.
        const hasData = !!(simulation as any)?.elevation?.stats && !!(simulation as any)?.flood?.stats
        const isSettled = ["Completed", "Error"].includes((simulation as any)?.status)
        const needsProcessing = !hasData && !isSettled
        const dismissOverlay = (warn: string | null) => {
          try {
            const el = document.getElementById("processing-overlay")
            if (el) el.remove()
          } catch {}
          if (warn) setDataWarn(warn)
        }
        if (needsProcessing) {
          const loadingDiv = document.createElement("div")
          loadingDiv.innerHTML = '<div style="background: rgba(11,15,23,0.95); padding: 10px 16px; border-radius: 12px; font-size: 13px; color: #f1f5f9; border: 1px solid #334155; box-shadow: 0 8px 24px rgba(0,0,0,0.5); text-align: center; font-family: monospace;">Processing elevation & flood...<br><span style="font-size: 11px; color: #94a3b8;">This may take a few seconds for new simulations</span><br><span style="display:inline-block; width:16px; height:16px; border:2px solid #22d3ee; border-top-color: transparent; border-radius:50%; animation: spin 1s linear infinite; margin-top: 6px;"></span></div><style>@keyframes spin { to { transform: rotate(360deg); } }</style>'
          loadingDiv.style.position = "absolute"
          loadingDiv.style.top = "50%"
          loadingDiv.style.left = "50%"
          loadingDiv.style.transform = "translate(-50%, -50%)"
          loadingDiv.style.zIndex = "1000"
          loadingDiv.id = "processing-overlay"
          divRef.current.appendChild(loadingDiv)
          // Poll until ready or settled — never strand the spinner
          const poll = setInterval(async () => {
            try {
              const res = await fetch(`/api/simulations/${simulation.id}`)
              const sim = await res.json()
              const freshHasData = !!(sim.elevation?.stats && sim.flood?.stats)
              const freshSettled = ["Completed", "Error"].includes(sim.status)
              if (freshHasData || freshSettled) {
                clearInterval(poll)
                const missing = [!sim.elevation?.stats && "elevation", !sim.flood?.stats && "flood"].filter(Boolean)
                dismissOverlay(missing.length ? `${(missing as string[]).join(" + ")} unavailable — showing available layers` : null)
                // Optionally reload the map overlays
                try {
                  const newElevUri = sim.elevation.elevationUri + `?v=${sim.elevation.stats.mean}`
                  if (layerRefs.current.terrainOverlay) {
                    layerRefs.current.terrainOverlay.setUrl(newElevUri)
                    if (layers?.terrain?.visible) layerRefs.current.terrainOverlay.addTo(map)
                  }
                  const floodPalette0 = (layers as any)?.depth?.palette ?? "blue"
                  const newFloodUri = sim.flood.floodUri.split("?")[0] + `?time=${time}&palette=${floodPalette0}&cv=${floodNonce ?? 0}&v=${sim.flood.stats.maxDepth}`
                  if (layerRefs.current.floodOverlay) {
                    layerRefs.current.floodOverlay.setUrl(newFloodUri)
                  }
                } catch {}
              }
            } catch {}
          }, 1500)
          setTimeout(() => {
            clearInterval(poll)
            // only warn if the overlay actually survived (clean dismisses no-op)
            try {
              if (document.getElementById("processing-overlay")) dismissOverlay("Still processing — showing available layers")
            } catch {}
          }, 30000)
        }
        // flood overlay from TIF per simulation + time — Flood depth §9
        const timeIdx = time ?? 0
        const floodVersion = (simulation as any)?.flood?.stats?.maxDepth ?? (simulation as any)?.metadata?.updated ?? Date.now()
        const floodPalette = (layers as any)?.depth?.palette ?? "blue"
        const baseFloodUri = (simulation as any)?.flood?.floodUri ? (simulation as any).flood.floodUri.split("?")[0] : `/api/simulations/${simulation.id}/flood`
        const floodUri = `${baseFloodUri}?time=${timeIdx}&palette=${floodPalette}&cv=${floodNonce ?? 0}&v=${encodeURIComponent(String(floodVersion))}`
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
        layerRefs.current.routeGroup = (L as any).layerGroup().addTo(map) // Safe Route polylines
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

        // Domain AOI square boundary outline
        try {
          const aoiBoundary = (L as any).rectangle(bounds, {
            color: "#06b6d4",
            weight: 1.5,
            fill: false,
            dashArray: "6, 6",
            interactive: false
          }).addTo(map)
          layerRefs.current.aoiBoundary = aoiBoundary
        } catch {}
        // Rainfall zones overlay — spatial rain input footprints, palette per index
        try {
          const zones = (simulation as any)?.rainfall?.zones
          if (Array.isArray(zones) && zones.length) {
            const zg = (L as any).layerGroup()
            zones.slice(0, 12).forEach((z: any, i: number) => {
              try {
                const ring = z?.polygon?.coordinates?.[0]
                if (!Array.isArray(ring) || ring.length < 4) return
                const latlngs = ring.map((c: any) => [c[1], c[0]])
                const color = ZONE_PALETTE[i % ZONE_PALETTE.length]
                // Live Chennai fine grid (12×12) drives the flood in blending — don't paint its input tint at all
                if ((simulation as any)?.live === true) return
                const val = (z as any).amount ?? (z as any).maxRain
                const label = val != null ? `${val}` : "—"
                const poly = (L as any).polygon(latlngs, {
                  color, weight: 2, dashArray: "4, 3",
                  fillColor: color, fillOpacity: 0.12,
                })
                poly.bindTooltip(`${z.id ?? "z" + (i + 1)}: ${label} ${z.unit === "total" ? "mm total" : "mm/hr"}`, { sticky: true })
                poly.addTo(zg)
              } catch {}
            })
            zg.addTo(map)
            layerRefs.current.zoneLayers = zg
          }
        } catch {}
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
        const floodPalette2 = (layers as any)?.depth?.palette ?? "blue"
        const newUri = (simulation as any)?.flood?.floodUri ? `${(simulation as any).flood.floodUri.split("?")[0]}?time=${timeIdx2}&palette=${floodPalette2}&cv=${floodNonce ?? 0}&v=${encodeURIComponent(String(floodVersion2))}` : `/api/simulations/${simulation.id}/flood?time=${timeIdx2}&palette=${floodPalette2}&cv=${floodNonce ?? 0}&v=${encodeURIComponent(String(floodVersion2))}`
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
  },[layers, time, floodNonce])

  // Safe Route overlay — draws selected fastest/safest polylines + destination
  useEffect(() => {
    if (!mapRef.current) return
    const L = (window as any).L
    if (!L || !layerRefs.current.routeGroup) return
    const group = layerRefs.current.routeGroup
    try { group.clearLayers() } catch {}
    if (!route) return
    try {
      const map = mapRef.current
      const samePath = route.fastest && route.safest &&
        JSON.stringify(route.fastest) === JSON.stringify(route.safest)
      if (route.fastest && !samePath && route.fastest.length > 1) {
        ;(L as any).polyline(route.fastest, { color: "#fbbf24", weight: 3, opacity: 0.85, dashArray: "8, 6" })
          .bindTooltip("Fastest route", { sticky: true }).addTo(group)
      }
      if (route.safest && route.safest.length > 1) {
        ;(L as any).polyline(route.safest, { color: "#22d3ee", weight: 4, opacity: 0.9 })
          .bindTooltip("Safest route", { sticky: true }).addTo(group)
      }
      if (route.dest && isFinite(route.dest.lat) && isFinite(route.dest.lon)) {
        ;(L as any).circleMarker([route.dest.lat, route.dest.lon], {
          radius: 7, color: "#34d399", weight: 2, fillColor: "#34d399", fillOpacity: 0.6,
        }).bindTooltip("Safe space", { sticky: true }).addTo(group)
      }
      try {
        const drawn = group.getLayers()
        if (drawn.length) map.fitBounds(group.getBounds().pad(0.2))
      } catch {}
    } catch {}
  }, [route])

  // Handle basemap tile layer switching
  useEffect(() => {
    if (!mapRef.current) return
    const L = (window as any).L
    if (!L) return
    try {
      if (layerRefs.current.baseLayer) {
        mapRef.current.removeLayer(layerRefs.current.baseLayer)
      }
      const bConfig = BASEMAP_TILES[basemap] || BASEMAP_TILES.dark
      const newBaseLayer = L.tileLayer(bConfig.url, { maxZoom: 19, attribution: bConfig.attr }).addTo(mapRef.current)
      newBaseLayer.bringToBack?.()
      layerRefs.current.baseLayer = newBaseLayer
    } catch {}
  }, [basemap])

  return (
    <div className="relative w-full h-full min-h-[500px]">
      <div
        ref={divRef}
        className="w-full h-full min-h-[500px] bg-[#070A0F] leaflet-container"
        data-testid="map-view"
        style={{width:"100%", height:"100%", minHeight:"500px"}}
      />

      {/* Non-blocking data-availability warning (never a stranded spinner) */}
      {dataWarn && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[500] flex items-center gap-2 px-3 py-1.5 rounded-xl glass-panel border border-amber-500/40 shadow-2xl text-[11px] font-mono text-amber-200">
          <span>{dataWarn}</span>
          <button
            type="button"
            aria-label="Dismiss data warning"
            onClick={() => setDataWarn(null)}
            className="px-1.5 rounded-md text-amber-300 hover:text-white hover:bg-slate-800/80 transition"
          >
            ×
          </button>
        </div>
      )}

      {/* Floating Basemap Selector */}
      <div className="absolute bottom-4 left-4 z-[400] flex items-center gap-1 p-1 rounded-xl glass-panel border border-slate-700/80 shadow-2xl text-[11px] font-mono">
        <span className="text-[10px] text-slate-400 px-2 uppercase font-semibold">Basemap</span>
        {(["dark", "hot", "satellite"] as const).map(b => (
          <button
            key={b}
            onClick={() => setBasemap(b)}
            className={`px-2.5 py-1 rounded-lg transition ${
              basemap === b
                ? "bg-cyan-500/20 text-cyan-300 font-bold border border-cyan-500/40 shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            {b === "dark" ? "Dark" : b === "hot" ? "HOT" : "Satellite"}
          </button>
        ))}
      </div>
    </div>
  )
}
