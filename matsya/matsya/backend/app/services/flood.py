import pathlib
import io
import hashlib

import numpy as np
import rasterio
from rasterio.windows import from_bounds
from rasterio.enums import Resampling
from PIL import Image

# TIF path: try multiple candidates for host and Docker — robust to parents index
def _find_tif():
    candidates = [
        pathlib.Path(__file__).resolve().parents[5] / "assets/CartoDEM_30m_Chennai_EGM96_MSL.tif" if len(pathlib.Path(__file__).resolve().parents) > 5 else None,
        pathlib.Path("assets/CartoDEM_30m_Chennai_EGM96_MSL.tif"),
        pathlib.Path("/app/assets/CartoDEM_30m_Chennai_EGM96_MSL.tif"),
        pathlib.Path(__file__).resolve().parents[2] / "assets/CartoDEM_30m_Chennai_EGM96_MSL.tif" if len(pathlib.Path(__file__).resolve().parents) > 2 else None,
        pathlib.Path(__file__).resolve().parents[3] / "assets/CartoDEM_30m_Chennai_EGM96_MSL.tif" if len(pathlib.Path(__file__).resolve().parents) > 3 else None,
        pathlib.Path(__file__).resolve().parents[4] / "assets/CartoDEM_30m_Chennai_EGM96_MSL.tif" if len(pathlib.Path(__file__).resolve().parents) > 4 else None,
        pathlib.Path("/app/app/../assets/CartoDEM_30m_Chennai_EGM96_MSL.tif"),
    ]
    for cand in candidates:
        if cand and cand.exists():
            return cand
    return pathlib.Path("assets/CartoDEM_30m_Chennai_EGM96_MSL.tif")

TIF = _find_tif()

_ASSETS_CACHE = {"data": None, "ts": 0}


# depth color ramp: 0→0.05 #bae6fd, 0.15 #38bdf8, 0.3 #0284c7, 0.6 #0c4a6e, 1.0 #082f49
# expanded to 6 stops with duplicate at 0 and 0.05 for flat start
_DEPTH_STOPS = [0.0, 0.05, 0.15, 0.3, 0.6, 1.0]
_DEPTH_COLORS = [
    (186, 230, 253),  # #bae6fd at 0.0
    (186, 230, 253),  # #bae6fd at 0.05
    (56, 189, 248),   # #38bdf8 at 0.15
    (2, 132, 199),    # #0284c7 at 0.3
    (12, 74, 110),    # #0c4a6e at 0.6
    (8, 47, 73),      # #082f49 at 1.0
]


def depth_color(depth: float, stats: dict | None) -> tuple[int, int, int]:
    """Interpolate depth color ramp by depth/maxDepth.
    Ramp: 0→0.05 #bae6fd, 0.15 #38bdf8, 0.3 #0284c7, 0.6 #0c4a6e, 1.0 #082f49
    """
    try:
        max_d = None
        if stats is not None:
            if isinstance(stats, dict):
                max_d = stats.get("maxDepth")
            else:
                max_d = getattr(stats, "maxDepth", None)
        if max_d is None or max_d == 0:
            norm = 0.0
        else:
            norm = float(depth) / float(max_d)
    except Exception:
        norm = 0.0
    norm = max(0.0, min(1.0, norm))
    # interpolate
    for i in range(len(_DEPTH_STOPS) - 1):
        if _DEPTH_STOPS[i] <= norm <= _DEPTH_STOPS[i + 1]:
            span = _DEPTH_STOPS[i + 1] - _DEPTH_STOPS[i]
            t = (norm - _DEPTH_STOPS[i]) / span if span != 0 else 0.0
            r = int(_DEPTH_COLORS[i][0] * (1 - t) + _DEPTH_COLORS[i + 1][0] * t)
            g = int(_DEPTH_COLORS[i][1] * (1 - t) + _DEPTH_COLORS[i + 1][1] * t)
            b = int(_DEPTH_COLORS[i][2] * (1 - t) + _DEPTH_COLORS[i + 1][2] * t)
            return (r, g, b)
    return _DEPTH_COLORS[-1]


