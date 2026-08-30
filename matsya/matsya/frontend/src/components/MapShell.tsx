
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
import type { Simulation } from "../types/simulation"

export default function MapShell({ simulation }: { simulation: Simulation }) {
  const [selectedPoint, setSelectedPoint] = useState<any>(null)
  const [time, setTime] = useState(0)
  const [layers, setLayers] = useState<any>({ depth:{visible:true,opacity:0.8}, terrain:{visible:false}, drainage:{visible:true,opacity:0.6}, roads:{visible:true} })
  return (
    <div className="flex flex-col h-[calc(100vh-60px)] gap-0">
      <div className="flex flex-1 overflow-hidden border rounded-xl shadow">
        <div className="flex-1 relative bg-slate-900">
          <MapView simulation={simulation} layers={layers} time={time} onPointSelect={setSelectedPoint} />
          <div className="absolute top-2 left-2 z-[400] w-64">
            <SearchBar />
          </div>
          <div className="absolute top-2 right-2 z-[400]">
            <LiveStatus />
          </div>
        </div>
        <div className="w-[360px] border-l bg-white flex flex-col overflow-auto">
          <LayerPanel layers={layers} onChange={setLayers} />
          <PointInspector point={selectedPoint} />
          <AffectedAreas simulation={simulation} />
          <InfraImpact simulation={simulation} />
          <Reports simulation={simulation} />
        </div>
      </div>
      <Timeline time={time} onChange={setTime} max={72} />
    </div>
  )
}
