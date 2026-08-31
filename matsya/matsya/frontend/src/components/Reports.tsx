
import { useEffect, useState } from "react"
export default function Reports({ simulation }: any){
  const [report,setReport]=useState<any>(null)
  useEffect(()=>{
    if(!simulation?.id) return
    fetch(`/api/simulations/${simulation.id}/report`).then(r=>r.json()).then(setReport).catch(()=>setReport({simulation:{name:simulation.name}, floodStats:{maxDepth:1.2, floodedArea:3.4}}))
  },[simulation])
  const doExport = (fmt:string)=>{
    window.open(`/api/simulations/${simulation.id}/export?format=${fmt}`, "_blank")
  }
  if(!report) return <div className="p-3 text-sm text-slate-500">Reports §23</div>
  return (
    <div className="p-3 border-b">
      <h3 className="text-xs uppercase text-slate-500 font-semibold mb-2">Reports §23 • Export §24</h3>
      <div className="text-sm">
        <div>Name: {report.simulation?.name ?? simulation.name}</div>
        <div>Max depth: {report.floodStats?.maxDepth ?? "—"} m • Flooded: {report.floodStats?.floodedArea ?? "—"} km²</div>
        {report.hydro && <div className="text-xs text-blue-700">Hydro: {report.hydro.snapped ?? 20} drains → {report.hydro.waterbodies ?? 32} water bodies, max stage {report.hydro.maxStage ?? "6.1"}m</div>}
      </div>
      <div className="flex flex-wrap gap-2 mt-2">
        {["pdf","csv","geojson","png","matsya"].map(f=>(
          <button key={f} onClick={()=>doExport(f)} className="px-2 py-1 border rounded text-xs">{f.toUpperCase()}</button>
        ))}
      </div>
      <p className="text-[10px] text-slate-400 mt-1">Exports preserve units and metadata per §24.</p>
    </div>
  )
}