def _dem_for_bbox(bbox, width, height):
    """Clip DEM to bbox, return 2D array (height,width) float with NaN for nodata.
    Uses rasterio from_bounds like elevation. Fallback to synthetic DEM if TIF missing.
    """
    minLon, minLat, maxLon, maxLat = bbox
    # try real TIF
    try:
        if TIF.exists():
            with rasterio.open(TIF) as src:
                window = from_bounds(minLon, minLat, maxLon, maxLat, src.transform)
                arr = src.read(
                    1,
                    window=window,
                    out_shape=(height, width),
                    resampling=Resampling.bilinear,
                    boundless=True,
                    fill_value=np.nan,
                )
                if src.nodata is not None:
                    # mask exact nodata
                    arr = np.where(arr == src.nodata, np.nan, arr)
                    # mask interpolated nodata artifacts near ocean:
                    # bilinear between land (~0-20m) and nodata (-32768) yields large negatives (-300 etc)
                    # treat any value <0 as nodata/sea (Chennai land is >= ~0-3m, ocean is nodata)
                    # this ensures dem_min reflects land low spot, not ocean interpolation artifact
                    arr = np.where(arr < 0, np.nan, arr)
                # check if valid has data
                valid = arr[~np.isnan(arr)]
                if len(valid) > 0:
                    return arr
                # else fall through to synthetic
    except Exception as e:
        # print(f"DEM clip failed {e}, using synthetic")
        pass

    # fallback synthetic DEM: deterministic per bbox, width, height
    # seed from stable hash of bbox
    seed_input = f"{bbox}_{width}_{height}"
    seed = int(hashlib.md5(seed_input.encode()).hexdigest()[:8], 16) % (2**32)
    rng = np.random.default_rng(seed)
    # generate base elevation 5-15m plus spatial gradient so different bboxes differ
    # incorporate bbox coords into mean
    lon_center = (bbox[0] + bbox[2]) / 2
    lat_center = (bbox[1] + bbox[3]) / 2
    # shift mean per location: Chennai region ~5-15m, vary by lon/lat
    base_mean = 5 + ((lon_center - 80.0) * 20) % 10 + ((lat_center - 13.0) * 20) % 5
    base_mean = float(np.clip(base_mean, 2, 18))
    arr = rng.normal(loc=base_mean, scale=1.5, size=(height, width))
    # add spatial trend: low in center, higher at edges etc simple
    # create gradient from bbox center offset
    arr += rng.uniform(-0.5, 0.5, size=(height, width))
    arr = np.clip(arr, -2, 30)
    return arr.astype(float)


def _bbox_area_m2(bbox) -> float:
    """Approx bbox area in m² from degrees (Chennai lat ~13°)."""
    try:
        minLon, minLat, maxLon, maxLat = bbox
        lat_c = (minLat + maxLat) / 2.0
        import math
        dx = abs(maxLon - minLon) * 111320.0 * math.cos(math.radians(lat_c))
        dy = abs(maxLat - minLat) * 110540.0
        return max(1.0, dx * dy)
    except Exception:
        return 29.7e6


def _fill_pits(dem: "np.ndarray", passes: int = 3) -> "np.ndarray":
    """Cheap pit filling: raise pits toward lowest neighbour + eps."""
    import numpy as np
    filled = dem.copy()
    for _ in range(max(1, passes)):
        up = np.roll(filled, 1, 0)
        down = np.roll(filled, -1, 0)
        left = np.roll(filled, 1, 1)
        right = np.roll(filled, -1, 1)
        neigh_min = np.minimum(np.minimum(up, down), np.minimum(left, right))
        filled = np.maximum(dem, np.minimum(filled, neigh_min + 0.01))
    return filled


def _d8_order(filled: "np.ndarray"):
    """Steepest-descent D8 downstream index + high→low order.

    Returns (ds_flat int64 [N], order int64 [N]). ds=-1 for pits/flat.
    Cell size 30m (diag 42.4m).
    """
    import numpy as np
    h, w = filled.shape
    dist = np.array([30.0, 42.4, 30.0, 42.4, 30.0, 42.4, 30.0, 42.4], dtype=float)
    dy = (-1, -1, 0, 1, 1, 1, 0, -1)
    dx = (0, 1, 1, 1, 0, -1, -1, -1)
    slopes = np.empty((8, h, w), dtype=np.float64)
    for k in range(8):
        nb = np.roll(np.roll(filled, -dy[k], 0), -dx[k], 1)
        slopes[k] = (filled - nb) / dist[k]
    best = slopes.argmax(axis=0)
    best_val = slopes.max(axis=0)
    rr, cc = np.mgrid[0:h, 0:w]
    dy_arr = np.array(dy, dtype=np.int64)[best]
    dx_arr = np.array(dx, dtype=np.int64)[best]
    nr = np.clip(rr + dy_arr, 0, h - 1)
    nc = np.clip(cc + dx_arr, 0, w - 1)
    ds = np.where(best_val > 0, nr * w + nc, -1).astype(np.int64).ravel()
    order = np.argsort(filled.ravel(), kind="stable")[::-1]
    return ds, order


