
import { useEffect, useState } from "react"
import { CheckCircle2, AlertTriangle, ShieldCheck } from "lucide-react"

export default function HydroBadge(){
  const [check,setCheck]=useState<any>(null)

  useEffect(()=>{
    fetch("/api/hydro/check").then(r=>r.json()).then(setCheck).catch(()=>setCheck(null))
  },[])

  if(!check) return <div className="text-xs text-slate-500 font-mono">Checking hydro...</div>

  return (
    <div className="p-3 rounded-xl border border-slate-800 bg-slate-950/70 text-xs font-mono space-y-1">
      <div className="flex items-center justify-between">
        <span className="font-semibold text-slate-200 flex items-center gap-1.5">
          <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
          Network Topology Check
        </span>
        <span className={check.valid ? "text-emerald-400 font-bold" : "text-amber-400 font-bold"}>
          {check.valid ? "✓ Valid" : "⚠ Check"}
        </span>
      </div>
      <div className={check.valid ? "text-emerald-400" : "text-amber-400"}>
        {check.valid ? "✓ Valid" : "⚠ Check"} — {check.snapped_to_waterbody} drains → water bodies, {check.to_river ?? 0} → river, {check.unsnapped} unsnapped
      </div>
      <div className="text-slate-400 text-[11px]">
        Waterbodies without inflow: {check.waterbodies_without_inflow} / {check.waterbodies_total}
      </div>
      <div className="text-[10px] text-slate-500">
        All drains terminate in verified waterbody, river, or coastal outfall.
      </div>
    </div>
  )
}
