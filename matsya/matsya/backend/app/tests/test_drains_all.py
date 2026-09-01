def test_drains_all():
    from app.services.hydro.asset_loader import load_assets
    data=load_assets("assets")
    # drains_all should be 10276 LineString (10257 Placemark + extra Multi)
    assert len(data["drains_all"]) >= 10257
    assert len(data["drains_all"]) == 10276
    assert len(data["micro"]) == 37
    assert len(data["macro"]) == 15
    assert len(data["waterbodies"]) == 4086
    assert len(data["rivers"]) >= 800
