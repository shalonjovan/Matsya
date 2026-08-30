
export default function PointInspector({ point }: any){
  if(!point) return <div className="p-3 border-b text-sm text-slate-500">Click map for point info §10</div>
  const typeLabel = point.type ?? "simulated"
  return (
    <div className="p-3 border-b">
      <h3 className="text-xs uppercase text-slate-500 font-semibold mb-2">Point Inspection §10 <span className="normal-case text-[10px] bg-slate-100 px-1 rounded">{typeLabel}</span></h3>
      <div className="text-sm space-y-1">
        <div>Lat {point.lat?.toFixed?.(5)} Lon {point.lon?.toFixed?.(5)}</div>
        <div>Elevation {point.elevation?.toFixed?.(2) ?? "—"} m <span className="text-xs text-slate-400">(measured)</span></div>
        <div>Flood depth {point.floodDepth?.toFixed?.(3) ?? point.water_depth?.toFixed?.(3) ?? "0.000"} m <span className="text-xs text-slate-400">(simulated)</span></div>
        <div>Velocity {point.velocity?.toFixed?.(2) ?? "0.00"} m/s</div>
        <div>First flooded {point.firstFlooded ?? "—"} • Peak {point.peak ?? "—"} • Duration {point.duration ?? "—"}</div>
        <div className="text-xs text-slate-500">Distinguishes measured / simulated / derived per §10. {point.nearestDrain && `Nearest drain: ${point.nearestDrain}`}</div>
      </div>
    </div>
  )
}
