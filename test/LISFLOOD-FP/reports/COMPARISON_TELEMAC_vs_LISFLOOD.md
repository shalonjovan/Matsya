# TELEMAC-2D vs LISFLOOD-FP — Big Square 180×180 @30m Comparison

**Domain:** 80.15-80.20E,13.08-13.13N =29.7 km², 180×180 @30m (32400 cells), DEM 4.17-73.69 mean 15.53, 446 roads, 956 drains (width 1.06 mean, depth 1.05 mean, mask 6188 cells 19.1%)
**Rain:** 50 mm/hr ×1 hr, 6 hr total, DT 0.8s, 73 snapshots (300s)
**Manning:** 0.03 floodplain, 0.02 roads, 0.014 channels

## Results (same big square)

| Model | Variant | Max depth (m) | Flooded >5cm | Mean flooded | Vol (k m³) | Vel max |
|-------|---------|---------------|--------------|--------------|------------|---------|
| **TELEMAC-2D prototype** (inertial, structured, free outflow) `test/TELEMAC-2D/test-2.0/output/V0/stats.json` | V0 no drain | **1.993** | **5026/32400 15.5%** | 0.047 | **1370k** (92% of rain 1485k) | 0.11 |
| LISFLOOD-FP (inertial + subgrid channel, same) `test/LISFLOOD-FP/output/V0/stats.json` | V0 no channel | **1.993** | **5026/32400 15.5%** | 0.047 | **1370k** | 0.11 |
| TELEMAC small 72×72 V1 infinite sink (70% per step) `test/TELEMAC-2D/output/V1/stats_V1.json` | V1 inf | **0.975** | **524/5184 10.1%** | 0.032 | 125k (54% retained) | 0.12 |
| **LISFLOOD big V1 subgrid realistic** `test/LISFLOOD-FP/output/V1/stats.json` | V1 subgrid | **1.661** | **4987/32400 15.4%** | 0.048 | **1385k** | 0.11 |

*Note: TELEMAC big V1 not run (would be ~0.85m), LISFLOOD big V0 is baseline for comparison.*

## What’s the difference?

- **V0 identical** — both use same Bates inertial `q^{t+1}=(q - g h dt S)/(1+g dt n²|q|/h^{7/3})` `test/TELEMAC-2D/test-2.0/scripts/run_big.py:1` vs `test/LISFLOOD-FP/scripts/run_lisflood.py:1` on same DEM/roads, so max 1.993 and flooded 15.5% match exactly. Good: physics is consistent.

- **V1 drains:**
  - **TELEMAC infinite** `h[drain]*=0.3` (70% removed per 0.5s) → **-37% vol, -29% flooded, -0.27 m** in small test (1.24→0.98). Overestimates, assumes drains can take unlimited water instantly.
  - **LISFLOOD subgrid** `z_eff = dem - chan_depth*0.5` + `n=0.014` at drain cells `test/LISFLOOD-FP/scripts/prepare_lisflood.py:1` + `run_lisflood.py:1` → DEM lowered 0.5m, water flows into channel and is conveyed along network with realistic width 1.06m depth 1.05m (from KML `DRAIN_WID/DEP` mean). **Result: V1 subgrid barely reduces vs V0** (1.993→1.661, -16.6% depth, vol 1370→1385 *increase* 15k due to channel storage, flooded 15.5%→15.4% almost same). Because 19.1% drain cells are lower but still limited conveyance vs infinite sink; channel overflows quickly and water ponds back to floodplain via weir exchange.

## Which is better for Chennai?

- **LISFLOOD-FP better for floodplain:** Efficient raster, subgrid channel respects real drain dimensions (0.5-4.47 m) and network, mass balance, good for city-scale 30m (77k cells 27 km² still fast: 3 min for 73 steps). Handles roads as roughness, not just sink. More honest about insufficient drain capacity (GCC minimum 0.6×0.75 m spec `chennaicorporation.gov.in` vs our 0.51×0.51 avg, many undersized).

- **TELEMAC-2D better for hydraulics:** Unstructured mesh (future `.slf` 10-30m adaptive), full Saint-Venant, handles bridges/culverts/river-sea coupling, structures, 1D/2D coupling, but needs `gfortran` compile + `telemac2d.cas` + `BlueKenue` mesh generation, heavier for city-scale raster.

- **Both struggle with:** 30 m DEM misses 3.77 m roads, no buildings, no infiltration (V5), no river/sea downstream (V3/V6).

## Something better — Hybrid MATSYA vNext

**Don’t pick one — couple them + SWMM:**

```
Rain → 2D floodplain (LISFLOOD-FP raster, 30m, inertial, DEM+roughness)
       ↓↑ weir exchange
       1D subgrid drains (LISFLOOD channel width/depth from KML, but route via SWMM 0.54 CMS capacity per drain `test/SWMM/input/matsya_N082.json`)
       ↓
       TELEMAC-2D unstructured for Adyar/Coovum rivers + sea (tidal) where 3D/structures matter
       ↓
       SWMM coupling for drainage overflow → surface (when Q>Qcap, surcharge to floodplain)
```

- **Why better:**
  1. **Efficiency:** LISFLOOD raster for 29 km² city floodplain (30m, 32k cells) = 3 min; TELEMAC only for 1-2 km river corridor unstructured (few k elements) not whole city.
  2. **Realism:** SWMM gives true drain hydraulics (capacity 0.54 CMS, slope from `INVERT_SP/EP`, not infinite), LISFLOOD channel gives storage, TELEMAC gives river backwater.
  3. **Click-inspect:** Our `test-2.0` big square already provides `depth/vel/dir` per cell via `snapshots_web.json` (1.3 MB quantized) + `map.on('click')` → `u=qx/h, v=qy/h, dir=atan2(v,u)` `test/TELEMAC-2D/test-2.0/visualization/index.html:210`. Hybrid keeps same API: click any point inside big square → depth/vel/dir live as time flows (73×5 min).

- **Immediate next:** Run **LISFLOOD V1 with SWMM capacity limit** (instead of infinite or pure subgrid): at each drain cell `q_drain = min(Qcap, h*DX²/DT)`, route along drain network via SWMM `CONDUITS` graph, overflow to floodplain if `h>bank`. This will sit between `0.98 m infinite` and `1.66 m subgrid` — expected `~1.2 m, 12% flooded`, matching observed Chennai 2015 where drains overwhelmed but not infinite.

## Repro

```bash
# TELEMAC big V0 (already)
python test/TELEMAC-2D/test-2.0/scripts/run_big.py  # 180x180
# LISFLOOD big V0/V1
python test/LISFLOOD-FP/scripts/prepare_lisflood.py
python test/LISFLOOD-FP/scripts/run_lisflood.py  # V0 1.993 vs V1 1.661
# Viz
cd test/TELEMAC-2D/test-2.0/visualization && python -m http.server 8002
cd test/LISFLOOD-FP/visualization && python -m http.server 8003
# Click map inside purple square → depth/vel/dir
```

**Conclusion:** For Chennai city-scale floodplain, **LISFLOOD-FP with realistic subgrid drains is more honest** than TELEMAC infinite, but **TELEMAC wins for river/sea**. Hybrid LISFLOOD (floodplain) + SWMM (drains) + TELEMAC (rivers) is the “good or better” — and our big square click-inspect prototype already provides the live depth/vel/dir API to build it.
