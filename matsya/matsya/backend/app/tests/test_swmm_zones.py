def test_single_gage_when_zoneless(tmp_path):
    from app.services.engine.swmm_inp import build_inp
    p = build_inp([{"id": "D1", "length_m": 100.0, "slope": 0.01, "z0": 10.0, "z1": 9.0,
                    "x0": 80.16, "y0": 13.10, "x1": 80.161, "y1": 13.101}],
                  {"rateMmHr": 50, "durationHr": 1}, [80.15, 13.08, 80.20, 13.13], str(tmp_path / "z0.inp"))
    text = open(p).read()
    assert text.count("RG1") >= 1 and "RGZ" not in text

def test_zoned_subcatchment_gets_zone_gage(tmp_path):
    from app.services.engine.swmm_inp import build_inp
    poly = {"type": "Polygon", "coordinates": [[[80.15, 13.08], [80.175, 13.08], [80.175, 13.13], [80.15, 13.13], [80.15, 13.08]]]}
    drains = [{"id": "DW", "length_m": 100.0, "slope": 0.01, "z0": 10.0, "z1": 9.0,
               "x0": 80.16, "y0": 13.10, "x1": 80.161, "y1": 13.101},
              {"id": "DE", "length_m": 100.0, "slope": 0.01, "z0": 10.0, "z1": 9.0,
               "x0": 80.19, "y0": 13.10, "x1": 80.191, "y1": 13.101}]
    rf = {"rateMmHr": 10, "durationHr": 1,
          "zones": [{"id": "w", "amount": 200, "unit": "rate", "polygon": poly}]}
    p = build_inp(drains, rf, [80.15, 13.08, 80.20, 13.13], str(tmp_path / "z1.inp"))
    text = open(p).read()
    assert "RGZ0" in text and "S0  RGZ0" in text and "S1  RG1" in text
