import { describe, it, expect, vi, afterEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import Event2015 from "../components/Event2015"

afterEach(() => { vi.unstubAllGlobals() })

const FACTS = { rainfallStations: [{ station: "Tambaram", mm24h: 494 }],
  release: { cusecs: 29000, hours: 21, modeled: false },
  referenceLocalities: [], excludedLocalities: [] }
const COMPARE = { localities: [
    { name: "Guindy", reportedBand: "severe", modeledBand: "moderate", modeledMaxCm: 86.4, match: false },
    { name: "Adyar mouth", reportedBand: "severe", modeledBand: "severe", modeledMaxCm: 199.9, match: true }],
  recall: 0.4, bandAgreement: 0.5, similarityPct: 45,
  formula: "similarityPct = round(50*recall + 50*bandAgreement)" }

function stub() {
  vi.stubGlobal("fetch", vi.fn(async (url: any, opts: any) => {
    if (String(url).includes("/facts")) return { ok: true, json: async () => ({ v: "1", data: FACTS }) }
    if (String(url).includes("/compare")) return { ok: true, json: async () => ({ v: "1", data: COMPARE }) }
    if (String(url).includes("/replay")) return { ok: true, json: async () => ({ v: "1", data: { simId: "abc" } }) }
    if (String(url).includes("/api/simulations/abc")) return { ok: true, json: async () => ({ id: "abc", status: "Completed" }) }
    throw new Error("unexpected " + url)
  }))
}

describe("Event2015", () => {
  it("shows observed facts with sources", async () => {
    stub()
    render(<Event2015 />)
    expect(await screen.findByText(/Tambaram/)).toBeInTheDocument()
    expect(screen.getByText(/494/)).toBeInTheDocument()
    expect(screen.getByText(/29,000 cusecs/)).toBeInTheDocument()
  })

  it("renders the computed similarity donut and locality table", async () => {
    stub()
    render(<Event2015 />)
    fireEvent.click(screen.getByText(/run replay/i))
    expect(await screen.findByText("45%", {}, { timeout: 15000 })).toBeInTheDocument()
    expect(screen.getByText(/Guindy/)).toBeInTheDocument()
    expect(screen.getByText(/Adyar mouth/)).toBeInTheDocument()
  })

  it("labels context-only data as not modeled", async () => {
    stub()
    render(<Event2015 />)
    expect(await screen.findByText(/not modeled/i)).toBeInTheDocument()
  })
})
