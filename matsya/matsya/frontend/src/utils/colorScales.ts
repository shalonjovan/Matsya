
export function depthToColor(d:number): [number,number,number,number] {
  if(d<0.01) return [0,0,0,0]
  if(d<0.05) return [186,230,253,180]
  if(d<0.15) return [56,189,248,190]
  if(d<0.3) return [14,165,233,195]
  if(d<0.6) return [2,132,199,200]
  if(d<1.0) return [12,74,110,210]
  return [2,48,71,220]
}
export const velocityScale = (v:number)=>`hsl(${240 - Math.min(v*100,240)}, 80%, 50%)`

export function hypsometricColor(elev: number, vmin: number, vmax: number): [number,number,number] {
  if (vmax===vmin) return [168,213,162]
  const norm = Math.max(0, Math.min(1, (elev - vmin)/(vmax - vmin)))
  const colors: [number,number,number][] = [[10,61,46],[44,95,45],[168,213,162],[210,180,140],[139,69,19],[254,254,254]]
  const stops = [0,0.2,0.5,0.7,0.85,1.0]
  for(let i=0;i<stops.length-1;i++){
    if(stops[i] <= norm && norm <= stops[i+1]){
      const t = (norm - stops[i])/(stops[i+1]-stops[i])
      const r = Math.round(colors[i][0]*(1-t)+colors[i+1][0]*t)
      const g = Math.round(colors[i][1]*(1-t)+colors[i+1][1]*t)
      const b = Math.round(colors[i][2]*(1-t)+colors[i+1][2]*t)
      return [r,g,b]
    }
  }
  return colors[colors.length-1]
}
