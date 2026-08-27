#!/usr/bin/env python3
"""Prepare big square test-2.0: 80.15-80.20,13.08-13.13 (~5.4x5.5 km =27 km2) 180x180 @30m"""
import pathlib, json, rasterio, rasterio.windows, numpy as np, geopandas as gpd
from shapely.geometry import box
import xml.etree.ElementTree as ET

BBOX=(80.15,13.08,80.20,13.13)
DEM_SRC="/home/cac/Storage/coding/projects/matsya/assets/CartoDEM_30m_Chennai_EGM96_MSL.tif"
ROADS_SRC="/home/cac/Storage/coding/projects/matsya/assets/roads.geojson"
KML_SRC="/home/cac/Storage/coding/projects/matsya/c4907fed-934b-4342-a3f4-74226853719d.kml"
OUT=pathlib.Path(__file__).parent.parent/"input"

def clip_dem():
    import rasterio
    with rasterio.open(DEM_SRC) as ds:
        w=rasterio.windows.from_bounds(*BBOX, transform=ds.transform).round_offsets().round_lengths()
        arr=ds.read(1, window=w, masked=False)
        tr=rasterio.windows.transform(w, ds.transform)
        prof=ds.profile.copy()
        prof.update(width=w.width, height=w.height, transform=tr, compress='lzw')
        # pit fill
        filled=arr.astype(float)
        filled[filled==-32768]=np.nan
        filled=np.nan_to_num(filled, nan=np.nanmean(filled))
        # simple pit fill 3 iterations
        for _ in range(3):
            pad=np.pad(filled,1,mode='edge')
            for i in range(filled.shape[0]):
                for j in range(filled.shape[1]):
                    c=filled[i,j]
                    neigh=pad[i:i+3, j:j+3]
                    m=np.min(neigh)
                    if c < m-0.05:
                        filled[i,j]=m+0.01
        with rasterio.open(OUT/"dem_clipped.tif",'w',**prof) as dst:
            dst.write(filled.astype(np.float32),1)
        print(f"DEM {arr.shape} -> {w.width}x{w.height} clip {OUT/'dem_clipped.tif'} min {filled.min():.2f} max {filled.max():.2f} mean {filled.mean():.2f}")
        return filled, tr, prof, w

def clip_roads():
    gdf=gpd.read_file(ROADS_SRC)
    if gdf.crs is None: gdf.set_crs(epsg=4326, inplace=True)
    bbox_poly=box(*BBOX)
    clipped=gdf[gdf.geometry.intersects(bbox_poly)].copy()
    clipped.geometry=clipped.geometry.intersection(bbox_poly)
    clipped=clipped[~clipped.geometry.is_empty]
    clipped.to_file(OUT/"roads_clipped.geojson", driver='GeoJSON')
    print(f"Roads {len(gdf)} -> {len(clipped)}")
    return clipped

def clip_drains():
    drains=[]
    ctx=ET.iterparse(KML_SRC, events=('end',))
    _,root=next(ctx)
    for ev,elem in ctx:
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
                avg_lon=sum(p[0] for p in coords)/len(coords); avg_lat=sum(p[1] for p in coords)/len(coords)
                if BBOX[0]<=avg_lon<=BBOX[2] and BBOX[1]<=avg_lat<=BBOX[3]:
                    drains.append({'coords':coords, 'raw':data, 'ward':data.get('WARD',''), 'objectid':int(data.get('OBJECTID','0') or 0)})
            elem.clear(); root.clear()
    print(f"Drains {len(drains)} in BBOX")
    import shapely.geometry as geom
    feats=[]
    for d in drains:
        ls=geom.LineString(d['coords'])
        ls2=ls.intersection(box(*BBOX))
        if ls2.is_empty: continue
        feats.append({'geometry':ls2, 'objectid':d['objectid'], 'ward':d['ward']})
    gdf=gpd.GeoDataFrame(feats, crs='EPSG:4326')
    gdf.to_file(OUT/"drains_clipped.geojson", driver='GeoJSON')
    print(f"Drains GeoJSON {len(gdf)}")
    return gdf

def rasterize():
    import rasterio
    with rasterio.open(OUT/"dem_clipped.tif") as ds:
        rows, cols=ds.height, ds.width
        tr=ds.transform
    from rasterio.features import rasterize
    drains=gpd.read_file(OUT/"drains_clipped.geojson")
    roads=gpd.read_file(OUT/"roads_clipped.geojson")
    drain_shapes=[(g,1) for g in drains.geometry]
    road_shapes=[(g,1) for g in roads.geometry]
    dm=rasterize(drain_shapes, out_shape=(rows,cols), transform=tr, fill=0, dtype='uint8', all_touched=True)
    rm=rasterize(road_shapes, out_shape=(rows,cols), transform=tr, fill=0, dtype='uint8', all_touched=True)
    np.save(OUT/"drain_mask.npy", dm)
    np.save(OUT/"road_mask.npy", rm)
    rough=np.full((rows,cols),0.03,dtype=np.float32)
    rough[rm==1]=0.02
    np.save(OUT/"roughness.npy", rough)
    print(f"Masks drain {dm.sum()} ({dm.sum()/dm.size*100:.1f}%) road {rm.sum()} ({rm.sum()/rm.size*100:.1f}%) rough mean {rough.mean():.3f}")
    # meta
    meta={"bbox":BBOX,"rows":rows,"cols":cols,"dx_deg":tr.a,"dy_deg":-tr.e,"transform":list(tr)[:6],"crs":"EPSG:4326"}
    with open(OUT/"domain_meta.json",'w') as f: json.dump(meta,f,indent=2)
    # cas
    cas_dir=OUT/"cas"; cas_dir.mkdir(exist_ok=True)
    cas=f"""TELEMAC-2D test-2.0 big square 80.15-80.20,13.08-13.13 {rows}x{cols} @30m ({rows*30/1000:.1f}km x {cols*30/1000:.1f}km)
GEOMETRY FILE = mesh.slf
BOUNDARY CONDITIONS FILE = mesh.cli
RESULTS FILE = results.slf
TIME STEP = 0.5
NUMBER OF TIME STEPS = 43200
MASS-BALANCE = YES
LAW OF BOTTOM FRICTION = 5
MANNING COEFFICIENT = 0.03
RAINFALL = YES
RAINFALL FILE = rainfall.txt
VARIABLES FOR GRAPHIC PRINTOUTS = U,V,H,S,B
"""
    (cas_dir/"telemac2d.cas").write_text(cas)
    (cas_dir/"rainfall.txt").write_text("# time rain\n"+"".join(f"{t} 50.0\n" for t in range(0,3601,300))+"3900 0.0\n21600 0.0\n")
    print("CAS written")

if __name__=="__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/"cas").mkdir(parents=True, exist_ok=True)
    clip_dem(); clip_roads(); clip_drains(); rasterize()
    print("Big square prepared", OUT)
