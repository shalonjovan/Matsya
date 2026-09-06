
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
  it("derives clock from minutesPerFrame", () => {
    render(<Timeline time={4} onChange={() => {}} max={7} minutesPerFrame={15} />)
    expect(screen.getByText("01:00")).toBeInTheDocument()
  })
  it("slider spans sim frames", () => {
    render(<Timeline time={0} onChange={() => {}} max={23} minutesPerFrame={15} />)
    expect(screen.getByRole("slider")).toHaveAttribute("max", "23")
  })
})
