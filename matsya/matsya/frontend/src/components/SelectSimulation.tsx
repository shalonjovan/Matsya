import { useRef, useState, useMemo, useEffect } from "react"
import { useSimulations, deleteSimulation, duplicateSimulation, exportSimulation, importSimulation, renameSimulation } from "../hooks/useSimulation"
import type { Simulation } from "../types/simulation"
import { 
  Play, 
  Plus, 
  Upload, 
  Copy, 
  Edit3, 
  Trash2, 
  Download, 
  Clock, 
  MapPin, 
  CloudRain, 
  Search, 
  Layers, 
  AlertTriangle, 

  Activity, 
  Compass, 
  Radio,
  X
} from "lucide-react"

const statusBadgeStyles: Record<string, { badge: string; dot: string }> = {
  Ready: {
    badge: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    dot: "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]"
  },
  Running: {
    badge: "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
    dot: "bg-cyan-400 animate-ping shadow-[0_0_8px_rgba(34,211,238,0.6)]"
  },
  Completed: {
    badge: "bg-blue-500/10 text-blue-300 border-blue-500/30",
    dot: "bg-blue-400 shadow-[0_0_8px_rgba(96,165,250,0.6)]"
  },
  Incomplete: {
    badge: "bg-amber-500/10 text-amber-400 border-amber-500/30",
    dot: "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.6)]"
  },
  Error: {
    badge: "bg-rose-500/10 text-rose-400 border-rose-500/30",
    dot: "bg-rose-400 shadow-[0_0_8px_rgba(251,113,133,0.6)]"
  },
  Live: {
    badge: "bg-purple-500/10 text-purple-400 border-purple-500/30",
    dot: "bg-purple-400 animate-pulse shadow-[0_0_8px_rgba(192,132,252,0.6)]"
  },
  Offline: {
    badge: "bg-slate-500/10 text-slate-400 border-slate-500/30",
    dot: "bg-slate-400"
  },
}

function formatBbox(bbox?: [number, number, number, number] | number[]) {
  if (!bbox || bbox.length !== 4) return "—"
  const [minLon, minLat, maxLon, maxLat] = bbox
  const fmt = (n: number) => Number(n).toFixed(2)
  return `${fmt(minLon)}-${fmt(maxLon)}, ${fmt(minLat)}-${fmt(maxLat)}`
}

function formatRainfall(rainfall?: { rateMmHr?: number; durationHr?: number } | any, live?: boolean) {
  if (!rainfall) return "—"
  const zones = Array.isArray(rainfall.zones) ? rainfall.zones : []
  // Live grid (and any zoned storm read on a live card): the headline is the
  // peak cell rate. The tick always stamps a numeric whole-bbox base rate
  // (0.0 when the feed has no base cell), which must not mask the cells.
  if (live && zones.length) {
    const max = Math.max(0, ...zones.map((z: any) => Number(z.amount ?? z.maxRain ?? 0) || 0))
    const dur = rainfall.durationHr ?? 24
    return `${max} mm/hr (zonal) × ${dur} hr`
  }
  // Live/variable zones have no single rateMmHr — derive max across zones
  if (rainfall.rateMmHr == null) {
    if (zones.length) {
      const max = Math.max(...zones.map((z: any) => Number(z.amount ?? z.maxRain ?? 0)))
      const dur = rainfall.durationHr ?? 24
      return `${max} mm/hr (zonal) × ${dur} hr`
    }
    return "—"
  }
  const rate = rainfall.rateMmHr
  const dur = rainfall.durationHr
  if (dur != null) return `${rate} mm/hr × ${dur} hr`
  return `${rate} mm/hr`
}

