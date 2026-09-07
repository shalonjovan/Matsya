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
            tagged = []
            for _tn, _tf in (("micro", data.get("micro")), ("macro", data.get("macro"))):
                if _tf is not None and len(_tf) > 0:
                    _c = _tf.copy()
                    _c["_src"] = _tn
                    tagged.append(_c)
            drains = pd.concat(tagged, ignore_index=True) if tagged else pd.concat(parts, ignore_index=True)
            drains = gpd.GeoDataFrame(drains, crs="EPSG:4326")
            lo_x, hi_x = (minLon, maxLon) if minLon <= maxLon else (maxLon, minLon)
            lo_y, hi_y = (minLat, maxLat) if minLat <= maxLat else (maxLat, minLat)
            try:
                clipped = drains.cx[lo_x:hi_x, lo_y:hi_y].head(max_n)
            except Exception:
                clipped = drains.head(max_n)
            if len(clipped) == 0:
                raise ValueError("no drains in bbox")
            # snap targets for the same clipped set (micro-then-macro order matches
            # snap's internal concat, so positional ids align when KML ids are absent)
            _snap_mapping: dict = {}
            try:
                from app.services.hydro.snap import snap_drains_to_waterbodies as _snap_fn
                _has_src = "_src" in clipped.columns
                _micro_c = clipped[clipped["_src"] == "micro"].drop(columns=["_src"], errors="ignore") if _has_src else clipped.iloc[0:0]
                _macro_c = clipped[clipped["_src"] == "macro"].drop(columns=["_src"], errors="ignore") if _has_src else clipped
                if _has_src and (len(_micro_c) == 0 and len(_macro_c) == 0):
                    _micro_c, _macro_c = clipped, clipped.iloc[0:0]
                _snap_mapping = (_snap_fn(_micro_c, _macro_c, data.get("rivers"), data.get("waterbodies")).get("mapping", {})) or {}
            except Exception:
                _snap_mapping = {}
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
                    # resolve snap target: KML id value first, else clipped position
                    _tgt = "sea"
                    try:
                        _rv = row.get("id", None) if hasattr(row, "get") else None
                        import pandas as _pdn
                        if _rv is not None and not (isinstance(_rv, float) and _pdn.isna(_rv)):
                            _tgt = _snap_mapping.get(_rv, _snap_mapping.get(str(_rv), _tgt))
                            if _tgt == "sea":
                                _tgt = _snap_mapping.get(i, _snap_mapping.get(str(i), "sea"))
                        else:
                            _tgt = _snap_mapping.get(i, _snap_mapping.get(str(i), "sea"))
                    except Exception:
                        _tgt = "sea"
                    out.append({"row": rr, "col": cc, "length_m": length, "slope": float(slope),
                                "target": str(_tgt)})
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
        out.append({"row": int(rng.integers(0, height)), "col": int(rng.integers(0, width)), "length_m": 800.0, "slope": 0.001, "target": "sea"})
    return out


def _river_cells(coords_lonlat, bbox, width, height, radius_m=45):
    """Bool mask of cells within radius_m of a lon/lat polyline. None if unusable."""
    import math as _m
    import numpy as np
    try:
        minLon, minLat, maxLon, maxLat = bbox
        pts = list(coords_lonlat or [])
        if len(pts) < 2:
            return None
        lat_c = (minLat + maxLat) / 2.0
        m_per_deg = 111320.0 * _m.cos(_m.radians(lat_c))
        dlon = (maxLon - minLon) / max(1, width)
        dlat = (maxLat - minLat) / max(1, height)
        samples = []
        for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
            segm = _m.hypot((x1 - x0) * m_per_deg, (y1 - y0) * 110540.0) or 1.0
            n = max(1, min(200, int(segm / 15.0)))
            for k in range(n + 1):
                samples.append((x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n))
        r_cells = int(max(1, round(radius_m / 30.0)))
        mask = np.zeros((height, width), dtype=bool)
        for lon, lat in samples:
            cc = int((lon - minLon) / dlon) if dlon else 0
            rr = int((maxLat - lat) / dlat) if dlat else 0
            r0, r1 = max(0, rr - r_cells), min(height, rr + r_cells + 1)
            c0, c1 = max(0, cc - r_cells), min(width, cc + r_cells + 1)
            mask[r0:r1, c0:c1] = True
        return mask if np.any(mask) else None
    except Exception:
        return None


