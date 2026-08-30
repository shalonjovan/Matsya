
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
