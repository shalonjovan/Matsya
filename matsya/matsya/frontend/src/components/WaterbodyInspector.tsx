
import { useState, useEffect } from "react"
import { Droplets } from "lucide-react"

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

  if(!waterbodyId) {
    return (
      <div className="p-3.5 border-b border-slate-800/80 text-xs text-slate-400 flex items-center gap-2 bg-slate-950/40">
        <Droplets className="w-4 h-4 text-sky-400" />
        <span>Click waterbody for stage/volume</span>
      </div>
    )
  }

  if(loading) {
    return (
      <div className="p-4 border-b border-slate-800 text-xs text-slate-400 flex items-center gap-2 bg-slate-950/60">
        <div className="w-3.5 h-3.5 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
        <span>Loading waterbody {waterbodyId}...</span>
      </div>
    )
  }

  if(!wb) {
    return (
      <div className="p-3 border-b border-slate-800 text-xs text-slate-500 bg-slate-950/60">
        Waterbody {waterbodyId} not found
      </div>
    )
  }

  const currentStage = wb.stage ?? wb.spill_crest ?? 5
  const crest = wb.crest ?? wb.spill_crest ?? 5
  const head = currentStage - crest
  const areaM2 = wb.area_m2 ?? 50000
  const areaKm2 = (areaM2 / 1000).toFixed(1)
  const volumeK = (areaM2 * Math.max(0, currentStage - (crest - 2)) / 1000).toFixed(1)
  const isSpilling = head > 0

  return (
    <div className="p-3.5 border-b border-slate-800/80 bg-slate-950/60">
      <div className="flex items-center justify-between mb-2.5">
        <h4 className="text-xs uppercase font-mono font-semibold tracking-wider text-sky-400 flex items-center gap-1.5">
          <Droplets className="w-3.5 h-3.5 text-sky-400" />
          Waterbody {wb.id}
        </h4>
        <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${
          isSpilling 
            ? "bg-rose-500/10 text-rose-400 border-rose-500/30" 
            : "bg-cyan-500/10 text-cyan-400 border-cyan-500/30"
        }`}>
          {isSpilling ? "Overtopping / Spill" : "Retaining"}
        </span>
      </div>

      <div className="space-y-2.5 text-xs">
        {/* Core hydraulic metrics */}
        <div className="grid grid-cols-2 gap-2">
          <div className="p-2.5 rounded-xl bg-slate-900/90 border border-slate-800">
            <div className="text-[10px] text-slate-400 mb-0.5">Area & Volume</div>
            <div className="font-mono text-xs text-slate-200">
              Area: {areaKm2}k m²
            </div>
            <div className="font-mono text-xs font-semibold text-cyan-300">
              Volume: {volumeK}k m³
            </div>
          </div>

          <div className="p-2.5 rounded-xl bg-slate-900/90 border border-slate-800">
            <div className="text-[10px] text-slate-400 mb-0.5">Stage & Crest</div>
            <div className="font-mono text-xs text-slate-200">
              Stage: {wb.stage?.toFixed?.(2) ?? wb.spill_crest?.toFixed?.(2)} m
            </div>
            <div className="font-mono text-xs text-slate-400">
              Crest: {crest.toFixed(2)} m • DEM: {wb.dem_elev?.toFixed?.(2) ?? "—"} m
            </div>
          </div>
        </div>

        {/* Head & Centroid banner */}
        <div className="p-2 rounded-lg bg-slate-900/70 border border-slate-800/90 flex items-center justify-between text-[11px] font-mono">
          <span className="text-slate-300">
            Head: <span className={head > 0 ? "text-rose-400 font-bold" : "text-cyan-400 font-bold"}>{head.toFixed(2)} m</span>
          </span>
          <span className="text-slate-500">
            Centroid: {wb.centroid?.[0]?.toFixed?.(4)}, {wb.centroid?.[1]?.toFixed?.(4)}
          </span>
        </div>

        {/* Formula and helper text - Commented out to declutter waterbody inspector */}
        {/*
        <div className="text-[10px] text-slate-400 font-mono">
          Storage S=Ah, outflow Q=1.7·L·h³/² when stage&gt;crest. Click map waterbody to inspect.
        </div>
        */}
      </div>
    </div>
  )
}
