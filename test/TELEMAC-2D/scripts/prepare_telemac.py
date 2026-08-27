#!/usr/bin/env python3
"""
Prepare TELEMAC-2D test case V0 (terrain+rain) and V1 (infinite drainage)
for MATSYA Chennai prototype
Domain: 80.155-80.175E, 13.11-13.13N (~2.16km x 2.22km =4.8 km2)
Resolution: 30m (CartoDEM native)
Includes: DEM, roads, drains
"""

import json, pathlib, rasterio, rasterio.windows, rasterio.transform
import numpy as np
import geopandas as gpd
from shapely.geometry import box, LineString, MultiLineString
import xml.etree.ElementTree as ET

# Config
BBOX = (80.155, 13.11, 80.175, 13.13) # lon_min, lat_min, lon_max, lat_max
DEM_SRC="/home/cac/Storage/coding/projects/matsya/assets/CartoDEM_30m_Chennai_EGM96_MSL.tif"
ROADS_SRC="/home/cac/Storage/coding/projects/matsya/assets/roads.geojson"
KML_SRC="/home/cac/Storage/coding/projects/matsya/c4907fed-934b-4342-a3f4-74226853719d.kml"
OUT_DIR=pathlib.Path(__file__).parent.parent / "input"
CLIPPED_DEM=OUT_DIR / "dem_clipped.tif"
CLIPPED_ROADS=OUT_DIR / "roads_clipped.geojson"
CLIPPED_DRAINS=OUT_DIR / "drains_clipped.geojson"
META_JSON=OUT_DIR / "domain_meta.json"

def clip_dem():
    with rasterio.open(DEM_SRC) as ds:
        window=rasterio.windows.from_bounds(*BBOX, transform=ds.transform).round_offsets().round_lengths()
        arr=ds.read(1, window=window, masked=False)
        # Handle nodata
        nodata=ds.nodata
        # Replace nodata with nearest valid? For Chennai, nodata -32768 only sea
        # Keep masked
        transform=rasterio.windows.transform(window, ds.transform)
        profile=ds.profile.copy()
        profile.update(width=window.width, height=window.height, transform=transform, compress='lzw')
        # Write
        with rasterio.open(CLIPPED_DEM,'w',**profile) as dst:
            dst.write(arr,1)
        print(f"Clipped DEM {arr.shape} -> {CLIPPED_DEM} bounds {BBOX} transform {transform}")
        # Stats
        valid=arr[arr!=nodata]
        if valid.size==0:
            valid=arr[~np.isnan(arr)]
        print(f"DEM stats valid {valid.size} min {valid.min():.2f} max {valid.max():.2f} mean {valid.mean():.2f} std {valid.std():.2f}")
        return arr, transform, profile, window

def clip_roads():
    gdf=gpd.read_file(ROADS_SRC)
    bbox_poly=box(*BBOX)
    # Ensure CRS EPSG:4326
    if gdf.crs is None:
        gdf.set_crs(epsg=4326, inplace=True)
    clipped=gdf[gdf.geometry.intersects(bbox_poly)].copy()
    # Clip geometry to bbox
    clipped.geometry=clipped.geometry.intersection(bbox_poly)
    # Drop empty
    clipped=clipped[~clipped.geometry.is_empty]
    clipped.to_file(CLIPPED_ROADS, driver='GeoJSON')
    print(f"Roads: {len(gdf)} -> clipped {len(clipped)} -> {CLIPPED_ROADS}")
    return clipped

