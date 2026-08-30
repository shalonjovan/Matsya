# MATSYA — Itzi Test (GRASS + 2D + SWMM)

**Clone:** `test/itzi/itzi` from https://github.com/ItziModel/itzi.git (26.6, 2025-08) — `itzi` 26.6 installed via `pip --ignore-requires-python` (needs GRASS 8.4, python 3.12-3.13, we have 3.14 with workaround)

**Why Itzi?** Open-source, GRASS-native, 2D surface (damped partial inertia, same Bates 2010 as TELEMAC/LISFLOOD) + **integrated SWMM** for drains (like our SWMM test), space-time rain, hotstart, mass balance. More mature than our prototypes for `drain → overflow → surface` coupling.

**What we have (same big square as TELEMAC test-2.0):**
- DEM 180×180 @30m `test/TELEMAC-2D/test-2.0/input/dem_clipped.tif` (4.17-73.69 m) → copied to `test/itzi/chennai_test/input/dem.tif` (EPSG:4326, 80.15-80.20,13.08-13.13)
- Friction 0.03 land /0.02 roads `test/TELEMAC-2D/test-2.0/input/roughness.npy` → `input/friction.tif`
- Rain 50 mm/hr×1 hr `input/rain_50mm.tif` (constant, for STRDS time-varying need t.create)
- Drains 956 in big square, 6188 cells 19.1% `input/drain_mask.npy`, channel width 1.06 m depth 1.05 m `input/channel_width.tif` — SWMM `input/drainage.inp` (currently N082 53 drains placeholder, need big square SWMM for true 956)
- Roads 446 `input/roads_clipped.geojson`
- Bctype/bcval outlet east low (row 38 col 179 dem 9.69) `input/bctype.tif` (4=fixed depth 0)

**What more needed for Itzi run:**
1. **GRASS GIS 8.4** (`grass --version` not found, `pacman -S grass` needs sudo, we have no password; alternative: `yay` or manual binary). Without GRASS, `itzi run` fails at `grass_session.py` `g.version` and `/tmp/grassdata/itzi_chennai` does not exist.
2. **GRASS location/mapset** `grass -c dem.tif /tmp/grassdata/itzi_chennai -e` + `r.in.gdal` for dem,friction,rain,bctype,bcval, `g.region raster=dem`, `r.mask` watershed if needed. Script `chennai_test/grass_setup.sh` does this.
3. **Proper SWMM big square** `input/drainage.inp` for 956 drains (currently N082 53 drains) — generate via `test/SWMM/scripts/kml_to_swmm.py --bbox 80.15,13.08,80.20,13.13 --out drainage_big.inp`
4. **Time-varying rain STRDS** for 50 mm/hr 0-60 min then 0 (Itzi example uses `t.create`/`t.register` with 3 maps 0,360,360 mm/hr; we have constant 50)
5. **Region/mask** `dem@itzi_chennai` must be set, `hmin 0.005`, `cfl 0.7`, `dtmax 5` already in `chennai.ini`
6. **Python 3.12** (Itzi requires 3.12-3.13, we forced 3.14) — use `uv python install 3.12` + `uv tool install itzi --python 3.12` for clean run.

**Test with Chennai data (prepared, not yet run due to GRASS):**
- `chennai_test/prepare_itzi_inputs.py` → `input/*.tif` (dem, friction, rain, bctype, drainage)
- `chennai_test/chennai.ini` — `[time] duration 02:00:00 record 00:05:00`, `[input] dem,friction,rain,bctype,bcval`, `[output] water_depth,wse,v,vdir,qx,qy,mean_drainage_flow`, `[drainage] swmm_inp=input/drainage.inp`, `[grass] grassdata=/tmp/grassdata location=itzi_chennai`
- `chennai_test/test_config.py` validates `ConfigReader` → `SimParams OK` (we did, `itzi run` now fails only at `grass` step with `/tmp/grassdata/itzi_chennai does not exist`, not config)
- **Next:** Install GRASS (`yay -S grass` or `sudo pacman -S grass`), run `bash grass_setup.sh`, then `itzi run chennai.ini` → would produce `itzi_chennai_water_depth` STRDS, `v`, `drainage.csv`, `itzi_chennai.csv` stats, view via `g.gui.animation` or `r.out.gdal`.

**Comparison to our prototypes:**
- TELEMAC prototype (structured 180×180, DT 0.8, inertial) and LISFLOOD (same but subgrid channel) are **like Itzi core** (`itzi_core/flow.c` damped partial inertia, same Bates) but Itzi adds GRASS GIS, SWMM coupling, and mass balance monitoring (our prototypes had -37% vol reduction for infinite drain, Itzi would give realistic with SWMM Qcap 0.54 CMS).
- Itzi is **better for Chennai drainage** than our hand-rolled infinite sink (TELEMAC V1) or DEM-lowered channel (LISFLOOD) because it does `SWMM DYNWAVE` + weir/orifice `orifice 0.167 free 0.54 submerged 0.056` coupling.

**What to do next:**
1. Install GRASS 8.4 + create location (see `grass_setup.sh`)
2. Regenerate big square SWMM (`kml_to_swmm.py --bbox ... --out drainage_big.inp`)
3. Run `itzi run chennai.ini` and compare to `test/TELEMAC-2D/test-2.0` (TELEMAC 1.99m/15.5% vs Itzi expected ~1.3m/12% with realistic drains)
4. For no-GRASS quick test, use `itzi-core` BMI directly with numpy arrays (like our prototypes) — see `src/itzi/bmi_itzi.py`.

See `chennai_test/README.md` for per-file details.
