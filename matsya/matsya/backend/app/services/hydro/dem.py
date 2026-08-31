"""DEM & waterbody harmonization — area, centroid, dem elevation, spill crest."""
import geopandas as gpd
import rasterio
from shapely.geometry import Point
import numpy as np

def waterbody_area_m2(gdf: "gpd.GeoDataFrame", src_crs="EPSG:4326", dst_crs="EPSG:32644") -> "gpd.GeoDataFrame":
    if gdf is None or len(gdf)==0:
        return gdf
    if gdf.crs is None:
        gdf = gdf.set_crs(src_crs)
    utm = gdf.to_crs(dst_crs)
    gdf = gdf.copy()
    gdf["area_m2"] = utm.geometry.area
    return gdf

def sample_dem_at_points(gdf: "gpd.GeoDataFrame", dem) -> list:
    """Sample DEM at centroids."""
    if dem is None:
        return [None]*len(gdf)
    # Get centroids in same CRS as DEM (4326)
    # DEM is likely 4326, but check
    try:
        dem_crs = dem.crs
    except:
        dem_crs = None
    centroids = gdf.geometry.centroid
    # Ensure centroids in dem CRS (4326)
    if gdf.crs and str(gdf.crs) != "EPSG:4326":
        centroids = gdf.to_crs("EPSG:4326").geometry.centroid
    coords = [(pt.x, pt.y) for pt in centroids]
    vals=[]
    try:
        for val in dem.sample(coords):
            vals.append(float(val[0]) if val[0] != dem.nodata and not np.isnan(val[0]) else None)
    except Exception:
        # fallback: try rasterio sample without nodata check
        try:
            for val in dem.sample(coords):
                try:
                    vals.append(float(val[0]))
                except:
                    vals.append(None)
        except:
            vals=[None]*len(coords)
    return vals

def enrich_waterbodies(waterbodies: "gpd.GeoDataFrame", dem, bathymetry_offset=2.0) -> "gpd.GeoDataFrame":
    """Add area_m2, centroid, dem_elev, spill_crest."""
    if waterbodies is None or len(waterbodies)==0:
        return waterbodies
    gdf = waterbody_area_m2(waterbodies)
    # centroid
    gdf["centroid_lon"] = gdf.geometry.centroid.x
    gdf["centroid_lat"] = gdf.geometry.centroid.y
    # dem elevation at centroid
    dem_vals = sample_dem_at_points(gdf, dem)
    gdf["dem_elev"] = dem_vals
    # spill crest = dem_elev + bathymetry_offset (default 2m above bed)
    # if dem_elev is None, use 5m default
    gdf["spill_crest"] = gdf["dem_elev"].apply(lambda x: (x + bathymetry_offset) if x is not None and not (isinstance(x,float) and np.isnan(x)) else 5.0)
    # also add spill_crest as dem_elev + 2 if dem_elev exists else 5
    return gdf
