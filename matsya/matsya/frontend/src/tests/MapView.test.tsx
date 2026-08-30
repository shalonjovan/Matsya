
import { describe, it, expect } from "vitest"
import { render } from "@testing-library/react"
import MapView from "../components/MapView"
describe("MapView",()=>{
  it("renders map div", ()=>{
    const sim:any={id:"1", area:{bbox:[80.15,13.08,80.20,13.13]}, rainfall:{rateMmHr:50,durationHr:1}}
    const {container}=render(<MapView simulation={sim} />)
    expect(container.querySelector("[data-testid='map-view']")).toBeInTheDocument()
  })
})