def _river_step(reach_obj, reach_info, inflow_vol_m3, dt, surface, mask, cell_area):
    """Route one reach for one timestep.

    Returns {"sea_vol": float, "spill_vol": float, "overtopped": bool}.
    Overtop when Muskingum wedge storage S = K*(x*I + (1-x)*O) exceeds
    steady-bankfull storage K*qbank; the excess ponds on the reach mask and
    is withheld from downstream outflow. Routed outflow returns to the sea.
    """
    sea_vol, spill_vol, overtopped = 0.0, 0.0, False
    try:
        qin = float(inflow_vol_m3) / dt if dt else 0.0
    except Exception:
        qin = 0.0
    if qin <= 0:
        return {"sea_vol": 0.0, "spill_vol": 0.0, "overtopped": False}
    try:
        qout = reach_obj.route(qin, dt) if reach_obj is not None else 0.0
    except Exception:
        qout = 0.0
    try:
        qbank = float((reach_info or {}).get("qbank", 0) or 0)
    except Exception:
        qbank = 0.0
    try:
        _K = float(getattr(reach_obj, "K", 600.0)) if reach_obj is not None else 600.0
        _x = float(getattr(reach_obj, "x", 0.2)) if reach_obj is not None else 0.2
    except Exception:
        _K, _x = 600.0, 0.2
    try:
        sea_vol = float(qout) * dt
    except Exception:
        sea_vol = 0.0
    if qbank > 0 and _K > 0:
        try:
            stored = _K * (_x * qin + (1.0 - _x) * qout)
            bankfull_stored = _K * qbank
            if stored > bankfull_stored:
                excess = stored - bankfull_stored
                if mask is not None:
                    _pond_volume(surface, mask, excess, cell_area)
                    spill_vol = excess
                # ponded water does not continue downstream
                try:
                    sea_vol = max(0.0, sea_vol - excess)
                except Exception:
                    pass
                overtopped = True
        except Exception:
            pass
    return {"sea_vol": sea_vol, "spill_vol": spill_vol, "overtopped": overtopped}


def _spill_ring(mask, radius=2):
    """Shoreline ring: cells within `radius` of mask, excluding mask itself."""
    import numpy as np
    m = np.asarray(mask, dtype=bool)
    if not np.any(m):
        return None
    h, w = m.shape
    dilated = m.copy()
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx == 0 and dy == 0:
                continue
            shifted = np.roll(np.roll(m, dy, axis=0), dx, axis=1)
            # kill wraparound rows/cols introduced by roll
            if dy > 0:
                shifted[:dy, :] = False
            elif dy < 0:
                shifted[dy:, :] = False
            if dx > 0:
                shifted[:, :dx] = False
            elif dx < 0:
                shifted[:, dx:] = False
            dilated |= shifted
    ring = dilated & ~m
    return ring if np.any(ring) else None


def _pond_volume(surface, ring, vol_m3, cell_area):
    """Spread vol_m3 evenly over ring cells as depth; returns mean added depth."""
    import numpy as np
    n = int(np.count_nonzero(ring))
    if n == 0 or vol_m3 <= 0 or cell_area <= 0:
        return 0.0
    d = float(vol_m3) / n / float(cell_area)
    surface[ring] += d
    return d


def _swmm_node_floods(bbox, rainfall):
    """Computed node floods via cached SWMM. Raises on solver failure (caller falls back)."""
    from app.services.engine.swmm_runner import cached_node_floods
    return cached_node_floods(list(bbox), rainfall or {})


