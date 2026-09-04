
import { useEffect, useState } from "react"
import { Radio, AlertTriangle, CheckCircle2, Activity, Wifi, WifiOff } from "lucide-react"

export default function LiveStatus(){
  const [connected,setConnected]=useState(navigator.onLine)
  const [alerts,setAlerts]=useState<any[]>([])
  const [liveMetrics, setLiveMetrics] = useState<{ rainfall: string; floodedArea: string }>({
    rainfall: "42 mm/hr",
    floodedArea: "3.4 km²"
  })

  useEffect(()=>{
    const onOnline=()=>setConnected(true)
    const onOffline=()=>setConnected(false)
    window.addEventListener("online", onOnline); window.addEventListener("offline", onOffline)
    fetch("/api/live/status").then(r=>r.json()).then(j=>{
      setConnected(j.connected ?? navigator.onLine)
      setAlerts(j.alerts ?? [])
      if (j.rainfall || j.floodedArea) {
        setLiveMetrics({
          rainfall: j.rainfall || "0 mm/hr",
          floodedArea: j.floodedArea || "0.0 km²"
        })
      }
    }).catch(()=>{})
    return ()=>{window.removeEventListener("online",onOnline); window.removeEventListener("offline",onOffline)}
  },[])

  return (
    <div className="glass-panel rounded-xl shadow-2xl p-3 text-xs max-w-xs border border-slate-700/80 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 font-mono text-[11px] text-slate-300">
          <span className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-400 animate-pulse shadow-[0_0_8px_rgba(52,211,153,0.8)]" : "bg-slate-500"}`} />
          <span>GCC RADAR FEED</span>
        </div>
        <div className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold border ${
          connected 
            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30" 
            : "bg-slate-500/10 text-slate-400 border-slate-500/30"
        }`}>
          {connected ? "Connected" : "Offline"} §17
        </div>
      </div>

      <div className="text-[11px] text-slate-300 font-mono pt-1 border-t border-slate-800 flex items-center justify-between">
        <span>Rain: <strong className="text-cyan-400">{liveMetrics.rainfall}</strong></span>
        <span>Flooded: <strong className="text-rose-400">{liveMetrics.floodedArea}</strong></span>
        <span className="text-slate-400">Alerts: {alerts.length}</span>
      </div>

      {alerts.length > 0 && (
        <div className="space-y-1 pt-1">
          {alerts.map((a:any,i:number)=>(
            <div 
              key={i} 
              className={`p-1.5 rounded-lg text-[10px] font-mono flex items-center gap-1.5 border ${
                a.level==="Critical"
                  ? "bg-rose-950/60 border-rose-800 text-rose-300"
                  : "bg-amber-950/60 border-amber-800 text-amber-300"
              }`}
            >
              <AlertTriangle className="w-3 h-3 shrink-0" />
              <span>{a.level}: {a.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
