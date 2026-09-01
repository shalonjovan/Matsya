
import { describe, it, expect } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import LayerPanel from "../components/LayerPanel"
describe("LayerPanel",()=>{
  it("toggles depth",()=>{
    let layers:any={depth:{visible:true,opacity:0.8}}
    render(<LayerPanel layers={layers} onChange={(n:any)=>{layers=n}} />)
    expect(screen.getByText("Flood depth")).toBeInTheDocument()
    const cb = screen.getByLabelText(/Flood depth/) as HTMLInputElement
    fireEvent.click(cb)
    expect(cb.checked).toBe(false)
  })
  it("legend shows maxDepth", ()=>{
    const sim:any={id:"1", flood:{stats:{maxDepth:1.2, floodedArea:0.5}}}
    render(<LayerPanel layers={{depth:{visible:true,opacity:0.8}}} simulation={sim} />)
    expect(screen.getByText(/1.2/)).toBeInTheDocument()
  })
})
