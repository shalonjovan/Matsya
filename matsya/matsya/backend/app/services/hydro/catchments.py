"""DEM catchments per river reach + tidal canal helpers (Phase 5).

Pure numpy D8 flow accumulation (no GRASS). Each grid cell drains to exactly
one reach or off-grid. Analytic tide is a placeholder with a documented
upgrade path to a live tide API.
"""
import math

CELL_DEG_LAT_M = 110540.0


def _bbox_grid(bbox, width=180, height=180):
    from app.services.flood import _dem_for_bbox
    import numpy as np
    dem = np.array(_dem_for_bbox(list(bbox), width, height), dtype=float)
    try:
        mv = float(np.nanmean(dem))
    except Exception:
        mv = 5.0
    if mv != mv:
        mv = 5.0
    return np.where(np.isnan(dem), mv, dem)


def delineate_catchments(bbox, width=180, height=180):
    """Map reach_id -> {area_m2, source}. Cells drain via D8 to a reach or edge."""
    import numpy as np
    from app.services.hydro.river_capacity import build_reaches
    minLon, minLat, maxLon, maxLat = [float(x) for x in bbox]
    lat_c = (minLat + maxLat) / 2.0
    m_per_deg = 111320.0 * math.cos(math.radians(lat_c))
    dlon = (maxLon - minLon) / max(1, width)
    dlat = (maxLat - minLat) / max(1, height)
    cell_m2 = abs(dlon * m_per_deg * dlat * CELL_DEG_LAT_M)
    dem = _bbox_grid(list(bbox), width, height)
    h, w = dem.shape

    # reach cells
    reach_of_cell = {}
    try:
        reaches = build_reaches(list(bbox), max_n=10) or []
    except Exception:
        reaches = []
    for r in reaches:
        rid = str(r.get("id", "?"))
        for (x0, y0), (x1, y1) in zip(r.get("coords", [])[:-1], r.get("coords", [])[1:]):
            segm = math.hypot((x1 - x0) * m_per_deg, (y1 - y0) * CELL_DEG_LAT_M) or 1.0
            n = max(1, min(200, int(segm / 15.0)))
            for k in range(n + 1):
                lon = x0 + (x1 - x0) * k / n
                lat = y0 + (y1 - y0) * k / n
                cc = int((lon - minLon) / dlon) if dlon else 0
                rr = int((maxLat - lat) / dlat) if dlat else 0
                if 0 <= rr < h and 0 <= cc < w:
                    reach_of_cell[(rr, cc)] = rid

    # D8 steepest descent (indices into 8 neighbours)
    dirs = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    dist = [math.sqrt(2), 1, math.sqrt(2), 1, 1, math.sqrt(2), 1, math.sqrt(2)]
    flow_to = {}
    for r in range(h):
        for c in range(w):
            best, best_slope = None, 0.0
            for k, (dr, dc) in enumerate(dirs):
                nr, nc = r + dr, c + dc
                if 0 <= nr < h and 0 <= nc < w:
                    s = (dem[r, c] - dem[nr, nc]) / dist[k]
                    if s > best_slope:
                        best_slope, best = s, (nr, nc)
            flow_to[(r, c)] = best  # None = pit or flat

    resolved = {}

    def outlet(cell):
        if cell in resolved:
            return resolved[cell]
        seen = []
        cur = cell
        while True:
            if cur in reach_of_cell:
                out = reach_of_cell[cur]
                break
            if cur in resolved:
                out = resolved[cur]
                break
            nxt = flow_to.get(cur)
            if nxt is None or nxt in seen:
                out = None
                break
            seen.append(cur)
            cur = nxt
        for s_ in seen:
            resolved[s_] = out
        return out

    areas: dict = {}
    for r in range(h):
        for c in range(w):
            o = outlet((r, c))
            if o is not None:
                areas[o] = areas.get(o, 0) + cell_m2
    return {rid: {"area_m2": round(a, 1), "source": "dem-d8"} for rid, a in areas.items()}


def buckingham_tide(hours=6):
    """Analytic semi-diurnal tide placeholder for Buckingham canal boundary.

    Upgrade path: replace constituents with a live tide API + file cache.
    Returns [(hour, stage_m)].
    """
    out = []
    for h in range(max(1, int(hours))):
        stage = 0.5 + 0.35 * math.sin(2 * math.pi * h / 12.42) + 0.15 * math.sin(2 * math.pi * h / 12.0)
        out.append((h, round(float(stage), 3)))
    return out
