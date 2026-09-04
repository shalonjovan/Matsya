export function interpolatePoints(points: {time:number, amount:number}[], totalTime: number, maxRain: number, steps: number, unit: "rate"|"total" = "rate"): number[] {
  if (!points || points.length===0) return Array(steps).fill(0)
  const sorted = [...points].sort((a,b)=>a.time-b.time)
  const dt = totalTime/steps
  const times = Array.from({length: steps}, (_,i)=> i*dt)
  // Simple linear for frontend preview (backend does spline)
  const values: number[] = []
  for (const t of times) {
    let v = sorted[0].amount
    for (let i=0;i<sorted.length-1;i++) {
      const p0=sorted[i], p1=sorted[i+1]
      if (p0.time <= t && t <= p1.time) {
        const span = p1.time - p0.time
        const frac = span===0?0:(t-p0.time)/span
        v = p0.amount*(1-frac) + p1.amount*frac
        break
      }
      if (t > sorted[sorted.length-1].time) v = sorted[sorted.length-1].amount
    }
    values.push(Math.max(0, Math.min(maxRain, v)))
  }
  if (unit==="total") {
    // For total, convert to rate
    const rates:number[] = []
    for (let i=0;i<values.length;i++) {
      if (i===0) rates.push(values[0]/dt)
      else rates.push((values[i]-values[i-1])/dt)
    }
    return rates.map(v=>Math.max(0, Math.min(maxRain, v)))
  }
  return values
}

export function randomPreset(preset: string, totalTime: number, maxRain: number): {time:number, amount:number}[] {
  if (preset==="burst") {
    return [{time:0,amount:0},{time:totalTime*0.1,amount:maxRain*0.9},{time:totalTime*0.3,amount:maxRain*0.4},{time:totalTime*0.6,amount:maxRain*0.2},{time:totalTime,amount:0}]
  } else if (preset==="gradual") {
    return [{time:0,amount:0},{time:totalTime*0.3,amount:maxRain*0.3},{time:totalTime*0.6,amount:maxRain*0.6},{time:totalTime,amount:maxRain*0.8}]
  } else if (preset==="double-peak") {
    return [{time:0,amount:0},{time:totalTime*0.2,amount:maxRain*0.8},{time:totalTime*0.5,amount:maxRain*0.2},{time:totalTime*0.7,amount:maxRain*0.9},{time:totalTime,amount:0}]
  } else {
    const pts=[{time:0,amount:Math.random()*maxRain*0.5}]
    for(let i=0;i<3;i++) pts.push({time:Math.random()*totalTime*0.9+0.1, amount:Math.random()*maxRain})
    pts.push({time:totalTime, amount:Math.random()*maxRain*0.3})
    pts.sort((a,b)=>a.time-b.time)
    return pts.map(p=>({time: Math.max(0,Math.min(totalTime,p.time)), amount: Math.max(0,Math.min(maxRain,p.amount))}))
  }
}
