"""Observed waterbody enrichment from the WRR Zenodo paper dataset.

Sources (extracted once to assets/waterbodies/enrich/, gitignored):
  lakes90/90_new_waterbodies.* — 90 lake polygons (UTM 44N) with Area_ha,
      VOL_MCM (model-mean volume, million m3) + LB_VOL/UB_VOL 95% CI.
  bathy/*.tif — 86 bathymetric bed-elevation rasters (m MSL, UTM 44N).
  wbs_acb.csv — 914 Adyar-basin lake locations + MaxArea_ha.

Join strategy (names are sparse on both sides: 29 distinct names in our KML,
ID-only in the ZIP): spatial overlap in EPSG:32644. A KML lake matches the ZIP
lake with the largest intersection when intersection/min(area) > 0.2 or the ZIP
centroid falls inside the KML polygon. Every attached field is stamped with its
source; unmatched lakes keep assumed defaults downstream.
"""
import json
import pathlib

MATCH_MIN_FRAC = 0.3
MATCH_MIN_INTER_M2 = 2000.0
MATCH_MAX_AREA_RATIO = 5.0

SOURCE_ZENODO = "WRR-Zenodo-SIWB"

# Tamil spelling variants observed across KML vs bathy filenames.
# Applied AFTER lowercasing/stripping, BEFORE comparison.
NAME_ALIASES = {
    "madavaram": "madhavaram",
    "kaveripak": "kaveripakkam",
    "pulal": "redhills",
    "puzhal": "redhills",
    "kuvam": "cooum",
    "korttalaiyar": "kortiaaaaalaiyar",
}

_NAME_STRIP = ("tank", "tanks", "eri", "lake", "lakes", "ponds", "reservoir",
               "thangal", "komban", "chitteri", "periya", "big", "large", "pudu")


def normalize_lake_name(name):
    """Lowercase alphanumeric tokens minus generic suffixes, aliases resolved."""
    import re
    import unicodedata
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", str(name).lower())
    s = "".join(c if (c.isalnum() or c == " ") else " " for c in s)
    toks = [t for t in s.split() if t and t not in _NAME_STRIP]
    toks = [NAME_ALIASES.get(t, t) for t in toks]
    return " ".join(toks)


def match_bathy_by_name(kml_gdf, index=None):
    """Name-anchored bathy matching with REQUIRED spatial confirmation.

    Normalizes KML DRNP_NAME/description vs bathy raster stems; a name hit only
    counts when the KML centroid falls inside the raster footprint (kills false
    friends like Edaiyarpakkam vs Pakkam). Disambiguates multi-candidate names
    (pakkam_big vs pakkam_chitteri) the same way; ambiguous names are dropped.
    Returns dict kml_index -> {bathy_stem, bed_min, bed_mean, match_score: 1.0,
    match_rule: "name-spatial"}.
    """
    out = {}
    if kml_gdf is None or len(kml_gdf) == 0:
        return out
    if index is None:
        index = bathy_index()
    if not index:
        return out
    # raster stem -> normalized token set
    stems = {}
    for stem in index:
        base = stem[:-4] if stem.lower().endswith("_idw") else stem
        stems[stem] = normalize_lake_name(base.replace("_", " "))
    try:
        k = kml_gdf.to_crs("EPSG:32644")
    except Exception:
        return out
    from shapely.geometry import box
    for idx, krow in k.iterrows():
        try:
            nm = None
            for col in ("DRNP_NAME", "drnp_name", "name", "NAME", "DESCR", "descr"):
                try:
                    v = krow.get(col) if hasattr(krow, "get") else None
                except Exception:
                    v = None
                if v and str(v).strip():
                    nm = str(v).strip()
                    break
            if not nm:
                continue
            norm = normalize_lake_name(nm)
            if not norm:
                continue
            geom = krow.geometry
            if geom is None or geom.is_empty:
                continue
            c = geom.centroid
            hits = []
            for stem, snorm in stems.items():
                if not snorm:
                    continue
                if norm == snorm or norm in snorm.split() or snorm in norm.split():
                    info = index[stem]
                    bl, bb, br, bt = box(*info["bounds_32644"]).bounds
                    if bl < c.x < br and bb < c.y < bt:
                        hits.append(stem)
            if len(hits) == 1:
                info = index[hits[0]]
                out[idx] = {"bathy_stem": hits[0], "bed_min": info["bed_min"],
                            "bed_mean": info["bed_mean"], "match_score": 1.0,
                            "match_rule": "name-spatial"}
        except Exception:
            continue
    return out


