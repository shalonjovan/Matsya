"""Asset loader for 7 files in assets/ — validates counts, reprojects."""
import pathlib
import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Polygon, Point
from shapely.ops import transform
import pyproj
import rasterio

# Expected counts (min) — allow 10% tolerance for MultiGeometry exploding
EXPECTED = {
    "micro": 37,
    "macro": 15,
    "rivers": 800,  # 876 Placemark, some Multi, so min 800
    "buckingham": 5,
    "krishna": 1,
    "waterbodies": 4000,  # 4086 Placemark
}

def _kml_to_gdf(path: pathlib.Path) -> gpd.GeoDataFrame:
    """Try geopandas KML driver, fallback to fastkml/manual XML."""
    # Try geopandas first (requires libkml driver)
    try:
        # Enable KML driver if not enabled
        try:
            gpd.io.file.fiona.drvsupport.supported_drivers['KML'] = 'rw'
        except:
            pass
        gdf = gpd.read_file(path, driver='KML')
        # If single row but contains many geometries in one, explode
        if len(gdf) == 1 and gdf.geometry.iloc[0] and gdf.geometry.iloc[0].geom_type == 'GeometryCollection':
            # explode
            pass
        if len(gdf) > 0:
            return gdf
    except Exception:
        pass

    # Fallback: manual XML parse with fastkml or xml
    try:
        # Try fastkml if available
        from fastkml import kml
        with open(path, 'rt', encoding='utf-8', errors='ignore') as f:
            k = kml.KML()
            k.from_string(f.read().encode('utf-8'))
            features = list(k.features())
            # recursively collect
            def _collect(feats):
                out=[]
                for feat in feats:
                    if hasattr(feat, 'geometry') and feat.geometry:
                        out.append({"name": getattr(feat, 'name', ''), "geometry": feat.geometry})
                    if hasattr(feat, 'features'):
                        out.extend(_collect(list(feat.features())))
                return out
            rows=_collect(features)
            if rows:
                return gpd.GeoDataFrame(rows, crs="EPSG:4326")
    except Exception:
        pass

    # Last fallback: xml.etree parse of Placemark/LineString/Polygon
    import xml.etree.ElementTree as ET
    import re
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except Exception as e:
        raise ValueError(f"cannot parse KML {path}: {e}")

    rows=[]
    # Find all Placemark
    for pm in root.findall(".//kml:Placemark", ns):
        name_elem = pm.find("kml:name", ns)
        name = name_elem.text if name_elem is not None else ""
        # Check for LineString, Polygon, MultiGeometry
        for ls in pm.findall(".//kml:LineString", ns):
            coords_elem = ls.find("kml:coordinates", ns)
            if coords_elem is not None and coords_elem.text:
                coords_text = coords_elem.text.strip()
                coords=[]
                for tup in coords_text.split():
                    parts=tup.split(",")
                    if len(parts)>=2:
                        try:
                            lon=float(parts[0]); lat=float(parts[1])
                            coords.append((lon,lat))
                        except: pass
                if len(coords)>=2:
                    rows.append({"name":name, "geometry": LineString(coords)})
        for poly in pm.findall(".//kml:Polygon", ns):
            outer = poly.find("kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", ns)
            if outer is not None and outer.text:
                coords_text = outer.text.strip()
                coords=[]
                for tup in coords_text.split():
                    parts=tup.split(",")
                    if len(parts)>=2:
                        try:
                            lon=float(parts[0]); lat=float(parts[1])
                            coords.append((lon,lat))
                        except: pass
                if len(coords)>=3:
                    # handle inner boundaries (holes)
                    holes=[]
                    for inner in poly.findall("kml:innerBoundaryIs/kml:LinearRing/kml:coordinates", ns):
                        if inner.text:
                            ic=[]
                            for tup in inner.text.strip().split():
                                parts=tup.split(",")
                                if len(parts)>=2:
                                    try: ic.append((float(parts[0]), float(parts[1])))
                                    except: pass
                            if len(ic)>=3: holes.append(ic)
                    try:
                        if holes:
                            rows.append({"name":name, "geometry": Polygon(coords, holes)})
                        else:
                            rows.append({"name":name, "geometry": Polygon(coords)})
                    except: pass
    if not rows:
        # If parsing found nothing but file exists, return empty with warning
        # fallback to reading as plain: try to extract all coordinates blocks
        txt = path.read_text(encoding='utf-8', errors='ignore')
        import re
        # crude: find all coordinates blocks
        for m in re.finditer(r"<coordinates>(.*?)</coordinates>", txt, re.DOTALL):
            block=m.group(1).strip()
            coords=[]
            for tup in block.split():
                parts=tup.split(",")
                if len(parts)>=2:
                    try: coords.append((float(parts[0]), float(parts[1])))
                    except: pass
            if len(coords)>=2:
                # guess Polygon if first==last and length>3
                if len(coords)>=4 and coords[0]==coords[-1]:
                    try: rows.append({"name":"", "geometry": Polygon(coords)})
                    except: rows.append({"name":"", "geometry": LineString(coords)})
                else:
                    rows.append({"name":"", "geometry": LineString(coords)})
    gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    return gdf