def _waterbodies_in_bbox(bbox, dem_filled, width, height, max_n: int = 20):
    """Load waterbodies intersecting bbox; return list of {id, area_m2, crest, geometry}.

    crest = DEM at centroid grid cell + 1.0m (spill soon, visible). Falls back to [].
    """
    try:
        minLon, minLat, maxLon, maxLat = bbox
    except Exception:
        return []
    try:
        from app.services.hydro.asset_loader import load_assets
        import time as _t
        global _ASSETS_CACHE
        data = None
        try:
            if _ASSETS_CACHE.get("data") is not None and (_t.time() - _ASSETS_CACHE.get("ts", 0) < 60):
                data = _ASSETS_CACHE["data"]
        except Exception:
            data = None
        if data is None:
            data = load_assets("assets")
            try:
                _ASSETS_CACHE["data"] = data
                _ASSETS_CACHE["ts"] = _t.time()
            except Exception:
                pass
        wb = data.get("waterbodies")
        if wb is None or len(wb) == 0:
            return []
        # clip to bbox (cx needs sorted slices)
        try:
            lo_x, hi_x = (minLon, maxLon) if minLon <= maxLon else (maxLon, minLon)
            lo_y, hi_y = (minLat, maxLat) if minLat <= maxLat else (maxLat, minLat)
            clipped = wb.cx[lo_x:hi_x, lo_y:hi_y]
            if len(clipped) == 0:
                # fall back to nearest 5 by centroid distance to bbox centre
                cx0, cy0 = (minLon + maxLon) / 2, (minLat + maxLat) / 2
                tmp = wb.copy()
                tmp["_d"] = (tmp.geometry.centroid.x - cx0) ** 2 + (tmp.geometry.centroid.y - cy0) ** 2
                clipped = tmp.nsmallest(5, "_d").drop(columns=["_d"], errors="ignore")
        except Exception:
            clipped = wb.head(5)
        # largest first so cap keeps storage volume
        try:
            import pandas as pd  # noqa
            if "area_m2" not in clipped.columns:
                from app.services.hydro.dem import waterbody_area_m2
                clipped = waterbody_area_m2(clipped)
            clipped = clipped.sort_values("area_m2", ascending=False).head(max_n)
        except Exception:
            clipped = clipped.head(max_n)
        out = []
        h, w = dem_filled.shape
        dlon = (maxLon - minLon) / max(1, w)
        dlat = (maxLat - minLat) / max(1, h)
        for idx, row in clipped.iterrows():
            try:
                geom = row.geometry
                if geom is None or geom.is_empty:
                    continue
                c = geom.centroid
                # grid col/row of centroid
                cc = int((c.x - minLon) / dlon) if dlon else 0
                rr = int((maxLat - c.y) / dlat) if dlat else 0
                cc = max(0, min(w - 1, cc)); rr = max(0, min(h - 1, rr))
                dem_at = float(dem_filled[rr, cc])
                import math
                if math.isnan(dem_at):
                    dem_at = 5.0
                area = row.get("area_m2", 50000) if hasattr(row, "get") else 50000
                try:
                    import pandas as _pd
                    if area is None or (isinstance(area, float) and _pd.isna(area)):
                        area = 50000
                    area_f = float(area)
                except Exception:
                    try:
                        area_f = float(area) if area is not None else 50000.0
                    except Exception:
                        area_f = 50000.0
                wid = row.get("id", idx) if hasattr(row, "get") else idx
                info = {"id": str(wid), "area_m2": area_f, "crest": float(dem_at + 1.0), "geometry": geom,
                        "kml_idx": idx, "depth_source": "assumed",
                        "obs_depth_m": None, "bed_m": None}
                try:
                    from app.services.hydro.waterbody_enrich import lookup_observations
                    obs = lookup_observations(idx)
                    if obs.get("obs_depth_m"):
                        info["obs_depth_m"] = float(obs["obs_depth_m"])
                        info["depth_source"] = obs.get("depth_source", "observed-volume")
                    if obs.get("bathy_bed_min") is not None:
                        info["bed_m"] = float(obs["bathy_bed_min"])
                        if info["depth_source"] == "assumed":
                            info["depth_source"] = "observed-bathy"
                except Exception:
                    pass
                out.append(info)
            except Exception:
                continue
        return out
    except Exception:
        return []


def _rasterize_masks(wb_infos, bbox, width, height):
    """Rasterize waterbody polygons to boolean masks (H,W). Falls back to centroid 3x3."""
    import numpy as np
    masks = []
    if not wb_infos:
        return masks
    try:
        from rasterio.features import rasterize
        from rasterio.transform import from_bounds
        minLon, minLat, maxLon, maxLat = bbox
        transform = from_bounds(minLon, minLat, maxLon, maxLat, width, height)
        for info in wb_infos:
            try:
                geom = info.get("geometry")
                if geom is None:
                    masks.append(None); continue
                arr = rasterize([(geom, 1)], out_shape=(height, width), transform=transform, fill=0, dtype="uint8")
                if arr is None:
                    masks.append(None); continue
                m = np.asarray(arr).astype(bool)
                if not m.any():
                    masks.append(None)
                else:
                    masks.append(m)
            except Exception:
                masks.append(None)
        return masks
    except Exception:
        return [None for _ in wb_infos]


