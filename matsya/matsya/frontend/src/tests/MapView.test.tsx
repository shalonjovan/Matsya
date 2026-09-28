
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
  it("probes the point API at the current slider time, not a stale one", {timeout: 25000}, async()=>{
    const sim:any={id:"7", area:{bbox:[80.15,13.08,80.20,13.13]}, rainfall:{rateMmHr:50,durationHr:1},
      flood:{floodUri:"/api/simulations/7/flood?time=0", stats:{maxDepth:0.5}}}
    const calls: string[] = []
    global.fetch = vi.fn((url)=>{
      calls.push(String(url))
      if(String(url).includes("/point"))
        return Promise.resolve({ok:true, json:()=>Promise.resolve({lat:13.1,lon:80.18,floodDepth:0.1})} as any)
      if(String(url).includes("/flood")) return Promise.resolve({ok:true, blob:()=>Promise.resolve(new Blob(["png"]))} as any)
      return Promise.resolve({ok:true, json:()=>Promise.resolve({drains:{features:[]}, waterbodies:{features:[]}})} as any)
    }) as any
    const {container, rerender}=render(<MapView simulation={sim} time={0} onPointSelect={()=>{}} />)
    await waitFor(()=> expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining("/api/layers/drains")), {timeout:8000})
    const el = container.querySelector("[data-testid='map-view']") as HTMLElement
    el.dispatchEvent(new MouseEvent("click", {bubbles:true, clientX:100, clientY:100}))
    await waitFor(()=> expect(calls.some(u=>u.includes("/point") && u.includes("time=0"))).toBe(true), {timeout:5000})
    // same sim, slider moved: the probe must follow (stale closure = still time=0)
    rerender(<MapView simulation={sim} time={40} onPointSelect={()=>{}} />)
    el.dispatchEvent(new MouseEvent("click", {bubbles:true, clientX:100, clientY:100}))
    await waitFor(()=> expect(calls.some(u=>u.includes("/point") && u.includes("time=40"))).toBe(true), {timeout:5000})
  })
  it("selects the grid cell under the clicked point on a live sim", async()=>{
    const origGetContext = HTMLCanvasElement.prototype.getContext
    HTMLCanvasElement.prototype.getContext = (() =>
      new Proxy({}, { get: () => () => undefined })) as any
    try {
      // jsdom's Leaflet derives an out-of-range lat/lon from a synthetic click,
      // so the cell spans far beyond the globe: any click must resolve it.
      // What is under test is the wiring (click -> geography -> cell), not
      // the cell's real extent.
      const cell = {id:"om-77", mode:"variable", unit:"rate", totalTime:24.0, maxRain:1.5,
        points:[{time:0.25,amount:0.5},{time:23.25,amount:0.5}],
        polygon:{type:"Polygon",coordinates:[[[-400,-200],[400,-200],[400,200],[-400,200],[-400,-200]]]}}
      const sim:any={id:"live", live:true, area:{bbox:[80.13968,13.01593,80.28967,13.14146]},
        rainfall:{rateMmHr:0,durationHr:24,zones:[cell]},
        flood:{floodUri:"/api/simulations/live/flood?time=0", stats:{maxDepth:0.5, minutesPerFrame:19.726}},
        results:{live:{windowStart:"2026-09-14T20:44:48+00:00",tickAt:"2026-09-15T08:44:48+00:00",windowEnd:"2026-09-15T20:44:48+00:00"}}}
      global.fetch = vi.fn((url)=>{
        if(String(url).includes("/point"))
          return Promise.resolve({ok:true, json:()=>Promise.resolve({lat:13.08,lon:80.21,floodDepth:0.1})} as any)
        if(String(url).includes("/flood")) return Promise.resolve({ok:true, blob:()=>Promise.resolve(new Blob(["png"]))} as any)
        return Promise.resolve({ok:true, json:()=>Promise.resolve({drains:{features:[]}, waterbodies:{features:[]}})} as any)
      }) as any
      const onCell = vi.fn()
      const {container}=render(
        <MapView simulation={sim} time={36} layers={{rainGrid:{visible:true,opacity:0.55}}} onCellSelect={onCell} />
      )
      await waitFor(()=> expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining("/api/layers/drains")), {timeout:8000})
      const el = container.querySelector("[data-testid='map-view']") as HTMLElement
      el.dispatchEvent(new MouseEvent("click", {bubbles:true, clientX:100, clientY:100}))
      // resolves by geography, so the drains layer above the grid cannot swallow it
      expect(onCell).toHaveBeenCalledWith(expect.objectContaining({ zoneId: "om-77" }))
    } finally {
      HTMLCanvasElement.prototype.getContext = origGetContext
    }
  })
  it("renders a live sim with a 144-cell grid without throwing", async()=>{
    // jsdom has no 2D canvas: hand Leaflet's Canvas renderer a no-op
    // context so vector redraws stay silent (production uses real canvas).
    const origGetContext = HTMLCanvasElement.prototype.getContext
    HTMLCanvasElement.prototype.getContext = (() =>
      new Proxy({}, { get: () => () => undefined })) as any
    try {
    const zones = Array.from({length:144},(_,i)=>({
      id:`om-${i}`, mode:"variable", unit:"rate", totalTime:24.0, maxRain:1.0,
      points:[{time:0.25,amount:0.5},{time:23.25,amount:0.5}],
      polygon:{type:"Polygon",coordinates:[[[80.14,13.02],[80.15,13.02],[80.15,13.03],[80.14,13.03],[80.14,13.02]]]}}))
    const sim:any={id:"live", live:true, area:{bbox:[80.13968,13.01593,80.28967,13.14146]},
      rainfall:{rateMmHr:0,durationHr:24,zones},
      flood:{floodUri:"/api/simulations/live/flood?time=0", stats:{maxDepth:0.5, minutesPerFrame:19.726}},
      results:{live:{windowStart:"2026-09-14T20:44:48+00:00",tickAt:"2026-09-15T08:44:48+00:00",windowEnd:"2026-09-15T20:44:48+00:00"}}}
    global.fetch = vi.fn((url)=>{
      if(String(url).includes("/flood")) return Promise.resolve({ok:true, blob:()=>Promise.resolve(new Blob(["png"]))} as any)
      return Promise.resolve({ok:true, json:()=>Promise.resolve({drains:{features:[]}, waterbodies:{features:[]}})} as any)
    }) as any
    const onCell = vi.fn()
    const {container}=render(
      <MapView simulation={sim} time={36} layers={{rainGrid:{visible:true,opacity:0.55}}} onCellSelect={onCell} />
    )
    await waitFor(()=> expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining("/api/layers/drains")), {timeout:8000})
    expect(container.querySelector("[data-testid='map-view']")).toBeInTheDocument()
    } finally {
      HTMLCanvasElement.prototype.getContext = origGetContext
    }
  })
})
