"""SWMM INP builder + input audit (Slice 1: parallel-reach network, honest defaults)."""

WIDTH_M = 1.0
DEPTH_M = 1.0
ROUGHNESS = 0.017


def audit_inputs(drains, rainfall):
    drains = list(drains or [])
    if not drains:
        return {"ready": False, "mode": "blocked-no-drains-in-bbox",
                "observed": [], "assumed": [],
                "missing": ["no drain reaches intersect simulation bbox"]}
    rate = (rainfall or {}).get("rateMmHr") or (rainfall or {}).get("constantRate")
    if not rate:
        return {"ready": False, "mode": "blocked-no-rainfall",
                "observed": ["drain count %d" % len(drains)], "assumed": [],
                "missing": ["rainfall rate"]}
    observed, assumed = ["drain count %d" % len(drains)], []
    if any(d.get("length_m") for d in drains):
        observed.append("conduit length from geometry")
    else:
        assumed.append("conduit length default 200m")
    for k in ("width: RECT_OPEN %.1fm" % WIDTH_M, "depth: %.1fm" % DEPTH_M,
              "roughness n=%.3f" % ROUGHNESS, "slope: DEM drop or 0.001",
              "inverts: DEM sample at endpoints"):
        assumed.append(k)
    return {"ready": True, "mode": "provisional-default-geometry",
            "observed": observed, "assumed": assumed, "missing": []}


def _rain_series(rainfall):
    """Return list of (hours_since_start, mm/hr). Supports constant + variable curve."""
    rainfall = rainfall or {}
    if rainfall.get("mode") == "variable" and rainfall.get("curve", {}).get("values"):
        vals = list(rainfall["curve"]["values"])
        total = float(rainfall.get("totalTime") or rainfall.get("durationHr") or 6)
        dt = total / max(1, len(vals))
        return [(i * dt, float(v)) for i, v in enumerate(vals)]
    rate = float(rainfall.get("rateMmHr") or rainfall.get("constantRate") or 50)
    dur = float(rainfall.get("durationHr") or rainfall.get("totalTime") or 1)
    return [(0.0, rate), (dur, rate), (dur + 0.01, 0.0)]


def _zone_regimes(rainfall, base_series):
    """Per-zone flat (hours, mm/hr) regimes. Returns ([(name, series)], zones).

    Zoneless -> ([], []) so the legacy single-gage output is untouched.
    Zone rate is absolute (rate as-is; total spread over the base duration).
    """
    try:
        from app.services.rainfall_zones import parse_zones
    except Exception:
        return [], []
    try:
        zones, _ = parse_zones(rainfall or {})
    except Exception:
        return [], []
    if not zones:
        return [], []
    try:
        _nz = [(t, v) for t, v in (base_series or []) if float(v) != 0.0]
        _T = float(_nz[-1][0]) if _nz else float((base_series or [(0.0, 0.0)])[-1][0])
        _T = max(0.25, _T)
    except Exception:
        _T = 1.0
    out = []
    for zi, z in enumerate(zones):
        try:
            amt = float(z.get("amount", 0.0))
            zr = amt if str(z.get("unit", "rate")) == "rate" else amt / _T
        except Exception:
            zr = 0.0
        out.append(("RAIN_Z%d" % zi, [(0.0, zr), (_T, zr), (_T + 0.01, 0.0)]))
    return out, zones


def _subcatch_gage(d, zones):
    """Gage name for a drain: zone containing the outlet midpoint wins (RGZ{i})."""
    if not zones:
        return "RG1"
    try:
        from app.services.rainfall_zones import zone_at
    except Exception:
        return "RG1"
    try:
        mx = (float(d.get("x0")) + float(d.get("x1"))) / 2.0
        my = (float(d.get("y0")) + float(d.get("y1"))) / 2.0
    except Exception:
        return "RG1"
    try:
        hit = zone_at(mx, my, zones)
        if hit is None:
            return "RG1"
        for zi, z in enumerate(zones):
            if str(z.get("id")) == str(hit.get("id")):
                return "RGZ%d" % zi
    except Exception:
        pass
    return "RG1"