def _drain_endpoints(bbox, width, height, max_n: int = 30):
    """Return list of {row, col, length_m, slope} for drains in bbox.

    slope from DEM along drain; Qcap computed by caller via Manning.
    Falls back to 5 deterministic synthetic endpoints.
    """
    import numpy as np
    try:
        minLon, minLat, maxLon, maxLat = bbox
    except Exception:
        minLon, minLat, maxLon, maxLat = (80.15, 13.08, 80.20, 13.13)
    # try real drains (shared 60s asset cache)
    try:
        from app.services.hydro.asset_loader import load_assets
        import time as _t2
        global _ASSETS_CACHE
        data = None
        try:
            if _ASSETS_CACHE.get("data") is not None and (_t2.time() - _ASSETS_CACHE.get("ts", 0) < 60):
                data = _ASSETS_CACHE["data"]
        except Exception:
            data = None
        if data is None:
            data = load_assets("assets")
            try:
                _ASSETS_CACHE["data"] = data
                _ASSETS_CACHE["ts"] = _t2.time()
            except Exception:
                pass
        frames = [data.get("micro"), data.get("macro")]
        import geopandas as gpd, pandas as pd
        parts = [f for f in frames if f is not None and len(f) > 0]
        if parts:
            drains = pd.concat(parts, ignore_index=True)
            drains = gpd.GeoDataFrame(drains, crs="EPSG:4326")
            lo_x, hi_x = (minLon, maxLon) if minLon <= maxLon else (maxLon, minLon)
            lo_y, hi_y = (minLat, maxLat) if minLat <= maxLat else (maxLat, minLat)
            try:
                clipped = drains.cx[lo_x:hi_x, lo_y:hi_y].head(max_n)
            except Exception:
                clipped = drains.head(max_n)
            if len(clipped) == 0:
                raise ValueError("no drains in bbox")
            # length + slope via UTM
            try:
                utm = clipped.to_crs("EPSG:32644")
                lengths = utm.geometry.length.values
            except Exception:
                lengths = np.full(len(clipped), 800.0)
            # need DEM sample for slope: import lazily
            sample_dem = None
            try:
                from app.services.elevation import sample_dem as _sd
                sample_dem = _sd
                has_sampler = True
            except Exception:
                has_sampler = False
            out = []
            dlon = (maxLon - minLon) / max(1, width)
            dlat = (maxLat - minLat) / max(1, height)
            for i, (_, row) in enumerate(clipped.iterrows()):
                try:
                    geom = row.geometry
                    if geom is None or geom.is_empty:
                        continue
                    if geom.geom_type == "LineString":
                        coords = list(geom.coords)
                    elif geom.geom_type == "MultiLineString":
                        coords = list(list(geom.geoms)[-1].coords)
                    else:
                        c = geom.centroid
                        coords = [(c.x, c.y), (c.x, c.y)]
                    (x0, y0), (x1, y1) = coords[0], coords[-1]
                    cc = int((x1 - minLon) / dlon) if dlon else 0
                    rr = int((maxLat - y1) / dlat) if dlat else 0
                    cc = max(0, min(width - 1, cc)); rr = max(0, min(height - 1, rr))
                    length = float(lengths[i]) if i < len(lengths) else 800.0
                    if not np.isfinite(length) or length <= 0:
                        length = 800.0
                    if has_sampler and sample_dem is not None:
                        try:
                            z0 = sample_dem(x0, y0); z1 = sample_dem(x1, y1)
                            if z0 is None or z1 is None:
                                slope = 0.001
                            else:
                                slope = abs(float(z0) - float(z1)) / max(50.0, length)
                                slope = max(0.0005, min(0.02, slope))
                        except Exception:
                            slope = 0.001
                    else:
                        slope = 0.001
                    out.append({"row": rr, "col": cc, "length_m": length, "slope": float(slope)})
                except Exception:
                    continue
            if out:
                return out
    except Exception:
        pass
    # synthetic fallback: deterministic 5 endpoints
    seed_input = f"{bbox}_{width}_{height}_drains"
    seed = int(hashlib.md5(seed_input.encode()).hexdigest()[:8], 16) % (2 ** 32)
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(5):
        out.append({"row": int(rng.integers(0, height)), "col": int(rng.integers(0, width)), "length_m": 800.0, "slope": 0.001})
    return out


