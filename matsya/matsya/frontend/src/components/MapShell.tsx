
import { useEffect, useState } from "react"
import MapView from "./MapView"
import LayerPanel from "./LayerPanel"
import Timeline from "./Timeline"
import PointInspector from "./PointInspector"
import SearchBar from "./SearchBar"
import AffectedAreas from "./AffectedAreas"
import InfraImpact from "./InfraImpact"
import Reports from "./Reports"
import LiveStatus from "./LiveStatus"
import HydroLayer from "./HydroLayer"
import WaterbodyInspector from "./WaterbodyInspector"
import type { Simulation } from "../types/simulation"
import SafeRoute from "./SafeRoute"
import {
  Layers,
  Crosshair,
  AlertTriangle,
  FileText,
  Navigation,
  PanelRightClose,
  PanelRightOpen
} from "lucide-react"

export default function MapShell({ simulation }: { simulation: Simulation }) {
  const [selectedPoint, setSelectedPoint] = useState<any>(null)
  const [selectedWaterbody, setSelectedWaterbody] = useState<string | null>(null)
  const [time, setTime] = useState(0)
  const floodSteps = Number((simulation as any)?.flood?.steps ?? (simulation as any)?.flood?.stats?.steps ?? 73) || 73
  const tmax = Math.max(0, floodSteps - 1)
  const mpf = Number((simulation as any)?.flood?.stats?.minutesPerFrame ?? 5) || 5
  useEffect(() => { setTime(t => Math.min(t, tmax)) }, [tmax])
  useEffect(() => { setRoute(null) }, [simulation.id])
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [activeTab, setActiveTab] = useState<"LAYERS" | "INSPECTOR" | "IMPACTS" | "REPORTS" | "ROUTES" | "ALL">("LAYERS")
  const [route, setRoute] = useState<{ safest: [number, number][]; fastest: [number, number][] | null; dest: { lat: number; lon: number } } | null>(null)

  const [layers, setLayers] = useState<any>({
    depth:{visible:true,opacity:0.8},
    terrain:{visible:false,opacity:0.7},
    drainage:{visible:true,opacity:0.7},
    hydro:{visible:true,opacity:0.8},
    water:{visible:true,opacity:0.7},
    infra:{visible:true,opacity:0.8},
    other:{visible:false,opacity:0.7},
    roads:{visible:true},
    buildings:{visible:true},
    rivers:{visible:true},
    canals:{visible:true}
  })

  // When point or waterbody selected, automatically switch to inspector tab and open sidebar
  const handlePointSelect = (p: any) => {
    setSelectedPoint(p)
    setActiveTab("INSPECTOR")
    setSidebarOpen(true)
  }

  const handleWaterbodySelect = (wbId: string) => {
    setSelectedWaterbody(wbId)
    setActiveTab("INSPECTOR")
    setSidebarOpen(true)
  }

  const toggleLayer = (layerKey: string) => {
    setLayers((prev: any) => ({
      ...prev,
      [layerKey]: {
        ...prev[layerKey],
        visible: !prev[layerKey]?.visible
      }
    }))
  }

  return (
    <div className="flex flex-col h-[calc(100vh-64px)] gap-0 bg-[#070A0F] text-slate-100 overflow-hidden">
      <div className="flex flex-1 overflow-hidden min-h-0 relative">

        {/* Map Viewport */}
        <div className="flex-1 relative bg-slate-950 min-h-0 min-w-0">
          <div className="absolute inset-0">
            <MapView
              key={simulation.id}
              simulation={simulation}
              layers={layers}
              time={Math.min(time, tmax)}
              onPointSelect={handlePointSelect}
              onWaterbodySelect={handleWaterbodySelect}
              route={route}
            />
          </div>

          {/* Floating Search Bar & Quick Hotspot Navigator */}
          <div className="absolute top-3 left-3 z-[400] space-y-2">
            <SearchBar />
          </div>

          {/* Floating Quick Layer Toggle Pills on Map - Commented out to declutter map view */}
          {/*
          <div className="absolute top-3 left-1/2 -translate-x-1/2 z-[400] hidden md:flex items-center gap-1.5 p-1 rounded-xl glass-panel border border-slate-700/80 shadow-2xl text-[11px] font-mono">
            <button
              onClick={() => toggleLayer("depth")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-semibold transition ${
                layers.depth?.visible
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${layers.depth?.visible ? "bg-cyan-400" : "bg-slate-600"}`} />
              Flood Inundation
            </button>

            <button
              onClick={() => toggleLayer("terrain")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-semibold transition ${
                layers.terrain?.visible
                  ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${layers.terrain?.visible ? "bg-emerald-400" : "bg-slate-600"}`} />
              CartoDEM 30m
            </button>

            <button
              onClick={() => toggleLayer("drainage")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-semibold transition ${
                layers.drainage?.visible
                  ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${layers.drainage?.visible ? "bg-indigo-400" : "bg-slate-600"}`} />
              Drains (10k)
            </button>

            <button
              onClick={() => toggleLayer("water")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-semibold transition ${
                layers.water?.visible
                  ? "bg-sky-500/20 text-sky-300 border border-sky-500/40 shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${layers.water?.visible ? "bg-sky-400" : "bg-slate-600"}`} />
              Waterbodies (4k)
            </button>
          </div>
          */}

          {/* Floating Live Telemetry Badge */}
          <div className="absolute top-3 right-3 z-[400] hidden sm:block">
            <LiveStatus />
          </div>

          {/* Floating Toggle Sidebar Button on Map */}
          <div className="absolute bottom-4 right-4 z-[400]">
            <button
              type="button"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              aria-label={sidebarOpen ? "Collapse analytical panel" : "Expand analytical panel"}
              aria-expanded={sidebarOpen}
              className="p-3 rounded-xl glass-panel text-slate-300 hover:text-white shadow-xl transition hover:border-cyan-500/50 focus-ring"
              title={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
            >
              {sidebarOpen ? <PanelRightClose className="w-4 h-4" /> : <PanelRightOpen className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Mobile Backdrop Overlay */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[450] md:hidden animate-in fade-in duration-150"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
        )}

        {/* Analytical Command Sidebar (Slide-over drawer on mobile, docked on desktop) */}
        {sidebarOpen && (
          <aside
            role="region"
            aria-label="Analytical panels and layers"
            className="fixed inset-y-0 right-0 z-[500] w-[90vw] max-w-sm md:static md:w-[380px] md:h-auto md:shrink-0 border-l border-slate-800 bg-[#0B0F17] flex flex-col overflow-hidden shadow-2xl transition-all duration-200"
          >
            {/* Mobile Header with Close Button */}
            <div className="flex items-center justify-between px-3.5 py-2.5 bg-slate-950/90 border-b border-slate-800/80 md:hidden">
              <span className="text-xs font-mono font-bold text-white flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-cyan-400" />
                ANALYTICAL TELEMETRY
              </span>
              <button
                type="button"
                onClick={() => setSidebarOpen(false)}
                aria-label="Close analytical drawer"
                className="p-1 rounded-lg text-slate-400 hover:text-white transition focus-ring"
              >
                <PanelRightClose className="w-4 h-4" />
              </button>
            </div>

            {/* Sidebar Navigation Tabs */}
            <div
              role="tablist"
              aria-label="Analytical views"
              className="flex border-b border-slate-800/90 bg-slate-950/80 p-1.5 gap-1 shrink-0 overflow-x-auto text-[11px] font-semibold font-mono"
            >
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === "LAYERS"}
                onClick={() => setActiveTab("LAYERS")}
                className={`flex items-center gap-1 px-3 py-1.5 rounded-lg transition focus-ring ${
                  activeTab === "LAYERS"
                    ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <Layers className="w-3.5 h-3.5" />
                Layers
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === "INSPECTOR"}
                onClick={() => setActiveTab("INSPECTOR")}
                className={`flex items-center gap-1 px-3 py-1.5 rounded-lg transition focus-ring ${
                  activeTab === "INSPECTOR"
                    ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <Crosshair className="w-3.5 h-3.5" />
                Inspect
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === "IMPACTS"}
                onClick={() => setActiveTab("IMPACTS")}
                className={`flex items-center gap-1 px-3 py-1.5 rounded-lg transition focus-ring ${
                  activeTab === "IMPACTS"
                    ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <AlertTriangle className="w-3.5 h-3.5" />
                Risk Zones
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === "REPORTS"}
                onClick={() => setActiveTab("REPORTS")}
                className={`flex items-center gap-1 px-3 py-1.5 rounded-lg transition focus-ring ${
                  activeTab === "REPORTS"
                    ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                Exports
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === "ROUTES"}
                onClick={() => setActiveTab("ROUTES")}
                className={`flex items-center gap-1 px-3 py-1.5 rounded-lg transition focus-ring ${
                  activeTab === "ROUTES"
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <Navigation className="w-3.5 h-3.5" />
                Safe Route
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === "ALL"}
                onClick={() => setActiveTab("ALL")}
                className={`px-2.5 py-1.5 rounded-lg transition focus-ring ${
                  activeTab === "ALL"
                    ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                All
              </button>
            </div>

            {/* Scrollable Panel Area */}
            <div className="flex-1 overflow-y-auto divide-y divide-slate-800/80">
              {(activeTab === "ALL" || activeTab === "LAYERS") && (
                <>
                  <HydroLayer simId={simulation.id} />
                  <LayerPanel layers={layers} onChange={setLayers} simulation={simulation} />
                </>
              )}

              {(activeTab === "ALL" || activeTab === "INSPECTOR") && (
                <>
                  <PointInspector point={selectedPoint} />
                  <WaterbodyInspector waterbodyId={selectedWaterbody} />
                </>
              )}

              {(activeTab === "ALL" || activeTab === "IMPACTS") && (
                <>
                  <AffectedAreas simulation={simulation} />
                  <InfraImpact simulation={simulation} />
                </>
              )}

              {(activeTab === "ALL" || activeTab === "REPORTS") && (
                <Reports simulation={simulation} />
              )}

              {(activeTab === "ALL" || activeTab === "ROUTES") && (
                <SafeRoute
                  simulation={simulation}
                  timeMin={Math.min(time, tmax) * mpf}
                  origin={selectedPoint ? { lat: selectedPoint.lat, lon: selectedPoint.lon } : null}
                  onSelectRoute={setRoute}
                />
              )}
            </div>
          </aside>
        )}
      </div>

      {/* Persistent Bottom Timeline */}
      <Timeline time={Math.min(time, tmax)} onChange={setTime} max={tmax} minutesPerFrame={mpf} />
    </div>
  )
}
