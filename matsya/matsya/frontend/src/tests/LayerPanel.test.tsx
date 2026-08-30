
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
})
