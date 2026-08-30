import { useEffect, useState } from "react"
import SelectSimulation from "./components/SelectSimulation"

function getWorldIdFromHash(): string | null {
  const hash = typeof window !== "undefined" ? window.location.hash : ""
  if (hash.startsWith("#/world/")) {
    const id = hash.slice("#/world/".length)
    // strip query/hash extras, take first segment before ? or /
    return id.split("?")[0].split("/")[0] || null
  }
  return null
}

function App() {
  const [worldId, setWorldId] = useState<string | null>(() => getWorldIdFromHash())
  const [showSelect, setShowSelect] = useState<boolean>(() => getWorldIdFromHash() === null)

  useEffect(() => {
    const onHashChange = () => {
      const wid = getWorldIdFromHash()
      setWorldId(wid)
      setShowSelect(wid === null)
    }
    window.addEventListener("hashchange", onHashChange)
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
  }

  const handleOpen = (id: string) => navigateWorld(id)

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
                // if no world selected, go to placeholder map
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
          <SelectSimulation onOpen={handleOpen} />
        ) : (
          <div className="p-6 bg-white rounded-xl shadow border">
            <h2 className="text-lg font-semibold mb-2">Map — world {worldId}</h2>
            <p className="text-sm text-slate-600 mb-4">
              Map view placeholder for simulation {worldId}. Task 2.1 will implement Leaflet map here.
            </p>
            <button onClick={navigateSelect} className="px-3 py-1.5 bg-slate-800 text-white rounded text-sm">
              Back to Select Simulation
            </button>
          </div>
        )}
      </main>
    </div>
  )
}

export default App
