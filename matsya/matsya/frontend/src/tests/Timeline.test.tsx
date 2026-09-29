
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
  it("marks NOW on the slider when nowFrame is given", () => {
    render(<Timeline time={36} onChange={() => {}} max={72} minutesPerFrame={19.726027397260275} nowFrame={36.49} />)
    const marker = screen.getByTestId("timeline-now-marker")
    expect(marker).toBeInTheDocument()
    expect(marker.style.left).toContain("50.6")
  })
  it("omits the NOW marker without nowFrame", () => {
    render(<Timeline time={36} onChange={() => {}} max={72} minutesPerFrame={19.726027397260275} />)
    expect(screen.queryByTestId("timeline-now-marker")).toBeNull()
  })
  it("shows the signed window offset at the playhead for live sims", () => {
    const props = { onChange: () => {}, max: 72, minutesPerFrame: 19.726027397260275, nowFrame: 36.49 }
    const { unmount } = render(<Timeline time={36} {...props} />)
    expect(screen.getByTestId("timeline-window-clock")).toHaveTextContent("NOW")
    unmount()
    render(<Timeline time={0} {...props} />)
    expect(screen.getByTestId("timeline-window-clock")).toHaveTextContent("−12:00")
  })
  it("labels the window ends relative to NOW", () => {
    render(<Timeline time={36} onChange={() => {}} max={72} minutesPerFrame={19.726027397260275} nowFrame={36.49} />)
    expect(screen.getByTestId("timeline-window-start")).toHaveTextContent("−12:00")
    expect(screen.getByTestId("timeline-window-end")).toHaveTextContent("+11:40")
  })
})
