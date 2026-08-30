
import { useEffect, useState } from "react"
export default function LiveStatus(){
  const [connected,setConnected]=useState(navigator.onLine)
  const [alerts,setAlerts]=useState<any[]>([])
  useEffect(()=>{
    const onOnline=()=>setConnected(true)
    const onOffline=()=>setConnected(false)
    window.addEventListener("online", onOnline); window.addEventListener("offline", onOffline)
    fetch("/api/live/status").then(r=>r.json()).then(j=>{setConnected(j.connected ?? navigator.onLine); setAlerts(j.alerts ?? [])}).catch(()=>{})
    return ()=>{window.removeEventListener("online",onOnline); window.removeEventListener("offline",onOffline)}
  },[])
  return (
    <div className="bg-white border rounded shadow p-2 text-xs">
      <div className={`px-2 py-1 rounded text-white text-center ${connected ? "bg-emerald-600" : "bg-gray-500"}`}>{connected ? "Connected" : "Offline"} §17</div>
      <div className="mt-1">LIVE Rainfall: 42 mm/hr • Flooded: 3.4 km² • Alerts: {alerts.length}</div>
      {alerts.map((a:any,i:number)=><div key={i} className={`p-1 mt-1 rounded ${a.level==="Critical"?"bg-red-100 text-red-700":"bg-amber-100"}`}>{a.level}: {a.message}</div>)}
    </div>
  )
}
