
import { useEffect, useState } from "react"
export function useSimulationResults(simId:string | null, runId:string | null){
  const [data,setData]=useState<any>(null)
  const [loading,setLoading]=useState(false)
  useEffect(()=>{
    if(!simId || !runId) return
    setLoading(true)
    let alive=true
    const poll=async()=>{
      try{
        const r=await fetch(`/api/simulations/${simId}/runs/${runId}`)
        if(!r.ok) return
        const j=await r.json()
        if(alive) setData(j)
        if(j.status==="Running" && alive) setTimeout(poll,1000)
      }catch{}
      finally{ if(alive) setLoading(false)}
    }
    poll()
    return()=>{alive=false}
  },[simId,runId])
  return {data,loading}
}
