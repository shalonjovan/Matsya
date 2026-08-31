"""Snap drains to waterbodies / rivers / sea."""
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, LineString
from shapely.ops import nearest_points
import numpy as np

def snap_drains_to_waterbodies(micro: "gpd.GeoDataFrame", macro: "gpd.GeoDataFrame", rivers: "gpd.GeoDataFrame", waterbodies: "gpd.GeoDataFrame", tol=50, river_tol=100):
    """
    Returns dict with mapping drain_idx -> target id, snapped GeoDF, stats.
    Target format: "wb:<idx>" or "river:<idx>" or "sea"
    """
    # Combine drains
    if micro is None or len(micro)==0:
        micro = gpd.GeoDataFrame(columns=["geometry"], crs="EPSG:4326")
    if macro is None or len(macro)==0:
        macro = gpd.GeoDataFrame(columns=["geometry"], crs="EPSG:4326")
    # Add source tag
    micro = micro.copy()
    macro = macro.copy()
    micro["src"] = "micro"
    macro["src"] = "macro"
    drains = gpd.GeoDataFrame(pd.concat([micro, macro], ignore_index=True), crs=micro.crs if micro.crs else "EPSG:4326")
    if drains.crs is None:
        drains = drains.set_crs("EPSG:4326")
    # Ensure ids (overwrite if all None)
    if "id" not in drains.columns or drains["id"].isnull().all():
        drains["id"] = range(len(drains))
    else:
        # ensure unique if duplicates
        if drains["id"].duplicated().any():
            drains["id"] = range(len(drains))
    if waterbodies is None or len(waterbodies)==0:
        waterbodies = gpd.GeoDataFrame(columns=["geometry"], crs="EPSG:4326")
    if rivers is None or len(rivers)==0:
        rivers = gpd.GeoDataFrame(columns=["geometry"], crs="EPSG:4326")
    if "id" not in waterbodies.columns or (len(waterbodies)>0 and waterbodies["id"].isnull().all()):
        waterbodies = waterbodies.copy()
        waterbodies["id"] = range(len(waterbodies))
    if "id" not in rivers.columns or (len(rivers)>0 and rivers["id"].isnull().all()):
        rivers = rivers.copy()
        rivers["id"] = range(len(rivers))

    # Reproject to UTM for meter distance (32644 for Chennai)
    drains_utm = drains.to_crs("EPSG:32644") if drains.crs else drains
    wb_utm = waterbodies.to_crs("EPSG:32644") if waterbodies.crs else waterbodies
    rivers_utm = rivers.to_crs("EPSG:32644") if rivers.crs else rivers

    mapping={}
    # Build spatial index for waterbodies if available
    # Use simple distance loop (for 52 drains vs 4086 polys, fine)
    snapped_geoms=[]
    for idx, row in drains_utm.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            mapping[row["id"]] = "sea"
            snapped_geoms.append(geom)
            continue
        # get end point (last coordinate)
        try:
            if geom.geom_type == "LineString":
                pt = Point(list(geom.coords)[-1])
            elif geom.geom_type == "MultiLineString":
                # take last line's last coord
                last = list(geom.geoms)[-1]
                pt = Point(list(last.coords)[-1])
            else:
                pt = geom.centroid
        except:
            pt = geom.centroid

        # nearest waterbody
        best_wb = None
        best_dist = float('inf')
        best_wb_id = None
        if len(wb_utm) > 0:
            # compute distances (could be slow, but ok for 52*4086)
            # Use vectorized distance
            try:
                dists = wb_utm.geometry.distance(pt)
                min_idx = dists.idxmin()
                min_dist = dists.min()
                if min_dist <= tol:
                    best_dist = min_dist
                    best_wb_id = wb_utm.loc[min_idx, "id"]
                    best_wb = wb_utm.loc[min_idx].geometry
            except Exception:
                # fallback loop
                for j, wb_row in wb_utm.iterrows():
                    try:
                        d = wb_row.geometry.distance(pt)
                        if d < best_dist and d <= tol:
                            best_dist = d
                            best_wb_id = wb_row["id"]
                            best_wb = wb_row.geometry
                    except: pass

        if best_wb_id is not None:
            mapping[row["id"]] = f"wb:{best_wb_id}"
            # snap: extend line to nearest point on waterbody boundary
            try:
                nearest = nearest_points(pt, best_wb)[1]
                # Create new geometry with last point snapped
                if geom.geom_type == "LineString":
                    coords = list(geom.coords)
                    coords[-1] = (nearest.x, nearest.y)
                    snapped_geoms.append(LineString(coords))
                else:
                    snapped_geoms.append(geom)
            except:
                snapped_geoms.append(geom)
            continue

        # nearest river
        best_river_id=None
        best_river_dist=float('inf')
        if len(rivers_utm) > 0:
            try:
                dists = rivers_utm.geometry.distance(pt)
                min_idx = dists.idxmin()
                min_dist = dists.min()
                if min_dist <= river_tol:
                    best_river_id = rivers_utm.loc[min_idx, "id"]
                    best_river_dist = min_dist
            except:
                for j, rrow in rivers_utm.iterrows():
                    try:
                        d = rrow.geometry.distance(pt)
                        if d < best_river_dist and d <= river_tol:
                            best_river_dist=d
                            best_river_id=rrow["id"]
                    except: pass
        if best_river_id is not None:
            mapping[row["id"]] = f"river:{best_river_id}"
            snapped_geoms.append(geom)
            continue

        # fallback to sea (if near coast or no other)
        mapping[row["id"]] = "sea"
        snapped_geoms.append(geom)

    # Build snapped GeoDF in original CRS (4326)
    snapped = drains.copy()
    # snapped_geoms are in 32644, need to transform back to 4326 for storage
    # Create GeoSeries in 32644 then to 4326
    try:
        snapped_utm_gs = gpd.GeoSeries(snapped_geoms, crs="EPSG:32644")
        snapped_4326 = snapped_utm_gs.to_crs("EPSG:4326")
        snapped["geometry"] = snapped_4326.geometry.values
    except:
        # fallback: keep original
        pass
    # For drains that were not snapped, keep original geom (already)
    # stats
    stats = {"total": len(drains), "snapped_to_waterbody": 0, "to_river": 0, "to_sea": 0, "unsnapped": 0}
    for v in mapping.values():
        if v.startswith("wb:"): stats["snapped_to_waterbody"]+=1
        elif v.startswith("river:"): stats["to_river"]+=1
        elif v=="sea": stats["to_sea"]+=1
        else: stats["unsnapped"]+=1
    # unsnapped is those not in mapping (should be 0)
    stats["unsnapped"] = stats["total"] - (stats["snapped_to_waterbody"]+stats["to_river"]+stats["to_sea"])
    if stats["unsnapped"]<0: stats["unsnapped"]=0
    return {"mapping": mapping, "snapped": snapped, "stats": stats}
