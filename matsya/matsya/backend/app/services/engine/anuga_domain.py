"""Sim-to-ANUGA domain inputs (Phase 2 — data prep only, no solver).

Builds, for a sim bbox: UTM elevation GeoTIFF, Manning roughness GeoTIFF,
rainfall series, and culvert stubs from the hydro graph. Everything unknown
is flagged in audit, same honesty convention as swmm_inp.
"""
import json
import math
import pathlib

CELL_M = 30.0
CRS = "EPSG:32644"

N_WATERBODY = 0.025
N_DRAIN = 0.017
N_URBAN = 0.035

_ASSET_CACHE = {"data": None, "ts": 0}


def _find_tif():
    here = pathlib.Path(__file__).resolve()
    for _ in range(8):
        cand = here / "assets" / "CartoDEM_30m_Chennai_EGM96_MSL.tif"
        if cand.exists():
            return cand
        here = here.parent
    for cand in (pathlib.Path("assets/CartoDEM_30m_Chennai_EGM96_MSL.tif"),
                 pathlib.Path("/app/assets/CartoDEM_30m_Chennai_EGM96_MSL.tif")):
        if cand.exists():
            return cand
    return None


def _load_assets_cached():
    import time as _t
    try:
        if _ASSET_CACHE.get("data") is not None and (_t.time() - _ASSET_CACHE.get("ts", 0) < 60):
            return _ASSET_CACHE["data"]
    except Exception:
        pass
    from app.services.hydro.asset_loader import load_assets
    data = load_assets("assets")
    try:
        _ASSET_CACHE["data"] = data
        _ASSET_CACHE["ts"] = _t.time()
    except Exception:
        pass
    return data


def _v(rainfall, keys, default):
    for k in keys:
        v = (rainfall or {}).get(k)
        if v is not None:
            return float(v)
    return default


def _rain_series(rainfall):
    """Mirror of swmm_inp._rain_series shape: [(hours, mm/hr)].

    NOTE: explicit None checks (not `or`) so a 0 mm/hr test storm stays 0.
    """
    rainfall = rainfall or {}
    if rainfall.get("mode") == "variable" and rainfall.get("curve", {}).get("values"):
        vals = list(rainfall["curve"]["values"])
        total = _v(rainfall, ("totalTime", "durationHr"), 6.0)
        dt = total / max(1, len(vals))
        return [(i * dt, float(v)) for i, v in enumerate(vals)]
    rate = _v(rainfall, ("rateMmHr", "constantRate"), 50.0)
    dur = _v(rainfall, ("durationHr", "totalTime"), 1.0)
    if dur <= 0:
        return [(0.0, rate)]
    return [(0.0, rate), (dur, rate)]


def build_domain_inputs(bbox, rainfall, hydro_graph, workdir, cell_m=CELL_M):
    """Clip DEM + paint Manning + expand rain + stub culverts. Returns dict.

    Keys: elevation_tif, manning_tif, rain_series, culverts, crs, cell_m,
    audit{observed[], assumed[]}.
    """
    import numpy as np
    import rasterio
    from rasterio import warp
    from rasterio.transform import from_origin
    out_dir = pathlib.Path(workdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    observed, assumed = [], []

    tif = _find_tif()
    if tif is None:
        raise FileNotFoundError("CartoDEM TIF not found")
    minLon, minLat, maxLon, maxLat = [float(x) for x in bbox]
    with rasterio.open(tif) as src:
        dst_crs = CRS
        # target grid in UTM at cell_m
        x0, y0 = warp.transform_bounds(src.crs, dst_crs, minLon, minLat, maxLon, maxLat)[:2]
        x1, y1 = warp.transform_bounds(src.crs, dst_crs, minLon, minLat, maxLon, maxLat)[2:]
        w = max(10, int((x1 - x0) / cell_m))
        h = max(10, int((y1 - y0) / cell_m))
        transform = from_origin(x0, y1, cell_m, cell_m)
        dem = np.empty((h, w), dtype=np.float64)
        warp.reproject(rasterio.band(src, 1), dem,
                       src_transform=src.transform, src_crs=src.crs,
                       dst_transform=transform, dst_crs=dst_crs,
                       resampling=warp.Resampling.bilinear,
                       src_nodata=src.nodata, dst_nodata=float("nan"))
    dem = np.where(dem < 0, np.nan, dem)  # ocean artifact mask, elevation.py convention
    observed.append("elevation from CartoDEM 30m resampled to %gm UTM" % cell_m)
    finite = np.isfinite(dem)
    if not finite.any():
        raise ValueError("DEM clip has no valid cells")
    dem_filled = np.where(finite, dem, float(np.nanmean(dem)))

    # Manning classes from KML geometry (values themselves are defaults: flagged)
    man = np.full(dem.shape, N_URBAN, dtype=np.float64)
    try:
        from rasterio.features import rasterize
        data = _load_assets_cached()
        shapes = []
        wb = data.get("waterbodies")
        if wb is not None and len(wb) > 0:
            wu = wb.to_crs(CRS)
            shapes += [(g, N_WATERBODY) for g in wu.geometry if g and not g.is_empty]
            observed.append("waterbody polygons (%d) from KML" % len(wu))
        for key in ("micro", "macro"):
            fr = data.get(key)
            if fr is not None and len(fr) > 0:
                du = fr.to_crs(CRS)
                shapes += [(g.buffer(15.0), N_DRAIN) for g in du.geometry if g and not g.is_empty]
        if shapes:
            _burn = np.asarray(rasterize(shapes, out_shape=dem.shape, transform=transform, fill=0),
                               dtype=np.float64)
            man = np.where(_burn > 0, _burn, man)
    except Exception:
        pass
    assumed.append("manning values urban=%.3f water=%.3f drain=%.3f (defaults)" % (N_URBAN, N_WATERBODY, N_DRAIN))

    elev_path = str(out_dir / "elevation.tif")
    man_path = str(out_dir / "manning.tif")
    for arr, path in ((dem_filled, elev_path), (man, man_path)):
        with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1],
                           count=1, dtype="float64", crs=CRS, transform=transform) as dst:
            dst.write(arr, 1)

    series = _rain_series(rainfall)

    culverts = []
    try:
        for link in (hydro_graph or {}).get("links", []):
            culverts.append({"drain_id": str(link.get("from", "?")), "waterbody_id": str(link.get("to", "?")),
                             "width_m": 1.0, "assumed": True})
    except Exception:
        pass
    if culverts:
        assumed.append("culvert width 1.0m default x%d" % len(culverts))

    return {"elevation_tif": elev_path, "manning_tif": man_path, "rain_series": series,
            "culverts": culverts, "crs": CRS, "cell_m": float(cell_m),
            "audit": {"observed": observed, "assumed": assumed}}
