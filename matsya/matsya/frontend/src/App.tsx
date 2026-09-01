import { useEffect, useState } from "react"
import SelectSimulation from "./components/SelectSimulation"
import CreateWizard from "./components/CreateWizard"
import MapShell from "./components/MapShell"
import type { Simulation } from "./types/simulation"
import { fetchSimulations } from "./hooks/useSimulation"

function getWorldIdFromHash(): string | null {
  const hash = typeof window !== "undefined" ? window.location.hash : ""
  if (hash.startsWith("#/world/")) {
    const id = hash.slice("#/world/".length)
    return id.split("?")[0].split("/")[0] || null
  }
  return null
}

function App() {
  const [worldId, setWorldId] = useState<string | null>(() => getWorldIdFromHash())
  const [showSelect, setShowSelect] = useState<boolean>(() => getWorldIdFromHash() === null)
  const [wizardOpen, setWizardOpen] = useState(false)
  const [editSim, setEditSim] = useState<Simulation | null>(null)
  const [currentSim, setCurrentSim] = useState<Simulation | null>(null)

  useEffect(() => {
    const onHashChange = () => {
      const wid = getWorldIdFromHash()
      setWorldId(wid)
      setShowSelect(wid === null)
      if (wid) {
        fetch(`/api/simulations/${wid}`).then(r=>r.json()).then(setCurrentSim).catch(()=>setCurrentSim(null))
      }
    }
    window.addEventListener("hashchange", onHashChange)
    if (worldId) {
      fetch(`/api/simulations/${worldId}`).then(r=>r.json()).then(setCurrentSim).catch(()=>{})
    }
    return () => window.removeEventListener("hashchange", onHashChange)
  }, [])

  const navigateSelect = () => {
    window.location.hash = "#/"
    setWorldId(null)
    setShowSelect(true)
  }

  const navigateWorld = (id: string) => {
    window.location.hash = `#/world/${id}`
    setWorldId(id)
    setShowSelect(false)
    fetch(`/api/simulations/${id}`).then(r=>r.json()).then(setCurrentSim).catch(()=>{})
  }

  const handleOpen = (id: string) => navigateWorld(id)
  const handleCreate = () => { setEditSim(null); setWizardOpen(true) }
  const handleEdit = (sim: Simulation) => { setEditSim(sim); setWizardOpen(true) }
  const handleCreated = (sim: Simulation) => {
    // refetch will happen in SelectSimulation, just navigate
    navigateWorld(sim.id)
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="flex items-center gap-4 px-4 py-3 bg-white border-b shadow-sm sticky top-0 z-10">
        <h1 className="text-2xl font-bold tracking-tight">MATSYA</h1>
        <nav className="flex gap-2">
          <button
            onClick={navigateSelect}
            className={`px-3 py-1.5 rounded-md text-sm font-medium border ${
              showSelect && !worldId ? "bg-blue-600 text-white border-blue-600" : "bg-white text-slate-700 border-slate-300"
            }`}
          >
            Select Simulation
          </button>
          <button
            onClick={() => {
              if (worldId) {
                setShowSelect(false)
              } else {
                window.location.hash = "#/world/demo"
                setWorldId("demo")
                setShowSelect(false)
              }
            }}
            className={`px-3 py-1.5 rounded-md text-sm font-medium border ${
              !showSelect ? "bg-blue-600 text-white border-blue-600" : "bg-white text-slate-700 border-slate-300"
            }`}
          >
            Map
          </button>
        </nav>
        {worldId && <span className="ml-auto text-xs text-slate-500 font-mono">world: {worldId}</span>}
      </header>

      <main className="p-4">
        {showSelect || !worldId ? (
          <SelectSimulation onOpen={handleOpen} onCreate={handleCreate} onEdit={handleEdit} />
        ) : currentSim ? (
          <MapShell key={currentSim.id} simulation={currentSim} />
        ) : (
          <div className="p-6 bg-white rounded-xl shadow border">
            <h2 className="text-xl font-semibold">World {worldId}</h2>
            <p className="text-slate-600">Loading simulation…</p>
            <div className="mt-4 h-96 bg-slate-100 rounded flex items-center justify-center">Map placeholder — select a simulation with data</div>
          </div>
        )}
      </main>
      <CreateWizard open={wizardOpen} onClose={()=>{setWizardOpen(false); setEditSim(null)}} onCreated={handleCreated} editSim={editSim} />
    </div>
  )
}

export default App
