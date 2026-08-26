# MATSYA — SWMM Drainage Test Report
**Date:** 2026-08-27  
**Zone:** Chennai GCC SWD KML `c4907fed-934b-4342-a3f4-74226853719d.kml`  
**Engine:** EPA SWMM 5.2.4 via `pyswmm 2.1.0` + `pyproj 3.7.2` (UTM44N)  
**Spec:** `MATSYA_project_context.md` Phase 0–1 (KML → hydraulic network → synthetic rainfall → validation)

---

## 1. Objective

Build smallest defensible drainage simulation for MATSYA per §10 *Immediate experiment*:

```
DEM / terrain (not yet) + Drainage KML + Synthetic rainfall → SWMM → water depth / runoff / drainage → validation
```

Test KML→SWMM conversion, hydraulic topology reconstruction, and SWMM engine execution.

---

## 2. Folder Created

`test/SWMM/` with subfolders `input/`, `output/`, `scripts/`, `reports/` — as requested.
All code is code-first (`kml_to_swmm.py:1`, `run_swmm.py:1`, `analyze_results.py:1`).

```
test/
└─ SWMM/
   ├─ input/                 # generated .inp + .json
   ├─ output/                # .rpt, .out, _summary.json
   ├─ scripts/               # converters & runners
   └─ reports/               # this report
```

---

## 3. SWMM Installation

```bash
pip install --break-system-packages pyswmm pyproj geopandas
```

- `pyswmm` wraps `libswmm5.so` (EPA engine) via `swmm.toolkit.solver`
- Verified with `Example1.inp` from `dleutnant/swmmr` (CMS/INTENSITY, HORTON, DYNWAVE) — simulation OK, then tailored for Chennai metric units.

No system `swmm` binary required; engine is programmatic.

---

## 4. KML Inspection (Phase 0)

**File:** `c4907fed-... .kml` (GCC Storm Water Drains), 554 240 lines, 10 257 Placemarks.

**Schema fields found** (`kml_to_swmm.py:90-184`): 42 fields including `DRAIN_WID`, `DRAIN_DEP`, `DRAIN_LEN`, `SHAPE_LEN`, `INVERT_SP/EP`, `STRT_EAST/NORTH`, `END_EAST/NORTH`, `DRAIN_SIZE`, `DRAIN_TYPE`, `TYP_MAT/SWD_MAT`, `COVER`, `LOCATION`, `WARD`, `ZONE`, `ST_NAME`, `STATUS`.

**Geometry:** `LineString` with 2–163 points per drain (mean 11.6), coordinates `lon,lat,0` WGS84 (`kml_to_swmm.py:249`).

**Statistics:**

| Metric | Value |
|--------|-------|
| Wards | ~205 unique (e.g., N082=53, N156=196 max, N150=179) |
| Zones | N01–N15 (N11=1471 largest) |
| Bounds (lon/lat) | 80.132–80.327, 12.862–13.230 |
| DRAIN_WID | 0–4.47 m, mean 0.886, median 0.88 (9 zeros) |
| DRAIN_DEP | 0–4.47 m, mean 0.885 (9 zeros) |
| DRAIN_LEN | 0–7188 m, mean 220 m |
| SHAPE_LEN | 0–3035 m, mean 216 m — mismatches flagged (`kml_to_swmm.py:261`) |
| INVERT_SP/EP | -0.9–104860 m (8 outliers >100 or <-5 flagged; e.g., 104860 at Thiruvallur High Road) |
| Missing inverts | ~117 of 20514 endpoints |
| COVER | Yes 8790, No 1331 |
| DRAIN_DETL | Closed 8471, Open 901 |
| STATUS | Good 9429, Bad 824 |

**Coordinate-system issue (§14):** `STRT_EAST/NORTH` & `END_EAST/NORTH` appear as UTM-like meters (~406k–427k E, 1 422k–1 462k N) but with data entry swaps (e.g., OBJECTID 433 `STRT_NORTH=412166` should be ~1.44M). Therefore **we ignore those fields** and compute lengths from WGS84→UTM44N via `pyproj.Transformer EPSG:4326→EPSG:32644` (`kml_to_swmm.py:187-219`). Chennai lon 80E → UTM44N (CM 81E) correct for metric distances.

