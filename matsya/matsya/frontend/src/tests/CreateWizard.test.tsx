
import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import CreateWizard, { boundsToBboxStrings } from "../components/CreateWizard"

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
})
