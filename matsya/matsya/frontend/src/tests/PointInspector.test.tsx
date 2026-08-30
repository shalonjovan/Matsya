
import { describe,it,expect } from "vitest"
import { render, screen } from "@testing-library/react"
import PointInspector from "../components/PointInspector"
describe("PointInspector",()=>{
  it("shows elevation",()=>{
    render(<PointInspector point={{lat:13.1,lon:80.17,elevation:15.5,floodDepth:0.42,velocity:0.3}} />)
    expect(screen.getByText(/Elevation/)).toBeInTheDocument()
    expect(screen.getByText(/0.42/)).toBeInTheDocument()
  })
})
