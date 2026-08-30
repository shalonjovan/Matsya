import { useRef, useState } from "react"
import { useSimulations, deleteSimulation, duplicateSimulation, exportSimulation, importSimulation, renameSimulation } from "../hooks/useSimulation"
import type { Simulation } from "../types/simulation"

const statusColor: Record<string, string> = {
  Ready: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  Running: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  Completed: "bg-emerald-600/20 text-emerald-300 border-emerald-600/30",
  Incomplete: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  Error: "bg-red-500/20 text-red-400 border-red-500/30",
  Live: "bg-purple-500/20 text-purple-400 border-purple-500/30",
  Offline: "bg-gray-500/20 text-gray-400 border-gray-500/30",
}

function formatBbox(bbox?: [number, number, number, number] | number[]) {
  if (!bbox || bbox.length !== 4) return "—"
  const [minLon, minLat, maxLon, maxLat] = bbox
  // keep 2 decimals for display but preserve if needed
  const fmt = (n: number) => Number(n).toFixed(2)
  return `${fmt(minLon)}-${fmt(maxLon)}, ${fmt(minLat)}-${fmt(maxLat)}`
}

function formatRainfall(rainfall?: { rateMmHr?: number; durationHr?: number } | any) {
  if (!rainfall || rainfall.rateMmHr == null) return "—"
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
    return d.toLocaleString()
  } catch {
    return String(raw)
  }
}

function getStatus(sim: Simulation): string {
  // backend has both top-level status and metadata.status
  const s: any = (sim as any).status ?? (sim as any).metadata?.status ?? "Ready"
  // ensure first letter capitalized, rest as is
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
  const fileRef = useRef<HTMLInputElement | null>(null)

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

  const handleDelete = async (sim: Simulation) => {
    setActionError(null)
    const confirmed = window.confirm(`Delete simulation "${sim.name}"? This cannot be undone.`)
    if (!confirmed) return
    try {
      await deleteSimulation(sim.id)
      await refetch()
    } catch (e: any) {
      setActionError(e?.message ?? "delete failed")
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

  const handleRename = async (sim: Simulation) => {
    setActionError(null)
    const newName = window.prompt("Rename simulation", sim.name)
    if (newName == null || newName.trim() === "" || newName === sim.name) return
    try {
      await renameSimulation(sim.id, newName.trim())
      await refetch()
    } catch (e: any) {
      setActionError(e?.message ?? "rename failed")
    }
  }

  const handleEdit = (sim: Simulation) => {
    if (onEdit) onEdit(sim)
    else handleRename(sim)
  }

  return (
    <div className="min-h-[70vh] bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 rounded-xl p-6 border border-slate-800">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight">Select Simulation</h2>
          <p className="text-sm text-slate-400">Choose a world to explore — or create a new one</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={handleCreate}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-md text-sm font-medium shadow"
          >
            Create
          </button>
          <button
            onClick={handleImportClick}
            className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-md text-sm border border-slate-600"
          >
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

      {actionError && (
        <div className="mb-4 p-3 bg-red-900/30 border border-red-700 text-red-300 rounded text-sm">{actionError}</div>
      )}

      {loading && <div className="text-slate-300 py-8 text-center">Loading simulations…</div>}

      {error && !loading && <div className="text-red-300 py-4 text-center">Failed to load: {error}</div>}

      {!loading && !error && (!data || data.length === 0) && (
        <div className="text-center py-16 border-2 border-dashed border-slate-700 rounded-xl bg-slate-900/50">
          <p className="text-slate-300 mb-3">No simulations yet</p>
          <button onClick={handleCreate} className="px-4 py-2 bg-emerald-600 text-white rounded-md text-sm">
            Create your first simulation
          </button>
        </div>
      )}

      {!loading && data && data.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {data.map((sim) => {
            const status = getStatus(sim)
            const badgeCls = statusColor[status] ?? "bg-slate-700 text-slate-200 border-slate-600"
            const bbox = (sim as any).area?.bbox
            const rainfall = (sim as any).rainfall
            return (
              <div
                key={sim.id}
                className="bg-[#1e293b] border border-[#334155] rounded-xl shadow-md hover:shadow-xl hover:border-slate-500 transition overflow-hidden flex flex-col"
              >
                {/* top accent */}
                <div className="h-1 w-full bg-gradient-to-r from-emerald-500 via-cyan-500 to-blue-500" />
                <div className="p-5 flex-1 flex flex-col">
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <h3 className="text-white font-semibold text-lg leading-tight line-clamp-2 flex-1">{sim.name}</h3>
                    <span
                      className={`px-2.5 py-0.5 rounded-full text-xs font-medium border whitespace-nowrap ${badgeCls}`}
                      title={`Status: ${status}`}
                    >
                      {status}
                    </span>
                  </div>

                  <div className="space-y-2 text-sm flex-1">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Area</span>
                      <span className="text-slate-200 font-mono text-xs text-right">{formatBbox(bbox)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Rainfall</span>
                      <span className="text-slate-200 text-xs text-right">{formatRainfall(rainfall)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Last modified</span>
                      <span className="text-slate-300 text-xs text-right">{formatLastModified(sim)}</span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="mt-5 flex flex-wrap gap-2">
                    <button
                      onClick={() => handleOpen(sim.id)}
                      className="flex-1 min-w-[60px] px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded text-sm font-medium"
                    >
                      Open
                    </button>
                    <button
                      onClick={() => handleEdit(sim)}
                      className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white rounded text-sm border border-slate-600"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleRename(sim)}
                      className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white rounded text-sm border border-slate-600"
                    >
                      Rename
                    </button>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <button
                      onClick={() => handleDuplicate(sim)}
                      className="flex-1 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white rounded text-sm border border-slate-600"
                    >
                      Duplicate
                    </button>
                    <button
                      onClick={() => handleExport(sim)}
                      className="flex-1 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white rounded text-sm border border-slate-600"
                    >
                      Export
                    </button>
                    <button
                      onClick={() => handleDelete(sim)}
                      className="px-3 py-1.5 bg-red-700 hover:bg-red-600 text-white rounded text-sm border border-red-600"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
