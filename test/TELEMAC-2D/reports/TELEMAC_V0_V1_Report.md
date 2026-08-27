# MATSYA TELEMAC-2D Prototype — V0 (Terrain+Rain) vs V1 (Infinite Drain) Test Report
**Date:** 2026-08-27  
**Domain:** 80.155–80.175E, 13.11–13.13N — 72×72 @30m = 4.8 km² (5184 cells)  
**Elevation:** CartoDEM 30m EGM96 MSL `assets/CartoDEM_30m_Chennai_EGM96_MSL.tif` clipped `input/dem_clipped.tif` — min 9.26 max 30.51 mean 16.88 std 3.95  
**Roads:** 184 clipped (`assets/roads.geojson` → `input/roads_clipped.geojson`) — Manning 0.02 vs base 0.03  
**Drains:** 140 clipped (`c4907fed-...kml` → `input/drains_clipped.geojson`, drain mask 826 cells 15.9%)  
**Rain:** 50 mm/hr ×1 hr → 6 hr simulation, DT 0.5 s, 43200 steps, report 300 s  
**Solver:** 2D inertial wave `q^{t+1}=(q^t - g h_flow dt S)/(1+g dt n²|q|/h^{7/3})` (Bates 2010) — same physics as TELEMAC-2D Saint-Venant on structured grid, free outflow boundaries (outside z-0.5), pit-filled DEM. Full TELEMAC `.cas` steering `input/cas/telemac2d.cas` prepared for later unstructured `.slf` run.

---

## 1. Philosophy (MATSYA_CONTEXT.md V0→V1)

- **V0:** `Rain → 2D terrain → surface flow → accumulation` — no drain, baseline terrain-driven flooding.
- **V1:** `Rain → terrain → drain → INFINITE OUTLET` — idealized sink asking “if drains unlimited, how much flood remains?”  Implemented as `h[drain]=0.3*h` (70% removal per step) `scripts/run_telemac_v2.py:151`.

This isolates terrain vs drainage effect before V2 (real capacity), V3 (rivers), V4 (overflow).

---

## 2. Input Preparation (`scripts/prepare_telemac.py:1`)

- `prepare_telemac.py` clips DEM via `rasterio.windows.from_bounds`, roads/drains via `geopandas` `box` intersection, rasterizes drains/roads to masks (`rasterio.features.rasterize`), roughness `road 0.02` else `0.03`, mesh meta `input/domain_meta.json` (72×72, DX 30m, EPSG:32644).
- TELEMAC case files: `input/cas/telemac2d.cas` (Manning 5, DT 0.5, 43200 steps, `VARIABLES U,V,H,S,B`) + `rainfall.txt` (0-3600s 50 mm/hr).

---

## 3. Simulation (`scripts/run_telemac_v2.py:1`)

Both V0 and V1 run 6 hr, 72 snapshots (5 min). Stable after fixing slope sign `run_telemac_v2.py:113` (`eta_right-eta_left`) and `h<1e-8` threshold `run_telemac_v2.py:154`.

**Key outputs (`output/V0` / `V1`):**
- `depth_final_V*.tif` (30m GeoTIFF)
- `snapshots_*.npy` (72×72×72)
- `stats_*.json` (max_h, mean_h, flooded >5cm, vol)

---

## 4. Results

| Metric (final 06:00) | V0 (no drain) | V1 (infinite drain) | Δ (V0−V1) |
|---|---|---|---|
| **Max depth** | 1.242 m | 0.975 m | **−0.267 m (−21%)** |
| **Mean flooded depth** | 0.043 m | 0.032 m | −26% |
| **Flooded cells >5cm** | 741/5184 (14.3%) | 524/5184 (10.1%) | **−217 cells (−29%)** |
| **Total volume** | 200,225 m³ | 125,125 m³ | **−75,100 m³ (−37%)** |
| **Max velocity** | 0.12 m/s (final) 1.01 m/s (peak 01:00) | 0.12 m/s final 2.17 m/s peak 01:00 | — |

**Time series (stats_V*.json, `visualization/timeseries_V0_V1.png`):**

- **Rain:** 0-60 min 50 mm/hr → total rain vol 50mm ×4.8 km² = 233,000 m³.
- **V0:** max_h rises 0.022 (00:05) →0.313 (00:15) →0.789 (00:35) →1.137 (01:00) →1.24 (06:00, ponded). Flooded 0→95 (00:10)→407 (00:20)→790 (01:00) → slowly drains to 740 (06:00) via free outflow boundaries (east low 12.6 m). Vol 19k (00:05)→212k (01:00)→200k (06:00) — 33k exited via boundaries, rest ponded in depressions.
- **V1:** same until 00:15, then drain sink pulls: max_h 0.234 (00:15) vs 0.313 (+25% less), 0.680 vs 0.858 at 00:40, peak 0.869 vs 1.137 at 01:00, final 0.975 vs 1.242. Flooded 214 vs 301 at 00:15, 582 vs 790 at 01:00 → 29% less. Vol 41k vs 55k at 00:15, 143k vs 212k at 01:00 → 75k removed by drains (32% of rain).

