
import { describe,it,expect } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import Timeline from "../components/Timeline"
describe("Timeline",()=>{
  it("play advances",()=>{
    let t=5
    render(<Timeline time={t} onChange={(n)=>{t=n}} />)
    expect(screen.getByText("▶ Play")).toBeInTheDocument()
    fireEvent.click(screen.getByText("+1"))
    expect(t).toBe(6)
  })
})
