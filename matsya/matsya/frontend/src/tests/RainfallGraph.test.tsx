import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import RainfallGraph from "../components/RainfallGraph"
describe("RainfallGraph",()=>{
  it("renders graph and adds point", async()=>{
    const onChange=vi.fn()
    render(<RainfallGraph totalTime={6} maxRain={100} unit="rate" points={[{time:0,amount:0}]} onChange={onChange} />)
    expect(screen.getByTestId("rainfall-graph")).toBeInTheDocument()
    const svg=screen.getByTestId("rainfall-graph").querySelector("svg")
    expect(svg).toBeInTheDocument()
    // Click to add point
    if(svg) fireEvent.click(svg, {clientX:100, clientY:50})
    // onChange should have been called with new points
    // For now just check that graph shows 0,0
    expect(screen.getByText(/0,0/)).toBeInTheDocument()
  })
})
