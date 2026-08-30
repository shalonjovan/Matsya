
import { useState } from "react"
export default function SearchBar(){
  const [q,setQ]=useState("")
  const [results,setResults]=useState<any[]>([])
  const doSearch=async()=>{
    if(!q.trim()) return
    // try Nominatim + local roads filter stub
    try{
      // if coords
      const coords=q.split(",").map(s=>parseFloat(s.trim()))
      if(coords.length===2 && coords.every(n=>!isNaN(n))){
        const [lat,lon]=coords
        setResults([{display_name:`${lat},${lon} (coords)`, lat,lon}])
        return
      }
      const res=await fetch(`https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(q)}&format=json&limit=5`)
      const data=await res.json()
      setResults(data)
    }catch{ setResults([])}
  }
  return (
    <div className="bg-white border rounded shadow p-2">
      <div className="flex gap-2">
        <input value={q} onChange={e=>setQ(e.target.value)} placeholder="Search places/coords/roads/rivers §11" className="flex-1 border rounded px-2 py-1 text-sm" />
        <button onClick={doSearch} className="px-3 py-1 bg-blue-600 text-white rounded text-sm">Search</button>
      </div>
      {results.length>0 && <ul className="mt-2 text-xs border-t">{results.map((r:any,i:number)=>(<li key={i} className="py-1 border-b hover:bg-slate-50 cursor-pointer" onClick={()=>{
        // would flyTo
        const lat=parseFloat(r.lat), lon=parseFloat(r.lon)
        if(!isNaN(lat)) window.dispatchEvent(new CustomEvent("matsya-flyto",{detail:{lat,lon}}))
      }}>{r.display_name}</li>))}</ul>}
    </div>
  )
}
