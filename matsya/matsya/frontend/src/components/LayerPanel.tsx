import { useEffect, useState } from "react"
import { Layers, Mountain, GitFork, Droplets, Waves, Building2 } from "lucide-react"

export default function LayerPanel({ layers, onChange, simulation }: any) {
  const [local, setLocal] = useState(layers)
  useEffect(()=>{ setLocal(layers) },[layers])

  const update = (k:string, patch:any)=>{
    const next={...local, [k]:{...local[k], ...patch}}
    setLocal(next); onChange?.(next)
  }

  const floodStats = simulation?.flood?.stats || simulation?.elevation?.stats
  const floodLegend = floodStats 
    ? `${floodStats.min?.toFixed?.(2) ?? "0"}→${floodStats.max?.toFixed?.(2) ?? floodStats.maxDepth?.toFixed?.(2) ?? "1.0"}m` 
    : "0→0.05 light, 0.3 medium, 1.0 dark"
  const depthPalette = (layers as any)?.depth?.palette ?? "blue"
  const paletteLegend = depthPalette === "greenred"
    ? "green→yellow→red"
    : "light blue→dark blue"

  const groups = [
    {
      id:"depth", 
      label:"Flood depth", 
      unit:"m", 
      icon: Waves, 
      color: "text-cyan-400",
      layers:["depth","velocity","direction","arrival","duration","hazard"],
    },
    {
      id:"terrain", 
      label:"Elevation", 
      unit:"m", 
      icon: Mountain, 
      color: "text-emerald-400",
      layers:["elevation"],
    },
    {
      id:"drainage", 
      label:"Drainage", 
      icon: GitFork, 
      color: "text-indigo-400",
      layers:["micro","macro","storm","conduits","junctions"]
    },
    {
      id:"hydro", 
      label:"Hydro (drains→waterbodies)", 
      unit:"", 
      icon: Droplets, 
      color: "text-blue-400",
      layers:["drains→waterbody flow","waterbody fill","river flow"]
    },
    {
      id:"water", 
      label:"Water", 
      icon: Waves, 
      color: "text-sky-400",
      layers:["rivers","canals","water Bodies","sea"]
    },
    {
      id:"infra", 
      label:"Infrastructure", 
      icon: Building2, 
      color: "text-slate-400",
      layers:["roads","buildings"]
    },
    {
      id:"other", 
      label:"Other", 
      icon: Layers, 
      color: "text-slate-500",
      layers:["admin","land cover"]
    },
  ]

  return (
    <div className="p-3.5 border-b border-slate-800/80 bg-slate-950/60">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs uppercase text-slate-400 font-mono font-semibold tracking-wider flex items-center gap-1.5">
          <Layers className="w-3.5 h-3.5 text-cyan-400" />
          Map Layers & Controls
        </h3>
        <span className="text-[10px] text-slate-500 font-mono">{groups.length} Groups</span>
      </div>

      <div className="space-y-3">
        {groups.map(g => {
          const Icon = g.icon
          const isVisible = local[g.id]?.visible ?? true
          const opacity = local[g.id]?.opacity ?? 0.8

          return (
            <div 
              key={g.id} 
              className={`p-2.5 rounded-xl border transition-all duration-150 ${
                isVisible 
                  ? "bg-slate-900/80 border-slate-800 shadow-sm" 
                  : "bg-slate-950/40 border-slate-900/60 opacity-60"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <label className="flex items-center gap-2 text-xs font-semibold text-slate-200 cursor-pointer select-none flex-1">
                  <input 
                    type="checkbox" 
                    checked={isVisible} 
                    onChange={e=>update(g.id,{visible:e.target.checked})} 
                    className="w-3.5 h-3.5 rounded border-slate-700 bg-slate-950 text-cyan-500 focus:ring-0 focus:ring-offset-0 cursor-pointer accent-cyan-500"
                  />
                  <Icon className={`w-3.5 h-3.5 ${g.color}`} />
                  <span>{g.label}</span>
                  {g.unit && <span className="text-[10px] text-slate-400 font-mono">({g.unit})</span>}
                </label>

                {/* Opacity slider */}
                <div className="flex items-center gap-1.5 shrink-0">
                  <input 
                    type="range" 
                    min={0} 
                    max={1} 
                    step={0.1} 
                    value={opacity} 
                    onChange={e=>update(g.id,{opacity:parseFloat(e.target.value)})} 
                    className="w-14 h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400" 
                    title="Opacity" 
                  />
                  <span className="text-[10px] text-slate-500 font-mono w-7 text-right">
                    {Math.round(opacity * 100)}%
                  </span>
                </div>
              </div>

              {/* Compact range for depth */}
              {g.id === "depth" && isVisible && (
                <div className="mt-1 space-y-1">
                  <div className="text-[10px] text-cyan-300/80 font-mono">
                    {floodLegend} • {paletteLegend}
                  </div>
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      aria-label="Blue depth palette"
                      aria-pressed={depthPalette === "blue"}
                      title="Blue depth palette"
                      onClick={() => update("depth", { palette: "blue" })}
                      className={`w-6 h-4 rounded border transition focus-ring ${
                        depthPalette === "blue"
                          ? "border-cyan-400 ring-1 ring-cyan-400"
                          : "border-slate-700"
                      }`}
                      style={{ background: "linear-gradient(90deg,#bae6fd,#38bdf8,#0284c7,#082f49)" }}
                    />
                    <button
                      type="button"
                      aria-label="Green-red depth palette"
                      aria-pressed={depthPalette === "greenred"}
                      title="Green-red depth palette"
                      onClick={() => update("depth", { palette: "greenred" })}
                      className={`w-6 h-4 rounded border transition focus-ring ${
                        depthPalette === "greenred"
                          ? "border-cyan-400 ring-1 ring-cyan-400"
                          : "border-slate-700"
                      }`}
                      style={{ background: "linear-gradient(90deg,#22c55e,#facc15,#dc2626)" }}
                    />
                  </div>
                </div>
              )}

              {/* Sub-layers & verbose legend - Commented out to declutter layer items */}
              {/*
              <div className="mt-1.5 pt-1.5 border-t border-slate-800/60 text-[11px] text-slate-400">
                <div className="line-clamp-1 text-[10px] text-slate-400 font-mono">
                  {g.layers.join(", ")}
                </div>
                <div className="text-[10px] text-cyan-300/80 mt-0.5 font-mono">
                  {g.id==="terrain" && simulation?.elevation?.stats 
                    ? `legend: ${simulation.elevation.stats.min.toFixed(1)}m → ${simulation.elevation.stats.max.toFixed(1)}m hypsometric` 
                    : g.id==="terrain" 
                    ? "legend: hypsometric tint per TIF" 
                    : g.id==="depth" 
                    ? `legend: ${floodLegend}` 
                    : "legend: 0→0.05 light, 0.3 medium, 1.0 dark"}
                </div>
              </div>
              */}
            </div>
          )
        })}
      </div>

      {/* Bottom hint text - Commented out to declutter panel */}
      {/*
      <div className="text-[10px] text-slate-400 mt-4 pt-3 border-t border-slate-800 font-mono">
        Adjust individual layer opacity to blend satellite, DEM elevation, and flood depths.
      </div>
      */}
    </div>
  )
}