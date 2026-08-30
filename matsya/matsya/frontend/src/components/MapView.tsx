import { useEffect, useRef } from "react"
import type { Simulation } from "../types/simulation"
import "leaflet/dist/leaflet.css"

export default function MapView({ simulation, layers, time, onPointSelect }: any) {
  const divRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<any>(null)
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
          ;(L as any).imageOverlay(canvas.toDataURL(), bounds, {opacity:0.6}).addTo(map)
        }
        map.on("click", (e:any)=>{
          const lat=e.latlng.lat, lon=e.latlng.lng
          fetch(`/api/simulations/${simulation.id}/point?lat=${lat}&lon=${lon}&time=${time}`).then(r=>r.json()).then(j=>onPointSelect?.(j)).catch(()=>onPointSelect?.({lat,lon, elevation:15.5, floodDepth:0.42, velocity:0.3}))
        })
        mapRef.current = map
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
  // react to time/layers without recreating map
  useEffect(()=>{
    if (!mapRef.current) return
    // stub: could update overlay opacity etc. based on layers/time
  },[time,layers])
  return <div ref={divRef} className="w-full h-full min-h-[500px] bg-slate-900 leaflet-container" data-testid="map-view" style={{width:"100%", height:"100%", minHeight:"500px"}} />
}
