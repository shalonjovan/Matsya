
import { Crosshair, Mountain, Waves, Gauge, Clock } from "lucide-react"

export default function PointInspector({ point }: any){
  if(!point) {
    return (
      <div className="p-4 border-b border-slate-800/80 text-xs text-slate-400 flex items-center gap-2 bg-slate-950/40">
        <Crosshair className="w-4 h-4 text-cyan-400 animate-pulse" />
        <span>Click anywhere on map to inspect depth & elevation</span>
      </div>
    )
  }

  const typeLabel = point.type ?? "simulated"
  const floodDepth = point.floodDepth ?? point.water_depth ?? 0
  
  // Hazard categorization
  const isHighRisk = floodDepth >= 0.5
  const isMediumRisk = floodDepth >= 0.15 && floodDepth < 0.5
  const hazardColor = isHighRisk 
    ? "text-rose-400 bg-rose-500/10 border-rose-500/30" 
    : isMediumRisk 
    ? "text-amber-400 bg-amber-500/10 border-amber-500/30" 
    : "text-emerald-400 bg-emerald-500/10 border-emerald-500/30"

  const hazardLabel = isHighRisk ? "High Hazard" : isMediumRisk ? "Moderate Inundation" : "Low / Safe"

  return (
    <div className="p-3.5 border-b border-slate-800/80 bg-slate-950/60">
      <div className="flex items-center justify-between mb-2.5">
        <h3 className="text-xs uppercase text-slate-400 font-mono font-semibold tracking-wider flex items-center gap-1.5">
          <Crosshair className="w-3.5 h-3.5 text-cyan-400" />
          Point Inspection
        </h3>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full border border-slate-700 bg-slate-900 text-slate-300">
          {typeLabel}
        </span>
      </div>

      <div className="space-y-2.5 text-xs">
        {/* Coordinates banner */}
        <div className="flex items-center justify-between py-1 px-2 bg-slate-900 rounded-lg font-mono text-[11px] text-slate-300 border border-slate-800">
          <span>Lat {point.lat?.toFixed?.(5)}</span>
          <span>Lon {point.lon?.toFixed?.(5)}</span>
        </div>

        {/* Core telemetry cards */}
        <div className="grid grid-cols-2 gap-2">
          {/* Elevation */}
          <div className="p-2.5 rounded-xl bg-slate-900/90 border border-slate-800" title="measured: CartoDEM 30m terrain elevation">
            <div className="flex items-center gap-1.5 text-slate-400 text-[11px] mb-1">
              <Mountain className="w-3.5 h-3.5 text-emerald-400" />
              <span>Elevation</span>
            </div>
            <div className="font-mono text-base font-bold text-white">
              {point.elevation?.toFixed?.(2) ?? "—"} <span className="text-xs text-slate-400 font-normal">m</span>
            </div>
            <span className="text-[10px] text-slate-500 block mt-0.5">measured</span>
          </div>

          {/* Flood Depth */}
          <div className="p-2.5 rounded-xl bg-slate-900/90 border border-slate-800" title="simulated: 2D dynamic hydrodynamic flow depth">
            <div className="flex items-center gap-1.5 text-slate-400 text-[11px] mb-1">
              <Waves className="w-3.5 h-3.5 text-cyan-400" />
              <span>Flood depth</span>
            </div>
            <div className="font-mono text-base font-bold text-cyan-300">
              {point.floodDepth?.toFixed?.(3) ?? point.water_depth?.toFixed?.(3) ?? "0.000"} <span className="text-xs text-slate-400 font-normal">m</span>
            </div>
            <span className="text-[10px] text-slate-500 block mt-0.5">simulated</span>
          </div>
        </div>

        {/* Velocity & Hazard Level */}
        <div className="p-2.5 rounded-xl bg-slate-900/90 border border-slate-800 flex items-center justify-between">
          <div>
            <div className="text-[10px] text-slate-400 flex items-center gap-1 mb-0.5">
              <Gauge className="w-3 h-3 text-blue-400" />
              Velocity
            </div>
            <div className="font-mono text-xs font-semibold text-slate-200">
              {point.velocity?.toFixed?.(2) ?? "0.00"} m/s
            </div>
          </div>

          <div className={`px-2 py-0.5 rounded-md border text-[10px] font-semibold ${hazardColor}`}>
            {hazardLabel}
          </div>
        </div>

        {/* Temporal telemetry */}
        <div className="p-2 rounded-lg bg-slate-900/50 border border-slate-800/80 text-[11px] text-slate-400 font-mono">
          <Clock className="w-3 h-3 text-slate-500 inline mr-1" />
          First flooded {point.firstFlooded ?? "—"} • Peak {point.peak ?? "—"} • Duration {point.duration ?? "—"}
        </div>

        {point.nearestDrain && (
          <div className="text-[10px] font-mono text-slate-400">
            Nearest drain: {point.nearestDrain}
          </div>
        )}

        {point.hydro && (
          <div className="p-2 rounded-lg bg-slate-900/50 border border-slate-800/80 text-[11px] text-slate-400 font-mono">
            mass err {point.hydro.mass_error ?? "—"} • {point.hydro.wbCount ?? 0} waterbodies{point.hydro.wbObserved ? ` (${point.hydro.wbObserved} observed)` : ""} • {point.hydro.surchargedDrains ?? 0} surcharged{point.hydro.drainSurcharge ? " • surcharge" : ""}{point.hydro.spillVolumeM3 ? ` • spill ${point.hydro.spillVolumeM3} m³` : ""}
          </div>
        )}
      </div>
    </div>
  )
}
