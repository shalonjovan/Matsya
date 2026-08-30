export const API="/api"
export async function fetchHealth(){ const r=await fetch(`${API}/health`); if(!r.ok) throw new Error("health"); return r.json() }