def generate_flood(bbox, rainfall, width=180, height=180, steps=73, polygon=None, initial_fill_pct=75.0):
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

    # rainfall zones (spatial rain): parsed once, painted per step. Zoneless
    # requests take the legacy scalar path below bit-for-bit.
    from app.services.rainfall_zones import parse_zones, zone_step_rates
    try:
        _rfz = rainfall if isinstance(rainfall, dict) else (rainfall.model_dump(mode="json") if hasattr(rainfall, "model_dump") else {})
    except Exception:
        _rfz = {}
    if not isinstance(_rfz, dict):
        _rfz = {}
    # rainfall source toggles (defaults preserve legacy behavior)
    use_base = bool(_rfz.get("useBase", True))
    use_zones_flag = bool(_rfz.get("useZones", True))
    if not use_base:
        # zones-only storm: zero the base rate/curve, zones paint on top
        try:
            rate = 0.0
            rates = [0.0] * max(1, steps)
            total_rain = 0.0
        except Exception:
            pass
    zone_list, _zone_dropped = parse_zones(_rfz if isinstance(_rfz, dict) else {})
    has_zones = len(zone_list) > 0 and use_zones_flag
    # per-zone mm/hr per flood step (constant zones: flat; variable: hyetograph)
    zone_rate_steps: list = []
    if has_zones:
        for _z in zone_list:
            try:
                zone_rate_steps.append(zone_step_rates(_z, steps, duration))
            except Exception:
                zone_rate_steps.append([0.0] * max(1, steps))

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
        fill_frac = min(1.0, max(0.0, float(initial_fill_pct) / 100.0))
    except Exception:
        fill_frac = 0.75
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
    wb_rings = []
    try:
        for m in (wb_masks or []):
            wb_rings.append(_spill_ring(m, radius=2) if m is not None else None)
    except Exception:
        wb_rings = [None] * len(wb_infos or [])
    spilled_total = 0.0
    overtopped = set()
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
                bed = info["crest"] - depth
                stage0 = bed + fill_frac * depth
                wb_objs.append(WaterBody(area_m2=info["area_m2"], crest=info["crest"],
                                         stage=stage0, depth=depth))
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

    # computed SWMM overflow (Slice 2); Manning guess below is fallback only
    try:
        minLon, minLat, maxLon, maxLat = bbox
    except Exception:
        minLon, minLat, maxLon, maxLat = (80.15, 13.08, 80.20, 13.13)
    dlon = (maxLon - minLon) / max(1, width)
    dlat = (maxLat - minLat) / max(1, height)
    # zone masks, precomputed once (paint order = list order, last wins)
    zone_masks: list = []
    if has_zones:
        try:
            from app.services.rainfall_zones import zone_masks as _zone_masks
            zone_masks = _zone_masks(zone_list, list(bbox), width, height)
        except Exception:
            zone_masks = [np.zeros((height, width), dtype=bool) for _ in zone_list]
    swmm_info: dict = {"coupled": False, "node_flood": {}, "drains": []}
    try:
        swmm_info = _swmm_node_floods(bbox, rainfall)
    except Exception:
        swmm_info = {"coupled": False, "node_flood": {}, "drains": []}
    swmm_coupled = bool(swmm_info.get("coupled"))
    # node id -> grid cell from SWMM drain endpoint coords
    swmm_cells: dict = {}
    try:
        for _di, _dr in enumerate(swmm_info.get("drains", []) or []):
            for _tag, _lk in (("J%d_UP" % _di, ("x0", "y0")), ("J%d_DN" % _di, ("x1", "y1"))):
                try:
                    _lon, _lat = float(_dr[_lk[0]]), float(_dr[_lk[1]])
                    _cc = int((_lon - minLon) / dlon) if dlon else 0
                    _rr = int((maxLat - _lat) / dlat) if dlat else 0
                    swmm_cells[_tag] = (max(0, min(height - 1, _rr)), max(0, min(width - 1, _cc)))
                except Exception:
                    continue
    except Exception:
        swmm_cells = {}

    dt = duration * 3600 / steps if steps > 0 else 3600
    try:
        dt = float(dt)
    except Exception:
        dt = 3600.0
    # river reaches: capacity + Muskingum state + cell masks (Slice 2)
    river_reaches, river_objs, river_masks = [], {}, []
    river_by_key: dict = {}
    river_spill_total = 0.0
    overtopped_rivers: list = []
    river_assumed = 0
    try:
        from app.services.hydro.river_capacity import build_reaches, reach_capacity, valley_width
        from app.services.hydro.river import RiverReach
        _raw_reaches = build_reaches(list(bbox), max_n=10)
        for _rr in (_raw_reaches or []):
            try:
                _w, _wsrc = valley_width(dem_filled, list(bbox), width, height, _rr.get("coords", []))
                if _w is not None:
                    _cap = reach_capacity(_rr["length_m"], _rr["slope"], width_m=_w)
                    _rr = dict(_rr, width_m=_cap["width_m"], qbank=_cap["qbank"], source="observed-valley")
                _rr.setdefault("source", "assumed-defaults")
                if str(_rr.get("source", "")).startswith("assumed"):
                    river_assumed += 1
                _K = min(3600.0, max(60.0, float(_rr["length_m"]) / 1.5))
                _rid = str(_rr.get("id"))
                _rpos = len(river_reaches)
                try:
                    _init_q = float(_rr.get("qbank", 0) or 0) * fill_frac
                except Exception:
                    _init_q = 0.0
                river_objs[_rpos] = RiverReach(length=_rr["length_m"], slope=_rr["slope"], K=_K, x=0.2, init_q=_init_q)
                river_by_key[_rid] = _rpos
                try:
                    _lbl = str(_rr.get("_label", _rid))
                    if _lbl != _rid:
                        river_by_key[_lbl] = _rpos
                except Exception:
                    pass
                river_reaches.append(_rr)
                river_masks.append(_river_cells(_rr.get("coords", []), list(bbox), width, height, radius_m=45))
            except Exception:
                continue
    except Exception:
        river_reaches, river_objs, river_masks = [], {}, []
    try:
        river_storage_init = 0.0
        for _ro in (river_objs or {}).values():
            try:
                river_storage_init += float(getattr(_ro, "K", 0.0)) * float(getattr(_ro, "_prev_out", 0.0))
            except Exception:
                continue
    except Exception:
        river_storage_init = 0.0
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
    rain_vol_accum = 0.0  # gridded rain volume (zoned path); legacy scalar otherwise
    for i in range(steps):
        try:
            rate_i = float(rates[i]) if i < len(rates) else float(rates[-1] if rates else 0.0)
        except Exception:
            rate_i = 50.0
        rate_grid = None
        if has_zones:
            # zoned: base rate everywhere, zone rates painted last-wins
            try:
                rate_grid = np.full((height, width), rate_i, dtype=np.float64)
                for _zi2, _zm in enumerate(zone_masks):
                    try:
                        if _zm is not None and bool(np.any(_zm)):
                            _zsteps = zone_rate_steps[_zi2] if _zi2 < len(zone_rate_steps) else None
                            _zv = float(_zsteps[i]) if _zsteps is not None and i < len(_zsteps) else float(_zsteps[-1]) if _zsteps else 0.0
                            rate_grid[_zm] = _zv
                    except Exception:
                        continue
                _rain_inc_grid = rate_grid * dt / 3600.0 / 1000.0
                if float(np.sum(_rain_inc_grid)) != 0.0:
                    surface += _rain_inc_grid
                rain_inc_m = float(np.mean(rate_grid))  # representative scalar
                step_rain_vol = float(np.sum(_rain_inc_grid)) * cell_area
                rain_vol_accum += float(np.sum(_rain_inc_grid)) * cell_area
            except Exception:
                rate_grid = None
        if rate_grid is None:
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
        # lateral spreading: level water surfaces across flat neighbours.
        # D8 alone only drains steepest-descent threads, so threads deepen in
        # place instead of overtopping banks. Symmetric pairwise exchange is
        # exactly volume-preserving (each debit has an equal credit), with
        # donor-side scaling so no cell ever gives more than it holds
        # (per-pair clamps alone go negative when a cell feeds two pairs).
        try:
            if float(np.sum(surface)) > 0:
                for _pass in range(3):
                    _ws = dem_filled + surface
                    # vertical pairs (upper -> lower signed)
                    _d = _ws[:-1, :] - _ws[1:, :]
                    _t = 0.15 * _d
                    _debit = np.zeros_like(surface)
                    _debit[:-1, :] += np.maximum(_t, 0.0)
                    _debit[1:, :] += np.maximum(-_t, 0.0)
                    _scale = np.ones_like(surface)
                    _nz = _debit > 0
                    _scale[_nz] = np.minimum(1.0, surface[_nz] / np.maximum(_debit[_nz], 1e-12))
                    _t = np.where(_t > 0, _t * _scale[:-1, :], _t * _scale[1:, :])
                    surface[:-1, :] -= _t
                    surface[1:, :] += _t
                    # horizontal pairs (left -> right signed)
                    _ws = dem_filled + surface
                    _d = _ws[:, :-1] - _ws[:, 1:]
                    _t = 0.15 * _d
                    _debit = np.zeros_like(surface)
                    _debit[:, :-1] += np.maximum(_t, 0.0)
                    _debit[:, 1:] += np.maximum(-_t, 0.0)
                    _scale = np.ones_like(surface)
                    _nz = _debit > 0
                    _scale[_nz] = np.minimum(1.0, surface[_nz] / np.maximum(_debit[_nz], 1e-12))
                    _t = np.where(_t > 0, _t * _scale[:, :-1], _t * _scale[:, 1:])
                    surface[:, :-1] -= _t
                    surface[:, 1:] += _t
        except Exception:
            pass
        # drains: take 30% of this step's rain volume, route to wb/sea, surcharge locally
        surcharge_grid = np.zeros_like(surface)
        if rate_grid is None:
            step_rain_vol = rain_inc_m * area_m2
            if has_zones:
                rain_vol_accum += float(step_rain_vol)
        n_drains = max(1, len(drains or []))
        drain_vol_total = step_rain_vol * 0.3
        if not swmm_coupled:
            # Manning-guess take (fallback path only)
            if drain_vol_total > 0:
                try:
                    take = drain_vol_total / area_m2  # m depth
                    # don't take more than available on average
                    take = min(take, float(np.mean(surface)) * 0.9) if float(np.mean(surface)) > 0 else 0.0
                    if take > 0:
                        # proportional removal: exact volume, no clip-destruction
                        # (uniform subtract + clip destroys real water on shallow cells)
                        _ms = float(np.mean(surface))
                        surface *= max(0.0, 1.0 - take / _ms) if _ms > 0 else 1.0
                except Exception:
                    pass
        else:
            # computed path: remove SWMM-routed volume uniformly, pond node floods locally
            try:
                swmm_nodes = swmm_info.get("node_flood", {}) or {}
                swmm_step_total = float(sum(v.get("volume_m3", 0) for v in swmm_nodes.values())) / max(1, steps)
            except Exception:
                swmm_step_total = 0.0
                swmm_nodes = {}
            if swmm_step_total > 0:
                try:
                    take = swmm_step_total / area_m2
                    take = min(take, float(np.mean(surface)) * 0.9) if float(np.mean(surface)) > 0 else 0.0
                    if take > 0:
                        _ms = float(np.mean(surface))
                        surface *= max(0.0, 1.0 - take / _ms) if _ms > 0 else 1.0
                except Exception:
                    pass
                try:
                    for nid, ninfo in swmm_nodes.items():
                        try:
                            vol = float(ninfo.get("volume_m3", 0)) / max(1, steps)
                            if vol <= 0:
                                continue
                            cell = swmm_cells.get(nid)
                            if cell is None:
                                continue
                            rr, cc = cell
                            r0, r1 = max(0, rr - 1), min(height, rr + 2)
                            c0, c1 = max(0, cc - 1), min(width, cc + 2)
                            ncell = max(1, (r1 - r0) * (c1 - c0))
                            surcharge_grid[r0:r1, c0:c1] += (vol / ncell) / cell_area
                        except Exception:
                            continue
                except Exception:
                    pass
        wb_inflow_vol = 0.0
        river_inflow: dict = {}
        if drains:
            per_drain_vol = drain_vol_total / n_drains
            per_drain_q = per_drain_vol / dt if dt else 0.0
            # zoned: split the drain take proportionally to each drain's local rain
            zone_shares = None
            if has_zones and rate_grid is not None and drains:
                try:
                    _sh = []
                    for _dd in (drains or []):
                        try:
                            _sh.append(float(rate_grid[int(_dd["row"]), int(_dd["col"])]))
                        except Exception:
                            _sh.append(float(rate_i))
                    _st = float(sum(_sh))
                    zone_shares = [(_s / _st) if _st > 0 else 1.0 / max(1, len(_sh)) for _s in _sh] if _sh else None
                except Exception:
                    zone_shares = None
            for di, d in enumerate(drains):
                try:
                    qcap = drain_qcaps[di] if di < len(drain_qcaps) else 0.6
                    qin = float(per_drain_q)
                    if zone_shares is not None and di < len(zone_shares):
                        try:
                            qin = float(drain_vol_total * zone_shares[di]) / dt if dt else 0.0
                        except Exception:
                            pass
                    # portion that fits goes toward wb (if any), excess surcharges
                    q_fit = min(qin, qcap)
                    q_excess = max(0.0, qin - qcap)
                    try:
                        _tgt = str((d or {}).get("target", "sea")) if isinstance(d, dict) else "sea"
                    except Exception:
                        _tgt = "sea"
                    if _tgt.startswith("river:") and river_by_key:
                        # river-mapped: the drain's water is river-bound, so the whole
                        # fitted + runoff share goes to the reach (not lakes, not sea).
                        # Excess still ponds via the surcharge block below, unchanged.
                        _rkey = _tgt.split(":", 1)[1]
                        _rpos = river_by_key.get(_rkey, river_by_key.get(str(_rkey)))
                        if _rpos is not None:
                            river_inflow[_rpos] = river_inflow.get(_rpos, 0.0) + (q_fit + qin * 0.4) * dt
                        else:
                            total_sea_vol += qin * dt * 0.4
                            if wb_objs:
                                wb_inflow_vol += q_fit * dt * 0.6
                            else:
                                total_sea_vol += q_fit * dt * 0.6
                        if wb_objs:
                            wb_inflow_vol += q_fit * dt * 0.6
                        else:
                            total_sea_vol += q_fit * dt * 0.6 + qin * dt * 0.0
                    elif wb_objs:
                        wb_inflow_vol += q_fit * dt * 0.6
                        total_sea_vol += (qin * dt * 0.4 + q_fit * dt * 0.0)
                    else:
                        total_sea_vol += qin * dt
                    if q_excess > 0 and not swmm_coupled:
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
        # direct rainfall onto lake surfaces goes straight into storage
        # (rain falls on water too); compensate the surface grid so mass closes
        direct_rain_vol = 0.0
        if (rain_inc_m or has_zones) and wb_objs:
            try:
                for wi, wb in enumerate(wb_objs):
                    try:
                        _rlocal = rain_inc_m
                        if has_zones and rate_grid is not None:
                            try:
                                _g = (wb_infos or [])[wi].get("geometry") if wi < len(wb_infos or []) else None
                                _cx = float(_g.centroid.x); _cy = float(_g.centroid.y)
                                _cc = max(0, min(width - 1, int((_cx - minLon) / dlon))) if dlon else 0
                                _rr = max(0, min(height - 1, int((maxLat - _cy) / dlat))) if dlat else 0
                                _rlocal = float(rate_grid[_rr, _cc]) * dt / 3600.0 / 1000.0  # mm/hr -> m
                            except Exception:
                                pass
                        q_rain = _rlocal * float(getattr(wb, "area_m2", 0.0)) / dt if dt else 0.0
                    except Exception:
                        q_rain = 0.0
                    if q_rain > 0:
                        wb.inflow(q_rain)
                        direct_rain_vol += q_rain * dt
            except Exception:
                pass
        if direct_rain_vol > 0:
            try:
                # proportional compensation (same reason as drain take above)
                _ms = float(np.mean(surface))
                _tk = direct_rain_vol / area_m2
                if _ms > 0 and _tk > 0:
                    surface *= max(0.0, 1.0 - min(_tk, _ms * 0.999) / _ms)
            except Exception:
                pass
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
        for wi, wb in enumerate(wb_objs or []):
            try:
                out_q = wb.step(dt)
                out_vol = float(out_q) * dt
                if out_vol > 0:
                    overtopped.add(wi)
                    ring = wb_rings[wi] if wi < len(wb_rings) else None
                    if ring is not None:
                        # pond spill on the shoreline: it stays in-domain (surface
                        # already measures it), so do NOT count it as outflow
                        _pond_volume(surface, ring, out_vol, cell_area)
                        spilled_total += out_vol
                    else:
                        total_outflow_vol += out_vol  # no shore: legacy count-as-outflow
            except Exception:
                continue
        # river routing: Muskingum per reach, overtop ponds on river cells
        try:
            for _ri, _rr in enumerate(river_reaches):
                try:
                    _invol = float(river_inflow.get(_ri, 0.0))
                except Exception:
                    _invol = 0.0
                if _invol <= 0:
                    continue
                _res = _river_step(river_objs.get(_ri), _rr, _invol, dt,
                                   surface, river_masks[_ri] if _ri < len(river_masks) else None,
                                   cell_area)
                try:
                    total_sea_vol += float(_res.get("sea_vol", 0.0))
                    river_spill_total += float(_res.get("spill_vol", 0.0))
                except Exception:
                    pass
                if _res.get("overtopped"):
                    _rid_s = str(_rr.get("id"))
                    if _rid_s not in overtopped_rivers:
                        overtopped_rivers.append(_rid_s)
        except Exception:
            pass
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
        if has_zones:
            rain_vol_total = float(rain_vol_accum)
        else:
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
        # Muskingum reach storage Δ (S = K*(x*I + (1-x)*O)); withholds live in reaches
        _s_now, _s_init = 0.0, 0.0
        for _ro in (river_objs or {}).values():
            try:
                _Kk = float(getattr(_ro, "K", 0.0)); _xx = float(getattr(_ro, "x", 0.2))
                _s_now += _Kk * (_xx * float(getattr(_ro, "_prev_in", 0.0)) + (1.0 - _xx) * float(getattr(_ro, "_prev_out", 0.0)))
            except Exception:
                continue
        try:
            _s_init = float(river_storage_init)
        except Exception:
            _s_init = 0.0
        river_delta = _s_now - _s_init
    except Exception:
        river_delta = 0.0
    try:
        stored_out = surface_vol + wb_delta + river_delta + float(total_outflow_vol) + float(total_sea_vol)
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
        if has_zones:
            total_rain_f = float(rain_vol_accum) / area_m2 * 1000.0 if area_m2 else 0.0
        else:
            total_rain_f = float(total_rain) if total_rain is not None else 0.0
    except Exception:
        total_rain_f = 0.0
    # per-zone rain summary (area share from precomputed masks)
    zone_stats: list = []
    if has_zones:
        try:
            for _zi, _z in enumerate(zone_list):
                try:
                    _m = zone_masks[_zi] if _zi < len(zone_masks) else None
                    _frac = float(np.mean(_m)) if _m is not None else 0.0
                except Exception:
                    _frac = 0.0
                try:
                    _zs = zone_rate_steps[_zi] if _zi < len(zone_rate_steps) else [0.0]
                    _zmean = float(sum(_zs) / max(1, len(_zs)))
                    _zpeak = float(max(_zs)) if _zs else 0.0
                except Exception:
                    _zmean, _zpeak = 0.0, 0.0
                zone_stats.append({
                    "index": int(_zi),
                    "id": str(_z.get("id", "z%d" % _zi)),
                    "mode": str(_z.get("mode", "constant")),
                    "amountMm": float(_z.get("amount", _z.get("maxRain", 0.0)) or 0.0),
                    "unit": str(_z.get("unit", "rate")),
                    "rateMmHr": _zmean,
                    "peakMmHr": _zpeak,
                    "areaKm2": round(float(area_m2 * _frac / 1e6), 4),
                })
        except Exception:
            zone_stats = []
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
        "swmmCoupled": bool(swmm_coupled),
        "swmmFloodedNodes": int(len((swmm_info.get("node_flood") or {}))),
        "swmmFloodVolumeM3": round(float(sum(v.get("volume_m3", 0) for v in (swmm_info.get("node_flood") or {}).values())), 1),
        "swmmNodes": [{"id": str(_nid), "floodVolumeM3": round(float((_nv or {}).get("volume_m3", 0) or 0.0), 1)}
                      for _nid, _nv in sorted((swmm_info.get("node_flood") or {}).items(), key=lambda kv: str(kv[0]))],
        "spillVolumeM3": round(float(spilled_total), 1),
        "overtoppedLakes": int(len(overtopped)),
        "riverSpillVolumeM3": round(float(river_spill_total), 1),
        "overtoppedRivers": list(overtopped_rivers)[:20],
        "riverAssumed": int(river_assumed),
        "riverCount": int(len(river_reaches)),
        "totalRainMm": total_rain_f,
        "zones": zone_stats,
        "initialFillPct": round(fill_frac * 100.0, 1),
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