def _enrich_dir():
    here = pathlib.Path(__file__).resolve()
    for _ in range(8):
        cand = here / "assets" / "waterbodies" / "enrich"
        if cand.exists():
            return cand
        here = here.parent
    for cand in (pathlib.Path("assets/waterbodies/enrich"),
                 pathlib.Path("/app/assets/waterbodies/enrich")):
        if cand.exists():
            return cand
    return pathlib.Path("assets/waterbodies/enrich")


def load_zip_lakes(enrich_dir=None):
    """90 ZIP lake polygons with observed volume fields. Returns GeoDataFrame or None."""
    import geopandas as gpd
    d = pathlib.Path(enrich_dir or _enrich_dir())
    shp = d / "lakes90" / "90_new_waterbodies.shp"
    if not shp.exists():
        return None
    gdf = gpd.read_file(shp)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:32644")
    else:
        gdf = gdf.to_crs("EPSG:32644")
    return gdf


def _obs_depth(row):
    """Mean depth (m) from observed volume/area. Returns (depth, source)."""
    try:
        vol_mcm = float(row.get("VOL_MCM"))
        area_ha = float(row.get("Area_ha"))
        if vol_mcm > 0 and area_ha > 0:
            return vol_mcm * 1e6 / (area_ha * 1e4), "observed-volume"
    except Exception:
        pass
    return None, "assumed"


def match_lakes(kml_gdf, zip_gdf=None, min_frac=MATCH_MIN_FRAC,
                min_inter_m2=MATCH_MIN_INTER_M2, max_ratio=MATCH_MAX_AREA_RATIO):
    """Overlap-join KML waterbodies to ZIP lakes.

    Returns dict kml_index -> {zip_id, area_ha, vol_mcm, vol_lb, vol_ub,
    obs_depth_m, depth_source, match_score}.
    """
    out = {}
    if kml_gdf is None or len(kml_gdf) == 0:
        return out
    if zip_gdf is None:
        zip_gdf = load_zip_lakes()
    if zip_gdf is None or len(zip_gdf) == 0:
        return out
    try:
        k = kml_gdf.to_crs("EPSG:32644")
        z = zip_gdf.to_crs("EPSG:32644")
    except Exception:
        return out
    try:
        sindex = z.sindex
    except Exception:
        sindex = None
    for idx, krow in k.iterrows():
        try:
            geom = krow.geometry
            if geom is None or geom.is_empty:
                continue
            k_area = float(geom.area)
            if k_area <= 0:
                continue
            cand_idx = list(sindex.intersection(geom.bounds)) if sindex is not None else list(range(len(z)))
            best, best_score = None, 0.0
            for j in cand_idx:
                try:
                    zgeom = z.geometry.iloc[j]
                    inter = geom.intersection(zgeom).area
                    if inter < min_inter_m2:
                        continue
                    z_area = float(zgeom.area)
                    if min(k_area, z_area) <= 0:
                        continue
                    ratio = max(k_area, z_area) / min(k_area, z_area)
                    if ratio > max_ratio:
                        continue
                    score = inter / min(k_area, z_area)
                    # centroid-inside counts as a match even for delineation drift
                    try:
                        inside = zgeom.centroid.within(geom)
                    except Exception:
                        inside = False
                    if inside and inter >= min_inter_m2 and ratio <= max_ratio:
                        score = max(score, 0.5)
                    if score > best_score:
                        best_score, best = score, j
                except Exception:
                    continue
            if best is not None and best_score >= min_frac:
                zrow = z.iloc[best]
                depth, source = _obs_depth(zrow)
                try:
                    vol = float(zrow.get("VOL_MCM"))
                except Exception:
                    vol = None
                try:
                    lb = float(zrow.get("LB_VOL"))
                except Exception:
                    lb = None
                try:
                    ub = float(zrow.get("UB_VOL"))
                except Exception:
                    ub = None
                try:
                    area_ha = float(zrow.get("Area_ha"))
                except Exception:
                    area_ha = None
                out[idx] = {"zip_id": str(zrow.get("ID", best)), "area_ha": area_ha,
                            "vol_mcm": vol, "vol_lb": lb, "vol_ub": ub,
                            "obs_depth_m": depth, "depth_source": source,
                            "match_score": round(float(best_score), 3)}
        except Exception:
            continue
    return out