**Missing hydraulic info (§15) — assumptions documented per run in JSON (§7 assumptions):**
- Diameter/width/depth: use `DRAIN_WID/DEP` directly, fallback 0.5 m.
- Invert: outlier >100 treated missing, imputed via nearest known with 0.001 slope.
- Manning: 0.014 concrete, 0.017 brick (per `TYP_MAT/SWD_MAT`), else 0.014.
- Slope: not assumed; computed as ( Invert_up − Invert_down )/length.
- Cross-section: `RECT_OPEN`, Geom1=depth, Geom2=width.
- Length: UTM geodesic sum, fallback `DRAIN_LEN` if <1 m.
- Outfalls: not in KML; reconstructed from topology (nodes with outgoing==0).

---

## 5. KML → SWMM Conversion

Implemented in `test/SWMM/scripts/kml_to_swmm.py:222-689`.

**Topology reconstruction:**

1. Project each drain’s lon/lat to UTM44N.
2. Compute `length_computed` = Σ hypot(dx,dy) (metric). Compare to `DRAIN_LEN`.
3. Collect 2×N endpoints (Ward N082 → 106 pts).
4. Union-find clustering with 5 m tolerance (`kml_to_swmm.py:293-355`). For N082: 106→93 clusters.
5. Handle self-loops (drain shorter than snap) by splitting (`:462-487`).
6. Junction elevation = min invert in cluster; impute missing via nearest neighbor (`:403-439`). `max_depth = max(DRAIN_DEP)+0.3`.
7. Flow direction = higher invert → lower; else KML order (`:488-506`).
8. Outfall detection: nodes with `outgoing==0 && incoming>0`; multi-inlet outfalls get dummy 10 m conduit to new outfall (`:581-667`) to satisfy SWMM Error 141.
9. Vertices = interior LineString points for map (`:574-579`).

**Output sections generated (`:692-937`):** `TITLE`, `OPTIONS` (CMS, HORTON, DYNWAVE, DEPTH offsets, 30 s routing), `EVAPORATION`, `RAINGAGES` (RG1 INTENSITY 0:05 → TS1), `SUBCATCHMENTS` (1 ha per junction, 70% imperv, 50 m width, 0.5% slope), `SUBAREAS`, `INFILTRATION`, `JUNCTIONS`, `OUTFALLS`, `CONDUITS`, `XSECTIONS` (RECT_OPEN), `LOSSES`, `TIMESERIES` (dense 5-min steps for 50 mm/hr × 60 min), `REPORT`, `MAP`, `COORDINATES` (lon/lat), `VERTICES`, `Polygons`, `SYMBOLS`.

**Warnings tracked in JSON:** len mismatches (5 for N082), outliers, adverse slopes (6 for N082, 25 for bbox).

---

## 6. Synthetic Rainfall Experiment (§16)

Controlled storm: **50 mm/hr for 60 min**, 6‑hr simulation to allow recession.  
Implemented as `RG1 INTENSITY 1.0 TIMESERIES TS1` with TS1 entries every 5 min at 50 mm/hr then 0 (`kml_to_swmm.py:728-735`). This yields total precip 54.167 mm after SWMM interpolation (50 mm/hr × 1 hr + 5‑min ramp) — validated via continuous 5‑min TS (initial sparse TS gave only 8 mm, fixed after inspection of `.rpt`).

**Mass balance target (§16):**  
`V_rain = V_runoff + V_infiltration + V_drainage + V_storage`

---

## 7. Simulations Executed

### 7.1 Ward N082 – Primary Small Test

- **Filter:** `WARD=N082` (Menambedu), 53 drains, bounds ≈ 80.15–80.16E, 13.11–13.12N.
- **Model:** 53 junctions, 41 outfalls, 54 conduits (53+1 dummy), 5 warnings, 6 adverse slopes.
- **Subcatch:** 53 ha total (1 ha each).
- **Command:**
  ```bash
  python scripts/kml_to_swmm.py --kml ../../KML --ward N082 --out input/matsya_N082.inp
  python scripts/run_swmm.py --inp input/matsya_N082.inp --out-dir output
  ```

**Results (`output/matsya_N082.rpt`):**

```
Runoff Quantity Continuity      hectare-m   mm
  Total Precipitation ......    2.871     54.167
  Infiltration Loss ........    0.058      1.087
  Surface Runoff ...........    2.820     53.204
  Final Storage ............    0.005      0.103
  Continuity Error (%) .....   -0.421

Flow Routing Continuity      hectare-m  10^6 L
  Wet Weather Inflow .......    2.817     28.17
  External Outflow .........    2.425     24.25
  Flooding Loss ............    0.370      3.70
  Final Stored Volume ......    0.025      0.25
  Continuity Error (%) .....    0.126

Flooding: 13 nodes flooded (max J0025 5.57 hr, 0.409 CMS, 1.288×10⁶ L)
Outfall Loading: 41 outfalls, total outflow 24.25×10⁶ L
Link Flow Summary: max flow 0.409 CMS (C_DUMMY_J0025), velocities 0.16–1.67 m/s, Full_Depth up to 0.83
```

