
import { useEffect, useState } from "react"
export default function Timeline({ time, onChange, max=72 }: { time:number, onChange:(n:number)=>void, max?:number }) {
  const [playing, setPlaying] = useState(false)
  useEffect(()=>{
    if (!playing) return
    const id=setInterval(()=>onChange((time+1)% (max+1)), 350)
    return ()=>clearInterval(id)
  },[playing,time,max,onChange])
  return (
    <div className="flex items-center gap-3 p-3 bg-white border-t">
      <button onClick={()=>setPlaying(!playing)} className="px-3 py-1 bg-blue-600 text-white rounded text-sm">{playing ? "⏸ Pause" : "▶ Play"}</button>
      <button onClick={()=>onChange(Math.max(0,time-1))} className="px-2 py-1 border rounded">-1</button>
      <input type="range" min={0} max={max} value={time} onChange={e=>onChange(parseInt(e.target.value))} className="flex-1" />
      <button onClick={()=>onChange(Math.min(max,time+1))} className="px-2 py-1 border rounded">+1</button>
      <span className="font-mono text-sm border px-2 py-1 rounded bg-slate-50">{String(Math.floor(time*5/60)).padStart(2,"0")}:{String((time*5)%60).padStart(2,"0")}</span>
      <span className="text-xs text-slate-500">{time+1}/{max+1} • map updates depth/area/velocity per §13</span>
    </div>
  )
}
