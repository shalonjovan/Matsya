import { describe, it, expect, vi, afterEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import LiveRealtime from "../components/LiveRealtime"

afterEach(() => { vi.unstubAllGlobals() })

const STATUS = { simId: "realtime-chennai-01", live: true, lastTickAt: "2026-09-09T06:00:00+00:00",
  nextTickAt: "2026-09-09T06:15:00+00:00", rainNowMmHr: 0.6, source: "dummy" }
const REPORTS = [{ id: "abc123", lat: 13.10, lon: 80.17, depthCm: 50, kind: "flooded",
  note: "ankle", createdAt: "2026-09-09T05:00:00+00:00", ageHrs: 1.0 }]

function stub() {
  vi.stubGlobal("fetch", vi.fn(async (url: any, opts: any) => {
    if (String(url).includes("/api/live/status"))
      return { ok: true, json: async () => STATUS } as any
    if (String(url).includes("/api/v1/crowd/reports") && (!opts || opts.method !== "POST"))
      return { ok: true, json: async () => ({ v: "1", data: { reports: REPORTS } }) } as any
    if (String(url).includes("/api/v1/crowd/reports"))
      return { ok: true, json: async () => ({ v: "1", data: { reportId: "new1" } }) } as any
    throw new Error("unexpected " + url)
  }))
}

describe("LiveRealtime", () => {
  it("shows live status with rain and tick times", async () => {
    stub()
    render(<LiveRealtime origin={null} />)
    expect(await screen.findByText(/realtime-chennai-01/)).toBeInTheDocument()
    expect(screen.getByText(/0.6 mm\/hr/)).toBeInTheDocument()
  })

  it("lists crowd reports", async () => {
    stub()
    render(<LiveRealtime origin={null} />)
    expect(await screen.findByText(/ankle/)).toBeInTheDocument()
    expect(screen.getByText(/50 cm/)).toBeInTheDocument()
  })

  it("submits a report with origin, depth, kind", async () => {
    const calls: any[] = []
    vi.stubGlobal("fetch", vi.fn(async (url: any, opts: any) => {
      if (String(url).includes("/api/live/status"))
        return { ok: true, json: async () => STATUS } as any
      if (String(url).includes("/api/v1/crowd/reports")) {
        if (opts && opts.method === "POST") {
          calls.push(JSON.parse(opts.body))
          return { ok: true, json: async () => ({ v: "1", data: { reportId: "new1" } }) } as any
        }
        return { ok: true, json: async () => ({ v: "1", data: { reports: [] } }) } as any
      }
      throw new Error("unexpected " + url)
    }))
    render(<LiveRealtime origin={{ lat: 13.10, lon: 80.17 }} />)
    fireEvent.change(screen.getByTestId("crowd-depth"), { target: { value: "50" } })
    fireEvent.click(screen.getByText(/report water/i))
    await screen.findByText(/reported/i)
    expect(calls[0]).toMatchObject({ lat: 13.10, lon: 80.17, depthCm: 50, kind: "flooded" })
  })
})
