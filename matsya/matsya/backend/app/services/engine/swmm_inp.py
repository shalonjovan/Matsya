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


def build_inp(drains, rainfall, bbox, out_path):
    drains = list(drains or [])
    series = _rain_series(rainfall)
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
         "[RAINGAGES]", "RG1  INTENSITY 0:05 1.0 TIMESERIES RAIN",
         "[JUNCTIONS]"]
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
    prev_min = -1
    stamped = []
    for t, v in series:
        m = int(float(t) * 60)
        if m <= prev_min:
            m = prev_min + 5
        prev_min = m
        stamped.append((m, float(v)))
    if stamped and stamped[-1][1] != 0.0:
        stamped.append((stamped[-1][0] + 5, 0.0))
    for m, v in stamped:
        L.append("RAIN  %02d:%02d:00  %.2f" % (m // 60, m % 60, v))
    L.append("[SUBCATCHMENTS]")
    for i in range(len(drains)):
        L.append("S%d  RG1  J%d_UP  0.5  60  100  0.5  0" % (i, i))
    L.append("[SUBAREAS]")
    for i in range(len(drains)):
        L.append("S%d  0.02  0.02  0.02  5  0  OUTLET  100" % i)
    L.append("[REPORT]")
    L += ["INPUT  NO", "CONTROLS NO", ""]
    with open(out_path, "w") as f:
        f.write("\n".join(L))
    return str(out_path)
