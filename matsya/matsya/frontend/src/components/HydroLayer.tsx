import { useEffect, useState } from "react"
import { Droplets } from "lucide-react"

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

  if(loading) return <div className="p-3 text-xs text-slate-400 font-mono">Loading hydro...</div>
  if(!summary) return <div className="p-3 text-xs text-slate-500 font-mono">No hydro data</div>

  return (
    <div className="p-3.5 border-b border-slate-800/80 bg-slate-950/60">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-xs uppercase font-mono font-semibold tracking-wider text-cyan-400 flex items-center gap-1.5">
          <Droplets className="w-3.5 h-3.5 text-cyan-400" />
          Drainage routing → water bodies & outfalls
        </h4>
        <span className="text-[10px] text-emerald-400 font-mono">Verified</span>
      </div>

      <div className="text-xs text-slate-300 font-mono mb-2">
        Drains: {summary.drains} • Waterbodies: {summary.waterbodies} • Rivers: {summary.rivers}
      </div>

      <div className="flex flex-wrap gap-1.5 mb-2 text-[11px] font-mono">
        <span className="px-2.5 py-1 bg-blue-600/20 text-blue-300 border border-blue-500/30 rounded-lg">
          snapped {summary.snapped_to_waterbody}
        </span>
        <span className="px-2.5 py-1 bg-sky-500/20 text-sky-300 border border-sky-500/30 rounded-lg">
          river {summary.to_river}
        </span>
        <span className="px-2.5 py-1 bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 rounded-lg">
          sea {summary.to_sea}
        </span>
      </div>

      {/* Verbose text descriptions - Commented out to declutter analytical panel */}
      {/*
      {graph && (
        <div className="text-[11px] text-slate-400 font-mono mb-1">
          Graph: {graph.drains?.features?.length ?? 0} drains with target, {graph.waterbodies?.features?.length ?? 0} waterbodies (sample) — drains end with arrow to blue polygon, not vanishing.
        </div>
      )}

      <div className="text-[10px] text-slate-500 font-mono">
        Legend: blue solid → waterbody, sky → river, cyan → sea. Waterbodies dynamic fill opacity indicates reservoir retention stage.
      </div>
      */}
    </div>
  )
}
