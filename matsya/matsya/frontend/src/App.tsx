import { useEffect, useState } from "react"
import SelectSimulation from "./components/SelectSimulation"
import CreateWizard from "./components/CreateWizard"
import MapShell from "./components/MapShell"
import Event2015 from "./components/Event2015"
import HomePage from "./components/HomePage"
import type { Simulation } from "./types/simulation"
import { fetchSimulations } from "./hooks/useSimulation"
import {
  Waves,
  Map as MapIcon,
  LayoutGrid,
  Plus,
  Clock,
  Cpu,
  Sun,
  Moon,
  Home as HomeIcon
} from "lucide-react"
import { ThemeProvider, useTheme } from "./components/ThemeContext"

function ThemeToggle() {
  const { theme, toggle } = useTheme()
  const dark = theme === "dark"
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      title={dark ? "Switch to light mode" : "Switch to dark mode"}
      className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border border-slate-700/80 bg-slate-900/80 text-slate-300 hover:text-white transition focus-ring"
    >
      {dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
    </button>
  )
}

function getWorldIdFromHash(): string | null {
  const hash = typeof window !== "undefined" ? window.location.hash : ""
  if (hash.startsWith("#/world/")) {
    const id = hash.slice("#/world/".length)
    return id.split("?")[0].split("/")[0] || null
  }
  return null
}

/** The landing page owns the bare `#/` route; the simulations list lives at `#/simulations`. */
function isHomeHash(): boolean {
  const hash = typeof window !== "undefined" ? window.location.hash : ""
  return hash === "" || hash === "#/" || hash === "#/home"
}

