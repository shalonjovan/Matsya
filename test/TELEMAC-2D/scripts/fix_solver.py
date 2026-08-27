#!/usr/bin/env python3
# Quick fix test: fill pits and adjust dt
import rasterio, numpy as np, pathlib
from scipy.ndimage import minimum_filter

tif="/home/cac/Storage/coding/projects/matsya/test/TELEMAC-2D/input/dem_clipped.tif"
with rasterio.open(tif) as ds:
    dem=ds.read(1).astype(float)
    # simple pit fill: iterative
    # Use approach: dem_filled = maximum of dem and minimum of neighbors + epsilon?
    # For now, just fill single-cell pits by replacing pit cell with min neighbor +0.01 if lower than all neighbors
    filled=dem.copy()
    rows,cols=dem.shape
    for _ in range(5):
        # For each cell, if it's lower than all 8 neighbors, raise to min neighbor
        padded=np.pad(filled,1,mode='edge')
        for i in range(rows):
            for j in range(cols):
                center=filled[i,j]
                neighbors=padded[i:i+3, j:j+3]
                min_nei=np.min(neighbors[neighbors!=center])
                if center < min_nei - 0.1: # pit
                    filled[i,j]=min_nei+0.01
    print(f"DEM before pit fill min {dem.min():.2f} max {dem.max():.2f} mean {dem.mean():.2f}")
    print(f"after fill min {filled.min():.2f} max {filled.max():.2f} mean {filled.mean():.2f}")
    # also check depressions depth
    diff=filled-dem
    print(f"pit fill diff max {diff.max():.2f} mean {diff.mean():.3f} cells changed {(diff>0.01).sum()}")
    # Save filled
    profile=ds.profile
    with rasterio.open("/tmp/dem_filled.tif",'w',**profile) as dst:
        dst.write(filled.astype(np.float32),1)
    # also check outflow: check edge elevations vs interior
    print("edge elevations", filled[0,:3], filled[-1,:3], filled[:,0][:3], filled[:,-1][:3])