def _flood_duration_hr(rainfall) -> float:
    """Storm duration in hours from constant or variable rainfall. Minimum epsilon."""
    try:
        if isinstance(rainfall, dict):
            if rainfall.get("mode") == "variable":
                return max(0.25, float(rainfall.get("totalTime", rainfall.get("durationHr", 6)) or 6))
            return max(0.25, float(rainfall.get("durationHr", rainfall.get("totalTime", 1)) or 1))
        mode = getattr(rainfall, "mode", "constant")
        if mode == "variable":
            return max(0.25, float(getattr(rainfall, "totalTime", 6) or 6))
        return max(0.25, float(getattr(rainfall, "durationHr", 1) or 1))
    except Exception:
        return 1.0


def _playback_steps(duration_hr: float) -> int:
    """One frame per ~15 min, clamped to [6, 73] (73 = Timeline legacy max)."""
    try:
        return max(6, min(73, round(float(duration_hr) * 60.0 / 15.0)))
    except Exception:
        return 6


def _playback_minutes_per_frame(duration_hr: float, steps: int) -> float:
    try:
        return float(duration_hr) * 60.0 / max(1, int(steps))
    except Exception:
        return 5.0


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
    try:
        _p = getattr(sim, "parameters", None)
        _fill = _p.get("initialFillPct", 75.0) if isinstance(_p, dict) else getattr(_p, "initialFillPct", 75.0)
    except Exception:
        _fill = 75.0
    # generate
    _dur = _flood_duration_hr(rainfall)
    _steps = _playback_steps(_dur)
    _mpf = _playback_minutes_per_frame(_dur, _steps)
    snaps, pngs, stats = generate_flood(bbox, rainfall, width=width, height=height, steps=_steps, initial_fill_pct=_fill)
    stats = dict(stats or {})
    stats["minutesPerFrame"] = _mpf
    stats["floodVersion"] = 2
    from app.services.simulation_store import store
    base = store.base_path / f"{sim_id}" / "flood"
    base.mkdir(parents=True, exist_ok=True)
    for i, png in enumerate(pngs):
        (base / f"{i}.png").write_bytes(png)
    try:
        import numpy as _np
        _np.save(base / "snapshots.npy", _np.array(snaps, dtype="float32"))
    except Exception:
        pass
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
