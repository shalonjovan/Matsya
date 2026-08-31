def test_coupled():
    from app.services.hydro.coupled_runner import run_coupled
    res=run_coupled("test-sim", hydro=True)
    assert "waterbody_levels" in res
    assert len(res["waterbody_levels"]) > 3
    assert "drain_outfalls" in res
    assert "river_flows" in res
    assert res["mass_error"] < 0.05
    assert res["stats"]["snapped_to_waterbody"] >= 0
    print(res["mass_error"], res["stats"])

def test_coupled_no_hydro():
    from app.services.hydro.coupled_runner import run_coupled
    res=run_coupled("test-sim", hydro=False)
    assert "waterbody_levels" in res
    assert res["mass_error"] < 0.05
