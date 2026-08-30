# Itzi Test — Chennai Big Square (same as TELEMAC test-2.0)

**Clone:** `test/itzi/itzi` from https://github.com/ItziModel/itzi.git (26.6, 2025-08, GRASS 8.4 required)
**Domain:** Same big square 180×180 @30m (80.15-80.20E,13.08-13.13N =29.7 km²) as `test/TELEMAC-2D/test-2.0`
**Data we have:** DEM 180×180 `test/TELEMAC-2D/test-2.0/input/dem_clipped.tif` (4.17-73.69 m), roads 446, drains 956 (width 1.06 m), SWMM `test/SWMM/input/matsya_N082.inp` etc., rainfall 50 mm/hr×1 hr
**What more needed for Itzi:** GRASS GIS database, friction raster, rainfall raster/STRDS, bctype/bcval, SWMM drainage, infiltration if needed, proper region/mask.

This folder prepares all Itzi inputs from existing Chennai data so `itzi run chennai.ini` would work once GRASS is installed.

Structure:
- `input/` — GeoTIFFs converted from existing test data (DEM, friction, rain, bctype)
- `grass_setup.sh` — creates GRASS location/mapset and imports rasters
- `chennai.ini` — Itzi config (time, input, output, drainage, statistics, grass)
- `output/` — would contain water_depth, wse, v, vdir, drainage_flow etc.

See `../itzi/docs/tutorial.rst` for full GRASS workflow.
