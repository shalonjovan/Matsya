import { describe, it, expect, vi, afterEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import SafeRoute, { toLatLngs } from "../components/SafeRoute"

afterEach(() => { vi.unstubAllGlobals() })

const SPACES = [
  { rank: 1, kind: "road", name: "Main Street", lat: 13.11, lon: 80.19,
    elevationM: 22.5, peakCm: 2.0,
    route: { etaMin: 4.5, maxDepthCm: 3.0, path: [[80.18, 13.10], [80.19, 13.11]], segmentIds: ["1#0000"] } },
  { rank: 2, kind: "ground", name: "High ground", lat: 13.12, lon: 80.20,
    elevationM: 25.0, peakCm: 0.0,
    route: { etaMin: 9.0, maxDepthCm: 0.0, path: [[80.18, 13.10], [80.20, 13.12]], segmentIds: [] } },
]

describe("toLatLngs", () => {
  it("converts API lon/lat to Leaflet lat/lon", () => {
    expect(toLatLngs([[80.19, 13.11]])).toEqual([[13.11, 80.19]])
    expect(toLatLngs(null)).toEqual([])
  })
})

describe("SafeRoute", () => {
  it("renders origin, threshold, and find button", () => {
    render(<SafeRoute simulation={{ id: "1" }} timeMin={0}
      origin={{ lat: 13.10, lon: 80.19 }} onSelectRoute={() => {}} />)
    expect(screen.getByTestId("saferoute-lat")).toHaveValue(13.10)
    expect(screen.getByTestId("saferoute-threshold")).toBeInTheDocument()
    expect(screen.getByText(/find safe space/i)).toBeInTheDocument()
  })

  it("lists ranked spaces and selects route on click", async () => {
    const onSelectRoute = vi.fn()
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: true, json: async () => ({ v: "1", data: { spaces: SPACES, reason: null } }),
    } as any)))
    render(<SafeRoute simulation={{ id: "1" }} timeMin={0}
      origin={{ lat: 13.10, lon: 80.18 }} onSelectRoute={onSelectRoute} />)
    fireEvent.click(screen.getByText(/find safe space/i))
    expect(await screen.findByText(/Main Street/)).toBeInTheDocument()
    expect(screen.getByText(/4.5 min/)).toBeInTheDocument()
    fireEvent.click(screen.getByText(/Main Street/))
    expect(onSelectRoute).toHaveBeenCalledWith(
      expect.objectContaining({ safest: [[13.10, 80.18], [13.11, 80.19]], dest: { lat: 13.11, lon: 80.19 } }))
  })

  it("shows honest empty state when nothing is reachable", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: true, json: async () => ({ v: "1", data: { spaces: [], reason: "no reachable safe space" } }),
    } as any)))
    render(<SafeRoute simulation={{ id: "1" }} timeMin={0}
      origin={{ lat: 13.10, lon: 80.18 }} onSelectRoute={() => {}} />)
    fireEvent.click(screen.getByText(/find safe space/i))
    expect(await screen.findByText(/no reachable safe space/i)).toBeInTheDocument()
  })

  it("shows a friendly message for API errors, not raw JSON", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: false, status: 422,
      text: async () => '{"detail":"origin outside routable network (200m)"}',
    } as any)))
    render(<SafeRoute simulation={{ id: "1" }} timeMin={0}
      origin={{ lat: 13.10, lon: 80.18 }} onSelectRoute={() => {}} />)
    fireEvent.click(screen.getByText(/find safe space/i))
    expect(await screen.findByText(/no mapped roads within 200 m/i)).toBeInTheDocument()
    expect(screen.queryByText(/{"detail"/)).not.toBeInTheDocument()
  })

  it("discloses when routing starts from a snapped road", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: true,
      json: async () => ({ v: "1", data: { spaces: SPACES, reason: null,
        originSnapped: { lat: 13.10, lon: 80.19, distanceM: 390 } } }),
    } as any)))
    render(<SafeRoute simulation={{ id: "1" }} timeMin={0}
      origin={{ lat: 13.10, lon: 80.18 }} onSelectRoute={() => {}} />)
    fireEvent.click(screen.getByText(/find safe space/i))
    expect(await screen.findByText(/nearest mapped road, 390 m away/i)).toBeInTheDocument()
  })
})