def bathy_index(enrich_dir=None, stats_cache="bathy_stats.json"):
    """Per-raster bed stats + footprint. Cached to JSON after first computation.

    Returns {stem: {path, bounds_32644, bed_min, bed_mean, valid_frac}}.
    """
    import numpy as np
    d = pathlib.Path(enrich_dir or _enrich_dir())
    cache = d / stats_cache
    if cache.exists():
        try:
            return json.loads(cache.read_text())
        except Exception:
            pass
    try:
        import rasterio
    except ImportError:
        return {}
    bdir = d / "bathy"
    if not bdir.exists():
        return {}
    out = {}
    for tif in sorted(bdir.glob("*.tif")):
        try:
            with rasterio.open(tif) as src:
                a = src.read(1).astype(np.float64)
                a[a > 1e30] = float("nan")
                v = a[np.isfinite(a)]
                if v.size == 0:
                    continue
                out[tif.stem] = {"path": str(tif), "bounds_32644": [float(x) for x in src.bounds],
                                 "bed_min": round(float(v.min()), 2), "bed_mean": round(float(v.mean()), 2),
                                 "valid_frac": round(float(v.size) / a.size, 3)}
        except Exception:
            continue
    try:
        cache.write_text(json.dumps(out, indent=1))
    except Exception:
        pass
    return out


def match_bathy(kml_gdf, index=None, min_frac=0.1):
    """Attach bathymetry rasters to KML lakes by VALID-PIXEL overlap.

    Footprint bounds prefilter, then rasterio.mask against the lake polygon:
    score = valid-pixel area inside lake / lake area. Kills footprint-only
    false matches (a big raster rect containing small nearby tanks).
    Returns dict kml_index -> {bathy_stem, bathy_path, bed_min, bed_mean, match_score}.
    """
    import numpy as np
    out = {}
    if kml_gdf is None or len(kml_gdf) == 0:
        return out
    if index is None:
        index = bathy_index()
    if not index:
        return out
    try:
        import rasterio
        from rasterio.mask import mask as rio_mask
        from shapely.geometry import box, mapping
    except ImportError:
        return out
    try:
        k = kml_gdf.to_crs("EPSG:32644")
    except Exception:
        return out
    open_cache = {}
    try:
        for idx, krow in k.iterrows():
            try:
                geom = krow.geometry
                if geom is None or geom.is_empty:
                    continue
                k_area = float(geom.area)
                if k_area <= 0:
                    continue
                best, best_score, best_info = None, 0.0, {}
                for stem, info in index.items():
                    try:
                        b = box(*info["bounds_32644"])
                        if not geom.intersects(b):
                            continue
                        if stem not in open_cache:
                            try:
                                open_cache[stem] = rasterio.open(info["path"])
                            except Exception:
                                open_cache[stem] = None
                        src = open_cache.get(stem)
                        if src is None:
                            continue
                        clipped, _ = rio_mask(src, [mapping(geom)], crop=True, filled=False)
                        band = clipped[0]
                        if hasattr(band, "mask"):
                            valid = (~band.mask).sum()
                            total = band.size
                        else:
                            arr = np.asarray(band, dtype=np.float64)
                            valid = int(np.isfinite(arr).sum())
                            total = arr.size
                        if total == 0:
                            continue
                        # valid-pixel area inside lake vs lake area
                        res = abs(src.res[0] * src.res[1])
                        score = (valid * res) / k_area
                        if score > best_score:
                            best_score, best, best_info = score, stem, info
                    except Exception:
                        continue
                if best is not None and best_score >= min_frac:
                    out[idx] = {"bathy_stem": best, "bathy_path": best_info["path"],
                                "bed_min": best_info["bed_min"], "bed_mean": best_info["bed_mean"],
                                "match_score": round(float(min(1.0, best_score)), 3)}
            except Exception:
                continue
    finally:
        for src in open_cache.values():
            try:
                if src is not None:
                    src.close()
            except Exception:
                pass
    return out


def _cache_path(enrich_dir=None):
    return pathlib.Path(enrich_dir or _enrich_dir()) / "match_cache.json"