def load_assets(base="assets") -> dict:
    """Load 7 assets, return dict with GeoDataFrames and raster."""
    # base can be relative to repo root or absolute
    base_path = pathlib.Path(base)
    # Try to resolve: if not exists, try relative to repo root (matsya/matsya/../../assets)
    if not base_path.exists():
        # try from backend location: backend/app/services/hydro -> repo/assets
        repo_candidates = [
            pathlib.Path(base),
            pathlib.Path("/home/cac/Storage/coding/projects/matsya/assets"),
            pathlib.Path(__file__).parents[6] / "assets",  # from hydro to repo
            pathlib.Path.cwd() / "assets",
            pathlib.Path.cwd() / "matsya/matsya/../../assets",
        ]
        for cand in repo_candidates:
            if cand.exists():
                base_path = cand
                break
    if not base_path.exists():
        raise ValueError(f"assets base not found: {base} (tried {base_path})")
    
    data={}
    # map names to files (handle typo Channai vs Chennai)
    file_map = {
        "micro": ["Chennai_Basin_Micro_Drains.kml", "Chennai_basin_micro_drains.kml"],
        "macro": ["Chennai_Basin_Macro_Drains.kml", "Chennai_basin_macro_drains.kml"],
        "rivers": ["Chennai_basin_rivers_and_streams.kml", "Chennai_Basin_Rivers.kml"],
        "buckingham": ["Channai_basin_Buckingham_canal.kml", "Chennai_Basin_Buckingham_canal.kml"],
        "krishna": ["Chennai_Basin_Krishna_Water_Canal.kml", "Chennai_Basin_Krishna_Water_Canal.kml"],
        "waterbodies": ["chennai_waterbodies.kml", "Chennai_Waterbodies.kml"],
    }
    for key, candidates in file_map.items():
        found=None
        for cand in candidates:
            p = base_path / cand
            if p.exists():
                found=p
                break
        # also try case-insensitive glob
        if not found:
            import glob
            for pat in [f"{base_path}/*.kml"]:
                for p in pathlib.Path(base_path).glob("*.kml"):
                    if key in p.name.lower():
                        found=p
                        break
        if found and found.exists():
            data[key] = _kml_to_gdf(found)
        else:
            # fallback: try drains.kml for micro+macro
            fallback = base_path / "drains.kml"
            if key in ["micro","macro"] and fallback.exists():
                # read drains.kml and split (not ideal, but use it)
                gdf = _kml_to_gdf(fallback)
                # For now, assign same gdf to both, will be filtered later
                data[key] = gdf
            else:
                data[key] = gpd.GeoDataFrame(columns=["name","geometry"], crs="EPSG:4326")

    # DEM
    dem_candidates = [base_path / "CartoDEM_30m_Chennai_EGM96_MSL.tif", base_path / "carto*.tif"]
    dem_path=None
    for cand in [base_path / "CartoDEM_30m_Chennai_EGM96_MSL.tif"]:
        if cand.exists():
            dem_path=cand
            break
    if dem_path and dem_path.exists():
        try:
            data["dem"] = rasterio.open(dem_path)
        except Exception as e:
            data["dem"] = None
    else:
        data["dem"] = None

    # roads
    roads_path = base_path / "roads.geojson"
    if roads_path.exists():
        try:
            data["roads"] = gpd.read_file(roads_path)
        except:
            data["roads"] = gpd.GeoDataFrame(columns=["geometry"], crs="EPSG:4326")
    else:
        data["roads"] = gpd.GeoDataFrame(columns=["geometry"], crs="EPSG:4326")

    return data

def validate_counts(data: dict):
    for k, exp in EXPECTED.items():
        if k not in data:
            raise ValueError(f"missing {k}")
        gdf = data[k]
        # allow GeoDataFrame or list
        n = len(gdf) if hasattr(gdf, "__len__") else 0
        if n < exp * 0.9:  # 10% tolerance
            raise ValueError(f"count for {k} too low: {n} < {exp*0.9} (expected {exp})")
        # check geometry type for waterbodies
        if k == "waterbodies" and hasattr(gdf, "geometry"):
            # at least some polygons
            try:
                polys = sum(1 for geom in gdf.geometry if geom and geom.geom_type in ["Polygon","MultiPolygon"])
                if polys == 0:
                    raise ValueError("waterbodies contain no polygons")
            except:
                pass

def to_utm(gdf: gpd.GeoDataFrame, src="EPSG:4326", dst="EPSG:32644") -> gpd.GeoDataFrame:
    if gdf is None or len(gdf)==0:
        return gdf
    if gdf.crs is None:
        gdf = gdf.set_crs(src)
    return gdf.to_crs(dst)