function formatLastModified(sim: Simulation) {
  const raw: any =
    (sim as any).metadata?.updated ??
    (sim as any).metadata?.created ??
    (sim as any).updated ??
    (sim as any).lastModified ??
    (sim as any).created ??
    null
  if (!raw) return "—"
  try {
    const d = new Date(raw)
    if (isNaN(d.getTime())) return String(raw)
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch {
    return String(raw)
  }
}

function getStatus(sim: Simulation): string {
  const s: any = (sim as any).status ?? (sim as any).metadata?.status ?? "Ready"
  return String(s)
}

export default function SelectSimulation({
  onOpen,
  onCreate,
  onEdit,
}: {
  onOpen?: (id: string) => void
  onCreate?: () => void
  onEdit?: (sim: Simulation) => void
}) {
  const { data, loading, error, refetch } = useSimulations()
  const [actionError, setActionError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState<string>("ALL")
  const [deleteTarget, setDeleteTarget] = useState<Simulation | null>(null)
  const [renameTarget, setRenameTarget] = useState<Simulation | null>(null)
  const [renameValue, setRenameValue] = useState("")
  const fileRef = useRef<HTMLInputElement | null>(null)

  // Keyboard Escape listener to dismiss any active modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setDeleteTarget(null)
        setRenameTarget(null)
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [])


  const handleOpen = (id: string) => {
    if (onOpen) onOpen(id)
    else window.location.hash = `#/world/${id}`
  }

  const handleCreate = () => {
    if (onCreate) onCreate()
    else window.location.hash = `#/create`
  }

  const handleDuplicate = async (sim: Simulation) => {
    setActionError(null)
    try {
      await duplicateSimulation(sim.id)
      await refetch()
    } catch (e: any) {
      setActionError(e?.message ?? "duplicate failed")
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    setActionError(null)
    try {
      await deleteSimulation(deleteTarget.id)
      setDeleteTarget(null)
      await refetch()
    } catch (e: any) {
      setActionError(e?.message ?? "delete failed")
    }
  }

  const confirmRename = async () => {
    if (!renameTarget || !renameValue.trim() || renameValue === renameTarget.name) {
      setRenameTarget(null)
      return
    }
    setActionError(null)
    try {
      await renameSimulation(renameTarget.id, renameValue.trim())
      setRenameTarget(null)
      await refetch()
    } catch (e: any) {
      setActionError(e?.message ?? "rename failed")
    }
  }

  const handleExport = async (sim: Simulation) => {
    setActionError(null)
    try {
      await exportSimulation(sim.id, sim.name)
    } catch (e: any) {
      setActionError(e?.message ?? "export failed")
    }
  }

  const handleImportClick = () => fileRef.current?.click()

  const handleImportChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    setActionError(null)
    const file = e.target.files?.[0]
    if (!file) return
    try {
      await importSimulation(file)
      await refetch()
    } catch (err: any) {
      setActionError(err?.message ?? "import failed")
    } finally {
      if (fileRef.current) fileRef.current.value = ""
    }
  }

  const openRenameModal = (sim: Simulation) => {
    setRenameTarget(sim)
    setRenameValue(sim.name)
  }

  const handleEdit = (sim: Simulation) => {
    if (onEdit) onEdit(sim)
    else openRenameModal(sim)
  }

  // Filtered simulations (live sim lives in its own pinned hero, never the grid)
  const liveSim = useMemo(() => (data ?? []).find((s: any) => s.live === true), [data])
  const filteredSims = useMemo(() => {
    if (!data) return []
    return data.filter(sim => {
      if ((sim as any).live === true) return false
      const matchesSearch = sim.name.toLowerCase().includes(searchQuery.toLowerCase())
      const status = getStatus(sim).toUpperCase()
      const matchesStatus = statusFilter === "ALL" || status === statusFilter
      return matchesSearch && matchesStatus
    })
  }, [data, searchQuery, statusFilter])

  // Aggregate stats
  const totalWorlds = data?.length ?? 0
  const activeCount = data?.filter(s => getStatus(s) === "Running" || getStatus(s) === "Ready").length ?? 0

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Hero & Mission Overview */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-slate-900 via-slate-900/90 to-cyan-950/40 border border-slate-800 p-6 shadow-2xl">
        <div className="absolute top-0 right-0 w-96 h-96 bg-cyan-500/5 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="flex h-2 w-2 rounded-full bg-cyan-400 animate-pulse" />
              <span className="text-xs font-mono uppercase tracking-wider text-cyan-400 font-semibold">GCC Spatial Intelligence Network</span>
            </div>
            <h2 className="text-3xl font-bold text-white tracking-tight">Select Simulation</h2>
            <p className="text-sm text-slate-400 mt-1 max-w-xl">
              Launch an existing Chennai hydrodynamic scenario, explore urban inundation models, or initialize a new simulation world.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={handleCreate}
              className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white rounded-xl text-sm font-semibold shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/30 transition duration-150 transform hover:-translate-y-0.5"
            >
              <Plus className="w-4 h-4" />
              Create
            </button>
            <button
              onClick={handleImportClick}
              className="flex items-center gap-2 px-4 py-2.5 bg-slate-800/90 hover:bg-slate-700 text-slate-200 hover:text-white rounded-xl text-sm font-medium border border-slate-700 transition duration-150 shadow"
            >
              <Upload className="w-4 h-4 text-slate-400" />
              Import
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".matsya,.zip"
              className="hidden"
              onChange={handleImportChange}
              data-testid="import-input"
            />
          </div>
        </div>

        {/* Quick System Telemetry Counters */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6 pt-6 border-t border-slate-800/80 text-xs">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-slate-800/80 border border-slate-700/60 text-cyan-400">
              <Layers className="w-4 h-4" />
            </div>
            <div>
              <div className="text-slate-400">Simulations</div>
              <div className="text-base font-bold text-white font-mono">{totalWorlds} Scenarios</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-slate-800/80 border border-slate-700/60 text-emerald-400">
              <Activity className="w-4 h-4" />
            </div>
            <div>
              <div className="text-slate-400">Engine Status</div>
              <div className="text-base font-bold text-emerald-400 font-mono">Ready ({activeCount} Active)</div>
            </div>
          </div>
          {/* static marketing numbers (not from API) */}
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-slate-800/80 border border-slate-700/60 text-blue-400">
              <Compass className="w-4 h-4" />
            </div>
            <div>
              <div className="text-slate-400">SWD Network</div>
              <div className="text-base font-bold text-white font-mono">10,257 Conduits</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-slate-800/80 border border-slate-700/60 text-purple-400">
              <Radio className="w-4 h-4" />
            </div>
            <div>
              <div className="text-slate-400">Waterbodies</div>
              <div className="text-base font-bold text-white font-mono">4,086 Tanks & Lakes</div>
            </div>
          </div>
        </div>
      </div>

      {/* Action error banner */}
      {actionError && (
        <div 
          role="alert"
          aria-live="assertive"
          className="p-4 bg-rose-950/50 border border-rose-800 text-rose-300 rounded-xl text-sm flex items-center justify-between gap-3 shadow-lg"
        >
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
            <span>{actionError}</span>
          </div>
          <button 
            type="button" 
            onClick={() => setActionError(null)}
            aria-label="Dismiss error notification"
            className="p-1 rounded-lg text-rose-400 hover:text-white hover:bg-rose-900/40 transition focus-ring"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Search & Filter Toolbar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-slate-900/60 p-3 rounded-xl border border-slate-800/80">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter simulations by name..."
            className="w-full bg-slate-950/80 border border-slate-700/80 rounded-lg pl-9 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition"
          />
        </div>

        <div className="flex items-center gap-1.5 self-start sm:self-auto overflow-x-auto w-full sm:w-auto">
          {["ALL", "READY", "RUNNING", "COMPLETED"].map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                statusFilter === status
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                  : "bg-slate-800/50 text-slate-400 hover:text-slate-200 border border-transparent"
              }`}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="text-center py-20 bg-slate-900/30 rounded-2xl border border-slate-800/60">
          <div className="inline-block w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin mb-3" />
          <div className="text-slate-400 text-sm font-medium">Loading simulation database…</div>
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="text-center py-16 bg-rose-950/20 rounded-2xl border border-rose-900/40 p-6">
          <AlertTriangle className="w-10 h-10 text-rose-400 mx-auto mb-3" />
          <div className="text-rose-300 font-semibold mb-1">Failed to load simulations</div>
          <p className="text-xs text-rose-400/80 max-w-md mx-auto mb-4">{error}</p>
          <button
            onClick={() => refetch()}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium border border-slate-700"
          >
            Retry Connection
          </button>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && (!data || data.length === 0) && (
        <div className="text-center py-20 border-2 border-dashed border-slate-800 rounded-2xl bg-slate-900/40 p-8">
          <div className="w-16 h-16 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 mx-auto mb-4">
            <Compass className="w-8 h-8" />
          </div>
          <h3 className="text-lg font-bold text-white mb-1">No Simulation Worlds Configured</h3>
          <p className="text-slate-400 text-sm max-w-md mx-auto mb-6">
            Initialize your first Chennai metropolitan flood scenario to analyze storm water dynamics and road inundation.
          </p>
          <button
            onClick={handleCreate}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-cyan-500 to-blue-600 text-white rounded-xl text-sm font-semibold shadow-lg shadow-cyan-500/20"
          >
            <Plus className="w-4 h-4" />
            Create your first simulation
          </button>
        </div>
      )}

      {/* Singular live entry — the one realtime sim, pinned above the grid */}
      {!loading && liveSim && (
        <div
          data-testid="live-hero"
          className="mb-6 rounded-2xl border border-emerald-500/40 bg-emerald-500/5 p-5 flex flex-col sm:flex-row sm:items-center gap-4"
        >
          <span className="relative flex h-3 w-3 shrink-0">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />
            <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-400" />
          </span>
          <div className="flex-1 min-w-0">
            <div className="text-[10px] font-mono text-emerald-300 font-semibold tracking-wider uppercase">LIVE • updating</div>
            <h3 className="text-white font-bold text-lg leading-snug truncate">{liveSim.name}</h3>
            <div className="text-[11px] text-slate-400 font-mono mt-0.5">
              {formatRainfall((liveSim as any).rainfall, true)} • updated {formatLastModified(liveSim)}
            </div>
          </div>
          <button
            onClick={() => handleOpen(liveSim.id)}
            className="flex items-center justify-center gap-2 px-6 py-2.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white rounded-xl text-xs font-bold shadow-md transition shrink-0"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            Open
          </button>
        </div>
      )}

      {/* Simulations Grid */}
      {!loading && filteredSims && filteredSims.length > 0 && (
        <div data-testid="sim-grid" className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredSims.map((sim) => {
            const status = getStatus(sim)
            const style = statusBadgeStyles[status] ?? statusBadgeStyles.Ready
            const bbox = (sim as any).area?.bbox
            const rainfall = (sim as any).rainfall

            return (
              <div
                key={sim.id}
                className="group glass-card rounded-2xl border border-slate-800 hover:border-cyan-500/50 transition-all duration-200 flex flex-col overflow-hidden hover:shadow-xl hover:shadow-cyan-950/30"
              >
                {/* Visual Card Banner with topographic styling */}
                <div className="h-20 w-full relative bg-gradient-to-br from-slate-800 via-slate-850 to-slate-900 border-b border-slate-800/80 p-4 flex items-center justify-between overflow-hidden">
                  <div className="absolute inset-0 opacity-10 bg-[radial-gradient(#38bdf8_1px,transparent_1px)] [background-size:12px_12px]" />
                  <div className="relative z-10">
                    <span className="text-[10px] font-mono text-cyan-400 font-semibold tracking-wider uppercase">SIMULATION WORLD</span>
                    <h3 className="text-white font-bold text-base leading-snug line-clamp-1 group-hover:text-cyan-300 transition">{sim.name}</h3>
                  </div>

                  <div className="relative z-10">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${style.badge}`}>
                      <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
                      {status}
                    </span>
                  </div>
                </div>

                {/* Body Metrics */}
                <div className="p-5 flex-1 flex flex-col justify-between space-y-4">
                  <div className="space-y-2.5 text-xs">
                    <div className="flex items-center justify-between py-1 border-b border-slate-800/60">
                      <span className="flex items-center gap-1.5 text-slate-400">
                        <MapPin className="w-3.5 h-3.5 text-slate-500" />
                        Area Bounds
                      </span>
                      <span className="text-slate-200 font-mono text-[11px]">{formatBbox(bbox)}</span>
                    </div>

                    <div className="flex items-center justify-between py-1 border-b border-slate-800/60">
                      <span className="flex items-center gap-1.5 text-slate-400">
                        <CloudRain className="w-3.5 h-3.5 text-cyan-400" />
                        Precipitation
                      </span>
                      <span className="text-cyan-300 font-mono font-medium">{formatRainfall(rainfall)}</span>
                    </div>

                    <div className="flex items-center justify-between py-1">
                      <span className="flex items-center gap-1.5 text-slate-400">
                        <Clock className="w-3.5 h-3.5 text-slate-500" />
                        Last modified
                      </span>
                      <span className="text-slate-400">{formatLastModified(sim)}</span>
                    </div>
                  </div>

                  {/* Primary & Secondary Actions */}
                  <div className="space-y-2 pt-2">
                    <button
                      onClick={() => handleOpen(sim.id)}
                      className="w-full flex items-center justify-center gap-2 py-2.5 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white rounded-xl text-xs font-bold shadow-md shadow-blue-900/30 transition transform hover:-translate-y-0.5"
                    >
                      <Play className="w-3.5 h-3.5 fill-current" />
                      Open
                    </button>

                    <div className="grid grid-cols-4 gap-1.5">
                      <button
                        onClick={() => handleEdit(sim)}
                        title="Edit parameters"
                        className="flex items-center justify-center gap-1 py-1.5 bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg text-xs font-medium border border-slate-700/60 transition"
                      >
                        <Edit3 className="w-3 h-3 text-slate-400" />
                        Edit
                      </button>
                      <button
                        onClick={() => handleDuplicate(sim)}
                        title="Duplicate world"
                        className="flex items-center justify-center gap-1 py-1.5 bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg text-xs font-medium border border-slate-700/60 transition"
                      >
                        <Copy className="w-3 h-3 text-slate-400" />
                        Copy
                      </button>
                      <button
                        onClick={() => handleExport(sim)}
                        title="Export .matsya archive"
                        className="flex items-center justify-center gap-1 py-1.5 bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg text-xs font-medium border border-slate-700/60 transition"
                      >
                        <Download className="w-3 h-3 text-cyan-400" />
                        Export
                      </button>
                      <button
                        onClick={() => setDeleteTarget(sim)}
                        title="Delete simulation"
                        className="flex items-center justify-center gap-1 py-1.5 bg-slate-800/80 hover:bg-rose-900/60 text-slate-400 hover:text-rose-300 rounded-lg text-xs font-medium border border-slate-700/60 hover:border-rose-800/60 transition"
                      >
                        <Trash2 className="w-3 h-3 text-rose-400" />
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* In-App Delete Confirmation Modal */}
      {deleteTarget && (
        <div 
          className="fixed inset-0 z-[9999] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-150"
          onClick={() => setDeleteTarget(null)}
        >
          <div 
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-dialog-title"
            className="glass-panel w-full max-w-md rounded-2xl p-6 border border-slate-800 shadow-2xl space-y-4"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-full bg-rose-500/20 border border-rose-500/30 text-rose-400">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div>
                <h4 id="delete-dialog-title" className="text-base font-bold text-white">Delete Simulation World?</h4>
                <p className="text-xs text-slate-400">This action will remove all saved rasters and parameters.</p>
              </div>
            </div>

            <div className="p-3 bg-slate-950/80 rounded-xl border border-slate-800 text-xs font-mono text-slate-300">
              Target: <span className="text-white font-bold">{deleteTarget.name}</span>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setDeleteTarget(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold transition focus-ring"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmDelete}
                className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-rose-600/30 transition focus-ring"
              >
                Confirm Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* In-App Rename Modal */}
      {renameTarget && (
        <div 
          className="fixed inset-0 z-[9999] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-150"
          onClick={() => setRenameTarget(null)}
        >
          <div 
            role="dialog"
            aria-modal="true"
            aria-labelledby="rename-dialog-title"
            className="glass-panel w-full max-w-md rounded-2xl p-6 border border-slate-800 shadow-2xl space-y-4"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-full bg-cyan-500/20 border border-cyan-500/30 text-cyan-400">
                <Edit3 className="w-6 h-6" />
              </div>
              <div>
                <h4 id="rename-dialog-title" className="text-base font-bold text-white">Rename Simulation</h4>
                <p className="text-xs text-slate-400">Enter a descriptive title for this scenario.</p>
              </div>
            </div>

            <div>
              <label htmlFor="rename-input-name" className="sr-only">Simulation Scenario Name</label>
              <input
                id="rename-input-name"
                type="text"
                value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") confirmRename()
                  if (e.key === "Escape") setRenameTarget(null)
                }}
                className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500 focus-ring transition"
                autoFocus
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setRenameTarget(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold transition focus-ring"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmRename}
                className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-cyan-600/30 transition focus-ring"
              >
                Save Name
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  )
}

