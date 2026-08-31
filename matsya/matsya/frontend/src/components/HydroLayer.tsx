import { useEffect, useState } from "react"

export default function HydroLayer({ simId }: { simId?: string }) {
  const [summary, setSummary] = useState<any>(null)
  const [graph, setGraph] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  useEffect(()=>{
    let alive=true
    async function fetchAll(){
      try{
        const [s,g]=await Promise.all([
          fetch("/api/hydro/summary").then(r=>r.json()),
          fetch("/api/hydro/graph").then(r=>r.json())
        ])
        if(alive){ setSummary(s); setGraph(g) }
      }catch(e){ if(alive) setSummary({error:String(e)}) }
      finally{ if(alive) setLoading(false) }
    }
    fetchAll()
    return ()=>{alive=false}
  },[simId])
  if(loading) return <div className="p-2 text-xs">Loading hydro...</div>
  if(!summary) return <div className="p-2 text-xs">No hydro data</div>
  return (
    <div className="p-2 border rounded bg-blue-50 text-xs space-y-1">
      <h4 className="font-semibold">Hydro: drains → water bodies §6</h4>
      <div> Drains: {summary.drains} • Waterbodies: {summary.waterbodies} • Rivers: {summary.rivers} </div>
      <div className="flex gap-2">
        <span className="px-2 py-0.5 bg-blue-600 text-white rounded">snapped {summary.snapped_to_waterbody}</span>
        <span className="px-2 py-0.5 bg-sky-500 text-white rounded">river {summary.to_river}</span>
        <span className="px-2 py-0.5 bg-cyan-500 text-white rounded">sea {summary.to_sea}</span>
      </div>
      {graph && <div className="text-[11px] text-slate-600">Graph: {graph.drains?.features?.length ?? 0} drains with target, {graph.waterbodies?.features?.length ?? 0} waterbodies (sample) — drains end with arrow to blue polygon, not vanishing.</div>}
      <div className="text-[11px] text-slate-500">Legend: blue solid → waterbody, sky → river, cyan → sea. Waterbodies fill opacity by stage (0→crest light, crest+1m dark) per §9.</div>
    </div>
  )
}
