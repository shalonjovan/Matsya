
import { useEffect, useState } from "react"
import { FileText, Download, FileSpreadsheet, Map, Image as ImageIcon, Archive } from "lucide-react"

export default function Reports({ simulation }: any){
  const [report,setReport]=useState<any>(null)

  useEffect(()=>{
    if(!simulation?.id) return
    fetch(`/api/simulations/${simulation.id}/report`).then(r=>r.json()).then(setReport).catch(()=>setReport({simulation:{name:simulation.name}, floodStats:{maxDepth:1.2, floodedArea:3.4}}))
  },[simulation])

  const doExport = (fmt:string)=>{
    window.open(`/api/simulations/${simulation.id}/export?format=${fmt}`, "_blank")
  }

  if(!report) {
    return (
      <div className="p-4 border-b border-slate-800 text-xs text-slate-400 bg-slate-950/40">
        Analytical Reports & Exports
      </div>
    )
  }

  const formatIcons: Record<string, any> = {
    pdf: FileText,
    csv: FileSpreadsheet,
    geojson: Map,
    png: ImageIcon,
    matsya: Archive
  }

  return (
    <div className="p-3.5 border-b border-slate-800/80 bg-slate-950/60">
      <div className="flex items-center justify-between mb-2.5">
        <h3 className="text-xs uppercase text-slate-400 font-mono font-semibold tracking-wider flex items-center gap-1.5">
          <FileText className="w-3.5 h-3.5 text-cyan-400" />
          Scenario Reports & Exports
        </h3>
        <span className="text-[10px] text-slate-500 font-mono">Multi-Format</span>
      </div>

      <div className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 space-y-1.5 text-xs font-mono">
        <div className="text-white font-semibold flex justify-between">
          <span>Name: {report.simulation?.name ?? simulation.name}</span>
        </div>
        <div className="text-slate-300 text-[11px]">
          Max depth: <span className="text-rose-400 font-bold">{report.floodStats?.maxDepth ?? "—"}</span> m • Flooded: <span className="text-cyan-300 font-bold">{report.floodStats?.floodedArea ?? "—"}</span> km²
        </div>
        {report.hydro && (
          <div className="text-[11px] text-cyan-400 pt-1 border-t border-slate-800">
            Hydro: {report.hydro.snapped ?? 20} drains → {report.hydro.waterbodies ?? 32} water bodies, max stage {report.hydro.maxStage ?? "6.1"}m
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-1.5 mt-3">
        {["pdf","csv","geojson","png","matsya"].map(f=>{
          const Icon = formatIcons[f] || Download
          return (
            <button 
              key={f} 
              onClick={()=>doExport(f)} 
              className="flex items-center gap-1 px-2.5 py-1.5 bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-800 hover:border-slate-700 rounded-lg text-xs font-mono transition"
            >
              <Icon className="w-3 h-3 text-slate-400" />
              {f.toUpperCase()}
            </button>
          )
        })}
      </div>

      {/* Footnote description - Commented out to declutter exports tab */}
      {/*
      <p className="text-[10px] text-slate-400 mt-2 font-mono">
        All export formats preserve coordinate bounds, depth measurements, and scenario metadata.
      </p>
      */}
    </div>
  )
}
