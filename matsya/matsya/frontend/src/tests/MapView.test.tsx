
import { describe, it, expect, vi } from "vitest"
import { render, waitFor } from "@testing-library/react"
import MapView from "../components/MapView"
describe("MapView",()=>{
  it("renders map div", ()=>{
    const sim:any={id:"1", area:{bbox:[80.15,13.08,80.20,13.13]}, rainfall:{rateMmHr:50,durationHr:1}}
    const {container}=render(<MapView simulation={sim} />)
    expect(container.querySelector("[data-testid='map-view']")).toBeInTheDocument()
  })
  it("fetches flood from tif per time", async()=>{
    const sim:any={id:"1", area:{bbox:[80.15,13.08,80.20,13.13]}, flood:{floodUri:"/api/simulations/1/flood?time=0", stats:{maxDepth:0.5}}}
    global.fetch = vi.fn((url)=>{
      if(String(url).includes("/flood")) return Promise.resolve({ok:true, blob:()=>Promise.resolve(new Blob(["png"]))} as any)
      return Promise.resolve({ok:true, json:()=>Promise.resolve({drains:{features:[]}, waterbodies:{features:[]}})} as any)
    }) as any
    render(<MapView simulation={sim} time={0} />)
    await waitFor(()=> expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining("/flood")))
  })
})
