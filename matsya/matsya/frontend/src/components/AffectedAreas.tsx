
import { useEffect, useState } from "react"
import { AlertTriangle, Navigation, MapPin } from "lucide-react"

export default function AffectedAreas({ simulation }: any){
  const [areas,setAreas]=useState<any[]>([])

  useEffect(()=>{
    if(!simulation?.id) return
    fetch(`/api/simulations/${simulation.id}/affected-areas`).then(r=>r.json()).then(setAreas).catch(()=>{
      // honest empty state: never fabricate hotspot names when data is unavailable
      setAreas([])
    })
  },[simulation])

  const flyToArea = (a: any) => {
    window.dispatchEvent(new CustomEvent("matsya-flyto",{detail:{lat:a.lat,lon:a.lon}}))
  }

  return (
    <div className="p-3.5 border-b border-slate-800/80 bg-slate-950/60">
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-xs uppercase text-slate-400 font-mono font-semibold tracking-wider flex items-center gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
          Critical Flood Hotspots
        </h3>
        <span className="text-[10px] text-slate-500 font-mono">{areas.length} Inundated Zones</span>
      </div>
      {/* Description subtitle - Commented out to declutter risk zones tab */}
      {/* <p className="text-[11px] text-slate-400 mb-3 font-mono">Ranked by peak flood inundation depth</p> */}

      <ol className="space-y-2">
        {areas.map((a:any)=>{
          const isExtreme = a.maxDepth >= 1.0
          const badgeClass = isExtreme 
            ? "bg-rose-500/10 text-rose-400 border-rose-500/30" 
            : "bg-amber-500/10 text-amber-400 border-amber-500/30"

          return (
            <li 
              key={a.name} 
              className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-cyan-500/50 hover:bg-slate-900 cursor-pointer transition flex items-center justify-between group"
              onClick={() => flyToArea(a)}
            >
              <div>
                <div className="font-semibold text-xs text-white group-hover:text-cyan-300 transition flex items-center gap-1.5">
                  <MapPin className="w-3 h-3 text-cyan-400" />
                  {a.rank}. {a.name}
                </div>
                <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                  Max depth: {a.maxDepth} m • Duration: {a.duration}
                </div>
              </div>

              <div className="flex items-center gap-2">
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono border ${badgeClass}`}>
                  {a.maxDepth}m
                </span>
                <Navigation className="w-3.5 h-3.5 text-slate-600 group-hover:text-cyan-400 transition" />
              </div>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