function App() {
  const [worldId, setWorldId] = useState<string | null>(() => getWorldIdFromHash())
  const [event2015, setEvent2015] = useState<boolean>(() => typeof window !== "undefined" && window.location.hash === "#/event/2015")
  const [showHome, setShowHome] = useState<boolean>(() => isHomeHash())
  const [showSelect, setShowSelect] = useState<boolean>(() => !isHomeHash() && getWorldIdFromHash() === null)
  const [wizardOpen, setWizardOpen] = useState(false)
  const [editSim, setEditSim] = useState<Simulation | null>(null)
  const [currentSim, setCurrentSim] = useState<Simulation | null>(null)
  const [currentTime, setCurrentTime] = useState<string>("")

  // Live digital clock (IST)
  useEffect(() => {
    const updateTime = () => {
      const d = new Date()
      setCurrentTime(d.toLocaleTimeString("en-IN", { hour12: false }))
    }
    updateTime()
    const id = setInterval(updateTime, 1000)
    return () => clearInterval(id)
  }, [])

  // Per-view document title (Home · Simulations · Map · 2015 Replay)
  useEffect(() => {
    const title = event2015
      ? "Chennai Dec 2015 Replay · MATSYA"
      : showHome
        ? "MATSYA — Urban Flood Nowcasting Twin for Chennai"
        : worldId
          ? `${currentSim?.name ?? "Flood Map"} · MATSYA`
          : "Simulations · MATSYA"
    document.title = title
  }, [event2015, showHome, worldId, currentSim])

  useEffect(() => {
    const onHashChange = () => {
      if (typeof window !== "undefined" && window.location.hash === "#/event/2015") {
        setEvent2015(true)
        return
      }
      setEvent2015(false)
      const onHome = isHomeHash()
      setShowHome(onHome)
      const wid = getWorldIdFromHash()
      setWorldId(wid)
      setShowSelect(!onHome && wid === null)
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

  const navigateHome = () => {
    window.location.hash = "#/"
    setShowHome(true)
    setWorldId(null)
    setShowSelect(false)
  }

  const navigateSelect = () => {
    window.location.hash = "#/simulations"
    setShowHome(false)
    setWorldId(null)
    setShowSelect(true)
  }

  const navigateEvent2015 = () => {
    window.location.hash = "#/event/2015"
    setEvent2015(true)
    setShowHome(false)
  }

  const navigateWorld = (id: string) => {
    window.location.hash = `#/world/${id}`
    setWorldId(id)
    setShowHome(false)
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
    <ThemeProvider>
    <div className="min-h-screen bg-[#070A0F] text-slate-100 flex flex-col selection:bg-cyan-500 selection:text-black">
      {/* Precision Operations Center Header */}
      <header className="h-16 flex items-center justify-between px-5 bg-slate-950/90 border-b border-slate-800/80 sticky top-0 z-30 backdrop-blur-xl">
        {/* Brand & System Status */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3 cursor-pointer" onClick={navigateSelect}>
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-600 via-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20 border border-cyan-400/30">
              <Waves className="w-5 h-5 text-white animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-black tracking-tight text-white font-mono">MATSYA</h1>
                <span className="px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 text-[10px] font-mono font-bold border border-cyan-500/20 tracking-wider">
                  v2.0-HYDRA
                </span>
              </div>
              {/* Header subtitle - Commented out to declutter header */}
              {/*
              <div className="text-[10px] font-mono text-slate-400 hidden sm:block">
                URBAN FLOOD TWIN • GREATER CHENNAI
              </div>
              */}
            </div>
          </div>

          <div className="h-6 w-px bg-slate-800 hidden md:block" />

          {/* Segmented View Switcher */}
          <nav className="flex items-center bg-slate-900/90 p-1 rounded-xl border border-slate-800 font-mono text-xs">
            <button
              onClick={navigateHome}
              className={`flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-lg font-semibold transition ${
                showHome
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <HomeIcon className="w-3.5 h-3.5" />
              <span>Home</span>
            </button>
            <button
              onClick={navigateSelect}
              className={`flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-lg font-semibold transition ${
                showSelect && !worldId && !showHome
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <LayoutGrid className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Select Simulation</span>
              <span className="sm:hidden">Sims</span>
            </button>
            <button
              onClick={() => {
                setShowHome(false)
                setEvent2015(false)
                if (worldId) {
                  setShowSelect(false)
                } else {
                  window.location.hash = "#/world/demo"
                  setWorldId("demo")
                  setShowSelect(false)
                }
              }}
              className={`flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-lg font-semibold transition ${
                !showSelect && !showHome && !event2015
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <MapIcon className="w-3.5 h-3.5" />
              <span>Map</span>
            </button>
            <button
              onClick={navigateEvent2015}
              className={`flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-lg font-semibold transition ${
                event2015
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <MapIcon className="w-3.5 h-3.5" />
              <span>2015 Replay</span>
            </button>
          </nav>
        </div>

        {/* Right Telemetry & Actions */}
        <div className="flex items-center gap-2 sm:gap-3">
          <ThemeToggle />
          {/* Live Clock IST */}
          <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 bg-slate-900/80 rounded-xl border border-slate-800 text-xs font-mono text-slate-300">
            <Clock className="w-3.5 h-3.5 text-cyan-400" />
            <span>{currentTime || "00:00:00"} IST</span>
          </div>

          {/* World context indicator - Commented out to declutter header */}
          {/*
          {worldId && (
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-slate-900/80 rounded-xl border border-slate-800 text-xs font-mono text-cyan-400">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
              <span className="text-slate-400">world:</span>
              <span className="font-bold text-white max-w-[80px] truncate">{worldId}</span>
            </div>
          )}
          */}

          {/* Quick Scenario Setup */}
          <button
            onClick={handleCreate}
            className="flex items-center gap-1.5 px-3 sm:px-3.5 py-1.5 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 font-bold text-xs rounded-xl shadow-lg shadow-cyan-500/20 transition focus-ring"
          >
            <Plus className="w-4 h-4" />
            <span className="hidden sm:inline">New Scenario</span>
            <span className="sm:hidden">New</span>
          </button>
        </div>
      </header>

      {/* Main Operations Area */}
      <main className={`flex-1 ${showHome || (!showSelect && worldId) ? "p-0" : "p-4 sm:p-6 max-w-7xl mx-auto w-full"}`}>
        {event2015 ? (
          <Event2015 />
        ) : showHome ? (
          <HomePage onLaunch={navigateSelect} onReplay2015={navigateEvent2015} />
        ) : showSelect || !worldId ? (
          <SelectSimulation onOpen={handleOpen} onCreate={handleCreate} onEdit={handleEdit} />
        ) : currentSim ? (
          <MapShell key={currentSim.id} simulation={currentSim} />
        ) : (
          <div className="p-8 glass-panel rounded-2xl border border-slate-800 text-center max-w-lg mx-auto my-12 space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center mx-auto text-cyan-400">
              <Cpu className="w-6 h-6 animate-pulse" />
            </div>
            <h2 className="text-lg font-bold text-white font-mono">World {worldId}</h2>
            <p className="text-sm text-slate-400">Loading simulation telemetry & raster data…</p>
            <div className="h-32 bg-slate-950/60 rounded-xl border border-slate-800/80 flex items-center justify-center text-xs text-slate-400 font-mono">
              Connecting to hydrodynamic computation node…
            </div>
            <button
              onClick={navigateSelect}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-semibold border border-slate-700 transition focus-ring"
            >
              Back to Simulations
            </button>
          </div>
        )}
      </main>


      <CreateWizard
        open={wizardOpen}
        onClose={()=>{setWizardOpen(false); setEditSim(null)}}
        onCreated={handleCreated}
        editSim={editSim}
      />
    </div>
    </ThemeProvider>
  )
}

export default App