def clip_drains():
    # Parse KML and filter
    drains=[]
    context=ET.iterparse(KML_SRC, events=('end',))
    _,root=next(context)
    for ev,elem in context:
        if elem.tag.endswith('Placemark'):
            data={}
            for sd in elem.iter():
                if sd.tag.endswith('SimpleData'):
                    data[sd.attrib.get('name')]=(sd.text or "").strip()
            coords=None
            for c in elem.iter():
                if c.tag.endswith('coordinates'):
                    if c.text:
                        pts=[]
                        for tok in c.text.strip().split():
                            lon,lat=map(float,tok.split(',')[:2])
                            pts.append((lon,lat))
                        coords=pts
                    break
            if coords:
                avg_lon=sum(p[0] for p in coords)/len(coords)
                avg_lat=sum(p[1] for p in coords)/len(coords)
                if BBOX[0]<=avg_lon<=BBOX[2] and BBOX[1]<=avg_lat<=BBOX[3]:
                    # Keep full LineString
                    # Simplify coords to LineString
                    drains.append({
                        'objectid': int(data.get('OBJECTID','0') or 0),
                        'ward': data.get('WARD',''),
                        'zone': data.get('ZONE',''),
                        'drain_wid': float(data.get('DRAIN_WID') or 0),
                        'drain_dep': float(data.get('DRAIN_DEP') or 0),
                        'invert_sp': data.get('INVERT_SP',''),
                        'invert_ep': data.get('INVERT_EP',''),
                        'st_name': data.get('ST_NAME',''),
                        'coords': coords,
                        'raw': data
                    })
            elem.clear(); root.clear()
    print(f"Drains clipped {len(drains)} in bbox")
    # Build GeoDataFrame
    import shapely.geometry as geom
    features=[]
    for d in drains:
        ls=geom.LineString(d['coords'])
        # Intersect with bbox
        bbox_poly=box(*BBOX)
        ls_clipped=ls.intersection(bbox_poly)
        if ls_clipped.is_empty:
            continue
        features.append({
            'geometry': ls_clipped,
            'objectid': d['objectid'],
            'ward': d['ward'],
            'zone': d['zone'],
            'drain_wid': d['drain_wid'],
            'drain_dep': d['drain_dep'],
            'invert_sp': d['invert_sp'],
            'invert_ep': d['invert_ep'],
            'st_name': d['st_name'],
        })
    gdf=gpd.GeoDataFrame(features, crs='EPSG:4326')
    gdf.to_file(CLIPPED_DRAINS, driver='GeoJSON')
    print(f"Drains GeoJSON {len(gdf)} -> {CLIPPED_DRAINS}")
    return gdf

def rasterize_drains_and_roads(dem_arr, transform):
    # Create masks at 30m grid
    # dem_arr shape (rows, cols) with transform
    rows, cols=dem_arr.shape
    # For drains: rasterize line presence
    # Use rasterio.features.rasterize
    from rasterio.features import rasterize
    import shapely.geometry as geom
    # Drain mask
    drains_gdf=gpd.read_file(CLIPPED_DRAINS)
    drain_shapes=[(geom, 1) for geom in drains_gdf.geometry]
    drain_mask=rasterize(drain_shapes, out_shape=(rows,cols), transform=transform, fill=0, dtype='uint8', all_touched=True)
    print(f"Drain mask {drain_mask.sum()} cells ({drain_mask.sum()/drain_mask.size*100:.1f}%)")
    # Road mask
    roads_gdf=gpd.read_file(CLIPPED_ROADS)
    road_shapes=[(geom, 1) for geom in roads_gdf.geometry]
    road_mask=rasterize(road_shapes, out_shape=(rows,cols), transform=transform, fill=0, dtype='uint8', all_touched=True)
    print(f"Road mask {road_mask.sum()} cells ({road_mask.sum()/road_mask.size*100:.1f}%)")
    # Save masks as npy for solver
    np.save(OUT_DIR / "drain_mask.npy", drain_mask)
    np.save(OUT_DIR / "road_mask.npy", road_mask)
    # Also roughness map
    # Base Manning 0.03 for land, 0.02 for roads, drains 0.014?
    roughness=np.full((rows,cols), 0.03, dtype=np.float32)
    roughness[road_mask==1]=0.02
    # Drains cells could be 0.014 but they are sink, roughness not needed
    np.save(OUT_DIR / "roughness.npy", roughness)
    print(f"Roughness saved mean {roughness.mean():.3f}")
    return drain_mask, road_mask, roughness

