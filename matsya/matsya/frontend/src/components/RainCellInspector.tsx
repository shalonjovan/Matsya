import {
  rateAtHour,
  frameToWindowHour,
  liveNowHour,
  cellWhenBadge,
  cellIndexToRowCol,
  cellAccumulation,
} from "../utils/rainGrid"

/**
 * Read-only inspector for one live rain-grid cell. Recomputes the rate
 * from the cell hyetograph on every render, so scrubbing the timeline
 * moves the playhead value with no extra wiring.
 */
export default function RainCellInspector({ cell, index, grid, time, mpf, live }: any) {
  if (!cell) {
    return (
      <div className="p-3.5 border-b border-slate-800/80 bg-slate-950/60" data-testid="raincell-panel">
        <h4 className="text-xs uppercase tracking-wider font-mono text-slate-400">Rain cell</h4>
        <p className="text-xs text-slate-500 mt-1">Click a rain grid cell to inspect its hourly rainfall.</p>
      </div>
    )
  }
  const pts = Array.isArray(cell.points) ? cell.points : []
  const totalTime = Number(cell.totalTime) || 24
  const hour = frameToWindowHour(time, mpf)
  const rate = rateAtHour(pts, hour)
  const now = liveNowHour(live)
  const peak = Math.max(Number(cell.maxRain) || 0, ...pts.map((p: any) => Number(p?.amount) || 0))
  const total = cellAccumulation(pts)
  const { row, col } = cellIndexToRowCol(index, grid)

  const when = cellWhenBadge(hour, mpf, live)

  // sparkline geometry
  const W = 200, H = 64, PAD = 4
  const span = Math.max(totalTime, ...pts.map((p: any) => Number(p?.time) || 0), 1)
  const top = Math.max(peak, 0.1)
  const xs = (t: number) => PAD + (Math.max(0, Math.min(span, t)) / span) * (W - PAD * 2)
  const ys = (a: number) => H - PAD - (Math.max(0, a) / top) * (H - PAD * 2)
  const line = pts
    .filter((p: any) => isFinite(Number(p?.time)) && isFinite(Number(p?.amount)))
    .sort((a: any, b: any) => Number(a.time) - Number(b.time))
    .map((p: any) => `${xs(Number(p.time)).toFixed(1)},${ys(Number(p.amount)).toFixed(1)}`)
    .join(" ")

  return (
    <div className="p-3.5 border-b border-slate-800/80 bg-slate-950/60" data-testid="raincell-panel">
      <div className="flex items-baseline justify-between">
        <h4 className="text-xs uppercase tracking-wider font-mono text-slate-400">
          Rain cell <span className="text-cyan-300">{String(cell.id ?? "")}</span>
        </h4>
        {row != null && col != null && (
          <span className="text-[10px] font-mono text-slate-500">row {row} · col {col}</span>
        )}
      </div>
      <div className="flex items-baseline gap-2 mt-1">
        <span className="text-2xl font-bold font-mono text-cyan-300" data-testid="raincell-rate">
          {rate.toFixed(1)} mm/hr
        </span>
        <span className="text-[11px] font-mono text-slate-400" data-testid="raincell-when">{when}</span>
      </div>
      <div className="text-[11px] font-mono text-slate-500 mt-0.5">
        {peak.toFixed(1)} mm/hr peak · {total.toFixed(1)} mm / {totalTime}h
      </div>
      {line && (
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-16 mt-2" data-testid="raincell-sparkline" role="img" aria-label="Cell hourly rainfall">
          {now != null && (
            <rect x={PAD} y={PAD} width={Math.max(0, xs(now) - PAD)} height={H - PAD * 2} fill="#64748b" opacity={0.15} />
          )}
          <polyline points={line} fill="none" stroke="#22d3ee" strokeWidth={1.5} />
          <line x1={xs(hour)} y1={PAD} x2={xs(hour)} y2={H - PAD} stroke="#fbbf24" strokeWidth={1.5} />
          {now != null && (
            <line x1={xs(now)} y1={PAD} x2={xs(now)} y2={H - PAD} stroke="#94a3b8" strokeWidth={1} strokeDasharray="3,2" data-testid="raincell-now-marker" />
          )}
        </svg>
      )}
    </div>
  )
}
