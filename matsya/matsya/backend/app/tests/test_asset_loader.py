def test_load_assets_counts():
    from app.services.hydro.asset_loader import load_assets, validate_counts
    data = load_assets("assets")
    # Check we loaded at least the expected
    assert "micro" in data
    assert "macro" in data
    assert "rivers" in data
    assert "waterbodies" in data
    # Check counts with tolerance
    assert len(data["micro"]) >= 30  # 37 expected, allow 30+
    assert len(data["macro"]) >= 12  # 15 expected
    assert len(data["rivers"]) >= 700  # 876 expected
    assert len(data["waterbodies"]) >= 3000  # 4086 expected
    # crs should be 4326 or set
    assert data["micro"].crs is not None or len(data["micro"])==0
    validate_counts(data)  # should not raise

def test_validate_counts_missing():
    from app.services.hydro.asset_loader import validate_counts
    import pytest
    with pytest.raises(ValueError):
        validate_counts({"micro": []})  # missing
    with pytest.raises(ValueError):
        validate_counts({"micro": [1]*37, "macro": []})  # macro missing
