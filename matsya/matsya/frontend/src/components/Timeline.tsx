
import { useEffect, useState } from "react"
import { Clock } from "lucide-react"

export default function Timeline({ time, onChange, max = 72, minutesPerFrame = 5 }: { time: number; onChange: (n: number) => void; max?: number; minutesPerFrame?: number }) {
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(350)

  useEffect(() => {
    if (!playing) return
    const id = setInterval(() => onChange((time + 1) % (max + 1)), speed)
    return () => clearInterval(id)
  }, [playing, time, max, onChange, speed])

  // Keyboard controls for timeline navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't intercept if user is typing in an input or textarea
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return

      if (e.code === "Space") {
        e.preventDefault()
        setPlaying(p => !p)
      } else if (e.code === "ArrowLeft") {
        e.preventDefault()
        onChange(Math.max(0, time - 1))
      } else if (e.code === "ArrowRight") {
        e.preventDefault()
        onChange(Math.min(max, time + 1))
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [time, max, onChange])

  const mpf = minutesPerFrame && minutesPerFrame > 0 ? minutesPerFrame : 5
  const totalMin = time * mpf
  const hours = Math.floor(totalMin / 60)
  const minutes = Math.floor(totalMin % 60)
  const timeFormatted = `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`

  return (
    <div 
      role="region"
      aria-label="Simulation temporal controls"
      className="bg-slate-950 border-t border-slate-800/90 px-4 py-2.5 select-none"
    >
      <div className="flex flex-col sm:flex-row items-center gap-3">
        {/* Playback Controls */}
        <div className="flex items-center gap-1.5 shrink-0">
          <button 
            type="button"
            onClick={() => setPlaying(!playing)} 
            aria-label={playing ? "Pause simulation timeline" : "Play simulation timeline"}
            className={`flex items-center justify-center gap-1.5 px-4 py-2 min-h-[38px] rounded-xl text-xs font-bold transition shadow-md focus-ring ${
              playing 
                ? "bg-amber-500/20 text-amber-300 border border-amber-500/40 hover:bg-amber-500/30" 
                : "bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-extrabold shadow-cyan-500/20"
            }`}
          >
            {playing ? "⏸ Pause" : "▶ Play"}
          </button>

          <button 
            type="button"
            onClick={() => onChange(Math.max(0, time - 1))} 
            aria-label={`Step backward ${mpf} minutes`}
            title={`Step backward ${mpf} minutes (← Arrow)`}
            className="px-3 py-2 min-h-[38px] bg-slate-900 hover:bg-slate-800 text-slate-300 rounded-lg text-xs font-mono border border-slate-800 transition focus-ring"
          >
            -1
          </button>

          <button 
            type="button"
            onClick={() => onChange(Math.min(max, time + 1))} 
            aria-label={`Step forward ${mpf} minutes`}
            title={`Step forward ${mpf} minutes (→ Arrow)`}
            className="px-3 py-2 min-h-[38px] bg-slate-900 hover:bg-slate-800 text-slate-300 rounded-lg text-xs font-mono border border-slate-800 transition focus-ring"
          >
            +1
          </button>

          {/* Speed Toggle */}
          <button
            type="button"
            onClick={() => setSpeed(s => (s === 350 ? 150 : s === 150 ? 50 : 350))}
            aria-label={`Playback speed: ${speed === 350 ? "1x" : speed === 150 ? "2x" : "5x"}`}
            title="Toggle playback speed"
            className="px-2.5 py-2 min-h-[38px] bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-cyan-300 rounded-lg text-[11px] font-mono border border-slate-800 transition focus-ring"
          >
            {speed === 350 ? "1x" : speed === 150 ? "2x" : "5x"}
          </button>
        </div>

        {/* Timeline Slider with Progress Bar */}
        <div className="flex-1 w-full flex flex-col justify-center gap-1">
          <div className="relative flex items-center">
            <input 
              type="range" 
              min={0} 
              max={max} 
              value={time} 
              onChange={e => onChange(parseInt(e.target.value))} 
              aria-label="Simulation time scrubber"
              aria-valuemin={0}
              aria-valuemax={max}
              aria-valuenow={time}
              aria-valuetext={`${timeFormatted} elapsed`}
              className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400 focus:outline-none focus-ring" 
            />
          </div>
          {/* Milestone markers - Commented out to declutter timeline */}
          {/*
          <div className="flex justify-between text-[10px] text-slate-400 font-mono px-0.5">
            <span>T+00:00 (Rain Onset)</span>
            <span className="hidden sm:inline">T+01:00 (Peak Rate)</span>
            <span className="hidden md:inline">T+03:30 (Lake Surcharge)</span>
            <span>T+06:00 (Recession)</span>
          </div>
          */}
        </div>

        {/* Digital Clock Display & Metadata */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-900/90 rounded-xl border border-slate-800 font-mono">
            <Clock className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-sm font-bold text-cyan-300">{timeFormatted}</span>
            <span className="text-[10px] text-slate-400">HRS</span>
          </div>

          {/* Telemetry subtitle - Commented out to declutter timeline */}
          {/*
          <span className="text-[11px] text-slate-400 font-mono hidden lg:inline">
            Step {time + 1} of {max + 1} • Dynamic 2D Inundation
          </span>
          */}
        </div>
      </div>
    </div>
  )
}