def _stamp_lines(name, series):
    """SWMM TIMESERIES rows for one series (legacy RAIN format)."""
    prev_min = -1
    stamped = []
    for t, v in (series or []):
        m = int(float(t) * 60)
        if m <= prev_min:
            m = prev_min + 5
        prev_min = m
        stamped.append((m, float(v)))
    if stamped and stamped[-1][1] != 0.0:
        stamped.append((stamped[-1][0] + 5, 0.0))
    return ["%s  %02d:%02d:00  %.2f" % (name, m // 60, m % 60, v) for m, v in stamped]


def build_inp(drains, rainfall, bbox, out_path):
    drains = list(drains or [])
    series = _rain_series(rainfall)
    zone_series, zones = _zone_regimes(rainfall, series)
    end_h = series[-1][0] + 1.0

    def hms(h):
        h = float(h)
        hh, mm = divmod(int(h * 60), 60)
        return "%02d:%02d:00" % (hh, mm)

    end_date = "01/02/2026" if end_h >= 24 else "01/01/2026"
    L = ["[TITLE]", "matsya-slice1", "[OPTIONS]",
         "FLOW_UNITS           CMS", "INFILTRATION         HORTON",
         "FLOW_ROUTING         DYNWAVE", "START_DATE           01/01/2026",
         "START_TIME           00:00:00", "END_DATE             " + end_date,
         "END_TIME             " + hms(end_h), "WET_STEP             00:05:00",
         "DRY_STEP             01:00:00", "ROUTING_STEP         30",
         "REPORT_STEP          00:05:00", "ALLOW_PONDING        YES",
         "[RAINGAGES]", "RG1  INTENSITY 0:05 1.0 TIMESERIES RAIN"]
    for _zs_name, _zs_series in zone_series:
        L.append("%s  INTENSITY 0:05 1.0 TIMESERIES %s"
                 % (_zs_name.replace("RAIN_Z", "RGZ", 1), _zs_name))
    L.append("[JUNCTIONS]")
    for i, d in enumerate(drains):
        z0 = float(d.get("z0", 10.0))
        z1 = float(d.get("z1", z0 - 1.0))
        L.append("J%d_UP  %.3f  2  0  0  0" % (i, z0))
        L.append("J%d_DN  %.3f  2  0  0  0" % (i, z1))
    # outfall inverts follow their junction (capped 2% connector slope) so the
    # short CX links never form supercritical drops that destabilize DYNWAVE
    _o_inv = []
    for i, d in enumerate(drains):
        try:
            _z1 = float(d.get("z1", 10.0))
        except Exception:
            _z1 = 10.0
        _o_inv.append(round(max(0.0, _z1 - 0.02 * 50.0), 3))
    L.append("[OUTFALLS]")
    for i in range(len(drains)):
        L.append("O%d  %.3f  FREE  NO" % (i, _o_inv[i]))
    L.append("[CONDUITS]")
    for i, d in enumerate(drains):
        length = max(20.0, float(d.get("length_m") or 200.0))
        L.append("C%d  J%d_UP  J%d_DN  %.1f  %.3f  0  0  0  0" % (i, i, i, length, ROUGHNESS))
        L.append("CX%d  J%d_DN  O%d  50  %.3f  0  0  0  0" % (i, i, i, ROUGHNESS))
    L.append("[XSECTIONS]")
    for i in range(len(drains)):
        L.append("C%d  RECT_OPEN  %.1f  %.1f  0  0  1" % (i, DEPTH_M, WIDTH_M))
        L.append("CX%d  RECT_OPEN  %.1f  %.1f  0  0  1" % (i, DEPTH_M, WIDTH_M))
    L.append("[TIMESERIES]")
    L.extend(_stamp_lines("RAIN", series))
    for _zs_name, _zs_series in zone_series:
        L.extend(_stamp_lines(_zs_name, _zs_series))
    L.append("[SUBCATCHMENTS]")
    for i, d in enumerate(drains):
        _g = _subcatch_gage(d if isinstance(d, dict) else {}, zones)
        L.append("S%d  %s  J%d_UP  0.5  60  100  0.5  0" % (i, _g, i))
    L.append("[SUBAREAS]")
    for i in range(len(drains)):
        L.append("S%d  0.02  0.02  0.02  5  0  OUTLET  100" % i)
    L.append("[REPORT]")
    L += ["INPUT  NO", "CONTROLS NO", ""]
    with open(out_path, "w") as f:
        f.write("\n".join(L))
    return str(out_path)
