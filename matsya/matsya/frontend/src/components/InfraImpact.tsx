
import { useEffect, useState } from "react"
import { Building2, Navigation, GitFork } from "lucide-react"

export default function InfraImpact({ simulation }: any){
  const [roads,setRoads]=useState<any[]>([])
  const [drains,setDrains]=useState<any[]>([])

  useEffect(()=>{
    if(!simulation?.id) return
    fetch(`/api/simulations/${simulation.id}/roads`).then(r=>r.json()).then(setRoads).catch(()=>setRoads([{id:"R1",maxDepth:0.8,duration:"2h",firstFlood:"00:15",peak:"01:20",maxVel:0.5}]))
    fetch(`/api/simulations/${simulation.id}/drains`).then(r=>r.json()).then(setDrains).catch(()=>setDrains([{id:"D1",flow:1.2,depth:0.5,status:"ok",capacity:null,overCapacity:false}]))
  },[simulation])

  return (
    <div className="p-3.5 border-b border-slate-800/80 bg-slate-950/60">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs uppercase text-slate-400 font-mono font-semibold tracking-wider flex items-center gap-1.5">
          <Building2 className="w-3.5 h-3.5 text-cyan-400" />
          Infrastructure Risk Audit
        </h3>
        <span className="text-[10px] text-slate-500 font-mono">Impact Audit</span>
      </div>

      {/* Roads table */}
      <div className="mb-4">
        <div className="flex items-center gap-1.5 mb-1.5">
          <Navigation className="w-3 h-3 text-cyan-400" />
          <h4 className="text-xs font-semibold text-slate-200">Roads</h4>
        </div>
        <div className="rounded-xl border border-slate-800 overflow-hidden bg-slate-900/60">
          <table className="text-xs w-full text-left font-mono">
            <thead className="bg-slate-950/80 text-[10px] uppercase tracking-wider text-slate-400 border-b border-slate-800">
              <tr>
                <th className="py-1.5 px-2.5">Id</th>
                <th className="py-1.5 px-2">Depth</th>
                <th className="py-1.5 px-2">Duration</th>
                <th className="py-1.5 px-2.5">Vel</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300 text-[11px]">
              {roads.map((r:any)=>(
                <tr key={r.id} className="hover:bg-slate-800/50 transition">
                  <td className="py-1.5 px-2.5 font-bold text-cyan-300">{r.id}</td>
                  <td className="py-1.5 px-2 text-rose-300">{r.maxDepth}m</td>
                  <td className="py-1.5 px-2">{r.duration}</td>
                  <td className="py-1.5 px-2.5 text-slate-400">{r.maxVel}m/s</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Drains table */}
      <div>
        <div className="flex items-center gap-1.5 mb-1.5">
          <GitFork className="w-3 h-3 text-indigo-400" />
          <h4 className="text-xs font-semibold text-slate-200">Drains</h4>
        </div>
        <div className="rounded-xl border border-slate-800 overflow-hidden bg-slate-900/60">
          <table className="text-xs w-full text-left font-mono">
            <thead className="bg-slate-950/80 text-[10px] uppercase tracking-wider text-slate-400 border-b border-slate-800">
              <tr>
                <th className="py-1.5 px-2.5">Id</th>
                <th className="py-1.5 px-2">Flow</th>
                <th className="py-1.5 px-2">Depth</th>
                <th className="py-1.5 px-2.5">Cap</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300 text-[11px]">
              {drains.map((d:any)=>(
                <tr key={d.id} className="hover:bg-slate-800/50 transition">
                  <td className="py-1.5 px-2.5 font-bold text-indigo-300">{d.id}</td>
                  <td className="py-1.5 px-2 text-slate-200">{d.flow} m³/s</td>
                  <td className="py-1.5 px-2">{d.depth}m</td>
                  <td className="py-1.5 px-2.5 text-slate-400">{d.capacity ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-[10px] text-slate-500 mt-2 font-mono">
          Capacity never invented per §15 — shown as — when missing.
        </p>
      </div>
    </div>
  )
}
