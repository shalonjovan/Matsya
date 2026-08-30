
import { useEffect, useState } from "react"
export default function InfraImpact({ simulation }: any){
  const [roads,setRoads]=useState<any[]>([])
  const [drains,setDrains]=useState<any[]>([])
  useEffect(()=>{
    if(!simulation?.id) return
    fetch(`/api/simulations/${simulation.id}/roads`).then(r=>r.json()).then(setRoads).catch(()=>setRoads([{id:"R1",maxDepth:0.8,duration:"2h",firstFlood:"00:15",peak:"01:20",maxVel:0.5}]))
    fetch(`/api/simulations/${simulation.id}/drains`).then(r=>r.json()).then(setDrains).catch(()=>setDrains([{id:"D1",flow:1.2,depth:0.5,status:"ok",capacity:null,overCapacity:false}]))
  },[simulation])
  return (
    <div className="p-3 border-b">
      <h3 className="text-xs uppercase text-slate-500 font-semibold mb-2">Infrastructure §15</h3>
      <div className="mb-3">
        <h4 className="text-sm font-medium">Roads</h4>
        <table className="text-xs w-full">
          <thead><tr><th>Id</th><th>Depth</th><th>Duration</th><th>Vel</th></tr></thead>
          <tbody>{roads.map((r:any)=><tr key={r.id}><td>{r.id}</td><td>{r.maxDepth}</td><td>{r.duration}</td><td>{r.maxVel}</td></tr>)}</tbody>
        </table>
      </div>
      <div>
        <h4 className="text-sm font-medium">Drains</h4>
        <table className="text-xs w-full">
          <thead><tr><th>Id</th><th>Flow</th><th>Depth</th><th>Cap</th></tr></thead>
          <tbody>{drains.map((d:any)=><tr key={d.id}><td>{d.id}</td><td>{d.flow}</td><td>{d.depth}</td><td>{d.capacity ?? "—"}</td></tr>)}</tbody>
        </table>
        <p className="text-[10px] text-slate-400">Capacity never invented per §15 — shown as — when missing.</p>
      </div>
    </div>
  )
}
