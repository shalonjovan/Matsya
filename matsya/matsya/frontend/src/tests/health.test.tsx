import { describe,it,expect,vi } from "vitest"
import { fetchHealth } from "../api/client"
global.fetch = vi.fn(()=>Promise.resolve({ok:true, json:()=>Promise.resolve({status:"ok",version:"0.1.0",engine:"anuga-mock"})})) as any
describe("health",()=>{it("fetches", async()=>{ const j=await fetchHealth(); expect(j.status).toBe("ok") })})
