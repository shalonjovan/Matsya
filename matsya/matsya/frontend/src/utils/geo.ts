export function latLonToRowCol(lat:number, lon:number, bbox:[number,number,number,number], rows:number, cols:number){
  const [minLon,minLat,maxLon,maxLat]=bbox
  const dy=(maxLat-minLat)/rows, dx=(maxLon-minLon)/cols
  const r=Math.floor((maxLat - lat)/dy)
  const c=Math.floor((lon - minLon)/dx)
  return [Math.max(0,Math.min(rows-1,r)), Math.max(0,Math.min(cols-1,c))]
}
export async function decodeSnapshotsWeb(json:any){
  // pako optional — stub for MVP, real decode when backend provides pako-compressed web json
  return json
}
