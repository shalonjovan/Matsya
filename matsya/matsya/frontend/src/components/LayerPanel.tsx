import { useEffect, useState } from "react"
export default function LayerPanel({ layers, onChange }: any) {
  const [local, setLocal] = useState(layers)
  // sync when parent changes
  useEffect(()=>{ setLocal(layers) },[layers])
  const update = (k:string, patch:any)=>{
    const next={...local, [k]:{...local[k], ...patch}}
    setLocal(next); onChange?.(next)
  }
  const groups = [
    {id:"depth", label:"Flood depth", unit:"m", layers:["depth","velocity","direction","arrival","duration","hazard"]},
    {id:"terrain", label:"Elevation", unit:"m", layers:["elevation"]},
    {id:"drainage", label:"Drainage", layers:["micro","macro","storm","conduits","junctions"]},
    {id:"hydro", label:"Hydro (drains→waterbodies)", unit:"", layers:["drains→waterbody flow","waterbody fill","river flow"]},
    {id:"water", label:"Water", layers:["rivers","canals","water Bodies","sea"]},
    {id:"infra", label:"Infrastructure", layers:["roads","buildings"]},
    {id:"other", label:"Other", layers:["admin","land cover"]},
  ]
  return (
    <div className="p-3 border-b">
      <h3 className="text-xs uppercase text-slate-500 font-semibold mb-2">Layers §9</h3>
      {groups.map(g=>(
        <div key={g.id} className="mb-3">
          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={local[g.id]?.visible ?? true} onChange={e=>update(g.id,{visible:e.target.checked})} />
              {g.label} {g.unit && <span className="text-xs text-slate-400">({g.unit})</span>}
            </label>
            <input type="range" min={0} max={1} step={0.1} value={local[g.id]?.opacity ?? 0.8} onChange={e=>update(g.id,{opacity:parseFloat(e.target.value)})} className="w-16" title="Opacity" />
          </div>
          <div className="text-xs text-slate-400 ml-6">{g.layers.join(", ")} — legend: 0→0.05 light, 0.3 medium, 1.0 dark</div>
        </div>
      ))}
      <div className="text-xs text-slate-500">Opacity and ordering where relevant per §9. Numerical layers show units and legend.</div>
    </div>
  )
}