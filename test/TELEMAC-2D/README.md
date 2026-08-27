# MATSYA — TELEMAC-2D Test (V0/V1)

Prototype 2D surface-water test including **elevation + roads + drains** before full TELEMAC compilation.

**Domain:** 80.155–80.175E, 13.11–13.13N — 72×72 @30m = 4.8 km² (5184 cells) — CartoDEM 30m EGM96 clip `input/dem_clipped.tif` (min 9.26 max 30.51 mean 16.88) + 184 roads (`input/roads_clipped.geojson` 3.77 m avg width) + 140 drains (`input/drains_clipped.geojson` mask 826 cells 15.9%).

**Inputs (`input/`):**
- `dem_clipped.tif` — CartoDEM 30m `assets/CartoDEM_30m_Chennai_EGM96_MSL.tif` → `scripts/prepare_telemac.py:1`
- `roads_clipped.geojson` — GCC EDP Roads `assets/roads.geojson`
- `drains_clipped.geojson` — GCC SWD `c4907fed-...kml`
- `drain_mask.npy`, `road_mask.npy`, `roughness.npy` (Manning 0.03 land, 0.02 roads), `domain_meta.json` (72×72)
- `cas/telemac2d.cas` — TELEMAC steering (DT 0.5, 43200 steps 6hr, Manning 5, `VARIABLES U,V,H,S,B`), `rainfall.txt` (50 mm/hr 1hr)

**Solver (`scripts/run_telemac_v2.py:1`):** 2D inertial wave `q^{t+1}=(q- g h dt S)/(1+g dt n²|q|/h^{7/3})` (Bates 2010) like TELEMAC-2D Saint-Venant on structured grid, free outflow (outside -0.5 m), pit-filled DEM. DT 0.5 s, DX 30 m, report 300 s.

**Run:**
```bash
python scripts/prepare_telemac.py   # clip
python scripts/run_telemac_v2.py    # V0 (no drain) + V1 (infinite sink h*=0.3) → output/V0,V1/
python scripts/generate_telemac_viz.py # PNGs
```

**Outputs (`output/V0` `V1`):**
- `depth_final_*.tif` (30m GeoTIFF)
- `snapshots_*.npy` (72×72×72)
- `stats_*.json` (72 steps, max_h, flooded >5cm, vol)

**Results:**
- V0: max 1.242 m, flooded 741/5184 (14.3%), vol 200k m³ (86% of rain 233k retained)
- V1: max 0.975 m, flooded 524/5184 (10.1%), vol 125k m³ → **-29% flooded, -37% vol, -0.27m depth** = infinite drain effect. Even unlimited drains leave 10% flooded → terrain depression, not just drain capacity.

**Visualization (`visualization/`):**
- `index.html` — Leaflet side-by-side `depth_V0.png`/`depth_V1.png` imageOverlay + drains/roads GeoJSON + Chart.js hydrograph + time slider (scrubs 72 snapshots)
  ```bash
  cd visualization && python -m http.server 8001 # http://localhost:8001
  ```
- `depth_V0.png`, `depth_V1.png`, `diff_V0_V1.png`, `timeseries_V0_V1.png` (static)

**Reports:** `reports/TELEMAC_V0_V1_Report.md` — full V0 vs V1 comparison, validation, next steps V2 (real drain Q 0.54 CMS from `test/SWMM`) + V3 rivers.

**Full TELEMAC:** `input/cas/telemac2d.cas` ready for `telemac2d.py` compile with unstructured `.slf` mesh (needs `gfortran`, `TELEMAC-MASCARET`). Prototype validates physics before compile.

