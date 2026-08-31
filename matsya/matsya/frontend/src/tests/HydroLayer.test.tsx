import { describe, it, expect, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import HydroLayer from "../components/HydroLayer"
describe("HydroLayer",()=>{
  it("renders drains ending", async()=>{
    global.fetch = vi.fn((url:any)=>{
      if (String(url).includes("/hydro/summary")) return Promise.resolve({ok:true, json:()=>Promise.resolve({drains:52, waterbodies:4086, rivers:876, snapped_to_waterbody:20, to_river:7, to_sea:25})} as any)
      if (String(url).includes("/hydro/graph")) return Promise.resolve({ok:true, json:()=>Promise.resolve({drains:{features: Array(52).fill({properties:{target:"wb:1"}})}, waterbodies:{features:[]}})} as any)
      return Promise.resolve({ok:true, json:()=>Promise.resolve({}) } as any)
    }) as any
    render(<HydroLayer simId="1"/>)
    expect(await screen.findByText(/snapped/)).toBeInTheDocument()
    await waitFor(()=> expect(screen.getByText(/water bodies/)).toBeInTheDocument())
  })
})
