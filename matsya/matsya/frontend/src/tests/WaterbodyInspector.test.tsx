
import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import WaterbodyInspector from "../components/WaterbodyInspector"
describe("WaterbodyInspector",()=>{
  it("shows stage", async()=>{
    global.fetch = vi.fn(()=>Promise.resolve({ok:true, json:()=>Promise.resolve([{id:0, area_m2:50000, spill_crest:5.0, stage:5.2, dem_elev:3.0, centroid:[80.17,13.10]}])} as any)) as any
    render(<WaterbodyInspector waterbodyId="0"/>)
    expect(await screen.findByText(/Waterbody 0/)).toBeInTheDocument()
  })
})
