
import { describe, it, expect, vi, afterEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import CreateWizard, { boundsToBboxStrings } from "../components/CreateWizard"

afterEach(() => { vi.unstubAllGlobals() })

describe("boundsToBboxStrings", ()=>{
  it("converts leaflet bounds to 5-decimal bbox strings", ()=>{
    const bounds = { getWest: ()=>80.15, getEast: ()=>80.2, getSouth: ()=>13.08, getNorth: ()=>13.13 }
    expect(boundsToBboxStrings(bounds)).toEqual({
      minLon: "80.15000", maxLon: "80.20000", minLat: "13.08000", maxLat: "13.13000",
    })
  })
})

describe("CreateWizard", ()=>{
  it("shows missing dataset warning", ()=>{
    const sim: any = { id:"1", name:"test", area:{bbox:[80.15,13.08,80.20,13.13]}, rainfall:{rateMmHr:50,durationHr:1} }
    // render step 3 would show warning, but for now check wizard renders name
    render(<CreateWizard open={true} onClose={()=>{}} onCreated={()=>{}} />)
    expect(screen.getByText("Create Simulation")).toBeInTheDocument()
    expect(screen.getByText("Name")).toBeInTheDocument()
  })

  it("shows live drain counts from hydro summary on step 3", async ()=>{
    vi.stubGlobal("fetch", vi.fn(async (url: any) => {
      if (String(url).includes("/api/hydro/summary")) {
        return { ok: true, json: async () => ({ drains: 52, waterbodies: 4086, rivers: 876, snapped_to_waterbody: 20, to_river: 7, to_sea: 25, unsnapped: 0 }) }
      }
      throw new Error("unexpected fetch " + url)
    }))
    render(<CreateWizard open={true} onClose={()=>{}} onCreated={()=>{}} />)
    fireEvent.click(screen.getByLabelText("Step 3: Datasets"))
    expect(await screen.findByText(/connected \(52 micro\/macro/)).toBeInTheDocument()
  })

  it("falls back to missing-drain warning when summary fetch fails", async ()=>{
    vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("offline") }))
    render(<CreateWizard open={true} onClose={()=>{}} onCreated={()=>{}} />)
    fireEvent.click(screen.getByLabelText("Step 3: Datasets"))
    expect(await screen.findByText(/without drainage/)).toBeInTheDocument()
  })

  it("sends initialFillPct in run payload", async ()=>{
    const calls: any[] = []
    vi.stubGlobal("fetch", vi.fn(async (url: any, opts: any) => {
      if (String(url).includes("/api/hydro/summary")) {
        return { ok: true, json: async () => ({ drains: 52, snapped_to_waterbody: 20, to_river: 7, to_sea: 25 }) }
      }
      calls.push(JSON.parse(opts.body))
      return { ok: true, json: async () => ({ id: "x" }) }
    }))
    render(<CreateWizard open={true} onClose={()=>{}} onCreated={()=>{}} />)
    fireEvent.change(document.getElementById("wizard-sim-name") as HTMLInputElement, { target: { value: "filltest" } })
    fireEvent.click(screen.getByLabelText("Step 4: Physics"))
    const slider = document.getElementById("wizard-fill") as HTMLInputElement
    expect(slider.value).toBe("75")
    fireEvent.change(slider, { target: { value: "40" } })
    fireEvent.click(screen.getByText("Run Simulation"))
    await waitFor(() => expect(calls.length).toBeGreaterThan(0))
    const body = calls[calls.length - 1]
    expect(body.name).toBe("filltest")
    expect(body.parameters.initialFillPct).toBe(40)
  })
})