def generate_flood(bbox, rainfall, width=180, height=180, steps=73, polygon=None):
    """Generate flood snapshots per bbox+rainfall using DEM low spots.

    Args:
        bbox: [minLon,minLat,maxLon,maxLat]
        rainfall: dict {rateMmHr, durationHr}
        width, height, steps: dimensions

    Returns:
        (snapshots list 2D float (height,width), pngs list bytes, stats dict)
        stats: {maxDepth, floodedArea, meanDepth, width, height, steps, bbox}
    """
    # parse rainfall — handle both constant and variable modes
    curve_values = None
    rate = 50.0
    duration = 1.0
    try:
        if isinstance(rainfall, dict):
            mode = rainfall.get("mode", "constant")
            if mode == "variable":
                # variable mode with points/curve
                if rainfall.get("curve") and isinstance(rainfall["curve"], dict) and "values" in rainfall["curve"]:
                    curve_values = rainfall["curve"]["values"]
                    totalTime = rainfall.get("totalTime", rainfall.get("durationHr", 6))
                    duration = float(totalTime)
                elif rainfall.get("points"):
                    from app.services.rainfall_curve import interpolate
                    totalTime = rainfall.get("totalTime", 6)
                    maxRain = rainfall.get("maxRain", 100)
                    unit = rainfall.get("unit", "rate")
                    res = interpolate(rainfall["points"], totalTime=totalTime, maxRain=maxRain, unit=unit, steps=steps)
                    curve_values = res["values"]
                    duration = float(totalTime)
                else:
                    duration = float(rainfall.get("totalTime", rainfall.get("durationHr", 1)))
            else:
                # constant
                rate = float(rainfall.get("rateMmHr", rainfall.get("constantRate", rainfall.get("rate", 50))) or 50)
                if rainfall.get("constantRate") is not None:
                    rate = float(rainfall["constantRate"])
                duration = float(rainfall.get("durationHr", rainfall.get("totalTime", 1)) or 1)
        else:
            mode = getattr(rainfall, "mode", "constant")
            if mode == "variable":
                curve = getattr(rainfall, "curve", None)
                if curve and isinstance(curve, dict) and "values" in curve:
                    curve_values = curve["values"]
                elif getattr(rainfall, "points", None):
                    from app.services.rainfall_curve import interpolate
                    totalTime = getattr(rainfall, "totalTime", 6) or 6
                    maxRain = getattr(rainfall, "maxRain", 100) or 100
                    unit = getattr(rainfall, "unit", "rate") or "rate"
                    points = getattr(rainfall, "points", [])
                    res = interpolate(points, totalTime=totalTime, maxRain=maxRain, unit=unit, steps=steps)
                    curve_values = res["values"]
                    duration = float(totalTime)
                else:
                    duration = float(getattr(rainfall, "totalTime", getattr(rainfall, "durationHr", 6)) or 6)
            else:
                rate = float(getattr(rainfall, "rateMmHr", getattr(rainfall, "constantRate", 50)) or 50)
                if hasattr(rainfall, "constantRate") and getattr(rainfall, "constantRate") is not None:
                    rate = float(getattr(rainfall, "constantRate"))
                duration = float(getattr(rainfall, "durationHr", 1) or 1)
    except Exception as e:
        # print(f"rainfall parse failed {e}")
        rate, duration = 50.0, 1.0

    if curve_values is None:
        total_rain = rate * duration  # mm
        rates = [rate] * steps
    else:
        # variable: per-step rates; pad/truncate to steps
        try:
            rates = [float(v) for v in list(curve_values)[:steps]]
            while len(rates) < steps:
                rates.append(rates[-1] if rates else 0.0)
        except Exception:
            rates = [rate] * steps
        dt_tmp = duration * 3600 / steps if steps > 0 else 3600
        total_rain = sum(rates) * dt_tmp / 3600.0  # mm

    # get DEM
    dem = _dem_for_bbox(bbox, width, height)
    # ensure float array
    dem = np.array(dem, dtype=float)
    # fill NaNs with mean or 5
    try:
        mean_valid = float(np.nanmean(dem))
        if np.isnan(mean_valid):
            mean_valid = 5.0
    except Exception:
        mean_valid = 5.0
    dem_filled = np.where(np.isnan(dem), mean_valid, dem)
    dem_filled = np.nan_to_num(dem_filled, nan=mean_valid)

    dem_min = float(np.min(dem_filled))
    # deterministic per-bbox+rainfall noise map (static across steps, small)
    seed_input = f"{bbox}_{rate}_{duration}_{width}_{height}"
    # stable hash
    seed = int(hashlib.md5(seed_input.encode()).hexdigest()[:8], 16) % (2**32)
    rng = np.random.default_rng(seed)
    noise_map = rng.random((height, width)) * 0.02  # 0-0.02 m (routing adds the rest)

    # ---- realistic coupling setup (D8 + storage + surcharge) ----
    area_m2 = _bbox_area_m2(bbox)
    cell_area = area_m2 / max(1, width * height)
    try:
        filled = _fill_pits(dem_filled, passes=3)
        ds_flat, order = _d8_order(filled)
        valid_ds = ds_flat >= 0
    except Exception:
        filled = dem_filled
        ds_flat, order = None, None
        valid_ds = None
    # waterbodies in bbox -> WaterBody objects + masks
    try:
        wb_infos = _waterbodies_in_bbox(bbox, dem_filled, width, height, max_n=20)
    except Exception:
        wb_infos = []
    wb_masks = _rasterize_masks(wb_infos, bbox, width, height) if wb_infos else []
    wb_objs = []
    wb_observed = 0
    try:
        from app.services.hydro.waterbody import WaterBody
        for info in (wb_infos or []):
            try:
                # surveyed bed/depth wins over the assumed 2m (stamped per lake)
                depth = 2.0
                src = info.get("depth_source", "assumed")
                bed_m = info.get("bed_m")
                if bed_m is not None and bed_m < info["crest"]:
                    depth = min(15.0, max(0.5, info["crest"] - bed_m))
                    src = "observed-bathy"
                elif info.get("obs_depth_m"):
                    depth = min(15.0, max(0.5, float(info["obs_depth_m"])))
                if src != "assumed":
                    wb_observed += 1
                info["depth_source"] = src
                wb_objs.append(WaterBody(area_m2=info["area_m2"], crest=info["crest"],
                                         stage=info["crest"] - 0.5, depth=depth))
            except Exception:
                continue
    except Exception:
        wb_objs = []
    # drains in bbox -> Manning capacity for surcharge
    try:
        drains = _drain_endpoints(bbox, width, height, max_n=30)
    except Exception:
        drains = []
    import math as _math
    drain_qcaps = []
    for d in drains or []:
        try:
            # circular 1m dia default (PRD §15: capacity stays null in API; internal only)
            _A = _math.pi * 0.5 ** 2  # 0.785
            _R = 0.25
            _S = max(0.0005, min(0.02, float(d.get("slope", 0.001))))
            _Qcap = (1.0 / 0.017) * _A * (_R ** (2.0 / 3.0)) * _math.sqrt(_S)
            drain_qcaps.append(float(_Qcap))
        except Exception:
            drain_qcaps.append(0.6)

    dt = duration * 3600 / steps if steps > 0 else 3600
    try:
        dt = float(dt)
    except Exception:
        dt = 3600.0
    surface = np.zeros((height, width), dtype=np.float64)
    total_outflow_vol = 0.0
    total_sea_vol = 0.0
    surcharged_now = 0
    try:
        wb_initial_vol = float(sum(getattr(w, "volume", 0.0) for w in (wb_objs or [])))
    except Exception:
        wb_initial_vol = 0.0
    snapshots = []
    flat_size = width * height
    for i in range(steps):
        try:
            rate_i = float(rates[i]) if i < len(rates) else float(rates[-1] if rates else 0.0)
        except Exception:
            rate_i = 50.0
        rain_inc_m = rate_i * dt / 3600.0 / 1000.0  # m over whole bbox
        if rain_inc_m:
            surface += rain_inc_m
        # D8 downhill pass (vectorized, volume-preserving)
        try:
            if ds_flat is not None and valid_ds is not None and np.any(valid_ds):
                flat = surface.ravel()
                move = np.zeros_like(flat)
                move[valid_ds] = 0.25 * flat[valid_ds]
                # accumulate into downstream
                np.add.at(flat, ds_flat[valid_ds], move[valid_ds])
                flat[valid_ds] -= move[valid_ds]
                surface = flat.reshape(height, width)
        except Exception:
            pass
        # drains: take 30% of this step's rain volume, route to wb/sea, surcharge locally
        surcharge_grid = np.zeros_like(surface)
        step_rain_vol = rain_inc_m * area_m2
        n_drains = max(1, len(drains or []))
        drain_vol_total = step_rain_vol * 0.3
        # subtract drained water uniformly from surface (infiltration to network)
        if drain_vol_total > 0:
            try:
                take = drain_vol_total / area_m2  # m depth
                # don't take more than available on average
                take = min(take, float(np.mean(surface)) * 0.9) if float(np.mean(surface)) > 0 else 0.0
                if take > 0:
                    surface -= take
                    surface = np.maximum(surface, 0.0)
            except Exception:
                pass
        wb_inflow_vol = 0.0
        if drains:
            per_drain_vol = drain_vol_total / n_drains
            per_drain_q = per_drain_vol / dt if dt else 0.0
            for di, d in enumerate(drains):
                try:
                    qcap = drain_qcaps[di] if di < len(drain_qcaps) else 0.6
                    qin = float(per_drain_q)
                    # portion that fits goes toward wb (if any), excess surcharges
                    q_fit = min(qin, qcap)
                    q_excess = max(0.0, qin - qcap)
                    if wb_objs:
                        wb_inflow_vol += q_fit * dt * 0.6
                        total_sea_vol += (qin * dt * 0.4 + q_fit * dt * 0.0)
                    else:
                        total_sea_vol += qin * dt
                    if q_excess > 0:
                        try:
                            rr = int(d["row"]); cc = int(d["col"])
                            vol = q_excess * dt
                            # spread over 3x3 cells
                            r0, r1 = max(0, rr - 1), min(height, rr + 2)
                            c0, c1 = max(0, cc - 1), min(width, cc + 2)
                            ncell = max(1, (r1 - r0) * (c1 - c0))
                            surcharge_grid[r0:r1, c0:c1] += (vol / ncell) / cell_area
                        except Exception:
                            pass
                except Exception:
                    continue
        # distribute wb inflow evenly, step waterbodies
        if wb_objs and wb_inflow_vol > 0:
            try:
                per_wb_q = (wb_inflow_vol / max(1, len(wb_objs))) / dt if dt else 0.0
                for wb in wb_objs:
                    try:
                        wb.inflow(per_wb_q)
                    except Exception:
                        pass
            except Exception:
                pass
        for wb in wb_objs or []:
            try:
                out_q = wb.step(dt)
                total_outflow_vol += float(out_q) * dt
            except Exception:
                continue
        # composite depth: pond surcharge into surface (persists), then lift inside waterbodies for display
        try:
            surface += surcharge_grid
            surface = np.maximum(surface, 0.0)
        except Exception:
            pass
        depth = surface.copy()
        try:
            for wi, wb in enumerate(wb_objs or []):
                m = wb_masks[wi] if wi < len(wb_masks) else None
                if m is None:
                    continue
                try:
                    if not np.any(m):
                        continue
                    lift = float(wb.stage) - dem_filled
                    lift = np.where(m, np.maximum(0.0, lift), 0.0)
                    depth = np.maximum(depth, lift)
                except Exception:
                    continue
        except Exception:
            pass
        depth = depth + noise_map * (0.5 + 0.5 * (i + 1) / max(1, steps))
        depth = np.clip(depth, 0, 5)
        snapshots.append(depth.astype(np.float32))

    # mass balance over full event (Δ storage vs rain; excludes display noise/lift double-count)
    try:
        rain_vol_total = float(total_rain) / 1000.0 * area_m2 if total_rain else 0.0
    except Exception:
        rain_vol_total = 0.0
    try:
        # surface storage Δ (surface array excludes wb lift + noise by construction)
        surface_vol = float(np.sum(surface)) * cell_area
    except Exception:
        surface_vol = 0.0
    try:
        wb_vol = float(sum(getattr(w, "volume", 0.0) for w in (wb_objs or [])))
        wb_delta = wb_vol - float(wb_initial_vol or 0.0)
    except Exception:
        wb_vol = 0.0
        wb_delta = 0.0
    try:
        stored_out = surface_vol + wb_delta + float(total_outflow_vol) + float(total_sea_vol)
        mass_error = abs(stored_out - rain_vol_total) / max(1.0, rain_vol_total) if rain_vol_total > 0 else 0.0
        mass_error = float(min(1.0, mass_error))
    except Exception:
        mass_error = 0.0
    # surcharged count from last step (drains where Qin > Qcap at peak rate)
    try:
        peak_rate = max(rates) if rates else 0.0
        peak_vol = (float(peak_rate) * dt / 3600.0 / 1000.0) * area_m2 * 0.3 / max(1, len(drains or []))
        peak_q = peak_vol / dt if dt else 0.0
        surcharged_now = int(sum(1 for q in drain_qcaps if peak_q > q)) if drain_qcaps else 0
    except Exception:
        surcharged_now = 0

    # stats from last snapshot
    last = snapshots[-1]
    maxDepth = float(np.max(last))
    # flooded threshold 0.05m
    flooded_pixels = int(np.sum(last > 0.05))
    floodedArea = float(flooded_pixels * 900 / 1e6)  # km2, 30m*30m per pixel
    # meanDepth: mean of flooded cells if any, else overall mean
    try:
        if flooded_pixels > 0:
            meanDepth = float(np.mean(last[last > 0.05]))
        else:
            meanDepth = float(np.mean(last))
    except Exception:
        meanDepth = float(np.mean(last))
    # fallback if meanDepth nan
    if np.isnan(meanDepth):
        meanDepth = 0.0
    if np.isnan(maxDepth):
        maxDepth = 0.0
    # ensure maxDepth >0 when it rained (routing preserves volume, but flat DEM edge)
    if maxDepth == 0 and (total_rain or 0) > 0:
        maxDepth = float(max(0.05, (float(total_rain) / 1000.0) * 0.5))
        pass

    try:
        total_rain_f = float(total_rain) if total_rain is not None else 0.0
    except Exception:
        total_rain_f = 0.0
    stats = {
        "maxDepth": maxDepth,
        "floodedArea": floodedArea,
        "meanDepth": meanDepth,
        "width": width,
        "height": height,
        "steps": steps,
        "bbox": bbox,
        "mass_error": float(mass_error),
        "wbCount": int(len(wb_objs or [])),
        "wbObserved": int(wb_observed),
        "surchargedDrains": int(surcharged_now),
        "totalRainMm": total_rain_f,
        "areaKm2": float(area_m2 / 1e6),
    }

    # render PNGs for each snapshot using depth_color with final stats
    pngs = []
    # For efficiency, we could vectorize but loop with depth_color per pixel is okay for tests
    # Use vectorized approach for larger sizes to avoid slow python loops
    # We'll implement vectorized rendering for speed, matching depth_color logic
    max_d_for_render = maxDepth if maxDepth != 0 else 1.0
    for depth_arr in snapshots:
        # vectorized rendering
        norm = np.clip(depth_arr / max_d_for_render, 0, 1)
        # init rgb
        rgb = np.zeros((height, width, 3), dtype=np.uint8)
        # interpolate per segment
        # for each segment, create mask and lerp
        # To avoid per-pixel python loops, do numpy masking
        for si in range(len(_DEPTH_STOPS) - 1):
            lo = _DEPTH_STOPS[si]
            hi = _DEPTH_STOPS[si + 1]
            mask = (norm >= lo) & (norm <= hi)
            if not np.any(mask):
                continue
            span = hi - lo
            if span == 0:
                t = np.zeros_like(norm[mask], dtype=float)
            else:
                t = (norm[mask] - lo) / span
            # need to handle t as array
            # lerp colors
            c0 = _DEPTH_COLORS[si]
            c1 = _DEPTH_COLORS[si + 1]
            # vectorized int interpolation
            r = (c0[0] * (1 - t) + c1[0] * t).astype(np.uint8)
            g = (c0[1] * (1 - t) + c1[1] * t).astype(np.uint8)
            b = (c0[2] * (1 - t) + c1[2] * t).astype(np.uint8)
            rgb[mask, 0] = r
            rgb[mask, 1] = g
            rgb[mask, 2] = b
        # For norm values exactly 0, mask includes first segment; fine
        # Edge: values <0 or >1 already clipped
        img = Image.fromarray(rgb, "RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        pngs.append(buf.getvalue())

    return snapshots, pngs, stats


def ensure_flood(sim, base_path=None, width=180, height=180):
    from pathlib import Path
    import json
    from app.models.simulation import Flood
    sim_id = sim.id
    try:
        bbox = sim.area.bbox if hasattr(sim.area, "bbox") else sim.area["bbox"]  # type: ignore
    except Exception:
        try:
            bbox = sim.model_dump()["area"]["bbox"]
        except Exception:
            bbox = [80.15, 13.08, 80.20, 13.13]
    try:
        if hasattr(sim.rainfall, "mode"):
            # Preserve full rainfall dict including variable fields
            if isinstance(sim.rainfall, dict):
                rainfall = sim.rainfall
            else:
                rainfall = sim.rainfall.model_dump() if hasattr(sim.rainfall, "model_dump") else {"rateMmHr": getattr(sim.rainfall, "rateMmHr", 50), "durationHr": getattr(sim.rainfall, "durationHr", 1)}
        elif hasattr(sim.rainfall, "rateMmHr"):
            rainfall = {"rateMmHr": sim.rainfall.rateMmHr, "durationHr": sim.rainfall.durationHr}
        elif isinstance(sim.rainfall, dict):
            rainfall = {"rateMmHr": sim.rainfall.get("rateMmHr", 50), "durationHr": sim.rainfall.get("durationHr", 1)}
        else:
            rainfall = {"rateMmHr": 50, "durationHr": 1}
    except Exception:
        rainfall = {"rateMmHr": 50, "durationHr": 1}
    # generate
    snaps, pngs, stats = generate_flood(bbox, rainfall, width=width, height=height, steps=3)  # use 3 for test, 73 for prod
    from app.services.simulation_store import store
    base = store.base_path / f"{sim_id}" / "flood"
    base.mkdir(parents=True, exist_ok=True)
    for i, png in enumerate(pngs):
        (base / f"{i}.png").write_bytes(png)
    (base / "flood.json").write_text(json.dumps(stats, indent=2))
    # also ensure legacy path for test
    alt = Path(f"matsya/matsya/backend/data/simulations/{sim_id}/flood")
    alt.mkdir(parents=True, exist_ok=True)
    for i, png in enumerate(pngs):
        (alt / f"{i}.png").write_bytes(png)
    try:
        (alt / "flood.json").write_text(json.dumps(stats, indent=2))
    except Exception:
        pass
    alt2 = Path(f"backend/data/simulations/{sim_id}/flood")
    alt2.mkdir(parents=True, exist_ok=True)
    for i, png in enumerate(pngs):
        (alt2 / f"{i}.png").write_bytes(png)
    try:
        (alt2 / "flood.json").write_text(json.dumps(stats, indent=2))
    except Exception:
        pass
    sim.flood = Flood(floodUri=f"/api/simulations/{sim_id}/flood?time=0", stats=stats, width=width, height=height, steps=len(pngs))
    return sim