def generate_mesh_info(dem_arr, transform):
    rows,cols=dem_arr.shape
    # For TELEMAC, structured grid nodes: (cols * rows) nodes, (rows-1)*(cols-1)*2 triangles
    # Generate node file (geo) and connectivity
    # Also save meta
    lon_min, lat_min, lon_max, lat_max = BBOX
    dx=transform.a # ~0.0002777 deg ≈30m; in meters approx 30.8
    dy= -transform.e # positive 0.0002777
    # Convert deg to meters for TELEMAC (uses meters). We'll keep UTM for simulation but for geo we need lat/lon?
    # TELEMAC expects mesh in meters (projected). We'll create UTM mesh for solver.
    from pyproj import Transformer
    tr=Transformer.from_crs("EPSG:4326","EPSG:32644", always_xy=True)
    # Build coordinates
    # Use rasterio affine to get center of each cell
    # For mesh nodes, use cell centers? Or corners? For TELEMAC, nodes at vertices.
    # We'll create nodes at cell centers for structured solver, but also generate corners for triangulation.
    # Simpler: For prototype, use cell-center grid.
    # Save mesh meta
    meta={
        'bbox': BBOX,
        'rows': rows, 'cols': cols,
        'dx_deg': dx, 'dy_deg': dy,
        'dx_m': 30.8, 'dy_m': 30.8, # approx
        'transform': list(transform)[:6],
        'crs': 'EPSG:4326',
        'crs_utm': 'EPSG:32644',
        'dem_file': str(CLIPPED_DEM),
    }
    with open(META_JSON,'w') as f:
        json.dump(meta,f,indent=2)
    print(f"Mesh meta {rows}x{cols} -> {META_JSON}")
    # Also generate TELEMAC steering file template
    cas_content=f"""TELEMAC-2D CASE - MATSYA V0/V1 prototype
 Domain 80.155-80.175,13.11-13.13 (4.8 km2, 30m grid {rows}x{cols})
 Generated by prepare_telemac.py

/ Mesh
GEOMETRY FILE          = mesh.slf
BOUNDARY CONDITIONS FILE = mesh.cli
RESULTS FILE           = results.slf

/ Time
TIME STEP              = 0.5
NUMBER OF TIME STEPS   = 43200  // 6 hr @0.5s
MASS-BALANCE           = YES

/ Physics
LAW OF BOTTOM FRICTION = 5  // Manning
MANNING COEFFICIENT    = 0.03  // base, roads 0.02 via friction file
CORIOLIS               = NO
TURBULENCE MODEL       = 1
VELOCITY DIFFUSIVITY   = 1.E-6

/ Initial / Boundary
INITIAL CONDITIONS     = 'CONSTANT ELEVATION'
INITIAL ELEVATION      = 0.0
PRESCRIBED ELEVATIONS  = 0;0
PRESCRIBED FLOWRATES   = 0;0
BOUNDARY CONDITIONS    = 5 4 4  // wall / free

/ Rainfall
RAINFALL               = YES
RAINFALL FILE          = rainfall.txt  // 50 mm/hr 1hr

/ Drain sink (V1)
/  For V1, add source term: drains as negative rainfall -infinite
/  Implemented in prototype as sink mask

/ Output
VARIABLES FOR GRAPHIC PRINTOUTS = U,V,H,S,B
LISTING PRINTOUT PERIOD = 100
GRAPHIC PRINTOUT PERIOD = 200

/ Roads roughness via friction file
FRICTION DATA FILE     = friction.slf
FRICTION DATA          = YES

"""
    (OUT_DIR / "cas" / "telemac2d.cas").parent.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "cas" / "telemac2d.cas").write_text(cas_content)
    (OUT_DIR / "cas" / "telemac2d_v1.cas").write_text(cas_content.replace("V0","V1")+"// V1: infinite drainage sink at drain_mask.npy\n")
    print(f"CAS files written to {OUT_DIR/'cas'}")
    # Also generate rainfall.txt
    rainfall_path=OUT_DIR / "cas" / "rainfall.txt"
    # Format: time(s) intensity(mm/hr)
    with open(rainfall_path,'w') as f:
        f.write("# time(s) rain(mm/hr)\n")
        for t in range(0, 3600+1, 300): # every 5 min for 1 hr
            f.write(f"{t} 50.0\n")
        f.write(f"{3900} 0.0\n")
        f.write(f"{21600} 0.0\n")
    print(f"Rainfall {rainfall_path}")

if __name__=="__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "cas").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "mesh").mkdir(parents=True, exist_ok=True)
    print("Clipping DEM...")
    dem_arr, transform, profile, window = clip_dem()
    print("Clipping roads...")
    clip_roads()
    print("Clipping drains...")
    clip_drains()
    print("Rasterizing...")
    rasterize_drains_and_roads(dem_arr, transform)
    print("Generating mesh...")
    generate_mesh_info(dem_arr, transform)
    print("Done. Input prepared in", OUT_DIR)
