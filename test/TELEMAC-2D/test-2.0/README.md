# MATSYA test-2.0 — Big Square Click-Inspect

**Goal:** Big square domain, calculate only inside, click any point → depth/velocity/direction live as time flows.

**Domain:** 80.15-80.20E,13.08-13.13N = 5.4×5.5 km =29.7 km², 180×180 @30m =32400 cells `input/domain_meta.json`

**Inputs:**
- DEM `input/dem_clipped.tif` 180×180 min 4.17 max 73.69 mean 15.53 (CartoDEM 30m EGM96 clip `scripts/prepare_big.py:1`)
- Roads 446 `input/roads_clipped.geojson` (avg width 3.77m) mask 2477 cells 7.6%
- Drains 956 drains `input/drains_clipped.geojson` mask 6188 cells 19.1% (but V0 = no drain sink, baseline)
- Roughness `input/roughness.npy` 0.03 land /0.02 road

**Solver:** Inertial wave `q^{t+1}=(q-g h dt S)/(1+g dt n²|q|/h^{7/3})` `scripts/run_big.py:1` DT 0.8 s, DX 30 m, 27000 steps → 73 snapshots (300s), pit-filled DEM, free outflow outside z-0.5, rain 50 mm/hr 3600s.

**Run:**
```bash
python scripts/prepare_big.py
python scripts/run_big.py  # 180x180 ~3 min
python scripts/generate_web.py
```

**Results (V0 big, no drain):**
- max depth 1.993 m at 06:00 (peak 1.507 at 01:00 rain stop +1.99 at 06:00 ponded), mean flooded 0.047 m, flooded >5cm 5026/32400 15.5% (max 5352), vol 1.37M m³ (vs rain 50mm×29.7km²=1.485M m³ → 92% retained, 8% outflow)
- Time series `output/V0/stats.json` + `visualization/timeseries.png` (blue max depth, green flooded%): 0→0.17 (00:10)→0.67 (00:20)→1.50 (01:00)→1.99 (06:00) — eastern low 4.17 m collects water.

**Visualization live click:**
```bash
cd test/TELEMAC-2D/test-2.0/visualization
python -m http.server 8002  # http://localhost:8002
```
- Map `index.html:1` Leaflet `tile.openstreetmap.fr/hot` (no API key) + canvas heatmap 180×180 from `snapshots_web.json` (1.3 MB quantized base64+zlib `scripts/generate_web.py:1`, pako inflate) — slider 0-72 (00:00-06:00) scrubs depth heatmap live via `renderDepth()` `index.html:158` `depthToColor()` 0-2m.
- **Click any point inside purple big square** (80.15-80.20,13.08-13.13) → samples `depth[t][row][col]`, `u=qx/h, v=qy/h` `run_big.py:1` stored `vel_u.npy`/`vel_v.npy` → popup `Depth 0.42 m | Vel 0.34 m/s | Dir 142° SE | u 0.12 v 0.31 | Cell [123,45] | Time 03:20` + time series at that cell `clickChart` (depth + vel vs time). Updates live as slider moves (`update()` `index.html:210`).
- Right `System Hydrograph` max depth / flooded % vs hr, rain bar 50 mm/hr 0-1hr.

**Possible?** Yes — obstacles were DEM 30m (road sub-pixel), 5.5km² 32k cells → 73×32k=2.3M floats per var → 1.3 MB quantized (was 45 MB float) via `depth_q=depth/2*255 uint8` `scripts/generate_web.py:1`, DT 0.5→0.8 for big speed, browser memory <20 MB, tile 403 fixed by HOT.

**Next:** V1 infinite drain for big square (same mask) would reduce flooded ~30% as in 72×72 test, then V2 real drain Q.
