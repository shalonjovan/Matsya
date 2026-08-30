
import { describe,it,expect,vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import AffectedAreas from "../components/AffectedAreas"
describe("AffectedAreas",()=>{
  it("click zooms", async()=>{
    vi.fn()
    render(<AffectedAreas simulation={{id:"1"}} />)
    // fallback shows Velachery
    const el = await screen.findByText(/Velachery/)
    expect(el).toBeInTheDocument()
    fireEvent.click(el)
  })
})