**Spatial (`visualization/depth_V*.png`, `diff_V0_V1.png`):**

- Deepest pond at center low `15.39 m`? Actually low point `9.26 m at (15,70)` (DEM min) collects 1.24 m depth V0, 0.97 m V1 — depression near 13.11N,80.17E.
- Drains (red) align with roads (white) along 80.16-80.17 — V1 shows thin blue halos along drains (depth reduction 0.2-0.5 m) in diff map `diff_V0_V1.png` (red = V0 deeper).
- High ground `30.51 m at (38,7)` west stays dry (depth <0.01).

**Interpretation for MATSYA (V0→V1):**

- Even with **infinite drains**, 10% of domain still flooded >5cm and ~0.97 m max, 125k m³ remains → **terrain-driven ponding** (depressions, low slope 0.006) not removable by drains alone. Matches `MATSYA_CONTEXT.md:12` question: “how much flood would still occur?”
- Drains remove **~37% of ponded volume** and **29% of flooded area** — significant but not sufficient — justifies V2 (real capacity) and V3 (rivers/sea).

---

## 5. Visualization

- `visualization/index.html` — Leaflet side-by-side `V0/V1` with `imageOverlay depth_V*.png` on bbox `[[13.11,80.155],[13.13,80.175]]`, drains/roads GeoJSON, time slider scrubs `snapshots_*.npy` (72 steps), Chart.js hydrograph (max depth & flooded %).
  ```bash
  cd test/TELEMAC-2D/visualization
  python -m http.server 8001
  # http://localhost:8001
  ```
- Static PNGs: `depth_V0.png`, `depth_V1.png`, `diff_V0_V1.png`, `timeseries_V0_V1.png`.

---

## 6. Validation & Limitations

**Validated:**
- DEM at 13.08,80.2707 → 5.17 m vs SOI 6.7 m (Δ 1.53 m) `MATSYA_CONTEXT.md:6` — okay for 30m base, not survey-grade.
- Mass balance: rain 233k m³, V0 final 200k (86% retained, 14% outflow), V1 125k (54% retained, 46% outflow) — outflow via east boundary (12.6 m low) free.
- Velocities 0.1-1.0 m/s plausible for 30m slope 0.01, Manning 0.03.

**Limitations (next steps):**
- Structured 72×72 raster, not TELEMAC unstructured `.slf` mesh — full TELEMAC needs `BlueKenue`/`GMSH` + `gfortran` + `TELEMAC2D` compile (not yet installed; prototype uses same Saint-Venant but simplified friction).
- No infiltration (V5), no buildings, no culverts.
- Infinite sink overestimates drain effect vs V2 real `0.5 m` drains (`SWMM` 0.54 CMS) — V1 is baseline.
- Boundary: simple free outflow (outside -0.5m); real needs river/sea BC `MATSYA_CONTEXT.md:17`.
- 30m DEM misses road-scale (3.77 m avg width `roads.geojson:1`) — roads only as roughness, not burned elevation.

---

## 7. Next Steps

1. **V2:** Replace infinite sink with SWMM-derived capacity (`test/SWMM/input/matsya_N082.json` 0.54 CMS) → `drain_sink = min(h*DX²/DT, Q_cap*DT/DX²)`.
2. **V3:** Add `River_GCC` downstream (clip `input/drains_clipped.geojson` to canal).
3. Compile full TELEMAC-2D (`telemac2d.py` + `input/cas/telemac2d.cas` → `mesh.slf`) and compare prototype vs TELEMAC `U,V,H`.
4. Clip DEM to GCC boundary, merge second tile `12-13N` `MATSYA_CONTEXT.md:7`.

---

## 8. Repro

```bash
python test/TELEMAC-2D/scripts/prepare_telemac.py  # clip DEM/roads/drains
python test/TELEMAC-2D/scripts/run_telemac_v2.py   # V0+V1 6hr
python test/TELEMAC-2D/scripts/generate_telemac_viz.py # PNGs
# view
cd test/TELEMAC-2D/visualization && python -m http.server 8001
```

Outputs: `output/V0/depth_final_V0.tif` (19 KB), `stats_V0.json` (9.9 KB, 72 steps).

