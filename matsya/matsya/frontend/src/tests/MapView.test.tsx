
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
  it("requests flood tiles in the selected palette", async()=>{
    const sim:any={id:"1", area:{bbox:[80.15,13.08,80.20,13.13]}, flood:{floodUri:"/api/simulations/1/flood?time=0", stats:{maxDepth:0.5}}}
    global.fetch = vi.fn((url)=>{
      if(String(url).includes("/flood")) return Promise.resolve({ok:true, blob:()=>Promise.resolve(new Blob(["png"]))} as any)
      return Promise.resolve({ok:true, json:()=>Promise.resolve({drains:{features:[]}, waterbodies:{features:[]}})} as any)
    }) as any
    render(<MapView simulation={sim} time={0} layers={{depth:{visible:true,opacity:0.6,palette:"greenred"}}} />)
    await waitFor(()=> expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining("palette=greenred")))
  })
  it("busts flood tile cache when the crowd version changes", async()=>{
    const sim:any={id:"1", area:{bbox:[80.15,13.08,80.20,13.13]}, flood:{floodUri:"/api/simulations/1/flood?time=0", stats:{maxDepth:0.5}}}
    global.fetch = vi.fn((url)=>{
      if(String(url).includes("/flood")) return Promise.resolve({ok:true, blob:()=>Promise.resolve(new Blob(["png"]))} as any)
      return Promise.resolve({ok:true, json:()=>Promise.resolve({drains:{features:[]}, waterbodies:{features:[]}})} as any)
    }) as any
    render(<MapView simulation={sim} time={0} floodNonce={7} />)
    await waitFor(()=> expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining("cv=7")))
  })
  it("does not strand the overlay on Completed sims with partial data", async()=>{
    const sim:any={id:"9", status:"Completed",
      area:{bbox:[80.15,13.08,80.20,13.13]},
      elevation:null, flood:{floodUri:"/api/simulations/9/flood?time=0", stats:{maxDepth:0.5}}}
    global.fetch = vi.fn((url)=>{
      if(String(url).includes("/api/simulations/9") && !String(url).includes("/flood"))
        return Promise.resolve({ok:true, json:()=>Promise.resolve(sim)} as any)
      return Promise.resolve({ok:true, json:()=>Promise.resolve({drains:{features:[]}, waterbodies:{features:[]}})} as any)
    }) as any
    const {container}=render(<MapView simulation={sim} time={0} />)
    // wait until async init has run past the overlay step (layer fetch proves it)
    await waitFor(()=> expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining("/api/layers/drains")), {timeout:5000})
    expect(container.querySelector("#processing-overlay")).not.toBeInTheDocument()
  })
  it("shows the overlay while Running and clears it when data arrives", async()=>{
    let pollCount = 0
    const running:any={id:"8", status:"Running", area:{bbox:[80.15,13.08,80.20,13.13]}, elevation:null, flood:null}
    const done:any={id:"8", status:"Completed", area:{bbox:[80.15,13.08,80.20,13.13]},
      elevation:{elevationUri:"/e", stats:{mean:5}}, flood:{floodUri:"/f", stats:{maxDepth:0.5}}}
    global.fetch = vi.fn((url)=>{
      if(String(url).includes("/api/simulations/8") && !String(url).includes("/flood")){
        pollCount++
        return Promise.resolve({ok:true, json:()=>Promise.resolve(pollCount < 2 ? running : done)} as any)
      }
      return Promise.resolve({ok:true, json:()=>Promise.resolve({drains:{features:[]}, waterbodies:{features:[]}})} as any)
    }) as any
    const {container}=render(<MapView simulation={running} time={0} />)
    await waitFor(()=> expect(container.querySelector("#processing-overlay")).toBeInTheDocument(), {timeout:5000})
    await waitFor(()=> expect(container.querySelector("#processing-overlay")).not.toBeInTheDocument(), {timeout:10000})
  })
})