**Validation:**
- Runoff error -0.42% (<5% good), Routing 0.126% excellent.
- Mass balance: 54.167 ≈ 53.204 + 1.087 + 0.103 (=54.394, diff -0.42% due to timing) — holds.
- Flooding at 13 nodes indicates capacity exceeded at 50 mm/hr, consistent with Bad status drains (5 in this ward).
- Shortest drain: C00036 min-elevation-drop warning handled via MIN_SLOPE 0.

### 7.2 BBox 320 – Medium Test

- **Filter:** `bbox 80.15,13.09,80.17,13.13` (central Chennai), 320 drains (N085 115, N081 67, N082 50…), 315 junctions, 237 outfalls, 335 conduits, 25 adverse slopes.
- **Subcatch:** 157.5 ha (0.5 ha each).
- **Results:**

```
Runoff: Total Precip 8.531 ha-m (54.167 mm), Runoff 8.439 ha-m (53.58 mm), Infil 0.865 mm, Error -0.60%
Routing: Wet Inflow 8.434 ha-m, Outflow 7.559 ha-m, Flooding Loss 0.756 ha-m, Error 0.038%
Flooding: 39 nodes (top J0444 0.78×10⁶ L, J0430 0.636, J0290 0.609), durations up to 5.91 hr
```

Both pass mass-balance validation; instability indexes “All links are stable.”

---

## 8. Outputs Produced

`input/`:
- `matsya_N082.inp` (82 KB, 1420 lines) + `.json` (14 KB assumptions)
- `matsya_bbox_320.inp` (409 KB) + `.json`

`output/`:
- `matsya_N082.rpt` (49 KB), `.out` (364 KB), `_summary.json`
- `matsya_bbox_320.rpt` (230 KB), `.out` (2.1 MB), `_summary.json`

All `.inp` are code-first and GIS-ready (COORDINATES lon/lat, VERTICES interior, Polygons for subcatchments).

---

## 9. Cross-Checks & Limitations

**Verified:**
- Length: UTM geodesic vs `DRAIN_LEN` mismatch flagged (e.g., OBJECTID1 239 vs 370).
- Invert outliers: 104860 at Thiruvallur High Road correctly imputed, not invented.
- Snap: 5 m merges exact coordinate matches (80.1583796) but keeps drains disconnected where gap >5 m — explains 41 outfalls (side drains often isolated, realistic for Chennai).
- Rainfall: Fixed from 8 mm to 54 mm by densifying TS at 5 min (see §6).

**Limitations (next phase):**
- No DEM: junction elevations only from inverts; missing inverts imputed, not surveyed.
- No mid-line snapping: tributary intersecting mid-line of main drain not merged (requires line-distance check).
- Subcatchments synthetic (70% imperv); need GIS delineation via DEM flow direction.
- Uniform Manning/infiltration; need material-specific calibration.
- Rivers/coastal downstream boundaries not modeled (Phase 4).
- Full 10 257-drain model not yet run (would be 10k conduits; bbox 320 is proxy; full inp generation is `python kml_to_swmm.py --kml ... --out input/matsya_full.inp` but not simulated due to runtime).

---

## 10. Next Steps (Roadmap)

- **Phase 1 → 2:** Add DEM (e.g., SRTM/COPERNICUS) for true invert + subcatchment delineation; benchmark TELMAC-2D/LISFLOOD-FP/ANUGA on 100 m×100 m toy slope.
- **Phase 3:** Couple SWMM drainage with 2D surface (exchange via inlet/outlet links).
- **Phase 5:** 3D hotspot at inlets/junctions with OpenFOAM/Basilisk vs 1D/2D.
- **Phase 6–7:** MATSYA orchestration, validation vs observed Chennai floods.

---

## 11. Reproducibility

```bash
# From project root matsya/
ls test/SWMM/scripts/kml_to_swmm.py  # converter, line-referenced above
cat test/SWMM/input/matsya_N082.json # assumptions
cat test/SWMM/output/matsya_N082.rpt # full hydraulics
python test/SWMM/scripts/analyze_results.py test/SWMM/output/matsya_N082.rpt
```

All outputs are versioned and mass-balance-checked.

---

*Evidence before synthesis: all claims backed by parsed `matsya_N082.rpt` and `matsya_N082.json` (see `test/SWMM/output/`).*  
*We are not building all of MATSYA at once — this is the small physically defensible experiment (§10) that can now be scaled.*
