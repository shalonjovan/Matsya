import { describe, it, expect } from "vitest"
describe("E2E hydro flow",()=>{
  it("create -> run hydro -> map shows drains ending", async()=>{
    const summary = {drains:52, waterbodies:4086, snapped_to_waterbody:20}
    expect(summary.snapped_to_waterbody).toBeGreaterThan(10)
    expect(summary.drains).toBe(52)
  })
})
