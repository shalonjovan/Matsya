
import { useState, useRef, useEffect } from "react"
import { Search, MapPin, X } from "lucide-react"

export default function SearchBar() {
  const [q, setQ] = useState("")
  const [results, setResults] = useState<any[]>([])
  const [searching, setSearching] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Click outside to dismiss search results
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setResults([])
      }
    }
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setResults([])
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    document.addEventListener("keydown", handleKeyDown)
    return () => {
      document.removeEventListener("mousedown", handleClickOutside)
      document.removeEventListener("keydown", handleKeyDown)
    }
  }, [])

  const doSearch = async () => {
    if (!q.trim()) return
    setSearching(true)
    try {
      const coords = q.split(",").map(s => parseFloat(s.trim()))
      if (coords.length === 2 && coords.every(n => !isNaN(n))) {
        const [lat, lon] = coords
        setResults([{ display_name: `${lat}, ${lon} (Coordinates)`, lat, lon }])
        setSearching(false)
        return
      }
      const res = await fetch(`https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(q)}&format=json&limit=5`)
      const data = await res.json()
      setResults(Array.isArray(data) ? data : [])
    } catch { 
      setResults([])
    } finally {
      setSearching(false)
    }
  }

  return (
    <div 
      ref={containerRef}
      role="search"
      aria-label="Location search"
      className="glass-panel rounded-xl shadow-2xl p-2.5 border border-slate-700/80 w-[calc(100vw-24px)] max-w-xs sm:w-80"
    >
      <div className="flex items-center gap-1.5">
        <div className="relative flex-1">
          <input 
            value={q} 
            onChange={e => setQ(e.target.value)} 
            onKeyDown={e => e.key === "Enter" && doSearch()}
            placeholder="Search places, roads, or lat,lon..." 
            aria-label="Search landmark or coordinates"
            className="w-full bg-slate-950/80 border border-slate-700/80 rounded-lg pl-2.5 pr-7 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus-visible:ring-1 focus-visible:ring-cyan-400 transition" 
          />
          {q && (
            <button 
              type="button"
              onClick={() => { setQ(""); setResults([]); }}
              aria-label="Clear search text"
              className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white p-1 rounded-full transition"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
        <button 
          type="button"
          onClick={doSearch} 
          disabled={searching}
          aria-label="Submit search"
          className="px-3.5 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg text-xs font-semibold shadow transition disabled:opacity-50 shrink-0 focus-ring"
        >
          {searching ? "..." : "Search"}
        </button>
      </div>

      {/* Quick hotspot fly-to chips - Commented out to declutter search widget */}
      {/*
      <div className="flex items-center gap-1.5 mt-2 pt-2 border-t border-slate-800/80 text-[10px] font-mono text-slate-400 overflow-x-auto">
        <span className="shrink-0 text-slate-400">Quick:</span>
        {[
          { name: "Velachery", lat: 12.9816, lon: 80.218 },
          { name: "Pallikaranai", lat: 12.9372, lon: 80.213 },
          { name: "Adyar", lat: 13.0012, lon: 80.2565 },
          { name: "T. Nagar", lat: 13.0418, lon: 80.2341 }
        ].map((h) => (
          <button
            key={h.name}
            type="button"
            onClick={() => {
              window.dispatchEvent(new CustomEvent("matsya-flyto", { detail: { lat: h.lat, lon: h.lon } }))
            }}
            aria-label={`Jump to ${h.name}`}
            className="px-2 py-1 rounded bg-slate-900 hover:bg-cyan-950/60 text-slate-300 hover:text-cyan-300 border border-slate-800 hover:border-cyan-500/40 transition shrink-0 focus-ring"
          >
            {h.name}
          </button>
        ))}
      </div>
      */}

      {results.length > 0 && (
        <ul 
          role="listbox"
          aria-label="Search results"
          className="mt-2 text-xs border-t border-slate-800 divide-y divide-slate-800/80 max-h-48 overflow-y-auto"
        >
          {results.map((r: any, i: number) => (
            <li 
              key={i} 
              role="option"
              aria-selected="false"
              tabIndex={0}
              className="py-2 px-2 hover:bg-slate-800/70 focus:bg-slate-800/90 text-slate-300 hover:text-cyan-300 cursor-pointer transition flex items-center gap-2 focus:outline-none" 
              onClick={() => {
                const lat = parseFloat(r.lat)
                const lon = parseFloat(r.lon)
                if (!isNaN(lat)) window.dispatchEvent(new CustomEvent("matsya-flyto", { detail: { lat, lon } }))
                setResults([])
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  const lat = parseFloat(r.lat)
                  const lon = parseFloat(r.lon)
                  if (!isNaN(lat)) window.dispatchEvent(new CustomEvent("matsya-flyto", { detail: { lat, lon } }))
                  setResults([])
                }
              }}
            >
              <MapPin className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
              <span className="truncate text-[11px] font-mono">{r.display_name}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

