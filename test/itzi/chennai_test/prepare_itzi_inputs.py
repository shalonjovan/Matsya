#!/usr/bin/env python3
"""Prepare Itzi inputs from existing Chennai test data (same big square as TELEMAC test-2.0)"""
import pathlib, rasterio, numpy as np, json
BASE=pathlib.Path(__file__).parent
INPUT=BASE/"input"
# Source is test-2.0 big square
SRC_DEM="/home/cac/Storage/coding/projects/matsya/test/TELEMAC-2D/test-2.0/input/dem_clipped.tif"
SRC_ROUGH="/home/cac/Storage/coding/projects/matsya/test/TELEMAC-2D/test-2.0/input/roughness.npy"
SRC_DRAIN="/home/cac/Storage/coding/projects/matsya/test/TELEMAC-2D/test-2.0/input/drain_mask.npy"

# Load and save as GeoTIFFs for GRASS import
import rasterio
with rasterio.open(SRC_DEM) as ds:
    dem=ds.read(1)
    prof=ds.profile
    bounds=ds.bounds
    # Save as input/dem.tif (for Itzi)
    with rasterio.open(INPUT/"dem.tif",'w',**prof) as dst:
        dst.write(dem,1)
    print(f"DEM {dem.shape} {dem.min():.2f}-{dem.max():.2f} -> {INPUT/'dem.tif'}")

# Friction: from roughness.npy (0.03 land, 0.02 roads)
rough=np.load(SRC_ROUGH)
with rasterio.open(SRC_DEM) as ds:
    prof=ds.profile
prof.update(dtype='float32', nodata=-9999)
with rasterio.open(INPUT/"friction.tif",'w',**prof) as dst:
    dst.write(rough.astype(np.float32),1)
print(f"Friction {rough.shape} mean {rough.mean():.3f} -> {INPUT/'friction.tif'}")

# Rain: constant 50 mm/hr for 1 hr, then 0. For Itzi we can create a single raster of 50 mm/hr and use it as constant, or create a time series
# Itzi expects rain as raster or STRDS. For simplicity, create a single rain raster 50 mm/hr
rain=np.full_like(dem, 50.0, dtype=np.float32)
with rasterio.open(INPUT/"rain_50mm.tif",'w',**prof) as dst:
    dst.write(rain,1)
print(f"Rain 50 mm/hr -> {INPUT/'rain_50mm.tif'}")

# Bctype / bcval: outlet at east low boundary (lowest DEM at east edge)
# Find lowest point on boundary (east edge, 4.17 m)
import numpy as np
# Create bctype raster: 0 = no boundary, 4 = fixed depth 0 (as in tutorial)
bctype=np.zeros_like(dem, dtype=np.int32)
bcval=np.zeros_like(dem, dtype=np.float32)
# Set outlet at east edge, middle row where DEM is low (row ~90, col 179)
# Find min DEM on east edge
east_col=dem[:,-1]
min_row=np.argmin(east_col)
bctype[min_row, -1]=4  # fixed depth
bcval[min_row, -1]=0.0
print(f"Bctype outlet at row {min_row} col {dem.shape[1]-1} dem {dem[min_row,-1]:.2f}")
with rasterio.open(INPUT/"bctype.tif",'w',**prof) as dst:
    dst.write(bctype,1)
with rasterio.open(INPUT/"bcval.tif",'w',**prof) as dst:
    dst.write(bcval,1)
print(f"Bctype/bcval -> {INPUT/'bctype.tif'}")

# Drainage: copy SWMM inp for Itzi coupling (use matsya_N082.inp as example, but need to clip to big square? For now use full)
import shutil
shutil.copy("/home/cac/Storage/coding/projects/matsya/test/SWMM/input/matsya_N082.inp", INPUT/"drainage.inp")
print(f"Drainage SWMM -> {INPUT/'drainage.inp'} (956 drains in big square, but SWMM inp is for N082 53 drains - for demo, would need big square SWMM)")

# Also create a big square SWMM inp by clipping? For now note
print("Note: For true big square, need SWMM inp clipped to 80.15-80.20,13.08-13.13 (956 drains) - currently using N082 53 drains as placeholder")

# Create meta for reference
meta={
    "bbox": [80.15,13.08,80.20,13.13],
    "rows": dem.shape[0],
    "cols": dem.shape[1],
    "dx": 30,
    "dem": str(INPUT/"dem.tif"),
    "friction": str(INPUT/"friction.tif"),
    "rain": str(INPUT/"rain_50mm.tif"),
    "bctype": str(INPUT/"bctype.tif"),
    "drainage": str(INPUT/"drainage.inp"),
    "notes": "Big square 180x180 @30m, same as TELEMAC test-2.0"
}
with open(INPUT/"meta.json",'w') as f:
    json.dump(meta,f,indent=2)
print(f"Meta -> {INPUT/'meta.json'}")
