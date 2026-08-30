
import { describe,it,expect } from "vitest"
import { render, screen } from "@testing-library/react"
import LiveStatus from "../components/LiveStatus"
describe("LiveStatus",()=>{
  it("shows offline/connected",()=>{
    render(<LiveStatus />)
    expect(screen.getByText(/Offline|Connected/)).toBeInTheDocument()
  })
})
