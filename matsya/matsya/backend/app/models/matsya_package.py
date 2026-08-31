"""Matsya package constants and helpers per prd §6 — v1.1 with hydro."""

MATSYA_VERSION = "1.1"

# ZIP layout per §6: portable simulation package contents
PACKAGE_FILES = [
    "metadata.json",
    "terrain/terrain.json",
    "terrain/dem.tif",
    "rainfall.json",
    "drainage/drainage.json",
    "rivers/rivers.json",
    "canals/canals.json",
    "waterbodies/waterbodies.json",
    "roads/roads.json",
    "buildings/buildings.json",
    "boundaries/boundaries.json",
    "parameters/parameters.json",
    "results/results.json",
    "matsya_version",
    # v1.1 hydro extension
    "hydro/graph.json",
    "hydro/snap.json",
    "hydro/waterbodies.geojson",
]

def get_package_structure():
    """Return expected ZIP structure."""
    return list(PACKAGE_FILES)