def rebuild_match_cache(kml_gdf=None, enrich_dir=None):
    """Full join over all KML lakes (minutes: 86 masked raster ops). Saves JSON cache."""
    from app.services.hydro.asset_loader import load_assets
    if kml_gdf is None:
        try:
            kml_gdf = load_assets("assets").get("waterbodies")
        except Exception:
            return {"lake": {}, "bathy": {}}
    lake = match_lakes(kml_gdf)
    bathy = match_bathy(kml_gdf)
    try:
        bathy_name = match_bathy_by_name(kml_gdf)
    except Exception:
        bathy_name = {}
    cache = {"lake": {str(k): v for k, v in lake.items()},
             "bathy": {str(k): v for k, v in bathy.items()},
             "bathy_name": {str(k): v for k, v in bathy_name.items()}}
    try:
        _cache_path(enrich_dir).write_text(json.dumps(cache))
    except Exception:
        pass
    return cache


def get_match_cache(enrich_dir=None):
    """Load cached join (builds on first call). Returns {lake: {...}, bathy: {...}}."""
    p = _cache_path(enrich_dir)
    if p.exists():
        try:
            c = json.loads(p.read_text())
            if isinstance(c, dict) and "bathy_name" in c and ("lake" in c or "bathy" in c):
                return {"lake": c.get("lake", {}), "bathy": c.get("bathy", {}),
                        "bathy_name": c.get("bathy_name", {})}
        except Exception:
            pass
    return rebuild_match_cache(enrich_dir=enrich_dir)


def lookup_observations(kml_idx, cache=None, enrich_dir=None):
    """Merged observed fields for one KML index label. Empty dict when unmatched."""
    try:
        c = cache if cache is not None else get_match_cache(enrich_dir)
        key = str(kml_idx)
        lake = (c.get("lake") or {}).get(key, {})
        bathy = (c.get("bathy") or {}).get(key, {})
        merged: dict = {"depth_source": "assumed"}
        if lake.get("obs_depth_m"):
            merged.update({"zip_id": lake.get("zip_id"), "zip_area_ha": lake.get("area_ha"),
                           "obs_volume_mcm": lake.get("vol_mcm"), "obs_vol_lb": lake.get("vol_lb"),
                           "obs_vol_ub": lake.get("vol_ub"), "obs_depth_m": lake.get("obs_depth_m"),
                           "depth_source": lake.get("depth_source", "observed-volume"),
                           "lake_match_score": lake.get("match_score")})
        if bathy.get("bed_min") is not None:
            merged.update({"bathy_stem": bathy.get("bathy_stem"), "bathy_bed_min": bathy.get("bed_min"),
                           "bathy_bed_mean": bathy.get("bed_mean"),
                           "bathy_match_score": bathy.get("match_score"),
                           "bathy_match_rule": bathy.get("match_rule", "spatial")})
            if merged.get("depth_source") == "assumed":
                merged["depth_source"] = "observed-bathy"
        try:
            named = (c.get("bathy_name") or {}).get(key, {})
        except Exception:
            named = {}
        if named.get("bed_min") is not None:
            # name-spatial is the stronger signal: wins over spatial-only
            merged.update({"bathy_stem": named.get("bathy_stem"), "bathy_bed_min": named.get("bed_min"),
                           "bathy_bed_mean": named.get("bed_mean"),
                           "bathy_match_score": named.get("match_score", 1.0),
                           "bathy_match_rule": "name-spatial"})
            if merged.get("depth_source") == "assumed":
                merged["depth_source"] = "observed-bathy"
        return merged
    except Exception:
        return {"depth_source": "assumed"}


