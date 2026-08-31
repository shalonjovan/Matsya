
import { useEffect, useState } from "react"
export default function HydroBadge(){
  const [check,setCheck]=useState<any>(null)
  useEffect(()=>{
    fetch("/api/hydro/check").then(r=>r.json()).then(setCheck).catch(()=>setCheck(null))
  },[])
  if(!check) return <div className="text-xs text-slate-400">Checking hydro...</div>
  return (
    <div className="p-2 border rounded bg-slate-50 text-xs">
      <div className="font-medium">Hydro check §7.1</div>
      <div className={check.valid ? "text-emerald-600" : "text-amber-600"}>{check.valid ? "✓ Valid" : "⚠ Check"} — {check.snapped_to_waterbody} drains → water bodies, {check.to_river ?? 0} → river, {check.unsnapped} unsnapped</div>
      <div>Waterbodies without inflow: {check.waterbodies_without_inflow} / {check.waterbodies_total}</div>
      <div className="text-[11px] text-slate-500">Drains end explicitly in waterbody/river/sea per Global Constraint, never vanish.</div>
    </div>
  )
}
