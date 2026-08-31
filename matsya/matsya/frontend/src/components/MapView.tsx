import { useEffect, useRef } from "react"
import type { Simulation } from "../types/simulation"
import "leaflet/dist/leaflet.css"
import { drainColor } from "../utils/hydro"

export default function MapView({ simulation, layers, time, onPointSelect, onWaterbodySelect }: any) {
  const divRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<any>(null)
  const layerRefs = useRef<any>({})
  useEffect(()=>{
    if (!divRef.current) return
    if (mapRef.current) {
      // update existing map bounds if simulation changes
      const bbox = simulation?.area?.bbox ?? [80.15,13.08,80.20,13.13]
      const bounds: any = [[bbox[1], bbox[0]], [bbox[3], bbox[2]]]
      try { mapRef.current.fitBounds(bounds) } catch {}
      return
    }
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
        // flood overlay mock 180x180
        const canvas = document.createElement("canvas"); canvas.width=180; canvas.height=180
        const ctx = canvas.getContext("2d")
        if (ctx) {
          const img = ctx.createImageData(180,180)
          for(let i=0;i<180*180;i++){ const d = Math.random()*0.3; const c = d>0.05? [56,189,248,180]:[0,0,0,0]; img.data[i*4]=c[0]; img.data[i*4+1]=c[1]; img.data[i*4+2]=c[2]; img.data[i*4+3]=c[3]}
          ctx.putImageData(img,0,0)
          const overlay = (L as any).imageOverlay(canvas.toDataURL(), bounds, {opacity: layers?.depth?.opacity ?? 0.6})
          // respect initial visibility
          if (layers?.depth?.visible ?? true) overlay.addTo(map)
          layerRefs.current.floodOverlay = overlay
        }
        // create layer groups for hydro
        layerRefs.current.drainLayers = (L as any).layerGroup()
        layerRefs.current.waterbodyLayers = (L as any).layerGroup()
        layerRefs.current.riverLayers = (L as any).layerGroup()
        layerRefs.current.waterGroup = (L as any).layerGroup()
        layerRefs.current.infraGroup = (L as any).layerGroup()
        // add groups to map initially based on visibility
        if (layers?.hydro?.visible ?? true) {
          layerRefs.current.drainLayers.addTo(map)
          layerRefs.current.waterbodyLayers.addTo(map)
          layerRefs.current.riverLayers.addTo(map)
        }
        map.on("click", (e:any)=>{
          const lat=e.latlng.lat, lon=e.latlng.lng
          fetch(`/api/simulations/${simulation.id}/point?lat=${lat}&lon=${lon}&time=${time}`).then(r=>r.json()).then(j=>onPointSelect?.(j)).catch(()=>onPointSelect?.({lat,lon, elevation:15.5, floodDepth:0.42, velocity:0.3}))
        })
        mapRef.current = map
        // hydro: fetch and draw drains->waterbodies
        fetch("/api/hydro/graph").then(r=>r.json()).then(g=>{
          try{
            const drains = g.drains?.features || []
            const wbs = g.waterbodies?.features || []
            // waterbodies polygons — add to waterbodyLayers group
            wbs.slice(0,50).forEach((f:any)=>{
              const latlngs = f.geometry.coordinates[0].map((c:any)=>[c[1], c[0]])
              const poly = (L as any).polygon(latlngs, {color:"#3b82f6", weight:1, fillColor:"#3b82f6", fillOpacity:0.2})
              poly.on("click", ()=> onWaterbodySelect?.(String(f.properties.id)))
              poly.addTo(layerRefs.current.waterbodyLayers)
            })
            // drains with arrow color by target — add to drainLayers group
            drains.slice(0,100).forEach((f:any)=>{
              const target = f.properties.target || "sea"
              const color = drainColor(target)
              let latlngs: any[] = []
              if (f.geometry.type==="LineString") latlngs = f.geometry.coordinates.map((c:any)=>[c[1], c[0]])
              else if (f.geometry.type==="MultiLineString") latlngs = f.geometry.coordinates[0].map((c:any)=>[c[1], c[0]])
              if(latlngs.length) (L as any).polyline(latlngs, {color, weight:2, opacity:0.7}).addTo(layerRefs.current.drainLayers)
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
    return ()=>{ cancelled = true; if (map) { try{ map.remove() }catch{} } }
  },[simulation])

  // react to layers visibility/opacity and time
  useEffect(()=>{
    if (!mapRef.current) return
    const map = mapRef.current
    const L = (window as any).L
    if (!L || !layerRefs.current) return
    // toggle flood depth canvas overlay
    if (layerRefs.current.floodOverlay) {
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
    // hydro layers: drains and waterbodies
    const hydroVisible = layers?.hydro?.visible ?? true
    const hydroOpacity = layers?.hydro?.opacity ?? 0.7
    ;["drainLayers","waterbodyLayers","riverLayers"].forEach(key=>{
      const group = layerRefs.current[key]
      if (!group) return
      try {
        if (hydroVisible) {
          if (!map.hasLayer(group)) group.addTo(map)
          // update opacity for polylines/polygons in group
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
