import { describe,it,expect,vi,afterEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import AffectedAreas from "../components/AffectedAreas"

afterEach(() => { vi.unstubAllGlobals() })

describe("AffectedAreas",()=>{
  it("renders computed hotspots from the API", async()=>{
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => ([
      {name:"near Main Road, Testville",maxDepth:1.24,duration:"0h 30m",rank:1,lat:13.10,lon:80.19},
    ]) } as any)))
    render(<AffectedAreas simulation={{id:"1"}} />)
    const el = await screen.findByText(/near Main Road/)
    expect(el).toBeInTheDocument()
    fireEvent.click(el)
  })
  it("shows an honest empty state when data is unavailable", async()=>{
    vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("offline") }))
    render(<AffectedAreas simulation={{id:"1"}} />)
    expect(await screen.findByText(/0 Inundated Zones/)).toBeInTheDocument()
    expect(screen.queryByText(/Velachery/)).not.toBeInTheDocument()
  })
})
