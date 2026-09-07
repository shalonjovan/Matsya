import { describe,it,expect,vi,afterEach } from "vitest"
import { render, screen } from "@testing-library/react"
import InfraImpact from "../components/InfraImpact"

afterEach(() => { vi.unstubAllGlobals() })

describe("InfraImpact",()=>{
  it("shows drain status instead of fabricated flow", async()=>{
    vi.stubGlobal("fetch", vi.fn(async (url: any) => {
      if (String(url).endsWith("/roads")) return { ok: true, json: async () => ([]) }
      if (String(url).endsWith("/drains")) return { ok: true, json: async () => ([
        {id:"D-2", depth:1.75, status:"surcharged", capacity:null, overCapacity:true},
      ]) }
      throw new Error("unexpected " + url)
    }))
    render(<InfraImpact simulation={{id:"1"}} />)
    expect(await screen.findByText("D-2")).toBeInTheDocument()
    expect(screen.getByText("surcharged")).toBeInTheDocument()
    expect(screen.queryByText(/m³\/s/)).not.toBeInTheDocument()
  })
})