def attach_observations(kml_gdf, enrich_dir=None):
    """Return a copy of kml_gdf with observed columns attached (no geometry change)."""
    import pandas as pd
    gdf = kml_gdf.copy()
    for col in ("zip_id", "zip_area_ha", "obs_volume_mcm", "obs_vol_lb", "obs_vol_ub",
                "obs_depth_m", "depth_source", "lake_match_score",
                "bathy_stem", "bathy_bed_min", "bathy_bed_mean", "bathy_match_score",
                "bathy_match_rule"):
        if col not in gdf.columns:
            gdf[col] = None
    gdf["depth_source"] = "assumed"
    try:
        cache = get_match_cache(enrich_dir)
        lake_m = cache.get("lake", {})
        bathy_m = cache.get("bathy", {})
        name_m = cache.get("bathy_name", {})
    except Exception:
        lake_m, bathy_m, name_m = {}, {}, {}
    for idx in gdf.index:
        try:
            m = lake_m.get(str(idx))
            if m:
                gdf.at[idx, "zip_id"] = m.get("zip_id")
                gdf.at[idx, "zip_area_ha"] = m.get("area_ha")
                gdf.at[idx, "obs_volume_mcm"] = m.get("vol_mcm")
                gdf.at[idx, "obs_vol_lb"] = m.get("vol_lb")
                gdf.at[idx, "obs_vol_ub"] = m.get("vol_ub")
                gdf.at[idx, "obs_depth_m"] = m.get("obs_depth_m")
                if m.get("obs_depth_m"):
                    gdf.at[idx, "depth_source"] = m.get("depth_source", "observed-volume")
                gdf.at[idx, "lake_match_score"] = m.get("match_score")
            b = bathy_m.get(str(idx))
            if b:
                gdf.at[idx, "bathy_stem"] = b.get("bathy_stem")
                gdf.at[idx, "bathy_bed_min"] = b.get("bed_min")
                gdf.at[idx, "bathy_bed_mean"] = b.get("bed_mean")
                gdf.at[idx, "bathy_match_score"] = b.get("match_score")
                gdf.at[idx, "bathy_match_rule"] = b.get("match_rule", "spatial")
                if gdf.at[idx, "depth_source"] == "assumed":
                    gdf.at[idx, "depth_source"] = "observed-bathy"
            n = name_m.get(str(idx))
            if n:
                gdf.at[idx, "bathy_stem"] = n.get("bathy_stem")
                gdf.at[idx, "bathy_bed_min"] = n.get("bed_min")
                gdf.at[idx, "bathy_bed_mean"] = n.get("bed_mean")
                gdf.at[idx, "bathy_match_score"] = n.get("match_score", 1.0)
                gdf.at[idx, "bathy_match_rule"] = "name-spatial"
                if gdf.at[idx, "depth_source"] == "assumed":
                    gdf.at[idx, "depth_source"] = "observed-bathy"
        except Exception:
            continue
    return gdf


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
    from app.services.hydro.asset_loader import load_assets
    data = load_assets("assets")
    wb = data.get("waterbodies")
    print("kml waterbodies:", len(wb) if wb is not None else None)
    zl = load_zip_lakes()
    print("zip lakes:", len(zl) if zl is not None else None)
    m = match_lakes(wb, zl) if wb is not None else {}
    print("lake matches:", len(m))
    obs = sum(1 for v in m.values() if v["obs_depth_m"])
    print("with observed depth:", obs)
    depths = sorted(v["obs_depth_m"] for v in m.values() if v["obs_depth_m"])
    if depths:
        print("obs depth range: %.2f - %.2f m, median %.2f" % (depths[0], depths[-1], depths[len(depths) // 2]))
    bi = bathy_index()
    print("bathy rasters indexed:", len(bi))
    bm = match_bathy(wb, bi) if wb is not None else {}
    print("bathy matches:", len(bm))
    nm = match_bathy_by_name(wb, bi) if wb is not None else {}
    print("name-spatial matches:", len(nm))
    for idx, v in sorted(nm.items(), key=lambda kv: str(kv[0])):
        nm_kml = "?"
        try:
            if wb is not None:
                row = wb.loc[idx]
                nm_kml = row.get("DRNP_NAME", "?") if hasattr(row, "get") else "?"
        except Exception:
            pass
        print("  kml %s %-22s <- %s" % (idx, str(nm_kml)[:22], v["bathy_stem"]))
    # big-square bbox overlap (lon/lat -> UTM, no guessing)
    try:
        if wb is None:
            raise ValueError("no waterbodies")
        import geopandas as gpd
        from shapely.geometry import box as _box
        sq = gpd.GeoSeries([_box(80.15, 13.08, 80.20, 13.13)], crs="EPSG:4326").to_crs("EPSG:32644")
        k = wb.to_crs("EPSG:32644")
        inside = k[k.geometry.intersects(sq.iloc[0])]
        print("kml lakes near big square:", len(inside))
        print("of those matched:", sum(1 for i in inside.index if i in m),
              "with bathy:", sum(1 for i in inside.index if i in bm))
    except Exception as e:
        print("bbox check failed:", e)
