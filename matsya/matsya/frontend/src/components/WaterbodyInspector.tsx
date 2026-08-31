
import { useState, useEffect } from "react"
export default function WaterbodyInspector({ waterbodyId }: { waterbodyId?: string | null }) {
  const [wb, setWb] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  useEffect(()=>{
    if(!waterbodyId) return
    setLoading(true)
    fetch(`/api/hydro/waterbodies?limit=100`).then(r=>r.json()).then(arr=>{
      const found = arr.find((x:any)=> String(x.id)===String(waterbodyId))
      setWb(found || arr[0])
      setLoading(false)
    }).catch(()=>setLoading(false))
  },[waterbodyId])
  if(!waterbodyId) return <div className="p-2 text-xs text-slate-500">Click waterbody for stage/volume</div>
  if(loading) return <div className="p-2 text-xs">Loading waterbody {waterbodyId}...</div>
  if(!wb) return <div className="p-2 text-xs">Waterbody {waterbodyId} not found</div>
  const head = (wb.stage ?? wb.spill_crest ?? 5) - wb.crest
  return (
    <div className="p-2 border rounded bg-blue-50 text-xs space-y-1">
      <h4 className="font-semibold">Waterbody {wb.id} §16</h4>
      <div>Area: {(wb.area_m2/1000).toFixed(1)}k m² • Stage: {wb.stage?.toFixed?.(2) ?? wb.spill_crest?.toFixed?.(2)} m • Volume: {(wb.area_m2 * Math.max(0, (wb.stage??wb.crest)- (wb.crest-2))/1000).toFixed(1)}k m³</div>
      <div>Crest: {wb.crest?.toFixed?.(2)} m • DEM: {wb.dem_elev?.toFixed?.(2) ?? "—"} m • Head: {head?.toFixed?.(2) ?? "0.00"} m</div>
      <div>Centroid: {wb.centroid?.[0]?.toFixed?.(4)}, {wb.centroid?.[1]?.toFixed?.(4)}</div>
      <div className="text-[11px] text-slate-500">Storage S=Ah, outflow Q=1.7·L·h³/² when stage&gt;crest. Click map waterbody to inspect.</div>
    </div>
  )
}
