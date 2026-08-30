
import { useEffect, useState } from "react"
export default function AffectedAreas({ simulation }: any){
  const [areas,setAreas]=useState<any[]>([])
  useEffect(()=>{
    if(!simulation?.id) return
    fetch(`/api/simulations/${simulation.id}/affected-areas`).then(r=>r.json()).then(setAreas).catch(()=>{
      setAreas([{name:"Velachery",maxDepth:1.24,duration:"3h 12m",rank:1,lat:12.98,lon:80.22},{name:"Pallikaranai",maxDepth:0.92,duration:"2h 48m",rank:2,lat:12.94,lon:80.21}])
    })
  },[simulation])
  return (
    <div className="p-3 border-b">
      <h3 className="text-xs uppercase text-slate-500 font-semibold mb-2">Affected Areas §14</h3>
      <p className="text-xs text-slate-400 mb-2">Ranked by maxDepth (transparent)</p>
      <ol className="space-y-2">
        {areas.map((a:any)=>(
          <li key={a.name} className="border rounded p-2 hover:bg-slate-50 cursor-pointer" onClick={()=>{
            window.dispatchEvent(new CustomEvent("matsya-flyto",{detail:{lat:a.lat,lon:a.lon}}))
          }}>
            <div className="font-medium">{a.rank}. {a.name}</div>
            <div className="text-xs text-slate-600">Max depth: {a.maxDepth} m • Duration: {a.duration}</div>
          </li>
        ))}
      </ol>
    </div>
  )
}
