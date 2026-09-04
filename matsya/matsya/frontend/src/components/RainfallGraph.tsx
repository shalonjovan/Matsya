import { useState, useRef, useEffect } from "react"

interface Point { time: number, amount: number }
interface Props {
  totalTime: number
  maxRain: number
  unit: "rate"|"total"
  points: Point[]
  onChange: (points: Point[]) => void
}

export default function RainfallGraph({ totalTime, maxRain, unit, points, onChange }: Props) {
  const [dragging, setDragging] = useState<number|null>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const width=400, height=200, pad=30
  // Sort points by time
  const sorted = [...points].sort((a,b)=>a.time-b.time)
  // Generate smooth curve points for display (interpolated)
  const steps=50
  const dt=totalTime/steps
  const curve: Point[] = []
  for(let i=0;i<=steps;i++){
    const t=i*dt
    // linear for display (backend does spline, but display linear is fine)
    let v=sorted[0]?.amount ?? 0
    for(let j=0;j<sorted.length-1;j++){
      const p0=sorted[j], p1=sorted[j+1]
      if(p0.time <= t && t <= p1.time){
        const f=(t-p0.time)/(p1.time-p0.time)
        v=p0.amount*(1-f)+p1.amount*f
        break
      }
      if(t>sorted[sorted.length-1].time) v=sorted[sorted.length-1].amount
    }
    curve.push({time:t, amount: Math.max(0, Math.min(maxRain, v))})
  }

  const xScale = (t:number)=> pad + (t/totalTime)*(width-pad*2)
  const yScale = (a:number)=> height - pad - (a/maxRain)*(height-pad*2)

  const handleMouseDown = (idx:number, e:React.MouseEvent)=>{
    e.preventDefault()
    setDragging(idx)
  }
  const handleMouseMove = (e:React.MouseEvent)=>{
    if(dragging===null || !svgRef.current) return
    const rect=svgRef.current.getBoundingClientRect()
    const x=e.clientX - rect.left
    const y=e.clientY - rect.top
    const t = ((x - pad)/(width-pad*2))*totalTime
    const a = ((height - pad - y)/(height-pad*2))*maxRain
    const newPoints = [...sorted]
    newPoints[dragging] = {time: Math.max(0, Math.min(totalTime, t)), amount: Math.max(0, Math.min(maxRain, a))}
    // Keep sorted by time, but dragging may cross
    newPoints.sort((a,b)=>a.time-b.time)
    onChange(newPoints)
  }
  const handleMouseUp = ()=> setDragging(null)
  const handleSvgClick = (e:React.MouseEvent)=>{
    if(dragging!==null) return
    if(!svgRef.current) return
    const rect=svgRef.current.getBoundingClientRect()
    const x=e.clientX - rect.left
    const y=e.clientY - rect.top
    // Only add if click is inside plot area
    if(x<pad || x>width-pad || y<pad || y>height-pad) return
    const t = ((x - pad)/(width-pad*2))*totalTime
    const a = ((height - pad - y)/(height-pad*2))*maxRain
    const newPoints = [...sorted, {time: Math.max(0, Math.min(totalTime, t)), amount: Math.max(0, Math.min(maxRain, a))}].sort((a,b)=>a.time-b.time)
    onChange(newPoints)
  }
  const handleDoubleClick = (idx:number)=>{
    if(sorted.length<=2) return
    const newPoints = sorted.filter((_,i)=>i!==idx)
    onChange(newPoints)
  }

  // Generate path for smooth curve
  const pathD = curve.map((p,i)=> `${i===0?"M":"L"}${xScale(p.time)},${yScale(p.amount)}`).join(" ")

  return (
    <div className="border rounded p-2 bg-white" data-testid="rainfall-graph" onMouseMove={handleMouseMove} onMouseUp={handleMouseUp} onMouseLeave={handleMouseUp}>
      <svg ref={svgRef} width={width} height={height} className="w-full h-auto border bg-slate-50" onClick={handleSvgClick}>
        {/* axes */}
        <line x1={pad} y1={height-pad} x2={width-pad} y2={height-pad} stroke="#334155" />
        <line x1={pad} y1={pad} x2={pad} y2={height-pad} stroke="#334155" />
        <text x={width/2} y={height-5} textAnchor="middle" fontSize={10}>Time (hr) 0→{totalTime}hr</text>
        <text x={10} y={15} fontSize={10} transform={`rotate(-90,10,${height/2})`} textAnchor="middle">Amount {unit==="rate"?"(mm/hr)":"(mm total)"} 0→{maxRain}</text>
        {/* grid */}
        {[0,0.25,0.5,0.75,1].map(frac=>(
          <g key={frac}>
            <line x1={xScale(frac*totalTime)} y1={pad} x2={xScale(frac*totalTime)} y2={height-pad} stroke="#e2e8f0" strokeDasharray="2,2" />
            <line x1={pad} y1={yScale(frac*maxRain)} x2={width-pad} y2={yScale(frac*maxRain)} stroke="#e2e8f0" strokeDasharray="2,2" />
          </g>
        ))}
        {/* curve */}
        <path d={pathD} fill="none" stroke="#3b82f6" strokeWidth={2} />
        {/* points */}
        {sorted.map((p,i)=>(
          <g key={i} onMouseDown={(e)=>handleMouseDown(i,e)} onDoubleClick={()=>handleDoubleClick(i)} style={{cursor:"move"}}>
            <circle cx={xScale(p.time)} cy={yScale(p.amount)} r={6} fill={dragging===i ? "#ef4444" : "#3b82f6"} stroke="white" strokeWidth={2} />
            <text x={xScale(p.time)} y={yScale(p.amount)-10} textAnchor="middle" fontSize={9} fill="#334155">{p.time.toFixed(1)},{p.amount.toFixed(0)}</text>
          </g>
        ))}
      </svg>
      <div className="text-xs text-slate-500 mt-1">Click to add point, drag to move, double-click to delete. Smooth spline between points.</div>
      <div className="text-xs font-mono">Equation: y = spline(x) with {points.length} points, {unit} 0→{maxRain}, time 0→{totalTime}hr</div>
    </div>
  )
}
