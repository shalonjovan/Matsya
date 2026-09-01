
import { useState } from "react"
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

export default function MapShell({ simulation }: { simulation: Simulation }) {
  const [selectedPoint, setSelectedPoint] = useState<any>(null)
  const [selectedWaterbody, setSelectedWaterbody] = useState<string | null>(null)
  const [time, setTime] = useState(0)
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
  return (
    <div className="flex flex-col h-[calc(100vh-64px)] gap-0">
      <div className="flex flex-1 overflow-hidden border rounded-xl shadow min-h-0">
        <div className="flex-1 relative bg-slate-900 min-h-0 min-w-0">
          <div className="absolute inset-0">
            <MapView key={simulation.id} simulation={simulation} layers={layers} time={time} onPointSelect={setSelectedPoint} onWaterbodySelect={setSelectedWaterbody} />
          </div>
          <div className="absolute top-2 left-2 z-[400] w-64">
            <SearchBar />
          </div>
          <div className="absolute top-2 right-2 z-[400]">
            <LiveStatus />
          </div>
        </div>
        <div className="w-[360px] shrink-0 border-l bg-white flex flex-col overflow-auto">
          <HydroLayer simId={simulation.id} />
          <LayerPanel layers={layers} onChange={setLayers} simulation={simulation} />
          <PointInspector point={selectedPoint} />
          <WaterbodyInspector waterbodyId={selectedWaterbody} />
          <AffectedAreas simulation={simulation} />
          <InfraImpact simulation={simulation} />
          <Reports simulation={simulation} />
        </div>
      </div>
      <Timeline time={time} onChange={setTime} max={72} />
    </div>
  )
}
