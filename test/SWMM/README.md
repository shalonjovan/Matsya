# MATSYA — SWMM Test

**Purpose:** Test Chennai drainage data (GCC SWD KML) through EPA SWMM.

**Structure:**
```
test/SWMM/
  input/          # SWMM .inp models + JSON conversion reports
    matsya_N082.inp          # 53 drains, Ward N082 (Menambedu) – primary small test
    matsya_N082.json         # conversion assumptions/warnings
    matsya_bbox_320.inp      # 320 drains, bbox 80.15,13.09,80.17,13.13 – medium test
    matsya_bbox_320.json
  output/         # simulation outputs
    matsya_N082.rpt          # SWMM report
    matsya_N082.out          # SWMM binary output
    matsya_N082_summary.json # parsed summary
    matsya_bbox_320.rpt/.out/.json
  scripts/
    kml_to_swmm.py           # KML → SWMM .inp converter (core)
    run_swmm.py              # pyswmm runner
    analyze_results.py       # mass balance / flooding analysis
  reports/
    MATSYA_SWMM_Test_Report.md
```

## Installation

```bash
pip install --break-system-packages pyswmm pyproj geopandas shapely pyarrow
# pyswmm includes swmm-toolkit (EPA SWMM 5.2.4 engine) as libswmm5.so
# pyproj for WGS84 (EPSG:4326) → UTM 44N (EPSG:32644) projection
python -c "import pyswmm; print(pyswmm.__version__)"
```

Verified: `pyswmm 2.1.0`, `pyproj 3.7.2`, `geopandas 1.1.4` on Python 3.14.

## Quick Start

### 1. Convert KML → SWMM

```bash
# Ward N082 (small, 53 drains, Managable for initial experiment)
python scripts/kml_to_swmm.py \
  --kml ../../c4907fed-934b-4342-a3f4-74226853719d.kml \
  --ward N082 \
  --out input/matsya_N082.inp

# BBox test (320 drains, ~80.15-80.17E, 13.09-13.13N)
python scripts/kml_to_swmm.py \
  --kml ../../c4907fed-934b-4342-a3f4-74226853719d.kml \
  --bbox 80.15,13.09,80.17,13.13 \
  --out input/matsya_bbox_320.inp

# Custom: synthetic rain 100 mm/hr for 2 hr, snap 2m
python scripts/kml_to_swmm.py --kml ../../KML --bbox ... --rain-intensity 100 --rain-duration-hr 2 --snap-tol 2 --out input/custom.inp
```

KML inspected: `10257` drains, bounds `lon 80.132-80.327, lat 12.862-13.230`. Key fields: `DRAIN_WID`, `DRAIN_DEP`, `INVERT_SP/EP`, `TYP_MAT/SWD_MAT`, `COVER`, `LineString` geometry. See `MATSYA_project_context.md` Sec 11-15.

### 2. Run SWMM

```bash
python scripts/run_swmm.py --inp input/matsya_N082.inp --out-dir output
# → output/matsya_N082.rpt, .out, _summary.json

# Analyze
python scripts/analyze_results.py output/matsya_N082.rpt
```

### 3. Validate

Continuity errors should be < 5%:
- Runoff Quantity Continuity < 1%
- Flow Routing Continuity < 1%

Flooding nodes indicate where drainage capacity is exceeded under synthetic storm.

## Conversion Pipeline

```
KML (WGS84 lon/lat)  ──iterparse──►  drains list
                              │
                              ▼
       pyproj Transformer EPSG:4326 → EPSG:32644 (UTM44N for Chennai)
                              │
                              ▼
           length_m = Σ euclidean(UTM)  vs  DRAIN_LEN/SHAPE_LEN
                              │
                              ▼
      endpoint clustering (snap_tol=5m → union-find)
             106 endpoints → ~93 clusters (Ward N082)
                              │
                              ▼
   junctions (elevation = min invert in cluster, max_depth = max DRAIN_DEP+0.3)
   conduits (direction = higher invert → lower, RECT_OPEN, manning per material)
   outfalls (outgoing==0, multi-inlet split with dummy 10m conduit)
                              │
                              ▼
       SWMM .inp sections: TITLE, OPTIONS, RAINGAGES, SUBCATCHMENTS,
       SUBAREAS, INFILTRATION, JUNCTIONS, OUTFALLS, CONDUITS, XSECTIONS,
       LOSSES, TIMESERIES (TS1 50mm/hr, 60min, 5-min steps), REPORT, COORDINATES, VERTICES, Polygons
                              │
                              ▼
                 SWMM engine (pyswmm / libswmm5.so)
                              │
                              ▼
        results: .rpt (continuity, flooding, flow), .out (binary), mass balance
```

## Assumptions Documented per Run (JSON)

- **CRS:** WGS84 → UTM44N for metric calculations (`test/SWMM/scripts/kml_to_swmm.py:187-203`)
- **Snap:** 5 m tolerance
- **Manning:** 0.014 concrete, 0.017 brick (`kml_to_swmm.py:67-82`)
- **XSection:** RECT_OPEN, width=DRAIN_WID, depth=DRAIN_DEP, fallback 0.5×0.5 (`:253-256`)
- **Invert:** outlier >100 or <-5 flagged as missing, imputed via nearest known with 0.001 slope (`:238-247`)
- **Subcatch:** 1 ha per junction (0.5 ha for bbox), 70% imperv, Horton 3.0/0.5 mm/hr (`:811-843`)
- **Rain:** synthetic RG1 INTENSITY 50 mm/hr, 60 min, TS1 at 5-min steps (`:728-735`)
- **Outfalls:** nodes with outgoing==0; multi-inlet outfalls get dummy conduit (`:605-667`)

## Results (Synthetic Storm)

| Model | Drains | Junctions | Outfalls | Conduits | Continuity (Runoff) | Continuity (Routing) | Flooded Nodes | Total Flood Vol |
|-------|--------|-----------|----------|----------|---------------------|----------------------|---------------|-----------------|
| N082 (Ward) | 53 | 53 | 41 | 54 | -0.42% | 0.126% | 13 | ~3.7×10⁶ L |
| bbox 320 | 320 | 315 | 237 | 335 | -0.60% | 0.038% | 39 | 7.56×10⁶ L |

Precip 54.167 mm (50 mm/hr × 1 hr + 5-min interpolation). Runoff ~53 mm, Infil ~1 mm — mass balance holds (V_rain ≈ V_runoff + V_infil + V_storage).

Flooding indicates drainage insufficiency under this storm — matches `MATSYA_project_context.md` experiment questions: *how much water remains, how long, where does it accumulate?*

## Next Steps (Roadmap Phase 1→2)

- DEM/elevation source for junction inverts where missing
- Reduce snap_tol to 2 m and introduce line-intersection snapping (tributary mid-line)
- Calibrate Mannings / infiltration from field data
- Replace synthetic subcatchments with GIS-delineated catchments
- Couple with 2D surface engine (TELEMAC-2D / LISFLOOD-FP / ANUGA)

## References

- `MATSYA_project_context.md` (§7 SWMM, §12 KML→SWMM, §16 Rainfall)
- EPA SWMM 5.2 Manual, `swmm_toolkit` docs
- GCC SWD KML: `c4907fed-934b-4342-a3f4-74226853719d.kml` (10257 drains, Ward N082 = 53)
