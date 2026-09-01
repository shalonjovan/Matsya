import { useEffect, useState, useCallback } from "react"
import type { Simulation } from "../types/simulation"

export const API_BASE = "/api"

export async function fetchSimulations(): Promise<Simulation[]> {
  const res = await fetch(`${API_BASE}/simulations`)
  if (!res.ok) throw new Error(`GET /api/simulations failed: ${res.status}`)
  const data = await res.json()
  return Array.isArray(data) ? data : []
}

export async function deleteSimulation(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/simulations/${id}`, { method: "DELETE" })
  if (!res.ok) throw new Error(`DELETE failed: ${res.status}`)
}

export async function duplicateSimulation(id: string, name?: string): Promise<Simulation> {
  const res = await fetch(`${API_BASE}/simulations/${id}/duplicate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(name ? { name } : {}),
  })
  if (!res.ok) throw new Error(`Duplicate failed: ${res.status}`)
  return res.json()
}

export async function exportSimulation(id: string, fallbackName = "simulation"): Promise<void> {
  const res = await fetch(`${API_BASE}/simulations/${id}/export`)
  if (!res.ok) throw new Error(`Export failed: ${res.status}`)
  const blob = await res.blob()
  // try to get filename from Content-Disposition
  let filename = `${fallbackName}.matsya`
  const disposition = res.headers.get("Content-Disposition")
  if (disposition) {
    const match = disposition.match(/filename="?([^"]+)"?/)
    if (match?.[1]) filename = match[1]
  }
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export async function importSimulation(file: File): Promise<Simulation> {
  const fd = new FormData()
  fd.append("file", file)
  const res = await fetch(`${API_BASE}/simulations/import`, {
    method: "POST",
    body: fd,
  })
  if (!res.ok) throw new Error(`Import failed: ${res.status}`)
  return res.json()
}

export async function renameSimulation(id: string, name: string): Promise<Simulation> {
  const res = await fetch(`${API_BASE}/simulations/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  })
  if (!res.ok) throw new Error(`Rename failed: ${res.status}`)
  return res.json()
}

// Simple in-memory cache for simulations list — 30s staleTime
let simCache: { data: Simulation[] | null, ts: number } = { data: null, ts: 0 }
const CACHE_TTL = 30000 // 30s

export function useSimulations() {
  const [data, setData] = useState<Simulation[] | null>(simCache.data)
  const [loading, setLoading] = useState(simCache.data === null)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async (force=false) => {
    const now = Date.now()
    if (!force && simCache.data && (now - simCache.ts < CACHE_TTL)) {
      setData(simCache.data)
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const sims = await fetchSimulations()
      simCache = { data: sims, ts: now }
      setData(sims)
    } catch (e: any) {
      setError(e?.message ?? "failed to fetch")
      setData([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refetch()
  }, [refetch])

  // Also invalidate cache on mutations
  const refetchForce = useCallback(()=> refetch(true), [refetch])

  return { data, loading, error, refetch: refetchForce, setData }
}

// also export singular alias for spec compatibility
export const useSimulation = useSimulations
export default useSimulations
